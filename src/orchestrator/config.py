"""Configuration management for Enterprise DevEx Orchestrator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


_load_env()


@dataclass(frozen=True)
class AzureConfig:
    """Azure-specific configuration."""

    subscription_id: str = field(
        default_factory=lambda: os.getenv("AZURE_SUBSCRIPTION_ID", "e47370c7-8804-46b9-86f9-a96f5e950535")
    )
    resource_group: str = field(default_factory=lambda: os.getenv("AZURE_RESOURCE_GROUP", "rg-devex-orchestrator"))
    location: str = field(default_factory=lambda: os.getenv("AZURE_LOCATION", "eastus2"))


@dataclass(frozen=True)
class CopilotConfig:
    """GitHub Copilot SDK configuration."""

    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))


@dataclass(frozen=True)
class LLMConfig:
    """LLM backend configuration."""

    azure_openai_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    azure_openai_api_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    azure_openai_deployment: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"))
    temperature: float = 0.0  # Deterministic output


@dataclass(frozen=True)
class AppConfig:
    """Root application configuration."""

    azure: AzureConfig = field(default_factory=AzureConfig)
    copilot: CopilotConfig = field(default_factory=CopilotConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_format: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "json"))
    output_base: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "out")))

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]


def get_config() -> AppConfig:
    """Return the singleton application configuration."""
    return AppConfig()
