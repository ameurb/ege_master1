from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware

from app.config import UPLOAD_DIR, SECRET_KEY
from app.auth import AuthRedirectException
from app.routers import upload, files, students, tp, attendance, evaluation, course
from app.routers import auth as auth_router

app = FastAPI(title="EGE Document Sharing")

# Session middleware (signed cookie, 24h expiry)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400)


@app.middleware("http")
async def inject_user(request: Request, call_next):
    """Make request.state.user available to all templates."""
    request.state.user = request.session.get("user") if "session" in request.scope else None
    response = await call_next(request)
    return response


@app.exception_handler(AuthRedirectException)
async def auth_redirect_handler(request: Request, exc: AuthRedirectException):
    return RedirectResponse(url=exc.redirect_url, status_code=303)


# Static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

@app.get("/")
async def root():
    return RedirectResponse(url="/login", status_code=303)


# Routers
app.include_router(auth_router.router)
app.include_router(upload.router)
app.include_router(files.router)
app.include_router(students.router)
app.include_router(tp.router)
app.include_router(attendance.router)
app.include_router(evaluation.router)
app.include_router(course.router)
