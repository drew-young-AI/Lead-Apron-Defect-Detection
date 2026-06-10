import numpy as np
from backend.core.dicom_reader import reader


def test_apply_windowing_zero_width():
    arr = np.linspace(0, 1023, num=1024).reshape((32,32)).astype(float)
    out = reader.apply_windowing(arr, wc=100.0, ww=0.0, photo_interp="MONOCHROME2")
    assert out.dtype == np.uint8
    assert out.shape == arr.shape
