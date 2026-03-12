"""Business service layer.

Put domain logic here, not in routers.  Services are framework-agnostic
and can be tested independently of FastAPI.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.repositories import BaseRepository


class ItemService:
    """Generic CRUD domain service with repository-backed persistence."""

    def __init__(self, project_name: str = "agent365", repo: BaseRepository | None = None) -> None:
        self.project_name = project_name
        self.repo = repo

    def list_items(self) -> list[dict]:
        """Return all items from the repository."""
        if self.repo:
            return self.repo.list_all()
        return [
            {
                "id": "sample-001",
                "name": "Example Item",
                "description": "Replace this stub with your data store query.",
                "project": self.project_name,
            }
        ]

    def create_item(self, name: str, description: str = "") -> dict:
        """Create and return a new item."""
        item = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": description,
            "project": self.project_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.repo:
            self.repo.create(item["id"], item)
        return item

    def get_item(self, item_id: str) -> dict | None:
        """Get a single item by ID."""
        if self.repo:
            return self.repo.get(item_id)
        return None

    def update_item(self, item_id: str, name: str | None = None, description: str | None = None) -> dict | None:
        """Update an existing item."""
        if not self.repo:
            return None
        item = self.repo.get(item_id)
        if not item:
            return None
        if name is not None:
            item["name"] = name
        if description is not None:
            item["description"] = description
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.repo.update(item_id, item)
        return item

    def delete_item(self, item_id: str) -> bool:
        """Delete an item by ID."""
        if self.repo:
            return self.repo.delete(item_id)
        return False
