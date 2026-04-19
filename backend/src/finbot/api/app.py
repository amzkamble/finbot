"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finbot.api.middleware import RequestLoggingMiddleware
from finbot.config.settings import get_settings
from finbot.utils.exceptions import (
    AuthenticationError,
    FinBotError,
    GuardrailTriggered,
    RateLimitExceeded,
    RBACAccessDenied,
)
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


def _register_exception_handlers(app: FastAPI) -> None:
    """Map custom exceptions to proper HTTP responses."""

    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": exc.message})

    @app.exception_handler(RBACAccessDenied)
    async def rbac_error_handler(request: Request, exc: RBACAccessDenied) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": exc.message})

    @app.exception_handler(GuardrailTriggered)
    async def guardrail_error_handler(request: Request, exc: GuardrailTriggered) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.message, "guard_name": exc.guard_name},
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": exc.message, "retry_after": exc.retry_after_seconds},
        )

    @app.exception_handler(FinBotError)
    async def finbot_error_handler(request: Request, exc: FinBotError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="FinBot API",
        description="RAG + RBAC Intelligent Finance Chatbot",
        version="0.1.0",
    )

    # ── CORS ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom middleware ───────────────────────────────────────────────
    app.add_middleware(RequestLoggingMiddleware)

    # ── Exception handlers ──────────────────────────────────────────────
    _register_exception_handlers(app)

    # ── Routes ──────────────────────────────────────────────────────────
    from finbot.api.routes.admin_routes import router as admin_router
    from finbot.api.routes.auth_routes import router as auth_router
    from finbot.api.routes.chat_routes import router as chat_router

    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
    app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])

    # ── Health check ────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        return {"status": "healthy", "version": "0.1.0"}

    logger.info("FinBot API created successfully")
    return app


# ── Application instance ────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("finbot.api.app:app", host="0.0.0.0", port=8000, reload=True)
