"""Business service layer.

Put domain logic here, not in routers.  Services are framework-agnostic
and can be tested independently of FastAPI.
"""

from __future__ import annotations

import uuid


class ItemService:
    """Example domain service -- replace with real business logic."""

    def __init__(self, project_name: str = "enterprise-grade-real-time") -> None:
        self.project_name = project_name
        # In production: inject a repository / data-access object here.

    def list_items(self) -> list[dict]:
        """Return a list of items (stub -- wire to a real data store)."""
        return [
            {
                "id": "sample-001",
                "name": "Example Item",
                "description": "Replace this stub with your data store query.",
                "project": self.project_name,
            }
        ]

    def create_item(self, name: str, description: str = "") -> dict:
        """Create and return a new item (stub -- wire to a real data store)."""
        return {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": description,
            "project": self.project_name,
        }
