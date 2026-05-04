from fastapi import Request


class AuthRedirectException(Exception):
    """Raised by auth dependencies to trigger a redirect to login."""
    def __init__(self, redirect_url: str = "/login"):
        self.redirect_url = redirect_url


def get_current_user(request: Request) -> dict | None:
    """Return current user from session, or None if not logged in."""
    return request.session.get("user")


def require_student(request: Request) -> dict:
    """Dependency: require a logged-in student."""
    user = request.session.get("user")
    if not user or user.get("role") != "student":
        raise AuthRedirectException(f"/login?next={request.url.path}")
    return user


def require_professor(request: Request) -> dict:
    """Dependency: require a logged-in professor."""
    user = request.session.get("user")
    if not user or user.get("role") != "professor":
        raise AuthRedirectException(f"/login?next={request.url.path}")
    return user


def require_any_user(request: Request) -> dict:
    """Dependency: require any logged-in user (student or professor)."""
    user = request.session.get("user")
    if not user:
        raise AuthRedirectException(f"/login?next={request.url.path}")
    return user
