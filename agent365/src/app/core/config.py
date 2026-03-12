"""Application configuration via pydantic-settings.

Environment variables are automatically loaded.  Values can be
overridden with a .env file during local development.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centralised configuration -- reads from environment variables."""

    app_name: str = Field(default="agent365", description="Application name")
    version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(default="dev", description="Runtime environment")
    port: int = Field(default=8000, description="HTTP listen port")

    # Storage mode: "memory" for in-memory (demo/dev), "azure" for Azure services
    storage_mode: str = Field(default="memory", description="Storage backend: memory or azure")

    # Azure integration
    azure_client_id: str = Field(default="", description="Managed identity client ID")
    key_vault_uri: str = Field(default="", description="Key Vault URI")
    key_vault_name: str = Field(default="", description="Key Vault name (fallback)")
    storage_account_url: str = Field(default="", description="Azure Storage account URL")
    cosmos_endpoint: str = Field(default="", description="Cosmos DB endpoint")
    cosmos_database: str = Field(default="", description="Cosmos DB database name")

    model_config = {"env_file": ".env", "extra": "ignore"}
