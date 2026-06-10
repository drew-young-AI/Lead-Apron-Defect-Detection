"""
POST /api/segment       – run segmentation on a bbox ROI
GET  /api/segment/methods – list available methods
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional

from ..core.dicom_reader import reader
from ..core.segmentation import run_segmentation, METHOD_HELP, extract_polygon, _cleanup, _mask_to_b64
from .dicom import _load_cached

router = APIRouter()


class SegmentRequest(BaseModel):
    path:           str
    bbox:           Dict[str, int]   # {x, y, w, h} in image coordinates
    method:         str   = "watershed"
    wc:             Optional[float] = None
    ww:             Optional[float] = None
    epsilon_factor: float = 0.005
    min_area:       int   = 16
    brush_mask_b64: Optional[str] = None  # [BUG #1] Brush mask for mask-guided segmentation


@router.post("/segment")
def segment(req: SegmentRequest):
    # ── load DICOM ──────────────────────────────────────────────────────
    try:
        data = _load_cached(req.path)
    except Exception as e:
        raise HTTPException(400, f"Cannot load DICOM: {e}")

    meta   = data["metadata"]
    px_arr = data["pixel_array"]

    wc = req.wc if req.wc is not None else meta["WindowCenter"]
    ww = req.ww if req.ww is not None else meta["WindowWidth"]

    # ── validate & crop bbox ────────────────────────────────────────────
    bbox = req.bbox
    x  = max(0, int(bbox.get("x", 0)))
    y  = max(0, int(bbox.get("y", 0)))
    w  = max(1, int(bbox.get("w", 1)))
    h  = max(1, int(bbox.get("h", 1)))
    x2 = min(int(px_arr.shape[1]), x + w)
    y2 = min(int(px_arr.shape[0]), y + h)

    if x2 <= x or y2 <= y:
        raise HTTPException(400, f"Invalid bounding box: x={x} y={y} w={w} h={h}")

    roi = reader.apply_windowing(
        px_arr[y:y2, x:x2], wc, ww, meta["PhotometricInterpretation"]
    )

    # ── mask-guided segmentation (if brush mask provided) ──────────────
    if req.brush_mask_b64:
        try:
            import base64, io
            from PIL import Image
            import numpy as np
            # Decode mask (expected full-image size or display size)
            mask_bytes = base64.b64decode(req.brush_mask_b64)
            mask_img = Image.open(io.BytesIO(mask_bytes)).convert('L')
            full_h, full_w = px_arr.shape[0], px_arr.shape[1]
            if mask_img.size != (full_w, full_h):
                # Resize mask to image pixel size (nearest to preserve binary)
                mask_img = mask_img.resize((full_w, full_h), Image.NEAREST)
            mask_np = (np.array(mask_img, dtype=np.uint8) > 10).astype(np.uint8) * 255
            mask_roi = mask_np[y:y2, x:x2]

            # Clean up and extract polygon from provided mask
            cleaned = _cleanup(mask_roi, min_area=req.min_area)
            pts_roi = extract_polygon(cleaned, epsilon_factor=req.epsilon_factor)
            pts_full = [[int(p[0] + x), int(p[1] + y)] for p in pts_roi]

            # Compute bbox from cleaned mask
            nz = np.argwhere(cleaned > 0)
            if len(nz):
                r0, c0 = nz.min(axis=0)
                r1, c1 = nz.max(axis=0)
                bbox = [int(c0) + x, int(r0) + y, int(c1 - c0), int(r1 - r0)]
            else:
                bbox = [x, y, x2 - x, y2 - y]

            mask_b64 = _mask_to_b64(cleaned)

            return {
                "polygon": pts_full,
                "bbox": bbox,
                "method": req.method or 'mask',
                "success": len(pts_full) >= 3,
                "mask_b64": mask_b64,
                "roi_x": x, "roi_y": y, "roi_w": x2 - x, "roi_h": y2 - y,
            }
        except Exception as e:
            import traceback
            print('[seg] brush-mask fallback failed:')
            traceback.print_exc()
            # fall back to standard ROI-based segmentation

    # ── run segmentation (single call – result already contains mask_b64) ─
    result = run_segmentation(
        roi,
        method         = req.method,
        offset_x       = x,
        offset_y       = y,
        epsilon_factor = req.epsilon_factor,
        min_area       = req.min_area,
    )

    return {
        **result,
        "roi_x": x, "roi_y": y, "roi_w": x2 - x, "roi_h": y2 - y,
    }


@router.get("/segment/methods")
def list_methods():
    return {"methods": [{"id": k, "description": v} for k, v in METHOD_HELP.items()]}
