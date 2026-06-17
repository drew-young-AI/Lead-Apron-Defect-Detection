"""
Annotation CRUD — all sop_uid passed as QUERY PARAM to avoid path-separator routing bugs.

Root cause of the save→reload bug:
  When sopUid = file path (e.g. /data/CT001.dcm) and it was put into the URL path
  segment as /annotations/%2Fdata%2FCT001.dcm, Starlette/uvicorn decoded %2F → /
  BEFORE routing, making the URL look like /annotations//data/CT001.dcm which
  matched no route → 404 → frontend caught exception → loaded empty list.

Fix: every endpoint uses Query(sop_uid=...) so the value is NEVER part of the URL path.
"""
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..core import annotation_store as store

router = APIRouter()


class AnnotationDoc(BaseModel):
    annotations: List[Dict[str, Any]]
    image_path:  Optional[str] = ""
    dicom_meta:  Optional[Dict[str, Any]] = {}
    image_info:  Optional[Dict[str, Any]] = {}
    notes:       Optional[str] = ""
    annotator:   Optional[str] = ""
    comments:    Optional[List[Dict[str, Any]]] = []
    annotator_history: Optional[List[Dict[str, Any]]] = []


class HistoryEntry(BaseModel):
    sop_uid:          str
    path:             Optional[str] = ""
    filename:         Optional[str] = ""
    annotation_count: Optional[int] = 0
    classes:          Optional[List[str]] = []
    patient_id:       Optional[str] = ""
    modality:         Optional[str] = ""
    image_size:       Optional[List[int]] = []
    saved_at:         Optional[str] = None


# ── Annotations ────────────────────────────────────────────────────────────

@router.get("/annotations")
def get_annotations(sop_uid: str = Query(..., description="SOPInstanceUID or file path")):
    """Load annotations.  sop_uid passed as query param — safe for paths with slashes."""
    return store.load(sop_uid)


@router.post("/annotations")
def save_annotations(
    sop_uid: str = Query(...),
    body:    AnnotationDoc = ...,
):
    """Save annotations.  sop_uid passed as query param."""
    data = body.dict()
    ok   = store.save(sop_uid, data)
    if not ok:
        raise HTTPException(500, "Failed to save annotations")
    return {"saved": True, "sop_uid": sop_uid, "count": len(body.annotations)}


@router.delete("/annotations/one")
def delete_one_annotation(
    sop_uid: str = Query(...),
    ann_id:  str = Query(...),
):
    """Delete a single annotation by ID."""
    ok = store.delete_annotation(sop_uid, ann_id)
    return {"deleted": ok, "ann_id": ann_id}


@router.get("/annotated")
def list_annotated():
    return {"items": store.list_annotated()}


# ── History ────────────────────────────────────────────────────────────────

@router.get("/history")
def get_history():
    records = store.load_history()
    return {"records": records}


@router.post("/history")
def add_history(entry: HistoryEntry):
    d = entry.dict()
    ok = store.save_history(d)
    return {"saved": ok}


@router.delete("/history/one")
def delete_history(sop_uid: str = Query(...)):
    ok = store.delete_history_entry(sop_uid)
    return {"deleted": ok}
