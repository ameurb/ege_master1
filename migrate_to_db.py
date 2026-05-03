"""Migrate existing JSON data to PostgreSQL database."""
import json
import os
import sys
from pathlib import Path

# Load env
from dotenv import load_dotenv
load_dotenv()

from app.database import get_db
from app.config import DATA_DIR, SUBMISSIONS_DIR

def migrate():
    print("Starting migration from JSON to PostgreSQL...")

    # 1. Settings
    settings_file = DATA_DIR / "settings.json"
    if settings_file.exists():
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
        with get_db() as cur:
            for key, value in settings.items():
                cur.execute(
                    "INSERT INTO settings (key, value) VALUES (%s, %s) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    (key, json.dumps(value)),
                )
        print(f"  Migrated settings: {list(settings.keys())}")

    # 2. Students
    students_file = DATA_DIR / "students.json"
    if students_file.exists():
        data = json.loads(students_file.read_text(encoding="utf-8"))
        students = data.get("students", [])
        with get_db() as cur:
            for s in students:
                cur.execute(
                    "INSERT INTO students (matricule, name, grp, team_id) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (matricule) DO NOTHING",
                    (s["matricule"], s["name"], s.get("group", ""), s.get("team_id", "")),
                )
        print(f"  Migrated {len(students)} students")

    # 3. TPs
    tps_file = DATA_DIR / "tps.json"
    if tps_file.exists():
        data = json.loads(tps_file.read_text(encoding="utf-8"))
        tps = data.get("tps", [])
        with get_db() as cur:
            for tp in tps:
                cur.execute(
                    "INSERT INTO tps (id, title, description, week, due_date, created_at, files, steps) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (
                        tp["id"], tp["title"], tp.get("description", ""),
                        tp.get("week", 1), tp.get("due_date", ""),
                        tp.get("created_at", "2026-01-01T00:00:00"),
                        json.dumps(tp.get("files", [])),
                        json.dumps(tp.get("steps", [])),
                    ),
                )
        print(f"  Migrated {len(tps)} TPs")

    # 4. Sessions
    sessions_file = DATA_DIR / "sessions.json"
    if sessions_file.exists():
        data = json.loads(sessions_file.read_text(encoding="utf-8"))
        session = data.get("active_session")
        if session and session.get("status") == "open":
            with get_db() as cur:
                cur.execute(
                    "INSERT INTO sessions (tp_id, started_at, started_by, status, pc_locks) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        session.get("tp_id", "all"),
                        session.get("started_at", "2026-01-01T00:00:00"),
                        session.get("started_by", "professor"),
                        session.get("status", "open"),
                        json.dumps(session.get("pc_locks", {})),
                    ),
                )
            print("  Migrated active session")
        else:
            print("  No active session to migrate")

    # 5. Attendance
    attendance_file = DATA_DIR / "attendance.json"
    if attendance_file.exists():
        data = json.loads(attendance_file.read_text(encoding="utf-8"))
        sessions = data.get("sessions", [])
        with get_db() as cur:
            for sess in sessions:
                cur.execute(
                    "INSERT INTO attendance_sessions (date, week, label, records) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (date) DO NOTHING",
                    (sess["date"], sess.get("week", 1), sess.get("label", ""), json.dumps(sess.get("records", {}))),
                )
        print(f"  Migrated {len(sessions)} attendance sessions")

    # 6. Grades
    grades_file = DATA_DIR / "grades.json"
    if grades_file.exists():
        data = json.loads(grades_file.read_text(encoding="utf-8"))
        grades = data.get("grades", {})
        count = 0
        with get_db() as cur:
            for tp_id, tp_grades in grades.items():
                for team_key, g in tp_grades.items():
                    cur.execute(
                        "INSERT INTO grades (tp_id, team_key, grade, max_grade, comment) "
                        "VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (tp_id, team_key) DO NOTHING",
                        (tp_id, team_key, g.get("grade", 0), g.get("max_grade", 20), g.get("comment", "")),
                    )
                    count += 1
        print(f"  Migrated {count} grades")

    # 7. Submissions (from file system meta.json files)
    if SUBMISSIONS_DIR.exists():
        count = 0
        for tp_dir in SUBMISSIONS_DIR.iterdir():
            if tp_dir.is_dir():
                tp_id = tp_dir.name
                for team_dir in tp_dir.iterdir():
                    if team_dir.is_dir():
                        meta_file = team_dir / "meta.json"
                        if meta_file.exists():
                            meta = json.loads(meta_file.read_text(encoding="utf-8"))
                            with get_db() as cur:
                                cur.execute(
                                    "INSERT INTO submissions (tp_id, team_key, submitted_at, ip_address, pc_id, team_members, files) "
                                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                                    "ON CONFLICT (tp_id, team_key) DO NOTHING",
                                    (
                                        tp_id, team_dir.name,
                                        meta.get("submitted_at", "2026-01-01T00:00:00"),
                                        meta.get("ip_address", ""),
                                        meta.get("pc_id", ""),
                                        json.dumps(meta.get("team_members", [])),
                                        json.dumps(meta.get("files", [])),
                                    ),
                                )
                            count += 1
        print(f"  Migrated {count} submissions")

    print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
