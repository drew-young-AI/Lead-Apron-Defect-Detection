"""
DICOM Reader – handles pydicom loading, windowing, MONOCHROME1/2,
Rescale Slope/Intercept, and PNG conversion.
"""
import io
import base64
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

import numpy as np
import pydicom
from PIL import Image


def _ensure_8bit(arr: np.ndarray) -> np.ndarray:
    """Clip and cast any float/int array to uint8 [0-255]."""
    return np.clip(arr, 0, 255).astype(np.uint8)


class DicomReader:

    def load(self, file_path: str) -> Dict[str, Any]:
        """Load a DICOM file and return pixel_array + metadata."""
        ds = pydicom.dcmread(str(file_path), force=True)

        # ── pixel data ──────────────────────────────────────────────────
        try:
            raw = ds.pixel_array.astype(np.float64)
        except Exception as e:
            raise RuntimeError(f"Cannot read pixel data: {e}")

        # Handle multi-frame (take first frame)
        if raw.ndim == 3:
            raw = raw[0]

        slope     = float(getattr(ds, "RescaleSlope",     1.0))
        intercept = float(getattr(ds, "RescaleIntercept", 0.0))
        raw = raw * slope + intercept

        # ── windowing defaults ───────────────────────────────────────────
        wc, ww = self._default_window(ds, raw)

        # ── photometric ──────────────────────────────────────────────────
        photo = str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2")).strip()

        # ── metadata ─────────────────────────────────────────────────────
        def tag(attr, default=""):
            v = getattr(ds, attr, default)
            return str(v) if v is not None else str(default)

        def tag_f(attr, default=0.0):
            v = getattr(ds, attr, None)
            if v is None:
                return default
            if hasattr(v, "__len__"):
                return float(v[0])
            return float(v)

        ps = getattr(ds, "PixelSpacing", [1.0, 1.0])
        metadata = {
            "PatientID":         tag("PatientID"),
            "StudyInstanceUID":  tag("StudyInstanceUID"),
            "SeriesInstanceUID": tag("SeriesInstanceUID"),
            "SOPInstanceUID":    tag("SOPInstanceUID"),
            "Modality":          tag("Modality"),
            "WindowCenter":      wc,
            "WindowWidth":       ww,
            "PhotometricInterpretation": photo,
            "Rows":    int(getattr(ds, "Rows",    raw.shape[0])),
            "Columns": int(getattr(ds, "Columns", raw.shape[1])),
            "PixelSpacing": [float(ps[0]), float(ps[1])],
            "BitsStored": int(getattr(ds, "BitsStored", 12)),
        }

        return {"pixel_array": raw, "metadata": metadata}

    # ── helpers ───────────────────────────────────────────────────────────

    def _default_window(self, ds, raw: np.ndarray) -> Tuple[float, float]:
        try:
            wc_raw = ds.WindowCenter
            ww_raw = ds.WindowWidth
            wc = float(wc_raw[0]) if hasattr(wc_raw, "__len__") else float(wc_raw)
            ww = float(ww_raw[0]) if hasattr(ww_raw, "__len__") else float(ww_raw)
            if ww <= 0:
                raise ValueError
            return wc, ww
        except Exception:
            p1  = float(np.percentile(raw, 1))
            p99 = float(np.percentile(raw, 99))
            ww  = max(p99 - p1, 1.0)
            wc  = (p99 + p1) / 2.0
            return wc, ww

    def apply_windowing(
        self,
        pixel_array: np.ndarray,
        wc: float,
        ww: float,
        photo_interp: str = "MONOCHROME2",
    ) -> np.ndarray:
        """Apply linear windowing → uint8 [0-255]."""
        low  = wc - ww / 2.0
        high = wc + ww / 2.0
        clipped = np.clip(pixel_array, low, high)
        scaled  = (clipped - low) / (high - low) * 255.0
        img8 = _ensure_8bit(scaled)

        if "MONOCHROME1" in photo_interp.upper():
            img8 = 255 - img8

        return img8

    def to_png_b64(self, arr8: np.ndarray) -> str:
        """Convert uint8 2-D array to base64-encoded PNG string."""
        img = Image.fromarray(arr8, mode="L")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=False)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def get_roi(
        self,
        pixel_array: np.ndarray,
        bbox: Dict[str, int],
        wc: float,
        ww: float,
        photo_interp: str = "MONOCHROME2",
    ) -> np.ndarray:
        """Crop + window a bounding box region, returns uint8."""
        x, y, w, h = int(bbox["x"]), int(bbox["y"]), int(bbox["w"]), int(bbox["h"])
        x = max(0, x); y = max(0, y)
        x2 = min(pixel_array.shape[1], x + w)
        y2 = min(pixel_array.shape[0], y + h)
        roi = pixel_array[y:y2, x:x2]
        return self.apply_windowing(roi, wc, ww, photo_interp)


# Singleton
reader = DicomReader()
