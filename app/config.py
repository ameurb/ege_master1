import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

TP_FILES_DIR = DATA_DIR / "tp_files"
TP_FILES_DIR.mkdir(exist_ok=True)

SUBMISSIONS_DIR = DATA_DIR / "submissions"
SUBMISSIONS_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
PORT = 9050

ALLOWED_EXTENSIONS = {
    ".pdf", ".ipynb", ".py", ".md", ".txt", ".csv",
    ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".html", ".json", ".xml", ".yaml", ".yml",
    ".zip", ".tar", ".gz", ".docx", ".xlsx", ".pptx",
}

SUBMISSION_EXTENSIONS = {".py", ".ipynb"}

SECRET_KEY = os.getenv("SECRET_KEY", "ege-secret-key-change-in-production-2026")
PROFESSOR_CODE = os.getenv("PROFESSOR_CODE", "prof2026")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ege_admin:ege_master1_2026@127.0.0.1:5432/ege_master1")
