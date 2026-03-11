"""Application configuration via pydantic-settings.

Environment variables are automatically loaded.  Values can be
overridden with a .env file during local development.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centralised configuration -- reads from environment variables."""

    app_name: str = Field(default="enterprise-grade-real-time", description="Application name")
    version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(default="dev", description="Runtime environment")
    port: int = Field(default=8000, description="HTTP listen port")

    # Azure integration
    azure_client_id: str = Field(default="", description="Managed identity client ID")
    key_vault_uri: str = Field(default="", description="Key Vault URI")
    key_vault_name: str = Field(default="", description="Key Vault name (fallback)")

    model_config = {"env_file": ".env", "extra": "ignore"}
