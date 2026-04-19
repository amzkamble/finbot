"""Admin panel endpoints (executive-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from finbot.api.deps import get_vector_store, require_executive
from finbot.auth.models import User, get_all_users, update_user_role
from finbot.config.settings import ALL_COLLECTIONS, ALL_ROLES
from finbot.models.requests import IngestRequest, UpdateRoleRequest
from finbot.models.responses import DocumentInfo, StatsResponse, UserResponse
from finbot.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/users", response_model=list[UserResponse])
async def list_users(user: User = Depends(require_executive)) -> list[UserResponse]:
    """List all users and their roles."""
    return [
        UserResponse(id=u.id, username=u.username, role=u.role) for u in get_all_users()
    ]


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    user: User = Depends(require_executive),
) -> UserResponse:
    """Update a user's role."""
    if body.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {ALL_ROLES}")

    updated = update_user_role(user_id, body.role)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(id=updated.id, username=updated.username, role=updated.role)


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents(user: User = Depends(require_executive)) -> list[DocumentInfo]:
    """List all ingested documents grouped by collection."""
    vector_store = get_vector_store()
    if vector_store is None:
        return []

    from qdrant_client import models

    documents: list[DocumentInfo] = []
    seen: set[str] = set()

    for collection in ALL_COLLECTIONS:
        try:
            records = vector_store.scroll_all(
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="collection",
                            match=models.MatchValue(value=collection),
                        )
                    ]
                ),
                limit=1000,
            )

            # Group by source_document
            doc_chunks: dict[str, int] = {}
            doc_roles: dict[str, list[str]] = {}
            for record in records:
                payload = record.payload or {}
                doc_name = payload.get("source_document", "Unknown")
                doc_chunks[doc_name] = doc_chunks.get(doc_name, 0) + 1
                if doc_name not in doc_roles:
                    doc_roles[doc_name] = payload.get("access_roles", [])

            for doc_name, count in doc_chunks.items():
                key = f"{collection}:{doc_name}"
                if key not in seen:
                    seen.add(key)
                    documents.append(
                        DocumentInfo(
                            filename=doc_name,
                            collection=collection,
                            chunk_count=count,
                            access_roles=doc_roles.get(doc_name, []),
                        )
                    )
        except Exception as exc:
            logger.warning("Failed to list docs for collection '%s': %s", collection, exc)

    return documents


@router.get("/stats", response_model=StatsResponse)
async def get_stats(user: User = Depends(require_executive)) -> StatsResponse:
    """Return system-wide statistics."""
    vector_store = get_vector_store()

    chunks_by_collection: dict[str, int] = {}
    chunks_by_type: dict[str, int] = {}
    total_chunks = 0

    if vector_store:
        from qdrant_client import models

        for collection in ALL_COLLECTIONS:
            try:
                count = vector_store.count(
                    query_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="collection",
                                match=models.MatchValue(value=collection),
                            )
                        ]
                    )
                )
                chunks_by_collection[collection] = count
                total_chunks += count
            except Exception:
                chunks_by_collection[collection] = 0

        for chunk_type in ["text", "table", "heading", "code"]:
            try:
                count = vector_store.count(
                    query_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="chunk_type",
                                match=models.MatchValue(value=chunk_type),
                            )
                        ]
                    )
                )
                chunks_by_type[chunk_type] = count
            except Exception:
                chunks_by_type[chunk_type] = 0

    all_users = get_all_users()
    users_by_role: dict[str, int] = {}
    for u in all_users:
        users_by_role[u.role] = users_by_role.get(u.role, 0) + 1

    # Count unique documents from chunks
    total_documents = sum(
        len(set()) for _ in ALL_COLLECTIONS
    )  # placeholder — will be replaced by actual doc counting

    return StatsResponse(
        total_documents=len(chunks_by_collection),
        total_chunks=total_chunks,
        chunks_by_collection=chunks_by_collection,
        chunks_by_type=chunks_by_type,
        total_users=len(all_users),
        users_by_role=users_by_role,
    )


@router.post("/ingest")
async def trigger_ingest(
    body: IngestRequest,
    user: User = Depends(require_executive),
) -> dict:
    """Trigger document ingestion for a collection (placeholder)."""
    if not body.validate_collection():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection. Must be one of: {ALL_COLLECTIONS} or 'all'",
        )

    # In a production system this would launch a background task
    return {
        "status": "accepted",
        "collection": body.collection,
        "message": f"Ingestion job queued for collection '{body.collection}'. "
                   f"Use the CLI for full ingestion: python -m scripts.ingest --collections {body.collection}",
    }
