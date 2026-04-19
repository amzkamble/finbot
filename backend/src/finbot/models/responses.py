"""Pydantic models for API response bodies."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Auth ────────────────────────────────────────────────────────────────────


class UserResponse(BaseModel):
    """Public-facing user information."""

    id: str
    username: str
    role: str


class LoginResponse(BaseModel):
    """Token + user info returned after successful login."""

    token: str
    user: UserResponse


# ── Chat ────────────────────────────────────────────────────────────────────


class SourceInfo(BaseModel):
    """A single source citation from the retrieval step."""

    document: str
    page: int = 1
    section: str = "Untitled Section"
    collection: str = "general"
    chunk_type: str = "text"


class RouteInfo(BaseModel):
    """Semantic routing decision details."""

    name: str
    confidence: float = 0.0
    was_rbac_filtered: bool = False
    original_route: str | None = None
    collections_searched: list[str] = Field(default_factory=list)


class InputGuardInfo(BaseModel):
    """Summary of input guardrail results."""

    pii_scrubbed: bool = False
    off_topic_score: float = 0.0
    injection_detected: bool = False
    rate_limit_remaining: int | None = None


class OutputGuardInfo(BaseModel):
    """Summary of output guardrail results."""

    grounding_score: float = 1.0
    grounding_warning: bool = False
    leakage_detected: bool = False
    citations_valid: bool = True
    citations_auto_added: bool = False


class GuardrailInfo(BaseModel):
    """Combined guardrail reporting for both input and output."""

    input: InputGuardInfo = Field(default_factory=InputGuardInfo)
    output: OutputGuardInfo = Field(default_factory=OutputGuardInfo)


class ChatResponse(BaseModel):
    """Full response from the /api/chat endpoint."""

    answer: str
    sources: list[SourceInfo] = Field(default_factory=list)
    route: RouteInfo = Field(default_factory=lambda: RouteInfo(name="unknown"))
    guardrails: GuardrailInfo = Field(default_factory=GuardrailInfo)
    blocked: bool = False
    blocked_reason: str | None = None
    metadata: dict = Field(default_factory=dict)


# ── Admin ───────────────────────────────────────────────────────────────────


class DocumentInfo(BaseModel):
    """Metadata for an ingested document."""

    filename: str
    collection: str
    chunk_count: int = 0
    access_roles: list[str] = Field(default_factory=list)


class StatsResponse(BaseModel):
    """System-wide statistics for the admin dashboard."""

    total_documents: int = 0
    total_chunks: int = 0
    chunks_by_collection: dict[str, int] = Field(default_factory=dict)
    chunks_by_type: dict[str, int] = Field(default_factory=dict)
    total_users: int = 0
    users_by_role: dict[str, int] = Field(default_factory=dict)
