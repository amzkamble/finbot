"""User data models and demo user definitions."""

from __future__ import annotations

from pydantic import BaseModel


class User(BaseModel):
    """Internal user representation."""

    id: str
    username: str
    password: str  # plain-text for demo only; hash in production
    role: str


# ── Demo Users ──────────────────────────────────────────────────────────────
# One user per role for demonstration purposes.

DEMO_USERS: list[User] = [
    User(id="u1", username="john_employee", password="demo123", role="employee"),
    User(id="u2", username="sarah_finance", password="demo123", role="finance_analyst"),
    User(id="u3", username="mike_engineer", password="demo123", role="engineer"),
    User(id="u4", username="lisa_marketing", password="demo123", role="marketing_specialist"),
    User(id="u5", username="alex_executive", password="demo123", role="executive"),
    User(id="u6", username="emma_hr", password="demo123", role="hr_representative"),
]

# Quick look-up by username
_USER_MAP: dict[str, User] = {u.username: u for u in DEMO_USERS}
_USER_MAP_BY_ID: dict[str, User] = {u.id: u for u in DEMO_USERS}


def get_user_by_username(username: str) -> User | None:
    """Return the demo user matching *username*, or ``None``."""
    return _USER_MAP.get(username)


def get_user_by_id(user_id: str) -> User | None:
    """Return the demo user matching *user_id*, or ``None``."""
    return _USER_MAP_BY_ID.get(user_id)


def get_all_users() -> list[User]:
    """Return every demo user."""
    return list(DEMO_USERS)


def update_user_role(user_id: str, new_role: str) -> User | None:
    """Update a demo user's role in-memory. Returns the updated user or None."""
    user = _USER_MAP_BY_ID.get(user_id)
    if user is None:
        return None
    user.role = new_role
    return user
