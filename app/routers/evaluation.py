from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.auth import require_professor
from datetime import datetime

from app.services.data_service import (
    get_tps, get_tp, get_students,
    get_evaluation_data, export_csv, export_xlsx,
    get_grades_for_tp, save_grades_for_tp,
    list_submissions, make_binome_key,
    get_participation_grades,
    get_attendance_for_date, save_attendance_session,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/evaluation")
async def evaluation_page(request: Request, user: dict = Depends(require_professor)):
    eval_data = get_evaluation_data()
    return templates.TemplateResponse("evaluation.html", {
        "request": request,
        "rows": eval_data["rows"],
        "tps": eval_data["tps"],
        "sessions": eval_data["attendance_sessions"],
    })


@router.get("/evaluation/grades/{tp_id}")
async def grade_entry_page(request: Request, tp_id: str, user: dict = Depends(require_professor)):
    tp = get_tp(tp_id)
    if not tp:
        return RedirectResponse(url="/evaluation", status_code=303)
    submissions = list_submissions(tp_id)
    grades = get_grades_for_tp(tp_id)
    participation = get_participation_grades()
    # Today's attendance for pre-fill
    today = datetime.now().strftime("%Y-%m-%d")
    today_attendance = get_attendance_for_date(today)
    today_records = today_attendance.get("records", {}) if today_attendance else {}
    today_notes = today_attendance.get("notes", {}) if today_attendance else {}
    # Enrich submissions with existing grades, participation, and today's attendance
    for sub in submissions:
        sub["grade_data"] = grades.get(sub["binome_key"])
        for m in sub.get("team_members", []):
            m["participation_grade"] = participation.get(m["matricule"])
            m["today_status"] = today_records.get(m["matricule"], "")
            m["today_note"] = today_notes.get(m["matricule"], "")
    return templates.TemplateResponse("grade_entry.html", {
        "request": request,
        "tp": tp,
        "submissions": submissions,
        "grades": grades,
        "today": today,
    })


@router.post("/api/evaluation/grades/{tp_id}")
async def api_save_grades(request: Request, tp_id: str, user: dict = Depends(require_professor)):
    form = await request.form()

    # Handle single grade save (from submission detail page)
    if form.get("binome_key"):
        binome_key = form["binome_key"]
        grade = float(form.get("grade", 0))
        max_grade = float(form.get("max_grade", 20))
        comment = form.get("comment", "")
        save_grades_for_tp(tp_id, {
            binome_key: {"grade": grade, "max_grade": max_grade, "comment": comment}
        })
        # Redirect back to submission detail
        referer = request.headers.get("referer", f"/evaluation/grades/{tp_id}")
        return RedirectResponse(url=referer, status_code=303)

    # Handle bulk grade save (from grade_entry page)
    grades_data = {}
    att_records = {}
    att_notes = {}
    for key, value in form.items():
        if key.startswith("grade_"):
            binome_key = key[6:]  # Remove "grade_" prefix
            grade_val = value.strip()
            if grade_val:
                max_grade = float(form.get(f"max_{binome_key}", 20))
                comment = form.get(f"comment_{binome_key}", "")
                grades_data[binome_key] = {
                    "grade": float(grade_val),
                    "max_grade": max_grade,
                    "comment": comment,
                }
        elif key.startswith("att_status_"):
            matricule = key[11:]  # Remove "att_status_" prefix
            if value:
                att_records[matricule] = value
        elif key.startswith("att_note_"):
            matricule = key[9:]  # Remove "att_note_" prefix
            if value.strip():
                att_notes[matricule] = float(value)

    if grades_data:
        save_grades_for_tp(tp_id, grades_data)

    # Save attendance for today if any attendance data was submitted
    if att_records:
        today = form.get("attendance_date", datetime.now().strftime("%Y-%m-%d"))
        tp_data = get_tp(tp_id)
        week = tp_data["week"] if tp_data else 0
        # Merge with existing attendance for today
        existing = get_attendance_for_date(today)
        if existing:
            merged_records = existing["records"]
            merged_notes = existing.get("notes", {})
            merged_records.update(att_records)
            merged_notes.update(att_notes)
            label = existing["label"]
            week = existing["week"] or week
        else:
            merged_records = att_records
            merged_notes = att_notes
            label = f"TP Session {today}"
        save_attendance_session(today, week, label, merged_records, merged_notes)

    return RedirectResponse(url=f"/evaluation/grades/{tp_id}", status_code=303)


@router.get("/api/evaluation/export")
async def api_export_csv(user: dict = Depends(require_professor)):
    csv_content = export_csv()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=evaluation_export.csv"},
    )


@router.get("/api/evaluation/export-xlsx")
async def api_export_xlsx(user: dict = Depends(require_professor)):
    xlsx_content = export_xlsx()
    return Response(
        content=xlsx_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=evaluation_export.xlsx"},
    )
