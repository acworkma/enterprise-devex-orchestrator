"""Seed data -- generic demo records."""

from __future__ import annotations

_SEED: dict[str, list[dict]] = {
    "item": [
        {"id": "item-001", "name": "Example Widget", "description": "A sample product item", "status": "active", "project": "demo", "created_at": "2024-03-15T08:00:00Z"},
        {"id": "item-002", "name": "Test Service", "description": "A sample service offering", "status": "active", "project": "demo", "created_at": "2024-03-15T09:00:00Z"},
        {"id": "item-003", "name": "Draft Report", "description": "Quarterly financial summary", "status": "draft", "project": "demo", "created_at": "2024-03-15T10:00:00Z"},
        {"id": "item-004", "name": "Archived Task", "description": "Completed migration task", "status": "archived", "project": "demo", "created_at": "2024-03-14T14:00:00Z"},
        {"id": "item-005", "name": "Pending Review", "description": "Code review for feature branch", "status": "pending", "project": "demo", "created_at": "2024-03-15T11:00:00Z"},
    ],
}


def get_seed_data(entity_name: str) -> list[dict]:
    """Return seed records for the given entity type."""
    return _SEED.get(entity_name, [])
