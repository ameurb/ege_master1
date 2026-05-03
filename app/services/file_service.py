import os
import re
import time
from pathlib import Path
from typing import Optional

from app.config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE


def sanitize_filename(name: str) -> str:
    """Sanitize filename: keep alphanumeric, hyphens, underscores, dots."""
    name = name.strip()
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    # Remove anything that's not alphanumeric, hyphen, underscore, or dot
    name = re.sub(r"[^\w\-.]", "", name)
    # Collapse multiple dots/underscores
    name = re.sub(r"\.{2,}", ".", name)
    name = re.sub(r"_{2,}", "_", name)
    return name or "unnamed"


def sanitize_category(name: str) -> str:
    """Sanitize category name for use as directory name."""
    name = name.strip().lower()
    name = name.replace(" ", "-")
    name = re.sub(r"[^\w\-]", "", name)
    return name or "general"


def create_category(name: str) -> dict:
    """Create a new category directory."""
    safe_name = sanitize_category(name)
    cat_dir = UPLOAD_DIR / safe_name
    cat_dir.mkdir(exist_ok=True)
    return {"name": safe_name, "path": str(cat_dir)}


async def save_file(file, category: str) -> dict:
    """Save an uploaded file to the given category."""
    safe_cat = sanitize_category(category)
    cat_dir = UPLOAD_DIR / safe_cat
    cat_dir.mkdir(exist_ok=True)

    safe_name = sanitize_filename(file.filename)
    ext = Path(safe_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '{ext}' is not allowed")

    dest = cat_dir / safe_name
    # If file exists, add timestamp
    if dest.exists():
        stem = Path(safe_name).stem
        safe_name = f"{stem}_{int(time.time())}{ext}"
        dest = cat_dir / safe_name

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large (max 100 MB)")
    dest.write_bytes(content)

    return {
        "filename": safe_name,
        "category": safe_cat,
        "size": len(content),
        "path": f"{safe_cat}/{safe_name}",
    }


def list_categories() -> list[dict]:
    """List all categories (subdirectories of uploads/)."""
    cats = []
    if not UPLOAD_DIR.exists():
        return cats
    for d in sorted(UPLOAD_DIR.iterdir()):
        if d.is_dir():
            file_count = sum(1 for f in d.iterdir() if f.is_file())
            cats.append({"name": d.name, "file_count": file_count})
    return cats


def list_files(category: Optional[str] = None) -> list[dict]:
    """List files, optionally filtered by category."""
    files = []
    if category:
        cat_dir = UPLOAD_DIR / sanitize_category(category)
        if cat_dir.exists():
            files = _files_in_dir(cat_dir, sanitize_category(category))
    else:
        # All files across all categories
        if UPLOAD_DIR.exists():
            for d in sorted(UPLOAD_DIR.iterdir()):
                if d.is_dir():
                    files.extend(_files_in_dir(d, d.name))
    # Sort by modification time, newest first
    files.sort(key=lambda f: f["modified"], reverse=True)
    return files


def _files_in_dir(directory: Path, category: str) -> list[dict]:
    """Get file info for all files in a directory."""
    result = []
    for f in directory.iterdir():
        if f.is_file():
            stat = f.stat()
            result.append({
                "filename": f.name,
                "category": category,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "extension": f.suffix.lower(),
                "path": f"{category}/{f.name}",
            })
    return result


def get_file_path(category: str, filename: str) -> Optional[Path]:
    """Get the full path to a file, or None if it doesn't exist."""
    safe_cat = sanitize_category(category)
    safe_name = sanitize_filename(filename)
    path = UPLOAD_DIR / safe_cat / safe_name
    if path.exists() and path.is_file():
        return path
    return None


def delete_file(category: str, filename: str) -> bool:
    """Delete a file. Returns True if deleted."""
    path = get_file_path(category, filename)
    if path:
        path.unlink()
        return True
    return False


def format_size(size: int) -> str:
    """Format file size for display."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
