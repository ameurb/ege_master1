from pathlib import Path
from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import require_student, require_professor, require_any_user

router = APIRouter(prefix="/course", tags=["course"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

MOODLE_DIR = Path(__file__).parent.parent.parent / "uploads" / "moodle"

# Course metadata — single source of truth
COURSE_WEEKS = [
    {
        "week": 0,
        "title": "Setup Guide",
        "subtitle": "Python environment — Colab & Anaconda",
        "html_file": "Week00_Setup.html",
        "notebooks": [],
        "datasets": [],
        "color": "gray",
        "icon": "⚙️",
    },
    {
        "week": 1,
        "title": "Python Fundamentals",
        "subtitle": "Variables, types, operators, f-strings, economic formulas",
        "html_file": "Week01_Complete.html",
        "notebooks": ["TP1_Economic_Calculator_Starter.ipynb"],
        "datasets": ["algeria_economic_combined.csv"],
        "color": "blue",
        "icon": "🐍",
    },
    {
        "week": 2,
        "title": "Data Structures & Functions",
        "subtitle": "Lists, dicts, loops, conditions, def/return/lambda",
        "html_file": "Week02_Complete.html",
        "notebooks": ["TP2_Country_Comparison_Starter.ipynb"],
        "datasets": [],
        "color": "indigo",
        "icon": "📋",
    },
    {
        "week": 3,
        "title": "Pandas — Data Analysis",
        "subtitle": "Load CSV, filter, aggregate, correlations, NumPy",
        "html_file": "Week03_Complete.html",
        "notebooks": ["TP3_Pandas_Analysis_Starter.ipynb"],
        "datasets": ["algeria_economic_combined.csv"],
        "color": "violet",
        "icon": "🐼",
    },
    {
        "week": 4,
        "title": "Data Visualization",
        "subtitle": "matplotlib — line, bar, scatter, histogram, dashboard",
        "html_file": "Week04_Complete.html",
        "notebooks": ["TP4_Visualization_Starter.ipynb"],
        "datasets": ["algeria_economic_combined.csv"],
        "color": "orange",
        "icon": "📊",
    },
    {
        "week": 5,
        "title": "Statistics & Econometrics",
        "subtitle": "OLS regression, correlation heatmap, Okun's Law",
        "html_file": "Week05_Complete.html",
        "notebooks": ["TP5_Statistics_Starter.ipynb"],
        "datasets": ["world_bank_economic_indicators.csv"],
        "color": "teal",
        "icon": "📈",
    },
    {
        "week": 6,
        "title": "Machine Learning",
        "subtitle": "Linear Regression, Random Forest, R², MAE, RMSE",
        "html_file": "Week06_Complete.html",
        "notebooks": ["TP6_MachineLearning_Starter.ipynb"],
        "datasets": ["world_bank_economic_indicators.csv"],
        "color": "purple",
        "icon": "🤖",
    },
    {
        "week": 7,
        "title": "Final Project",
        "subtitle": "Instructions, rubric, presentation guide",
        "html_file": "Week07_Complete.html",
        "notebooks": [],
        "datasets": ["algeria_economic_combined.csv", "world_bank_economic_indicators.csv"],
        "color": "red",
        "icon": "🎯",
    },
    {
        "week": 8,
        "title": "Exam Preparation",
        "subtitle": "Full review, Python cheat sheet, practice quiz",
        "html_file": "Week08_Complete.html",
        "notebooks": [],
        "datasets": [],
        "color": "slate",
        "icon": "📝",
    },
]


def get_week(week_num: int) -> dict | None:
    for w in COURSE_WEEKS:
        if w["week"] == week_num:
            return w
    return None


def get_progress(matricule: str) -> set[int]:
    """Return set of completed week numbers for a student."""
    progress_file = MOODLE_DIR.parent / "course_progress" / f"{matricule}.json"
    if not progress_file.exists():
        return set()
    import json
    try:
        data = json.loads(progress_file.read_text())
        return set(data.get("completed", []))
    except Exception:
        return set()


def save_progress(matricule: str, week: int) -> None:
    """Mark a week as completed for a student."""
    import json
    progress_dir = MOODLE_DIR.parent / "course_progress"
    progress_dir.mkdir(parents=True, exist_ok=True)
    progress_file = progress_dir / f"{matricule}.json"
    completed = get_progress(matricule)
    completed.add(week)
    progress_file.write_text(json.dumps({"completed": sorted(completed)}))


# ---------------------------------------------------------------------------
# Routes — student
# ---------------------------------------------------------------------------

@router.get("")
async def course_index(request: Request, user: dict = Depends(require_any_user)):
    if user.get("role") == "professor":
        return RedirectResponse("/course/manage", status_code=303)
    completed = get_progress(user["matricule"])
    weeks_with_status = []
    for w in COURSE_WEEKS:
        weeks_with_status.append({
            **w,
            "completed": w["week"] in completed,
            "available": (MOODLE_DIR / w["html_file"]).exists(),
        })
    return templates.TemplateResponse("course.html", {
        "request": request,
        "weeks": weeks_with_status,
        "completed_count": len(completed),
        "total_weeks": len(COURSE_WEEKS),
    })


@router.get("/week/{week_num}")
async def course_week(request: Request, week_num: int, user: dict = Depends(require_student)):
    week = get_week(week_num)
    if not week:
        return RedirectResponse("/course")
    completed = get_progress(user["matricule"])
    # Auto-mark as completed when opened
    save_progress(user["matricule"], week_num)
    # Check which files actually exist
    notebooks_available = [n for n in week["notebooks"] if (MOODLE_DIR / n).exists()]
    datasets_available = [d for d in week["datasets"] if (MOODLE_DIR / d).exists()]
    prev_week = get_week(week_num - 1)
    next_week = get_week(week_num + 1)
    return templates.TemplateResponse("course_week.html", {
        "request": request,
        "week": week,
        "week_num": week_num,
        "html_url": f"/uploads/moodle/{week['html_file']}",
        "notebooks": notebooks_available,
        "datasets": datasets_available,
        "completed": week_num in completed,
        "prev_week": prev_week,
        "next_week": next_week,
    })


@router.get("/download/{filename}")
async def course_download(filename: str, user: dict = Depends(require_student)):
    """Download a course file (notebook or dataset)."""
    # Security: only allow files in moodle dir, no path traversal
    safe_name = Path(filename).name
    file_path = MOODLE_DIR / safe_name
    if not file_path.exists() or not file_path.is_file():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=safe_name)


# ---------------------------------------------------------------------------
# Routes — professor: course management
# ---------------------------------------------------------------------------

@router.get("/manage")
async def course_manage(request: Request, user: dict = Depends(require_professor)):
    weeks_status = []
    for w in COURSE_WEEKS:
        weeks_status.append({
            **w,
            "available": (MOODLE_DIR / w["html_file"]).exists(),
            "notebooks_available": [n for n in w["notebooks"] if (MOODLE_DIR / n).exists()],
            "datasets_available": [d for d in w["datasets"] if (MOODLE_DIR / d).exists()],
        })
    return templates.TemplateResponse("course_manage.html", {
        "request": request,
        "weeks": weeks_status,
        "total": len(COURSE_WEEKS),
        "published": sum(1 for w in weeks_status if w["available"]),
    })
