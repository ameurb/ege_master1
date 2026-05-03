from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from app.auth import require_professor
from app.services.data_service import (
    get_students, get_students_by_group, get_attendance, save_attendance_session,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/attendance")
async def attendance_page(request: Request, user: dict = Depends(require_professor)):
    students = get_students()
    sessions = get_attendance()
    # Build matrix: student -> {date: status}
    matrix = {}
    for s in students:
        matrix[s["matricule"]] = {"name": s["name"], "group": s.get("group", "")}
        for sess in sessions:
            matrix[s["matricule"]][sess["date"]] = sess.get("records", {}).get(s["matricule"], "")
            note = sess.get("notes", {}).get(s["matricule"])
            if note is not None:
                matrix[s["matricule"]][sess["date"] + "_note"] = note
    return templates.TemplateResponse("attendance.html", {
        "request": request,
        "students": students,
        "sessions": sessions,
        "matrix": matrix,
    })


@router.get("/attendance/session")
async def attendance_session_form(request: Request, user: dict = Depends(require_professor), date: Optional[str] = None):
    students = get_students()
    groups = get_students_by_group()
    # If date given, pre-fill existing records
    existing = {}
    existing_notes = {}
    if date:
        for sess in get_attendance():
            if sess["date"] == date:
                existing = sess.get("records", {})
                existing_notes = sess.get("notes", {})
                break
    return templates.TemplateResponse("attendance_session.html", {
        "request": request,
        "students": students,
        "groups": groups,
        "date": date or "",
        "existing": existing,
        "existing_notes": existing_notes,
    })


@router.post("/api/attendance/session")
async def api_save_attendance(request: Request, user: dict = Depends(require_professor)):
    form = await request.form()
    date = form.get("date", "")
    week = int(form.get("week", 1))
    label = form.get("label", f"Semaine {week}")
    records = {}
    notes = {}
    for key, value in form.items():
        if key.startswith("status_"):
            matricule = key[7:]  # Remove "status_" prefix
            records[matricule] = value
        elif key.startswith("note_"):
            matricule = key[5:]  # Remove "note_" prefix
            if value.strip():
                notes[matricule] = float(value)
    save_attendance_session(date, week, label, records, notes)
    return RedirectResponse(url="/attendance", status_code=303)
