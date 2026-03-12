"""Repository pattern -- pluggable storage backends.

Switch between in-memory (demo/dev) and Azure SDK (production)
by setting the STORAGE_MODE environment variable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseRepository(ABC):
    """Abstract base for all repositories."""

    @abstractmethod
    def get(self, entity_id: str) -> dict | None: ...

    @abstractmethod
    def list_all(self) -> list[dict]: ...

    @abstractmethod
    def create(self, entity_id: str, data: dict) -> dict: ...

    @abstractmethod
    def update(self, entity_id: str, data: dict) -> dict | None: ...

    @abstractmethod
    def delete(self, entity_id: str) -> bool: ...


class InMemoryRepository(BaseRepository):
    """Dict-backed repository for demos and testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def get(self, entity_id: str) -> dict | None:
        return self._store.get(entity_id)

    def list_all(self) -> list[dict]:
        return list(self._store.values())

    def create(self, entity_id: str, data: dict) -> dict:
        self._store[entity_id] = data
        return data

    def update(self, entity_id: str, data: dict) -> dict | None:
        if entity_id not in self._store:
            return None
        self._store[entity_id] = data
        return data

    def delete(self, entity_id: str) -> bool:
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False
