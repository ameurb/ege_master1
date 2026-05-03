import uuid
from datetime import datetime
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException, Depends, Cookie
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from app.auth import require_student, require_professor
from app.config import SUBMISSION_EXTENSIONS
from app.services.file_service import sanitize_filename, format_size
from app.services.preview_service import render_preview
from app.services.data_service import (
    get_tps, get_tp, create_tp, update_tp, delete_tp, delete_tp_file, add_tp_file, get_tp_files_dir,
    get_active_session, start_session, stop_session,
    check_pc_lock, lock_pc, make_binome_key,
    get_student, get_students,
    get_submission_dir, save_submission_meta, get_submission_meta,
    list_submissions, get_submission_files, get_submission_file_path,
    toggle_tp_step, get_team_key_for_student,
    mark_students_present, auto_mark_attendance_on_session_stop,
    get_grades_for_tp,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _get_client_ip(request: Request) -> str:
    """Get real client IP, checking proxy headers first."""
    # Cloudflare
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    # Standard proxy header
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    # Direct connection
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Student-facing: TP list and detail
# ---------------------------------------------------------------------------

@router.get("/tp")
async def tp_list(request: Request, user: dict = Depends(require_student)):
    tps = get_tps()
    team_key = get_team_key_for_student(user["matricule"])
    # Build submission status map
    submitted_ids = set()
    for tp in tps:
        if get_submission_meta(tp["id"], team_key):
            submitted_ids.add(tp["id"])
    # Group by week
    by_week: dict[int, list] = {}
    for tp in tps:
        w = tp.get("week", 0)
        by_week.setdefault(w, []).append(tp)
    session = get_active_session()
    return templates.TemplateResponse("tp_list.html", {
        "request": request,
        "tps_by_week": dict(sorted(by_week.items())),
        "active_session": session,
        "submitted_ids": submitted_ids,
    })


@router.get("/tp/manage")
async def tp_manage(request: Request, user: dict = Depends(require_professor)):
    tps = get_tps()
    session = get_active_session()
    sub_counts = {tp["id"]: len(list_submissions(tp["id"])) for tp in tps}
    return templates.TemplateResponse("tp_manage.html", {
        "request": request,
        "tps": tps,
        "active_session": session,
        "sub_counts": sub_counts,
    })


@router.get("/tp/session")
async def tp_session(request: Request, user: dict = Depends(require_professor)):
    session = get_active_session()
    tp = get_tp(session["tp_id"]) if session and session.get("tp_id") != "all" else None
    # Enrich PC locks with team names
    pc_locks = []
    if session:
        for pc_id, lock in session.get("pc_locks", {}).items():
            pc_locks.append({
                "pc_id": pc_id[:8],  # Short ID for display
                "team_key": lock.get("team_key", ""),
                "names": lock.get("team_names", lock.get("team_key", "")),
                "locked_at": lock.get("locked_at", ""),
            })

    # Collect all submissions across all TPs for this session
    all_submissions = []
    tps = get_tps()
    for t in tps:
        subs = list_submissions(t["id"])
        for sub in subs:
            # Only show submissions made during this session
            if session and sub.get("submitted_at", "") >= session.get("started_at", ""):
                sub["tp_title"] = t["title"]
                all_submissions.append(sub)

    # Sort by submission time (newest first)
    all_submissions.sort(key=lambda s: s.get("submitted_at", ""), reverse=True)

    return templates.TemplateResponse("tp_session.html", {
        "request": request,
        "session": session,
        "tp": tp,
        "pc_locks": pc_locks,
        "submissions": all_submissions,
        "submission_count": len(all_submissions),
    })


@router.get("/tp/submit")
async def tp_submit_form(request: Request, user: dict = Depends(require_student), ege_pc_id: Optional[str] = Cookie(None)):
    session = get_active_session()
    if not session:
        return templates.TemplateResponse("tp_submit.html", {
            "request": request,
            "error": "No active TP session. Wait for the professor to start one.",
            "session": None,
            "tp": None,
            "tps": [],
        })

    tps = get_tps()
    ip = _get_client_ip(request)

    # Auto-fill student info from session
    from app.services.data_service import get_team_members, set_team
    student = get_student(user["matricule"])
    team_members = get_team_members(user["matricule"])

    # Auto-create solo team if no team set
    if not student.get("team_id"):
        set_team([user["matricule"]])
        student = get_student(user["matricule"])
        team_members = get_team_members(user["matricule"])

    # Assign a PC ID cookie if not present
    pc_id = ege_pc_id or str(uuid.uuid4())

    # Check if this PC is locked to another team
    team_key = student.get("team_id", user["matricule"])
    lock_status = check_pc_lock(pc_id, team_key)
    pc_locked = lock_status == "locked_other"

    response = templates.TemplateResponse("tp_submit.html", {
        "request": request,
        "error": "This PC is already used by another team in this session." if pc_locked else None,
        "session": session,
        "tp": None,
        "tps": tps,
        "client_ip": ip,
        "student": student,
        "team_members": team_members,
    })
    if not ege_pc_id:
        response.set_cookie("ege_pc_id", pc_id, max_age=86400 * 30, httponly=True)
    return response


@router.get("/tp/{tp_id}")
async def tp_detail(request: Request, tp_id: str, user: dict = Depends(require_student)):
    tp = get_tp(tp_id)
    if not tp:
        raise HTTPException(status_code=404, detail="TP not found")
    files_dir = get_tp_files_dir(tp_id)
    files = []
    for f in sorted(files_dir.iterdir()):
        if f.is_file():
            files.append({
                "name": f.name,
                "size_display": format_size(f.stat().st_size),
            })
    session = get_active_session()
    return templates.TemplateResponse("tp_detail.html", {
        "request": request,
        "tp": tp,
        "files": files,
        "active_session": session,
    })


@router.get("/tp/{tp_id}/view/{filename}")
async def view_tp_file(request: Request, tp_id: str, filename: str, user: dict = Depends(require_student)):
    tp = get_tp(tp_id)
    if not tp:
        raise HTTPException(status_code=404, detail="TP not found")
    files_dir = get_tp_files_dir(tp_id)
    safe_name = sanitize_filename(filename)
    path = files_dir / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    content, ptype = render_preview(path)
    return templates.TemplateResponse("tp_file_view.html", {
        "request": request,
        "tp": tp,
        "filename": safe_name,
        "content": content,
        "preview_type": ptype,
    })


@router.get("/tp/{tp_id}/download/{filename}")
async def download_tp_file(tp_id: str, filename: str, user: dict = Depends(require_student)):
    files_dir = get_tp_files_dir(tp_id)
    safe_name = sanitize_filename(filename)
    path = files_dir / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=safe_name, media_type="application/octet-stream")


# ---------------------------------------------------------------------------
# Teacher: TP management
# ---------------------------------------------------------------------------

@router.post("/api/tp")
async def api_create_tp(
    user: dict = Depends(require_professor),
    tp_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    week: int = Form(1),
    due_date: str = Form(""),
    files: list[UploadFile] = File(None),
):
    try:
        tp = create_tp(tp_id.strip(), title.strip(), description.strip(), week, due_date.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Save attached files
    if files:
        tp_dir = get_tp_files_dir(tp_id.strip())
        for f in files:
            if f.filename and f.size and f.size > 0:
                safe_name = sanitize_filename(f.filename)
                content = await f.read()
                (tp_dir / safe_name).write_bytes(content)
                add_tp_file(tp_id.strip(), safe_name)

    return RedirectResponse(url="/tp/manage", status_code=303)


@router.post("/api/tp/{tp_id}/files")
async def api_add_tp_files(
    tp_id: str,
    files: list[UploadFile] = File(...),
    user: dict = Depends(require_professor),
):
    tp = get_tp(tp_id)
    if not tp:
        raise HTTPException(status_code=404, detail="TP not found")
    tp_dir = get_tp_files_dir(tp_id)
    for f in files:
        if f.filename and f.size and f.size > 0:
            safe_name = sanitize_filename(f.filename)
            content = await f.read()
            (tp_dir / safe_name).write_bytes(content)
            add_tp_file(tp_id, safe_name)
    return RedirectResponse(url="/tp/manage", status_code=303)


@router.post("/api/tp/{tp_id}/files/{filename}/delete")
async def api_delete_tp_file(tp_id: str, filename: str, user: dict = Depends(require_professor)):
    if not delete_tp_file(tp_id, filename):
        raise HTTPException(status_code=404, detail="TP not found")
    return RedirectResponse(url="/tp/manage", status_code=303)


@router.post("/api/tp/{tp_id}/delete")
async def api_delete_tp(tp_id: str, user: dict = Depends(require_professor)):
    if not delete_tp(tp_id):
        raise HTTPException(status_code=404, detail="TP not found")
    return RedirectResponse(url="/tp/manage", status_code=303)


@router.post("/api/tp/{tp_id}/edit")
async def api_edit_tp(
    tp_id: str,
    title: str = Form(...),
    description: str = Form(""),
    week: int = Form(1),
    due_date: str = Form(""),
    user: dict = Depends(require_professor),
):
    tp = update_tp(tp_id, title.strip(), description.strip(), week, due_date.strip())
    if not tp:
        raise HTTPException(status_code=404, detail="TP not found")
    return RedirectResponse(url="/tp/manage", status_code=303)


@router.post("/api/tp/{tp_id}/steps/{step_num}/toggle")
async def api_toggle_step(tp_id: str, step_num: int, user: dict = Depends(require_professor)):
    step = toggle_tp_step(tp_id, step_num)
    if not step:
        raise HTTPException(status_code=404, detail="TP or step not found")
    return RedirectResponse(url=f"/tp/{tp_id}/steps", status_code=303)


@router.get("/tp/{tp_id}/steps")
async def tp_steps_page(request: Request, tp_id: str, user: dict = Depends(require_professor)):
    tp = get_tp(tp_id)
    if not tp:
        raise HTTPException(status_code=404, detail="TP not found")
    return templates.TemplateResponse("tp_steps.html", {
        "request": request,
        "tp": tp,
    })


# ---------------------------------------------------------------------------
# Session management (PC locking)
# ---------------------------------------------------------------------------

@router.post("/api/tp/session/start")
async def api_start_session(user: dict = Depends(require_professor), tp_id: str = Form(...)):
    try:
        session = start_session(tp_id)
        return RedirectResponse(url="/tp/session", status_code=303)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/tp/session/stop")
async def api_stop_session(user: dict = Depends(require_professor)):
    session = get_active_session()
    if session:
        auto_mark_attendance_on_session_stop(session)
    stop_session()
    return RedirectResponse(url="/tp/manage", status_code=303)


# ---------------------------------------------------------------------------
# Student submission
# ---------------------------------------------------------------------------

@router.post("/api/tp/submit")
async def api_submit(
    request: Request,
    user: dict = Depends(require_student),
    tp_id: str = Form(...),
    files: list[UploadFile] = File(...),
    ege_pc_id: Optional[str] = Cookie(None),
):
    from app.services.data_service import get_team_key_for_student, get_team_members

    # Check active session
    session = get_active_session()
    if not session:
        raise HTTPException(status_code=400, detail="No active session")

    tp_id = tp_id.strip()
    ip = _get_client_ip(request)
    matricule = user["matricule"]

    # Get team key
    team_key = get_team_key_for_student(matricule)
    team_members = get_team_members(matricule)

    if not team_key or not team_members:
        raise HTTPException(status_code=400, detail="You must set your team first (go to Set Team page)")

    # Check PC lock via browser cookie
    pc_id = ege_pc_id or str(uuid.uuid4())
    lock_status = check_pc_lock(pc_id, team_key)
    if lock_status == "locked_other":
        raise HTTPException(status_code=403, detail="This PC is already used by another team in this session. Use a different computer.")

    # Validate files
    valid_files = []
    for f in files:
        if f.filename and f.size and f.size > 0:
            ext = Path(f.filename).suffix.lower()
            if ext not in SUBMISSION_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Only .py and .ipynb files are allowed. Got: {f.filename}")
            valid_files.append(f)

    if not valid_files:
        raise HTTPException(status_code=400, detail="No valid files uploaded")

    # Lock this PC to this team
    team_names = " & ".join(m["name"] for m in team_members)
    lock_pc(pc_id, team_key, team_names)

    # Save files (overwrite previous submission)
    sub_dir = get_submission_dir(tp_id, team_key)
    for old_file in sub_dir.iterdir():
        if old_file.is_file() and old_file.name != "meta.json":
            old_file.unlink()

    saved_files = []
    for f in valid_files:
        safe_name = sanitize_filename(f.filename)
        content = await f.read()
        (sub_dir / safe_name).write_bytes(content)
        saved_files.append(safe_name)

    # Save metadata
    members_info = [{"name": m["name"], "matricule": m["matricule"]} for m in team_members]
    meta = {
        "tp_id": tp_id,
        "team_members": members_info,
        "submitted_at": datetime.now().isoformat(),
        "files": saved_files,
        "ip_address": ip,
        "pc_id": pc_id,
    }
    save_submission_meta(tp_id, team_key, meta)

    # Auto-mark all team members as present in attendance
    team_matricules = [m["matricule"] for m in team_members]
    mark_students_present(team_matricules, session)

    # Set the pc_id cookie on the response (persists across login/logout)
    response = RedirectResponse(url=f"/tp/{tp_id}", status_code=303)
    response.set_cookie("ege_pc_id", pc_id, max_age=86400 * 30, httponly=True)
    return response


# ---------------------------------------------------------------------------
# Teacher: view submissions
# ---------------------------------------------------------------------------

@router.get("/tp/{tp_id}/submissions")
async def tp_submissions(request: Request, tp_id: str, user: dict = Depends(require_professor)):
    tp = get_tp(tp_id)
    if not tp:
        raise HTTPException(status_code=404, detail="TP not found")
    submissions = list_submissions(tp_id)
    grades = get_grades_for_tp(tp_id)
    return templates.TemplateResponse("tp_submissions.html", {
        "request": request,
        "tp": tp,
        "submissions": submissions,
        "grades": grades,
    })


@router.get("/tp/{tp_id}/submissions/{binome_key}")
async def tp_submission_detail(request: Request, tp_id: str, binome_key: str, user: dict = Depends(require_professor)):
    tp = get_tp(tp_id)
    if not tp:
        raise HTTPException(status_code=404, detail="TP not found")
    meta = get_submission_meta(tp_id, binome_key)
    if not meta:
        raise HTTPException(status_code=404, detail="Submission not found")
    files = get_submission_files(tp_id, binome_key)

    # Render previews for each file
    previews = []
    for f in files:
        file_path = get_submission_file_path(tp_id, binome_key, f["name"])
        if file_path:
            content, ptype = render_preview(file_path)
            previews.append({
                "name": f["name"],
                "size": format_size(f["size"]),
                "extension": f["extension"],
                "preview_content": content,
                "preview_type": ptype,
            })

    # Get grades
    from app.services.data_service import get_grades_for_tp
    grades = get_grades_for_tp(tp_id)
    grade = grades.get(binome_key)

    return templates.TemplateResponse("tp_submission_detail.html", {
        "request": request,
        "tp": tp,
        "meta": meta,
        "binome_key": binome_key,
        "files": previews,
        "grade": grade,
    })


@router.get("/tp/{tp_id}/submissions/{binome_key}/download/{filename}")
async def download_submission_file(tp_id: str, binome_key: str, filename: str, user: dict = Depends(require_professor)):
    path = get_submission_file_path(tp_id, binome_key, filename)
    if not path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")
