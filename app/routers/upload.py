from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends

from app.auth import require_professor
from app.services.file_service import save_file, create_category

router = APIRouter()


@router.post("/api/upload")
async def upload_files(
    user: dict = Depends(require_professor),
    files: list[UploadFile] = File(...),
    category: str = Form("general"),
):
    results = []
    errors = []
    for f in files:
        try:
            info = await save_file(f, category)
            results.append(info)
        except ValueError as e:
            errors.append({"filename": f.filename, "error": str(e)})
        except Exception as e:
            errors.append({"filename": f.filename, "error": f"Upload failed: {e}"})
    return {"uploaded": results, "errors": errors}


@router.post("/api/category")
async def create_new_category(user: dict = Depends(require_professor), name: str = Form(...)):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Category name is required")
    cat = create_category(name)
    return cat
