"""Role-Based Access Control enforcement logic."""

from __future__ import annotations

from finbot.config.settings import ALL_COLLECTIONS, FOLDER_RBAC_MAP
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


def get_accessible_collections(role: str) -> list[str]:
    """
    Return the list of collections a given role may access.

    Always includes ``"general"`` since every role has access to it.

    Parameters
    ----------
    role : str
        The user's role (e.g., ``"engineer"``, ``"executive"``).

    Returns
    -------
    list[str]
        Collection names the role is permitted to query.
    """
    accessible = [
        collection
        for collection, allowed_roles in FOLDER_RBAC_MAP.items()
        if role in allowed_roles
    ]

    # Guarantee "general" is always present
    if "general" not in accessible:
        accessible.insert(0, "general")

    logger.debug("Role '%s' → accessible collections: %s", role, accessible)
    return accessible


def check_access(role: str, collection: str) -> bool:
    """
    Check whether *role* is permitted to access *collection*.

    Parameters
    ----------
    role : str
        The user's role.
    collection : str
        The target collection name.

    Returns
    -------
    bool
        ``True`` if access is allowed.
    """
    allowed_roles = FOLDER_RBAC_MAP.get(collection, [])
    return role in allowed_roles


def get_role_description(role: str) -> str:
    """Return a human-friendly description for the role."""
    descriptions = {
        "employee": "General Employee — access to company-wide documents only",
        "finance_analyst": "Finance Analyst — access to general + finance documents",
        "engineer": "Engineer — access to general + engineering documents",
        "marketing_specialist": "Marketing Specialist — access to general + marketing documents",
        "executive": "Executive — full access to all departments",
        "hr_representative": "HR Representative — access to general + HR documents",
    }
    return descriptions.get(role, f"Unknown role: {role}")
