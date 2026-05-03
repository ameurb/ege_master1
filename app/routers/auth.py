from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import PROFESSOR_CODE
from app.auth import require_student, require_professor
from app.services.data_service import (
    get_student, get_tps, get_active_session, get_tp,
    get_submission_meta, get_team_key_for_student,
    get_grades, get_attendance,
    get_students, list_submissions, set_team,
    get_team_members, get_max_team_size, get_settings, save_settings,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/login")
async def login_page(request: Request, next: str = "/dashboard", error: str = ""):
    user = request.session.get("user")
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "next": next,
        "error": error,
    })


@router.post("/login")
async def login_submit(
    request: Request,
    code: str = Form(...),
    next: str = Form("/dashboard"),
):
    code = code.strip()

    # Check professor code
    if code == PROFESSOR_CODE:
        request.session["user"] = {
            "role": "professor",
            "name": "Professor",
        }
        return RedirectResponse(url=next, status_code=303)

    # Check student matricule
    student = get_student(code)
    if student:
        request.session["user"] = {
            "role": "student",
            "matricule": student["matricule"],
            "name": student["name"],
        }
        return RedirectResponse(url=next, status_code=303)

    # Invalid
    return templates.TemplateResponse("login.html", {
        "request": request,
        "next": next,
        "error": "Invalid matricule or code. Please try again.",
    })


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/dashboard")
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user["role"] == "student":
        return _student_dashboard(request, user)
    return _professor_dashboard(request, user)


def _student_dashboard(request: Request, user: dict):
    matricule = user["matricule"]
    student = get_student(matricule)

    # Get team members (excluding self)
    team_members = get_team_members(matricule)
    partners = [m for m in team_members if m["matricule"] != matricule]

    tps = get_tps()
    grades = get_grades()
    active_session = get_active_session()

    # Build per-TP submission + grade info
    tp_info = []
    team_key = get_team_key_for_student(matricule)

    for tp in tps:
        meta = get_submission_meta(tp["id"], team_key)
        tp_grade = grades.get(tp["id"], {}).get(team_key)
        tp_info.append({
            "tp": tp,
            "submitted": meta is not None,
            "submitted_at": meta.get("submitted_at", "") if meta else "",
            "grade": tp_grade,
        })

    # Attendance
    attendance_sessions = get_attendance()
    present_count = 0
    total_sessions = len(attendance_sessions)
    attendance_records = []
    for sess in attendance_sessions:
        status = sess.get("records", {}).get(matricule, "")
        if status == "present":
            present_count += 1
        attendance_records.append({
            "date": sess["date"],
            "label": sess.get("label", ""),
            "status": status,
        })
    att_pct = round(present_count / total_sessions * 100) if total_sessions > 0 else 0

    return templates.TemplateResponse("dashboard_student.html", {
        "request": request,
        "student": student,
        "partners": partners,
        "tp_info": tp_info,
        "active_session": active_session,
        "attendance_records": attendance_records,
        "present_count": present_count,
        "total_sessions": total_sessions,
        "att_pct": att_pct,
        "max_team_size": get_max_team_size(),
    })


def _professor_dashboard(request: Request, user: dict):
    students = get_students()
    tps = get_tps()
    active_session = get_active_session()
    active_tp = get_tp(active_session["tp_id"]) if active_session else None

    # All submissions across all TPs
    all_submissions = []
    for tp in tps:
        for sub in list_submissions(tp["id"]):
            sub["tp_title"] = tp["title"]
            sub["tp_id"] = tp["id"]
            all_submissions.append(sub)
    all_submissions.sort(key=lambda s: s.get("submitted_at", ""), reverse=True)
    total_submissions = len(all_submissions)
    recent_submissions = all_submissions[:10]

    return templates.TemplateResponse("dashboard_professor.html", {
        "request": request,
        "student_count": len(students),
        "tp_count": len(tps),
        "tps": tps,
        "active_session": active_session,
        "active_tp": active_tp,
        "recent_submissions": recent_submissions,
        "total_submissions": total_submissions,
        "max_team_size": get_max_team_size(),
    })


def _format_short_name(full_name: str) -> str:
    """Convert 'LASTNAME Firstname' to 'LASTNAME F.'"""
    parts = full_name.split()
    if len(parts) < 2:
        return full_name
    lastname = parts[0]
    first_initial = parts[1][0].upper() if parts[1] else ""
    return f"{lastname} {first_initial}."


@router.get("/api/student-lookup")
async def student_lookup(matricule: str = ""):
    """Live lookup for binome input — returns name + group."""
    student = get_student(matricule.strip())
    if student:
        return {"found": True, "name": student["name"], "group": student.get("group", "")}
    return {"found": False}


@router.get("/binome")
async def binome_page(request: Request, user: dict = Depends(require_student)):
    matricule = user["matricule"]
    student = get_student(matricule)
    if not student:
        return RedirectResponse(url="/dashboard", status_code=303)

    team_members = get_team_members(matricule)
    partners = [m for m in team_members if m["matricule"] != matricule]

    return templates.TemplateResponse("binome_select.html", {
        "request": request,
        "student": student,
        "partners": partners,
        "max_team_size": get_max_team_size(),
    })


@router.post("/api/binome")
async def api_set_binome(
    request: Request,
    partner1_matricule: str = Form(""),
    partner2_matricule: str = Form(""),
    user: dict = Depends(require_student),
):
    matricule = user["matricule"]
    mat1 = partner1_matricule.strip()
    mat2 = partner2_matricule.strip()

    # Build list of team members
    team = [matricule]
    if mat1:
        team.append(mat1)
    if mat2:
        team.append(mat2)

    # Check no duplicates
    if len(set(team)) != len(team):
        return RedirectResponse(url="/binome?error=same", status_code=303)

    # Validate all exist
    for m in team:
        if not get_student(m):
            return RedirectResponse(url="/binome?error=invalid", status_code=303)

    # Check team size allowed
    max_size = get_max_team_size()
    if len(team) > max_size:
        return RedirectResponse(url="/binome?error=toomany", status_code=303)

    success = set_team(team)
    if success:
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/binome?error=failed", status_code=303)


@router.post("/api/settings/team-size")
async def api_set_team_size(
    max_team_size: int = Form(...),
    user: dict = Depends(require_professor),
):
    settings = get_settings()
    settings["max_team_size"] = max(1, min(3, max_team_size))
    save_settings(settings)
    return RedirectResponse(url="/dashboard", status_code=303)
