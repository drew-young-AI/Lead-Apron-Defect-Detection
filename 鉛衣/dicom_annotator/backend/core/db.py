"""
SQLite index for DICOM files and annotation records.

Tables
------
files       – uploaded-file registry (file_id, sop_uid, path, sha256, upload_time)
annotations – annotation existence index (file_id, version, saved_at)
path_cache  – path → file_id; populated whenever /api/metadata is served
              so that annotated-file marking survives across restarts
"""
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

DB_PATH = Path(__file__).parent.parent.parent / "data" / "index.db"
_lock   = threading.Lock()


# ── connection factory ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


# ── schema ──────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables + indexes if they don't exist. Idempotent."""
    with _lock:
        con = _connect()
        con.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                file_id     TEXT PRIMARY KEY,
                sop_uid     TEXT NOT NULL,
                path        TEXT NOT NULL,
                sha256      TEXT,
                upload_time TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS annotations (
                file_id          TEXT PRIMARY KEY,
                version          INTEGER NOT NULL DEFAULT 1,
                saved_at         TEXT    NOT NULL,
                annotation_count INTEGER          DEFAULT 0,
                has_notes        INTEGER          DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS path_cache (
                path      TEXT PRIMARY KEY,
                file_id   TEXT NOT NULL,
                cached_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_files_sop
                ON files(sop_uid);
            CREATE INDEX IF NOT EXISTS idx_pc_file_id
                ON path_cache(file_id);
        """)
        
        # 動態新增 original_name 欄位以相容舊資料庫
        try:
            con.execute("ALTER TABLE files ADD COLUMN original_name TEXT")
            con.commit()
        except sqlite3.OperationalError:
            pass

        # 動態新增 annotation_count 與 has_notes 欄位以相容舊資料庫
        try:
            con.execute("ALTER TABLE annotations ADD COLUMN annotation_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            con.execute("ALTER TABLE annotations ADD COLUMN has_notes INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        con.commit()

        # 一次性升級：將現有 JSON 檔案中的標註數量與備註狀態同步至 SQLite
        try:
            annotations_dir = DB_PATH.parent / "annotations"
            if annotations_dir.exists():
                for p in annotations_dir.glob("*.json"):
                    try:
                        import json
                        doc = json.loads(p.read_text(encoding="utf-8"))
                        fid = doc.get("file_id") or doc.get("sop_uid")
                        if fid and doc.get("annotations"):
                            anns = doc.get("annotations", [])
                            count = len(anns)
                            has_notes = 1 if doc.get("notes") else 0
                            con.execute("""
                                INSERT INTO annotations(file_id, version, saved_at, annotation_count, has_notes)
                                VALUES(?,?,?,?,?)
                                ON CONFLICT(file_id) DO UPDATE SET
                                    annotation_count=excluded.annotation_count,
                                    has_notes=excluded.has_notes
                            """, (fid, doc.get("version", 1), doc.get("saved_at", ""), count, has_notes))
                    except Exception:
                        pass
                con.commit()
        except Exception as e:
            print(f"[db] Migration error: {e}")
            
        con.close()


# ── files ───────────────────────────────────────────────────────────────────

def upsert_file(file_id: str, sop_uid: str, path: str,
                sha256: str, upload_time: str, original_name: Optional[str] = None) -> None:
    with _lock:
        con = _connect()
        con.execute("""
            INSERT INTO files(file_id, sop_uid, path, sha256, upload_time, original_name)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(file_id) DO UPDATE SET
                sop_uid=excluded.sop_uid,
                path=excluded.path,
                sha256=excluded.sha256,
                upload_time=excluded.upload_time,
                original_name=excluded.original_name
        """, (file_id, sop_uid, path, sha256, upload_time, original_name))
        con.commit()
        con.close()


def get_file_by_sha(sha256: str) -> Optional[dict]:
    """Find a file by pixel-data hash (catches renamed duplicates)."""
    with _lock:
        con = _connect()
        row = con.execute(
            "SELECT * FROM files WHERE sha256=? LIMIT 1", (sha256,)
        ).fetchone()
        con.close()
        return dict(row) if row else None


def get_file(file_id: str) -> Optional[dict]:
    with _lock:
        con = _connect()
        row = con.execute(
            "SELECT * FROM files WHERE file_id=?", (file_id,)
        ).fetchone()
        con.close()
        return dict(row) if row else None


def get_file_by_path(path: str) -> Optional[dict]:
    """Return a file record by its stored path."""
    with _lock:
        con = _connect()
        row = con.execute("SELECT * FROM files WHERE path=? LIMIT 1", (path,)).fetchone()
        con.close()
        return dict(row) if row else None


def delete_file(file_id: str) -> bool:
    """Remove file record, its path_cache entry and annotation index.

    Returns True if a row was deleted, False otherwise.
    """
    with _lock:
        con = _connect()
        row = con.execute("SELECT path FROM files WHERE file_id=?", (file_id,)).fetchone()
        if not row:
            con.close()
            return False
        path = row['path']
        con.execute("DELETE FROM files WHERE file_id=?", (file_id,))
        con.execute("DELETE FROM path_cache WHERE path=?", (path,))
        con.execute("DELETE FROM annotations WHERE file_id=?", (file_id,))
        con.commit()
        con.close()
        return True


def list_all_files() -> List[dict]:
    with _lock:
        con = _connect()
        rows = con.execute(
            "SELECT * FROM files ORDER BY upload_time DESC"
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]


# ── annotations ─────────────────────────────────────────────────────────────

def upsert_annotation(file_id: str, version: int, saved_at: str,
                      annotation_count: int = 0, has_notes: int = 0) -> None:
    with _lock:
        con = _connect()
        con.execute("""
            INSERT INTO annotations(file_id, version, saved_at, annotation_count, has_notes)
            VALUES(?,?,?,?,?)
            ON CONFLICT(file_id) DO UPDATE SET
                version=excluded.version,
                saved_at=excluded.saved_at,
                annotation_count=excluded.annotation_count,
                has_notes=excluded.has_notes
        """, (file_id, version, saved_at, annotation_count, has_notes))
        con.commit()
        con.close()


def delete_annotation_record(file_id: str) -> bool:
    with _lock:
        con = _connect()
        cur = con.execute(
            "DELETE FROM annotations WHERE file_id=?", (file_id,)
        )
        con.commit()
        changed = cur.rowcount > 0
        con.close()
        return changed


def list_annotated_ids() -> List[str]:
    with _lock:
        con = _connect()
        rows = con.execute("SELECT file_id FROM annotations").fetchall()
        con.close()
        return [r["file_id"] for r in rows]


# ── path cache ───────────────────────────────────────────────────────────────

def cache_path(path: str, file_id: str, cached_at: str) -> None:
    """Record path → file_id so tree can show annotated dots after restart."""
    with _lock:
        con = _connect()
        con.execute("""
            INSERT INTO path_cache(path, file_id, cached_at)
            VALUES(?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                file_id=excluded.file_id,
                cached_at=excluded.cached_at
        """, (path, file_id, cached_at))
        con.commit()
        con.close()


def get_annotated_paths() -> List[str]:
    """
    Return file paths that have saved annotations.
    Achieved via INNER JOIN of path_cache and annotations.
    """
    with _lock:
        con = _connect()
        rows = con.execute("""
            SELECT pc.path
            FROM   path_cache pc
            INNER JOIN annotations a ON pc.file_id = a.file_id
        """).fetchall()
        con.close()
        return [r["path"] for r in rows]


def get_annotated_details() -> List[dict]:
    """
    Return a list of dicts with keys: path, annotation_count, has_notes
    """
    with _lock:
        con = _connect()
        rows = con.execute("""
            SELECT pc.path, a.annotation_count, a.has_notes
            FROM   path_cache pc
            INNER JOIN annotations a ON pc.file_id = a.file_id
        """).fetchall()
        con.close()
        return [dict(r) for r in rows]
