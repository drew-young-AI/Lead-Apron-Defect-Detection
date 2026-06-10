# DICOM Defect Annotation Tool

A semi-automatic label tool for DICOM (and industrial X-ray) defect annotation,
producing YOLO segmentation / COCO output for downstream model training.

## Quick Start

```bash
python app.py
# → open http://localhost:8000
```

The first run auto-installs all Python dependencies.

## Requirements

- Python 3.9+
- pip

## Usage

1. **Load dataset** – enter the root folder that contains your `.dcm` files and click **Load**.
   The left panel shows a recursive file tree.

2. **View image** – click any file. Use mouse-wheel to zoom, Alt+drag to pan.
   Drag the **WC / WW** sliders (or right-click-drag on the canvas) to adjust windowing.

3. **Draw bounding box** – select the **▣ Box** tool, drag a rectangle around the defect.

4. **Run segmentation** – choose a method in the right panel and click **▶ Run Segmentation**.

   | Method | Best for |
   |--------|----------|
   | GrabCut | Enclosed blobs with clear boundary *(default)* |
   | Otsu | High-contrast defects, metal inclusions |
   | Adaptive | Uneven background, low-contrast areas |
   | Canny | Cracks, linear/edge-type defects |
   | Watershed | Clustered / adjacent multiple defects |
   | Region Growing | Isolated dark pinholes |
   | Chan-Vese | Smooth organic shapes |

5. **Accept polygon** – review the orange preview polygon, then click **✓ Accept**.

6. **Edit vertices** – switch to **⊹ Edit** tool.
   Drag existing vertices; click on a polygon edge to insert a vertex;
   right-click a vertex to delete it.

7. **Save** – press **S** or click 💾 Save. Annotations stored in `data/annotations/`.

8. **Export** – click 📤 Export to download YOLO seg, YOLO det, or COCO JSON.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| B | Box tool |
| R | Brush tool |
| H | Pan tool |
| E | Edit vertices |
| S | Save |
| N / P | Next / Prev image |
| F | Fit to screen |
| Del | Delete selected annotation |
| Wheel | Zoom |
| Alt + drag | Pan |
| Esc | Deselect |

## Output Formats

### YOLO Segmentation (`.txt`)
```
# class x1 y1 x2 y2 ... (normalised 0-1)
0 0.234 0.456 0.289 0.432 ...
```

### YOLO Detection (`.txt`)
```
# class cx cy w h (normalised 0-1)
0 0.500 0.432 0.120 0.089
```

### COCO JSON
Standard COCO format with `images`, `annotations`, `categories`.

## Annotation JSON schema (`data/annotations/<sop>.json`)

```json
{
  "sop_uid": "...",
  "image_path": "/path/to/image.dcm",
  "dicom_meta": { "PatientID": "...", "SOPInstanceUID": "..." },
  "image_info": { "width": 2048, "height": 2048, "wc": 128, "ww": 256 },
  "annotations": [
    {
      "id": "ann_1234_1",
      "class": "defect",
      "type": "polygon",
      "polygon": [[x,y], ...],
      "bbox": [x, y, w, h],
      "auto": true,
      "method": "grabcut",
      "created": "2025-01-01T00:00:00",
      "modified": "2025-01-01T00:00:00"
    }
  ]
}
```

## Project Structure

```
dicom_annotator/
├── app.py                  ← Entry point
├── requirements.txt
├── backend/
│   ├── main.py             ← FastAPI app
│   ├── api/
│   │   ├── dicom.py        ← File scan, image serving
│   │   ├── annotation.py   ← CRUD
│   │   ├── segment.py      ← Segmentation dispatcher
│   │   └── export.py       ← YOLO / COCO export
│   └── core/
│       ├── dicom_reader.py      ← pydicom + windowing
│       ├── segmentation.py      ← 7 algorithms
│       └── annotation_store.py  ← JSON persistence
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js          ← API client
│       ├── viewer.js       ← Canvas DICOM viewer
│       ├── tools.js        ← Box / Brush / Edit tools
│       ├── annotations.js  ← Annotation manager
│       └── main.js         ← App controller
└── data/
    └── annotations/        ← JSON annotation files
```

---

## v2 Changes (Bug Fixes + New Features)

### Bug Fixes
1. **DPR accumulation bug** – `ctx.scale(dpr,dpr)` was called on every resize, compounding
   transforms. Fixed: `ctx.setTransform(dpr,0,0,dpr,0,0)` is now called at the *start of
   every render frame*, so the transform is always correct.
2. **Box → Segmentation bbox** – bbox was re-fetched from the (possibly deselected) annotation.
   Fixed: `lastSegBbox` is stored the moment the box is drawn and used directly.
3. **Double segmentation run** – the `/api/segment` endpoint ran the segmentation twice.
   Fixed: `run_segmentation()` now returns `mask_b64` directly; no second call needed.
4. **WW slider range** – sliders had a fixed range that didn't match many DICOMs.
   Fixed: range is dynamically set to match each loaded DICOM's window values.
5. **Coordinate normalisation on load** – bbox fields stored in different keys
   (`bbox_x/bbox_y` vs `bbox[0..3]`) were not always read back correctly.
   Fixed in `annotations.js` `load()`.

### New: History / Memory Feature
- Every **Save** records an entry in `data/history.json`.
- The **🕐 History** tab in the left panel lists all saved sessions (newest first).
- Each entry shows: filename, annotation count, classes, time ago, file path.
- **Click** any history item to jump directly to that file (even without loading a root folder).
- **✕** removes a single record; the header "✕" clears all.
- **Export → All history** downloads annotations for every previously saved session.
