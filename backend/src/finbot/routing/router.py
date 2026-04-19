"""Semantic query router with RBAC-aware classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from semantic_router.routers import SemanticRouter
from semantic_router.encoders import HuggingFaceEncoder

from finbot.auth.rbac import get_accessible_collections
from finbot.config.settings import get_settings
from finbot.routing.routes import ALL_ROUTES
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RouteResult:
    """Result of classifying a query through the semantic router."""

    route_name: str
    target_collections: list[str] = field(default_factory=list)
    confidence: float = 0.0
    was_rbac_filtered: bool = False
    original_route: str | None = None


class QueryRouter:
    """
    Classify user queries into department routes using ``semantic-router``
    and enforce RBAC by filtering routes the user cannot access.
    """

    def __init__(self) -> None:
        settings = get_settings()

        # Use the same embedding model as retrieval to guarantee consistency
        encoder = HuggingFaceEncoder(name="sentence-transformers/all-MiniLM-L6-v2")

        # Build the route layer
        self._layer = SemanticRouter(encoder=encoder)
        
        # Explicitly add routes to ensure the index is populated and ready
        if ALL_ROUTES:
            self._layer.add(ALL_ROUTES)
            
        self._routes_by_name = {r.name: r for r in ALL_ROUTES}
        logger.info("QueryRouter initialised with %d routes and ready index", len(ALL_ROUTES))

    # ── Public API ──────────────────────────────────────────────────────

    def classify(self, query: str, user_role: str) -> RouteResult:
        """
        Classify *query* into a route and apply RBAC filtering.
        """
        # 1. Run the semantic router
        route_choice = self._layer(query)
        
        # IMPORTANT: Log this as INFO so you can see it in your terminal
        if route_choice:
            score = getattr(route_choice, "score", getattr(route_choice, "similarity_score", 0.0))
            logger.info("ROUTER DEBUG | Query: '%s' | Matched: %s | Score: %.4f", query, route_choice.name, score)
        else:
            logger.info("ROUTER DEBUG | Query: '%s' | No match found.", query)

        # 2. Handle no-match
        if route_choice is None or route_choice.name is None:
            logger.info("Query '%s' did not match any route (fallback)", query)
            return RouteResult(
                route_name="cross_department_route",
                target_collections=get_accessible_collections(user_role),
                confidence=0.0,
                was_rbac_filtered=False,
            )

        matched_name = route_choice.name
        route_meta = self._routes_by_name.get(matched_name)
        
        # Get confidence score safely
        confidence = getattr(route_choice, "score", getattr(route_choice, "similarity_score", 0.0))

        # 3. RBAC enforcement
        required_roles = []
        if route_meta and hasattr(route_meta, "metadata"):
            required_roles = route_meta.metadata.get("required_roles", [])

        if user_role in required_roles:
            target_collection = "cross_department"
            if route_meta and hasattr(route_meta, "metadata"):
                target_collection = route_meta.metadata.get("target_collection", "cross_department")

            collections = [target_collection] if target_collection != "cross_department" else get_accessible_collections(user_role)

            logger.info("MATCH | route=%s score=%.2f -> collections=%s", matched_name, confidence, collections)
            return RouteResult(
                route_name=matched_name,
                target_collections=collections,
                confidence=confidence,
                was_rbac_filtered=False,
            )
        else:
            accessible = get_accessible_collections(user_role)
            logger.warning("RBAC | user=%s role=%s blocked route=%s -> fallback to %s", "user", user_role, matched_name, accessible)
            return RouteResult(
                route_name="cross_department_route",
                target_collections=accessible,
                confidence=confidence,
                was_rbac_filtered=True,
                original_route=matched_name,
            )

    def get_route_info(self) -> list[dict[str, Any]]:
        """Return metadata about all configured routes (for admin/debug)."""
        info = []
        for route in ALL_ROUTES:
            info.append(
                {
                    "name": route.name,
                    "utterance_count": len(route.utterances),
                    "target_collection": route.metadata.get("target_collection", ""),
                    "required_roles": route.metadata.get("required_roles", []),
                    "description": route.metadata.get("description", ""),
                }
            )
        return info
