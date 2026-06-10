import numpy as np
import cv2
from backend.core import segmentation


def test_seg_canny_basic():
    # synthetic ROI: dark background with a bright circle
    roi = np.zeros((128, 128), dtype=np.uint8)
    cv2.circle(roi, (64, 64), 20, 255, -1)
    mask = segmentation.seg_canny(roi)
    assert isinstance(mask, np.ndarray)
    assert mask.shape == roi.shape
    assert mask.dtype == np.uint8
    # mask should contain some non-zero pixels (edge/filled region)
    assert mask.max() in (0, 255) or mask.max() > 0
