from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from .api import dicom, annotation, segment, export
from .core import db as _db

app = FastAPI(title="DICOM Defect Annotation Tool", version="2.0.0")

# Restrict CORS to localhost only.
# The frontend is served from the same origin (port 8000), so same-origin
# requests don't need CORS at all.  These entries cover dev tools and
# alternative loopback addresses only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialise SQLite schema on every startup (idempotent)."""
    _db.init_db()


app.include_router(dicom.router,      prefix="/api", tags=["dicom"])
app.include_router(annotation.router, prefix="/api", tags=["annotation"])
app.include_router(segment.router,    prefix="/api", tags=["segment"])
app.include_router(export.router,     prefix="/api", tags=["export"])

FRONTEND = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND / "index.html"))


@app.get("/{path:path}")
async def catch_all(path: str):
    fp = FRONTEND / path
    if fp.exists() and fp.is_file():
        return FileResponse(str(fp))
    return FileResponse(str(FRONTEND / "index.html"))
