from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.auth import require_professor
from app.services.data_service import (
    get_students, add_student, delete_student, import_students_csv,
    get_students_by_group,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/students")
async def students_page(request: Request, user: dict = Depends(require_professor)):
    students = get_students()
    groups = get_students_by_group()
    return templates.TemplateResponse("students.html", {
        "request": request,
        "students": students,
        "groups": groups,
    })


@router.post("/api/students")
async def api_add_student(
    user: dict = Depends(require_professor),
    matricule: str = Form(...),
    name: str = Form(...),
    group: str = Form("G1"),
    binome_matricule: str = Form(""),
):
    try:
        student = add_student(matricule.strip(), name.strip(), group.strip(), binome_matricule.strip())
        return RedirectResponse(url="/students", status_code=303)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/students/import")
async def api_import_students(user: dict = Depends(require_professor), file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    result = import_students_csv(content)
    return RedirectResponse(url="/students", status_code=303)


@router.post("/api/students/{matricule}/delete")
async def api_delete_student(matricule: str, user: dict = Depends(require_professor)):
    if delete_student(matricule):
        return RedirectResponse(url="/students", status_code=303)
    raise HTTPException(status_code=404, detail="Student not found")
