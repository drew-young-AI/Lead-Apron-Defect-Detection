"""
Annotation storage + history tracking.

data/annotations/<safe_id>.json  – per-image annotation documents
data/history.json                – chronological save log (memory feature)

Key guarantees
--------------
* Atomic writes  – temp file in same dir  →  os.replace (POSIX rename, atomic)
* Correct IDs    – file_id stored *inside* JSON, never reconstructed from filename
* SQLite-backed  – upsert_annotation / delete_annotation_record keep index in sync
* Orphan safety  – list_annotated falls back to filesystem scan + SQLite back-fill
"""
import json
import os
import time
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from . import db

STORE_DIR    = Path(__file__).parent.parent.parent / "data" / "annotations"
HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "history.json"


# ── internal helpers ────────────────────────────────────────────────────────

def _safe_id(file_id: str) -> str:
    """Sanitise file_id → safe filesystem name (strip metacharacters)."""
    for ch in r'. / \ : * ? " < > |'.split():
        file_id = file_id.replace(ch, "_")
    return file_id


def _ann_path(file_id: str) -> Path:
    return STORE_DIR / f"{_safe_id(file_id)}.json"


def _atomic_write(path: Path, data: Any) -> None:
    """
    Write JSON to *path* atomically.
    Steps: mkstemp in same dir → write → os.replace
    On error, temp file is removed; original is untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(path))          # atomic on POSIX & NTFS
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── annotation CRUD ────────────────────────────────────────────────────────

def load(file_id: str) -> Dict[str, Any]:
    p = _ann_path(file_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"file_id": file_id, "sop_uid": file_id,
            "annotations": [], "version": 1}


def save(file_id: str, data: Dict[str, Any]) -> bool:
    existing  = load(file_id)
    version   = existing.get("version", 0) + 1
    saved_at  = time.strftime("%Y-%m-%dT%H:%M:%S")

    data["file_id"]  = file_id
    data["sop_uid"]  = file_id          # backward-compat alias
    data["version"]  = version
    data["saved_at"] = saved_at

    # ── annotator history ────────────────────────────────────────────────
    annotator = data.get("annotator", "").strip() or "未指定"
    hist = existing.get("annotator_history", [])
    
    # 限制歷程長度避免 JSON 過度膨脹 (例如最多保留最後 100 筆)
    hist.append({
        "annotator": annotator,
        "saved_at": saved_at,
        "action": f"儲存標記 ({len(data.get('annotations', []))} 個)"
    })
    if len(hist) > 100:
        hist = hist[-100:]
        
    data["annotator_history"] = hist

    try:
        _atomic_write(_ann_path(file_id), data)

        # Keep SQLite annotation index in sync
        anns = data.get("annotations", [])
        notes = data.get("notes", "")
        if anns or notes:
            count = len(anns)
            has_notes = 1 if notes else 0
            db.upsert_annotation(file_id, version, saved_at, count, has_notes)
        else:
            db.delete_annotation_record(file_id)

        return True
    except Exception as exc:
        print(f"[store] save error: {exc}")
        return False


def delete_annotation(file_id: str, ann_id: str) -> bool:
    doc    = load(file_id)
    before = len(doc["annotations"])
    doc["annotations"] = [
        a for a in doc["annotations"] if str(a.get("id")) != ann_id
    ]
    if len(doc["annotations"]) < before:
        return save(file_id, doc)
    return False


def delete_doc(file_id: str) -> bool:
    """Delete the entire annotation document for a given file_id.

    This removes the JSON file on disk (if present) and clears the
    SQLite annotation index for that file.
    """
    p = _ann_path(file_id)
    try:
        if p.exists():
            os.unlink(p)
    except Exception:
        pass

    # Ensure DB index is cleaned as well
    try:
        db.delete_annotation_record(file_id)
    except Exception:
        pass

    return True


def list_annotated() -> List[str]:
    """
    Return file_ids that have saved annotations.

    Primary source: SQLite annotations table (fast).
    Fallback:       filesystem scan (handles pre-SQLite migration).
    """
    ids = db.list_annotated_ids()
    if ids:
        return ids

    # Fallback – scan JSON files; also back-fills SQLite for next call
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    result: List[str] = []
    for p in STORE_DIR.glob("*.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            fid = doc.get("file_id") or doc.get("sop_uid")
            anns = doc.get("annotations", [])
            notes = doc.get("notes", "")
            if fid and (anns or notes):
                result.append(fid)
                count = len(anns)
                has_notes = 1 if notes else 0
                db.upsert_annotation(
                    fid,
                    doc.get("version", 1),
                    doc.get("saved_at", ""),
                    count,
                    has_notes,
                )
        except Exception:
            pass
    return result


# ── history (memory feature) ───────────────────────────────────────────────

def load_history() -> List[Dict[str, Any]]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_history(entry: Dict[str, Any]) -> bool:
    history = load_history()

    # Upsert: remove existing record for same key
    key = (entry.get("sop_uid") or entry.get("file_id")
           or entry.get("path", ""))
    history = [
        h for h in history
        if (h.get("sop_uid") or h.get("file_id")
            or h.get("path", "")) != key
    ]
    entry["saved_at"] = entry.get("saved_at",
                                  time.strftime("%Y-%m-%dT%H:%M:%S"))
    history.insert(0, entry)
    history = history[:500]

    try:
        _atomic_write(HISTORY_FILE, history)
        return True
    except Exception as exc:
        print(f"[history] write error: {exc}")
        return False


def delete_history_entry(sop_uid: str) -> bool:
    history = load_history()
    before  = len(history)
    history = [
        h for h in history
        if h.get("sop_uid") != sop_uid and h.get("file_id") != sop_uid
    ]
    if len(history) < before:
        try:
            _atomic_write(HISTORY_FILE, history)
            return True
        except Exception:
            pass
    return False
