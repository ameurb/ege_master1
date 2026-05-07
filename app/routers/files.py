from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.auth import require_professor
from app.services.file_service import (
    list_categories, list_files, get_file_path, delete_file, format_size,
)
from app.services.preview_service import render_preview

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _enrich_files(files: list[dict]) -> list[dict]:
    """Add display-friendly fields to file dicts."""
    for f in files:
        f["size_display"] = format_size(f["size"])
        f["modified_display"] = datetime.fromtimestamp(f["modified"]).strftime("%Y-%m-%d %H:%M")
    return files


@router.get("/")
async def home(request: Request):
    if not request.session.get("user"):
        return RedirectResponse(url="/login", status_code=303)
    cats = list_categories()
    recent = _enrich_files(list_files())[:20]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "categories": cats,
        "recent_files": recent,
    })


@router.get("/folder/{category}")
async def folder_view(request: Request, category: str):
    cats = list_categories()
    files = _enrich_files(list_files(category))
    cat_names = [c["name"] for c in cats]
    if category not in cat_names and not files:
        raise HTTPException(status_code=404, detail="Category not found")
    return templates.TemplateResponse("folder.html", {
        "request": request,
        "category": category,
        "categories": cats,
        "files": files,
    })


@router.get("/api/files")
async def api_list_files(category: str | None = None):
    files = list_files(category)
    return {"files": _enrich_files(files)}


@router.get("/api/categories")
async def api_list_categories():
    return {"categories": list_categories()}


@router.get("/preview/{category}/{filename}")
async def preview_file(request: Request, category: str, filename: str):
    path = get_file_path(category, filename)
    if not path:
        raise HTTPException(status_code=404, detail="File not found")

    preview_content, preview_type = render_preview(path)

    return templates.TemplateResponse("preview.html", {
        "request": request,
        "filename": filename,
        "category": category,
        "file_path": f"{category}/{filename}",
        "extension": path.suffix.lower(),
        "preview_content": preview_content,
        "preview_type": preview_type,
        "size_display": format_size(path.stat().st_size),
    })


@router.get("/download/{category}/{filename}")
async def download_file(category: str, filename: str):
    path = get_file_path(category, filename)
    if not path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


@router.delete("/api/files/{category}/{filename}")
async def api_delete_file(category: str, filename: str, user: dict = Depends(require_professor)):
    if delete_file(category, filename):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="File not found")
