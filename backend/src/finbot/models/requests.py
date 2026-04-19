"""Pydantic models for API request bodies."""

from __future__ import annotations

from pydantic import BaseModel, Field

from finbot.config.settings import ALL_COLLECTIONS, ALL_ROLES


class LoginRequest(BaseModel):
    """Credentials for authentication."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


class ChatRequest(BaseModel):
    """User chat message."""

    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=100)


class UpdateRoleRequest(BaseModel):
    """Admin request to change a user's role."""

    role: str = Field(..., description="New role to assign")

    def validate_role(self) -> bool:
        return self.role in ALL_ROLES


class IngestRequest(BaseModel):
    """Admin request to trigger document ingestion."""

    collection: str = Field(
        default="all",
        description="Collection to ingest, or 'all' for every collection",
    )

    def validate_collection(self) -> bool:
        return self.collection == "all" or self.collection in ALL_COLLECTIONS
