"""
POST /api/export/yolo_det   →  YOLO detection  (.txt per image)
POST /api/export/yolo_seg   →  YOLO segmentation (.txt per image)
POST /api/export/coco       →  COCO JSON

Body for all:
{
  "items": [
    {
      "image_path": "...",
      "sop_uid": "...",
      "width": 2048,
      "height": 2048,
      "annotations": [
        { "id": "...", "class": "defect", "polygon": [[x,y],...], "bbox": [x,y,w,h] }
      ]
    }
  ],
  "class_map": {"defect": 0, "void": 1}   // optional, default all→0
}
"""
import io, json, zipfile, time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

CLASS_DEFAULT = {"hole": 0, "void": 0, "defect": 0, "crack": 1}


class ExportItem(BaseModel):
    image_path:  str
    sop_uid:     str
    width:       int
    height:      int
    annotations: List[Dict[str, Any]]


class ExportRequest(BaseModel):
    items:     List[ExportItem]
    class_map: Optional[Dict[str, int]] = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _class_id(name: str, cmap: dict) -> int:
    return cmap.get(name, cmap.get("defect", 0))


def _yolo_det_line(ann: dict, W: int, H: int, cmap: dict) -> Optional[str]:
    bbox = ann.get("bbox")
    if not bbox or len(bbox) < 4:
        pts = ann.get("polygon", [])
        if not pts:
            return None
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        bbox = [min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)]
    x, y, w, h = bbox
    cx = (x + w/2) / W;  cy = (y + h/2) / H
    nw = w / W;           nh = h / H
    cid = _class_id(ann.get("class", "defect"), cmap)
    return f"{cid} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def _yolo_seg_line(ann: dict, W: int, H: int, cmap: dict) -> Optional[str]:
    pts = ann.get("polygon", [])
    if len(pts) < 3:
        return _yolo_det_line(ann, W, H, cmap)
    cid  = _class_id(ann.get("class", "defect"), cmap)
    coords = " ".join(f"{p[0]/W:.6f} {p[1]/H:.6f}" for p in pts)
    return f"{cid} {coords}"


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/export/yolo_det")
def export_yolo_det(req: ExportRequest):
    return _zip_yolo(req, mode="det")


@router.post("/export/yolo_seg")
def export_yolo_seg(req: ExportRequest):
    return _zip_yolo(req, mode="seg")


def _zip_yolo(req: ExportRequest, mode: str):
    cmap = req.class_map or CLASS_DEFAULT
    buf  = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # classes.txt
        inv = {v: k for k, v in cmap.items()}
        classes_txt = "\n".join(inv[i] for i in sorted(inv))
        zf.writestr("classes.txt", classes_txt)

        for item in req.items:
            lines = []
            for ann in item.annotations:
                if mode == "det":
                    line = _yolo_det_line(ann, item.width, item.height, cmap)
                else:
                    line = _yolo_seg_line(ann, item.width, item.height, cmap)
                if line:
                    lines.append(line)

            stem = item.sop_uid.replace(".", "_").replace("/", "_")
            zf.writestr(f"labels/{stem}.txt", "\n".join(lines))

        # data.yaml
        yaml_content = (
            "path: .\ntrain: images/train\nval: images/val\n\n"
            f"nc: {len(cmap)}\n"
            f"names: {list(inv[i] for i in sorted(inv))}\n"
        )
        zf.writestr("data.yaml", yaml_content)

    buf.seek(0)
    ts = time.strftime("%Y%m%d_%H%M%S")
    fname = f"yolo_{mode}_{ts}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@router.post("/export/coco")
def export_coco(req: ExportRequest):
    cmap = req.class_map or CLASS_DEFAULT
    inv  = {v: k for k, v in cmap.items()}

    categories = [{"id": v+1, "name": k, "supercategory": "defect"}
                  for k, v in cmap.items()]

    images, annotations = [], []
    ann_id = 1

    for img_id, item in enumerate(req.items, start=1):
        images.append({
            "id":        img_id,
            "file_name": item.image_path,
            "sop_uid":   item.sop_uid,
            "width":     item.width,
            "height":    item.height,
        })

        for ann in item.annotations:
            pts = ann.get("polygon", [])
            seg = [[c for pt in pts for c in pt]] if pts else []

            bbox = ann.get("bbox")
            if not bbox and pts:
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                bbox = [min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)]
            bbox = bbox or [0, 0, 1, 1]

            area = bbox[2] * bbox[3]
            cid  = _class_id(ann.get("class","defect"), cmap) + 1  # COCO 1-indexed

            annotations.append({
                "id":          ann_id,
                "image_id":    img_id,
                "category_id": cid,
                "segmentation": seg,
                "bbox":        bbox,
                "area":        float(area),
                "iscrowd":     0,
            })
            ann_id += 1

    coco = {
        "info":        {"description": "DICOM Defect Annotations", "version": "1.0"},
        "categories":  categories,
        "images":      images,
        "annotations": annotations,
    }

    content = json.dumps(coco, indent=2, ensure_ascii=False)
    ts = time.strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=coco_{ts}.json"},
    )
