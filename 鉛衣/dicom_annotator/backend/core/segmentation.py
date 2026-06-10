"""
Segmentation pipeline for DICOM defect annotation.
Each method targets different defect characteristics found in industrial X-ray NDT.
"""
import io, base64, traceback
import numpy as np
import cv2
from typing import Tuple, List, Dict, Any
from PIL import Image
from scipy import ndimage

try:
    from skimage.segmentation import morphological_chan_vese
    _SKIMAGE_OK = True
except ImportError:
    _SKIMAGE_OK = False


# ── preprocessing ──────────────────────────────────────────────────────────

def _to_8u(roi: np.ndarray) -> np.ndarray:
    if roi.dtype == np.uint8:
        return roi.copy()
    mn, mx = roi.min(), roi.max()
    if mx == mn:
        return np.zeros(roi.shape, dtype=np.uint8)
    return ((roi - mn) / (mx - mn) * 255).astype(np.uint8)


def _clahe(img8: np.ndarray, clip: float = 2.0) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8)).apply(img8)


def _cleanup(mask: np.ndarray, min_area: int = 16) -> np.ndarray:
    """Fill holes, remove small blobs, smooth edges."""
    m = (mask > 0).astype(np.uint8)
    filled = ndimage.binary_fill_holes(m).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(filled, 8)
    out = np.zeros_like(filled)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = 1
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, k)
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, k)
    return (out * 255).astype(np.uint8)


def _mask_to_b64(mask: np.ndarray) -> str:
    img = Image.fromarray(mask, mode='L')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


# ── individual segmentation methods ───────────────────────────────────────

def seg_otsu(roi: np.ndarray, **kw) -> np.ndarray:
    """CLAHE + Otsu. Best for: high-contrast defects, metal inclusions."""
    img = _clahe(_to_8u(roi), 2.0)
    _, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if np.count_nonzero(mask) > mask.size // 2:
        mask = cv2.bitwise_not(mask)
    return mask


def seg_adaptive(roi: np.ndarray, **kw) -> np.ndarray:
    """Adaptive threshold. Best for: uneven background illumination."""
    img = _clahe(_to_8u(roi), 3.0)
    h, w = img.shape
    bs = max(11, (min(h, w) // 8) | 1)
    return cv2.adaptiveThreshold(img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, bs, 5)


def seg_canny(roi: np.ndarray, **kw) -> np.ndarray:
    """CLAHE + Canny + morphological fill. Best for: cracks, linear defects."""
    img = _clahe(_to_8u(roi), 2.5)
    blur = cv2.GaussianBlur(img, (5, 5), 0)
    val, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    edges = cv2.Canny(blur, int(val * 0.5), int(val))
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k, iterations=2)
    h, w = closed.shape
    fl = closed.copy()
    fm = np.zeros((h+2, w+2), dtype=np.uint8)
    cv2.floodFill(fl, fm, (0, 0), 255)
    inner = cv2.bitwise_not(fl)
    return cv2.bitwise_or(closed, inner)


def seg_grabcut(roi: np.ndarray, **kw) -> np.ndarray:
    """GrabCut. Best for: enclosed blobs with moderately clear boundary."""
    img8 = _to_8u(roi)
    h, w = img8.shape
    if h < 10 or w < 10:
        return seg_otsu(roi)
    bgr = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)
    mask_ = np.zeros((h, w), dtype=np.uint8)
    bgd = np.zeros((1, 65), dtype=np.float64)
    fgd = np.zeros((1, 65), dtype=np.float64)
    mg = max(2, int(min(h, w) * 0.1))
    rect = (mg, mg, max(1, w - 2*mg), max(1, h - 2*mg))
    try:
        cv2.grabCut(bgr, mask_, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
        return np.where(
            (mask_ == cv2.GC_BGD) | (mask_ == cv2.GC_PR_BGD), 0, 255
        ).astype(np.uint8)
    except Exception:
        return seg_otsu(roi)


def seg_watershed(roi: np.ndarray, **kw) -> np.ndarray:
    """Watershed. Best for: multiple adjacent/clustered defects."""
    img8 = _to_8u(roi)
    _, binary = cv2.threshold(img8, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    k = np.ones((3, 3), np.uint8)
    sure_bg = cv2.dilate(binary, k, iterations=3)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    mx = dist.max()
    if mx == 0:
        return binary
    _, sure_fg = cv2.threshold(dist, 0.5 * mx, 255, 0)
    sure_fg = sure_fg.astype(np.uint8)
    unknown = cv2.subtract(sure_bg, sure_fg)
    _, markers = cv2.connectedComponents(sure_fg)
    markers += 1
    markers[unknown == 255] = 0
    bgr = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)
    cv2.watershed(bgr, markers)
    return np.where(markers > 1, 255, 0).astype(np.uint8)


def seg_region_growing(roi: np.ndarray, tolerance: float = 20.0, **kw) -> np.ndarray:
    """Region growing from darkest pixel. Best for: isolated dark pinholes."""
    img8 = _to_8u(roi).astype(np.int32)
    h, w = img8.shape
    sy, sx = np.unravel_index(int(np.argmin(img8)), img8.shape)
    seed_val = img8[sy, sx]
    visited = np.zeros((h, w), dtype=bool)
    mask = np.zeros((h, w), dtype=np.uint8)
    stack = [(int(sx), int(sy))]
    while stack:
        x, y = stack.pop()
        if x < 0 or x >= w or y < 0 or y >= h or visited[y, x]:
            continue
        if abs(img8[y, x] - seed_val) > tolerance:
            continue
        visited[y, x] = True
        mask[y, x] = 255
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            stack.append((x+dx, y+dy))
    return mask


def seg_chan_vese(roi: np.ndarray, **kw) -> np.ndarray:
    """Chan-Vese level-set. Best for: smooth organic shapes."""
    if not _SKIMAGE_OK:
        return seg_grabcut(roi)
    img8 = _to_8u(roi)
    seg = morphological_chan_vese(img8.astype(np.float64)/255.0, num_iter=100, smoothing=3)
    mask = (seg * 255).astype(np.uint8)
    mfg = float(img8[mask==255].mean()) if mask.any() else 128
    mbg = float(img8[mask==0].mean()) if (mask==0).any() else 128
    if mfg > mbg:
        mask = cv2.bitwise_not(mask)
    return mask


# ── polygon extraction ─────────────────────────────────────────────────────

def extract_polygon(mask: np.ndarray, epsilon_factor: float = 0.005) -> List[List[int]]:
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 9:
        return []
    eps = max(1.0, epsilon_factor * cv2.arcLength(largest, True))
    approx = cv2.approxPolyDP(largest, eps, True)
    pts = [[int(p[0][0]), int(p[0][1])] for p in approx]
    return pts if len(pts) >= 3 else []


# ── method registry ────────────────────────────────────────────────────────

METHOD_MAP = {
    "otsu":           seg_otsu,
    "adaptive":       seg_adaptive,
    "canny":          seg_canny,
    "grabcut":        seg_grabcut,
    "watershed":      seg_watershed,
    "region_growing": seg_region_growing,
    "chan_vese":      seg_chan_vese,
}

METHOD_HELP = {
    "otsu":           "CLAHE + Otsu – fast, high-contrast defects",
    "adaptive":       "CLAHE + Adaptive threshold – uneven background",
    "canny":          "Canny edges + fill – cracks, linear defects",
    "grabcut":        "GrabCut – enclosed blobs (recommended default)",
    "watershed":      "Watershed – clustered / adjacent defects",
    "region_growing": "Region growing – isolated dark pinholes",
    "chan_vese":      "Chan-Vese – smooth organic shapes",
}


# ── main dispatcher ────────────────────────────────────────────────────────

def run_segmentation(
    roi:            np.ndarray,
    method:         str   = "grabcut",
    offset_x:       int   = 0,
    offset_y:       int   = 0,
    epsilon_factor: float = 0.005,
    min_area:       int   = 16,
) -> Dict[str, Any]:
    """
    Run segmentation on a uint8 ROI crop.
    Returns polygon in full-image coordinates (offset applied),
    plus cleaned mask as base64 PNG for preview.
    """
    fn = METHOD_MAP.get(method, seg_grabcut)

    try:
        raw_mask = fn(roi)
    except Exception as exc:
        print(f"[seg] {method} failed: {exc}\n{traceback.format_exc()}")
        raw_mask = seg_otsu(roi)

    cleaned = _cleanup(raw_mask, min_area=min_area)
    pts_roi  = extract_polygon(cleaned, epsilon_factor=epsilon_factor)

    # Translate polygon to full-image coordinates
    pts_full = [[p[0] + offset_x, p[1] + offset_y] for p in pts_roi]

    # Bounding box from mask
    nz = np.argwhere(cleaned > 0)
    if len(nz):
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0)
        bbox = [int(c0)+offset_x, int(r0)+offset_y, int(c1-c0), int(r1-r0)]
    else:
        bbox = [offset_x, offset_y, roi.shape[1], roi.shape[0]]

    # Encode mask thumbnail
    mask_b64 = _mask_to_b64(cleaned)

    return {
        "polygon":  pts_full,
        "bbox":     bbox,
        "method":   method,
        "success":  len(pts_full) >= 3,
        "mask_b64": mask_b64,
    }
