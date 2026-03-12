"""Dependency injection helpers for FastAPI.

Use these with `Depends()` in route functions to obtain
configured clients and settings.
"""

from __future__ import annotations

from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from core.config import Settings
from domain.repositories import InMemoryRepository


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


# Repository singletons keyed by entity name
_repositories: dict[str, object] = {}


def get_repository(entity_name: str, storage_mode: str = "memory"):
    """Factory that returns a repository for the given entity.

    In 'memory' mode, returns an InMemoryRepository (pre-seeded on first call).
    In 'azure' mode, extend with CosmosRepository / BlobRepository as needed.
    """
    key = f"{entity_name}:{storage_mode}"
    if key not in _repositories:
        if storage_mode == "azure":
            # Placeholder for Azure SDK repositories
            _repositories[key] = InMemoryRepository()
        else:
            repo = InMemoryRepository()
            # Auto-seed demo data on first access
            try:
                from domain.seed_data import get_seed_data
                for item in get_seed_data(entity_name):
                    repo.create(item["id"], item)
            except (ImportError, KeyError):
                pass
            _repositories[key] = repo
    return _repositories[key]


def get_keyvault_client() -> SecretClient:
    """Dependency that yields an authenticated SecretClient."""
    settings = get_settings()
    credential = DefaultAzureCredential(
        managed_identity_client_id=settings.azure_client_id or None
    )
    vault_uri = settings.key_vault_uri
    if not vault_uri and settings.key_vault_name:
        vault_uri = f"https://{settings.key_vault_name}.vault.azure.net"
    if not vault_uri:
        raise ValueError("KEY_VAULT_URI or KEY_VAULT_NAME must be set")
    return SecretClient(vault_url=vault_uri, credential=credential)


def get_blob_service() -> BlobServiceClient:
    """Dependency that yields an authenticated BlobServiceClient."""
    from azure.storage.blob import BlobServiceClient

    settings = get_settings()
    credential = DefaultAzureCredential(
        managed_identity_client_id=settings.azure_client_id or None
    )
    if not settings.storage_account_url:
        raise ValueError("STORAGE_ACCOUNT_URL not configured")
    return BlobServiceClient(
        account_url=settings.storage_account_url, credential=credential
    )
