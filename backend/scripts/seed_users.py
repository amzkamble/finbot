"""Seed demo users — useful for fresh installations."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from finbot.auth.models import DEMO_USERS
from finbot.auth.rbac import get_accessible_collections, get_role_description


def main() -> None:
    print("=" * 60)
    print("  FinBot Demo Users")
    print("=" * 60)

    for user in DEMO_USERS:
        collections = get_accessible_collections(user.role)
        desc = get_role_description(user.role)
        print(f"\n  👤 {user.username}")
        print(f"     Password : {user.password}")
        print(f"     Role     : {user.role}")
        print(f"     Access   : {', '.join(collections)}")
        print(f"     {desc}")

    print("\n" + "=" * 60)
    print("  These users are available in-memory — no seeding needed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
