"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from finbot.auth.jwt_handler import create_access_token
from finbot.auth.models import get_user_by_username
from finbot.auth.rbac import get_accessible_collections, get_role_description
from finbot.models.requests import LoginRequest
from finbot.models.responses import LoginResponse, UserResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """Authenticate a user and return a JWT token."""
    user = get_user_by_username(body.username)
    if user is None or user.password != body.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(
        data={
            "sub": user.id,
            "username": user.username,
            "role": user.role,
        }
    )

    return LoginResponse(
        token=token,
        user=UserResponse(id=user.id, username=user.username, role=user.role),
    )


@router.get("/me", response_model=dict)
async def get_me(
    authorization: str = "",
) -> dict:
    """Return the current user's info from the token."""
    from fastapi import Header

    from finbot.api.deps import get_current_user

    # This will be called via the dependency injection in practice
    # For now, we provide a simple inline version
    from finbot.auth.jwt_handler import decode_token

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)

    from finbot.auth.models import get_user_by_id

    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    accessible = get_accessible_collections(user.role)

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "role_description": get_role_description(user.role),
        "accessible_collections": accessible,
    }
