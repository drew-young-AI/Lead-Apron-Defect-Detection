"""
POST /api/upload          – validate + store a DICOM file → {file_id, path, metadata}
GET  /api/uploaded        – list all uploaded files (from SQLite index)
GET  /api/annotated_paths – paths of annotated files (SQLite join; for tree marking)
GET  /api/files           – scan a root folder for .dcm files → tree
GET  /api/image           – windowed DICOM image as base64 PNG
GET  /api/metadata        – DICOM metadata JSON  (also populates path_cache)
"""
import hashlib
import io
import os
import time
import tempfile
from pathlib import Path
from typing import Optional, List

import pydicom
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ..core.dicom_reader import reader
from ..core import db

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent.parent
UPLOAD_DIR = BASE_DIR / "backend" / "uploads"

def resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.exists():
        return p.absolute()
    
    # 嘗試相對於 BASE_DIR
    rel_p = BASE_DIR / p
    if rel_p.exists():
        return rel_p.absolute()
        
    # 嘗試提取檔名，看是否在 UPLOAD_DIR
    parts = p.parts
    if "uploads" in parts or "backend" in parts:
        filename = p.name
        curr_upload_p = UPLOAD_DIR / filename
        if curr_upload_p.exists():
            return curr_upload_p.absolute()
            
    # 如果以上都找不到，但路徑是相對路徑，就回傳絕對化路徑
    if not p.is_absolute():
        return rel_p.absolute()
    return p

def normalize_path(path_str: str) -> str:
    resolved = resolve_path(path_str)
    try:
        # 如果是 uploads 下的檔案，轉為相對於 BASE_DIR 的相對路徑
        return resolved.relative_to(BASE_DIR).as_posix()
    except ValueError:
        # 否則回傳絕對路徑的 posix 格式
        return resolved.as_posix()

# ── in-memory LRU-style cache (path → {pixel_array, metadata}) ─────────────
_META_CACHE: dict = {}
_CACHE_MAX   = 50      # keep memory bounded


# ══════════════════════════════════════════════════════════════════════════════
#  Upload
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/upload")
async def upload_dicom(file: UploadFile = File(...)):
    """
    Validate and persist a DICOM file.

    Algorithm
    ---------
    1. Read raw bytes
    2. Compute sha256 (dedup + fallback id)
    3. Parse with pydicom (raises 400 if invalid)
    4. file_id = SOPInstanceUID  ‖  sha256[:16]
    5. Atomic write to UPLOAD_DIR  (temp → os.replace)
    6. Set permissions 0o600
    7. Update SQLite: files + path_cache
    8. Load + cache metadata

    Returns {file_id, sop_uid, path, sha256, metadata}
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    filename = file.filename if file else ""
    if not filename.lower().endswith((".dcm", ".dicom")):
        raise HTTPException(400, "Only DICOM files (.dcm, .dicom) are allowed. JPEG, PNG, BMP images are not supported.")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")

    sha = hashlib.sha256(raw).hexdigest()

    # ── DICOM validation ────────────────────────────────────────────────
    try:
        ds  = pydicom.dcmread(io.BytesIO(raw), force=True)
        sop = str(getattr(ds, "SOPInstanceUID", "") or "").strip()
    except Exception as exc:
        raise HTTPException(400, f"Not a valid DICOM file: {exc}")

    file_id = sop if sop else sha[:16]

    # ── duplicate detection ────────────────────────────────────────────
    # Check 1: exact SOPInstanceUID match  → definitive duplicate
    dup_exact = db.get_file(file_id) if file_id else None
    if dup_exact:
        try:
            data = _load_cached(dup_exact["path"])
            meta = data["metadata"]
        except Exception:
            meta = {"SOPInstanceUID": sop or file_id}
        return {
            "file_id":   file_id,
            "sop_uid":   sop or file_id,
            "path":      normalize_path(dup_exact["path"]),
            "original_name": dup_exact.get("original_name") or Path(dup_exact["path"]).name,
            "sha256":    sha,
            "metadata":  meta,
            "duplicate": "exact",         # frontend shows warning
        }

    # Check 2: same pixel hash, different metadata  → pixel duplicate
    dup_sha = db.get_file_by_sha(sha)
    if dup_sha:
        try:
            data = _load_cached(dup_sha["path"])
            meta = data["metadata"]
        except Exception:
            meta = {}
        return {
            "file_id":   dup_sha["file_id"],
            "sop_uid":   dup_sha["sop_uid"],
            "path":      normalize_path(dup_sha["path"]),
            "original_name": dup_sha.get("original_name") or Path(dup_sha["path"]).name,
            "sha256":    sha,
            "metadata":  meta,
            "duplicate": "pixel",
        }


    safe_name = file_id
    for ch in r'. / \ : * ? " < > |'.split():
        safe_name = safe_name.replace(ch, "_")
    safe_name += ".dcm"
    dest = UPLOAD_DIR / safe_name

    # ── atomic write ───────────────────────────────────────────────────
    fd, tmp = tempfile.mkstemp(dir=str(UPLOAD_DIR), suffix=".tmp")
    try:
        os.write(fd, raw)
        os.close(fd)
        os.replace(tmp, str(dest))
        os.chmod(str(dest), 0o600)
    except Exception as exc:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise HTTPException(500, f"Failed to store file: {exc}")

    # ── update SQLite ──────────────────────────────────────────────────
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    norm_dest = normalize_path(str(dest))
    orig_name = file.filename if file else None
    db.upsert_file(file_id, sop or file_id, norm_dest, sha, now, orig_name)
    db.cache_path(norm_dest, file_id, now)

    # ── load + cache metadata ──────────────────────────────────────────
    try:
        data = reader.load(str(dest))
        _cache_set(norm_dest, data)
        meta = data["metadata"]
    except Exception:
        meta = {"SOPInstanceUID": sop or file_id}

    return {
        "file_id": file_id,
        "sop_uid": sop or file_id,
        "path":    norm_dest,
        "original_name": orig_name,
        "sha256":  sha,
        "metadata": meta,
    }


@router.get("/uploaded")
def list_uploaded():
    """List all files in the upload index (newest first)."""
    return {"files": db.list_all_files()}


@router.get("/annotated_paths")
def get_annotated_paths():
    """
    File-system paths whose annotations are saved.
    Uses SQLite JOIN: path_cache ∩ annotations.
    Populated whenever /api/metadata or /api/upload is called.
    """
    paths = db.get_annotated_paths()
    details = db.get_annotated_details()
    details_map = {d["path"]: {"count": d["annotation_count"], "has_notes": d["has_notes"]} for d in details}
    return {"paths": paths, "details": details_map}


# ══════════════════════════════════════════════════════════════════════════════
#  File tree
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/files")
def get_files(root: str = Query(..., description="Root folder to scan")):
    """Recursively scan root folder for .dcm files → nested tree."""
    root_p = Path(root).expanduser()
    if not root_p.exists():
        raise HTTPException(404, f"Path not found: {root}")
    if not root_p.is_dir():
        raise HTTPException(400, "Path is not a directory")

    dcm_files = sorted(root_p.rglob("*.dcm")) + sorted(root_p.rglob("*.DCM"))
    return {
        "root":  str(root_p),
        "tree":  _build_tree(root_p, dcm_files),
        "total": len(dcm_files),
    }


class DeleteFilesRequest(BaseModel):
    paths: List[str]
    remove_annotations: bool = True


@router.post("/files/delete")
def delete_files(request: DeleteFilesRequest):
    """Delete one or more files (and optionally their annotations).

    Body: { "paths": ["/full/path/to/a.dcm", ...], "remove_annotations": true }
    """
    result = {"deleted": [], "not_found": [], "errors": []}
    for p in request.paths:
        norm_path = normalize_path(p)
        rec = db.get_file_by_path(norm_path)
        if not rec:
            # 嘗試使用解析後的實體絕對路徑再查一次
            resolved_p = resolve_path(p)
            rec = db.get_file_by_path(str(resolved_p))
        if not rec:
            # 嘗試使用原始傳入的路徑再查一次
            rec = db.get_file_by_path(p)
            
        if not rec:
            result["not_found"].append(p)
            continue
        file_id = rec["file_id"]
        try:
            # attempt to remove the file from disk (best-effort)
            resolved_p = resolve_path(p)
            try:
                os.remove(str(resolved_p))
            except Exception:
                pass

            # remove DB records (files / path_cache / annotations index)
            db.delete_file(file_id)

            # remove annotation document if requested
            if request.remove_annotations:
                try:
                    from ..core import annotation_store
                    annotation_store.delete_doc(file_id)
                except Exception:
                    pass

            result["deleted"].append(p)
        except Exception as exc:
            result["errors"].append({"path": p, "error": str(exc)})
    return result


def _build_tree(root: Path, files: list) -> list:
    nodes: dict = {}
    for fp in files:
        parts = list(fp.relative_to(root).parts)
        cur   = nodes
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = str(fp)

    def to_list(d: dict, pfx: Path) -> list:
        out = []
        for k, v in sorted(d.items()):
            if isinstance(v, dict):
                out.append({"name": k, "type": "folder",
                             "path": str(pfx / k),
                             "children": to_list(v, pfx / k)})
            else:
                out.append({"name": k, "type": "dicom", "path": v})
        return out

    return to_list(nodes, root)


# ══════════════════════════════════════════════════════════════════════════════
#  Image / Metadata
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/image")
def get_image(
    path: str          = Query(...),
    wc:   Optional[float] = Query(None),
    ww:   Optional[float] = Query(None),
):
    """Return windowed DICOM slice as base64 PNG."""
    try:
        data = _load_cached(path)
    except Exception as exc:
        raise HTTPException(400, str(exc))

    meta  = data["metadata"]
    wc_u  = wc if wc is not None else meta["WindowCenter"]
    ww_u  = ww if ww is not None else meta["WindowWidth"]
    arr8  = reader.apply_windowing(
        data["pixel_array"], wc_u, ww_u, meta["PhotometricInterpretation"]
    )
    return {
        "image_data": reader.to_png_b64(arr8),
        "width":  meta["Columns"],
        "height": meta["Rows"],
        "wc": wc_u,
        "ww": ww_u,
    }


@router.get("/metadata")
def get_metadata(path: str = Query(...)):
    """Return DICOM metadata. Also caches path → SOPInstanceUID for tree marking."""
    try:
        data = _load_cached(path)
    except Exception as exc:
        raise HTTPException(400, str(exc))

    meta = data["metadata"]
    sop  = str(meta.get("SOPInstanceUID", "") or "").strip()
    if sop:
        norm_path = normalize_path(path)
        db.cache_path(norm_path, sop, time.strftime("%Y-%m-%dT%H:%M:%S"))

    return meta


# ── cache helpers ──────────────────────────────────────────────────────────

def _load_cached(path: str) -> dict:
    norm_path = normalize_path(path)
    if norm_path not in _META_CACHE:
        resolved = resolve_path(path)
        data = reader.load(str(resolved))
        _cache_set(norm_path, data)
    return _META_CACHE[norm_path]


def _cache_set(path: str, data: dict) -> None:
    if len(_META_CACHE) >= _CACHE_MAX:
        del _META_CACHE[next(iter(_META_CACHE))]
    _META_CACHE[path] = data
