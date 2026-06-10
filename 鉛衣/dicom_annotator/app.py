#!/usr/bin/env python3
"""
DICOM Defect Annotation Tool  v2.0
Run:  python app.py
Open: http://localhost:8005

Install dependencies once: see requirements.txt
"""
import os
from pathlib import Path

os.chdir(Path(__file__).parent)

if __name__ == "__main__":
    import uvicorn

    print("=" * 55)
    print("   DICOM Defect Annotation Tool  v2.0")
    print("=" * 55)
    print("\n[Start]  http://localhost:8005")
    print("   Ctrl+C to stop\n")

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8005,
        reload=False,
        log_level="warning",
    )
