from fastapi import Request

from ..models import User


def get_current_user(request: Request) -> User:
    """Retrieve current user from forwarded headers in request."""
    # X-Forwarded-User, X-Forwarded-Email, X-Forwarded-Preferred-Username and X-Forwarded-Groups
    user_id = request.headers.get("X-Forwarded-User", "anonymous")
    username = request.headers.get("X-Forwarded-Preferred-Username", "anonymous")
    email = request.headers.get("X-Forwarded-Email", "anonymous@gpf.fr")

    groups_str = request.headers.get("X-Forwarded-Groups")
    if groups_str is None:
        groups: list[str] = []
    else:
        groups = [g.strip() for g in groups_str.split(",") if g.strip()]

    return User(id=user_id, username=username, email=email, groups=groups)
