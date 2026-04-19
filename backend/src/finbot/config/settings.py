"""Centralized application configuration using Pydantic BaseSettings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── RBAC Mapping ────────────────────────────────────────────────────────────
# Maps each document collection (folder) to the roles that may access it.

FOLDER_RBAC_MAP: dict[str, list[str]] = {
    "general": [
        "employee",
        "finance_analyst",
        "engineer",
        "marketing_specialist",
        "executive",
        "hr_representative",
    ],
    "finance": ["finance_analyst", "executive"],
    "engineering": ["engineer", "executive"],
    "marketing": ["marketing_specialist", "executive"],
    "hr": ["hr_representative", "executive"],
}

ALL_ROLES: list[str] = [
    "employee",
    "finance_analyst",
    "engineer",
    "marketing_specialist",
    "executive",
    "hr_representative",
]

ALL_COLLECTIONS: list[str] = list(FOLDER_RBAC_MAP.keys())

SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".docx", ".md", ".csv", ".pptx"}


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM & Embeddings ────────────────────────────────────────────────
    openai_api_key: str = ""
    groq_api_key: str = ""
    llm_model: str = "llama-3.1-8b-instant"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ── Qdrant ──────────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "finbot_docs"

    # ── JWT ──────────────────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 480

    # ── Rate Limiting ───────────────────────────────────────────────────
    rate_limit_per_minute: int = 20
    rate_limit_per_hour: int = 100
    rate_limit_per_day: int = 500

    # ── Guardrails ──────────────────────────────────────────────────────
    grounding_threshold: float = 0.7
    min_citations: int = 1
    enable_llm_injection_check: bool = True
    enable_off_topic_check: bool = True

    # ── Semantic Router ─────────────────────────────────────────────────
    router_encoder: str = "openai"
    router_score_threshold: float = 0.3

    # ── Application ─────────────────────────────────────────────────────
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    data_dir: str = "../../data"

    # ── Derived helpers ─────────────────────────────────────────────────
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).resolve()

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper


# ── Singleton accessor ──────────────────────────────────────────────────────

_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
