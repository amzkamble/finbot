"""Custom exception classes for the FinBot application."""

from __future__ import annotations


class FinBotError(Exception):
    """Base exception for all FinBot errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ── Auth / RBAC ─────────────────────────────────────────────────────────────


class AuthenticationError(FinBotError):
    """Raised when authentication fails (invalid credentials, expired token)."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class RBACAccessDenied(FinBotError):
    """Raised when a user tries to access a resource outside their role."""

    def __init__(self, role: str, collection: str) -> None:
        super().__init__(
            f"Role '{role}' is not permitted to access collection '{collection}'",
            status_code=403,
        )
        self.role = role
        self.collection = collection


# ── Guardrails ──────────────────────────────────────────────────────────────


class GuardrailTriggered(FinBotError):
    """Raised when an input or output guardrail blocks the request."""

    def __init__(self, guard_name: str, reason: str) -> None:
        super().__init__(
            f"Guardrail '{guard_name}' triggered: {reason}",
            status_code=422,
        )
        self.guard_name = guard_name
        self.reason = reason


class RateLimitExceeded(FinBotError):
    """Raised when a user exceeds the configured rate limit."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            f"Rate limit exceeded. Please retry after {retry_after_seconds} seconds.",
            status_code=429,
        )
        self.retry_after_seconds = retry_after_seconds


# ── Ingestion ───────────────────────────────────────────────────────────────


class UnsupportedFormatError(FinBotError):
    """Raised when a document has an unsupported file extension."""

    def __init__(self, extension: str) -> None:
        super().__init__(
            f"Unsupported document format: '{extension}'",
            status_code=400,
        )
        self.extension = extension


class ConversionError(FinBotError):
    """Raised when Docling fails to convert a document."""

    def __init__(self, file_path: str, reason: str) -> None:
        super().__init__(
            f"Failed to convert '{file_path}': {reason}",
            status_code=500,
        )
        self.file_path = file_path
        self.reason = reason


# ── Routing ─────────────────────────────────────────────────────────────────


class RoutingError(FinBotError):
    """Raised when the semantic router fails to classify a query."""

    def __init__(self, message: str = "Query routing failed") -> None:
        super().__init__(message, status_code=500)
