"""Configuration management for Enterprise DevEx Orchestrator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv


# Orchestrator version
__version__ = "1.3.0"

# Supported LLM providers
SUPPORTED_PROVIDERS = ["azure_openai", "openai", "anthropic", "copilot_sdk", "template-only"]

# Supported models per provider
SUPPORTED_MODELS: dict[str, list[str]] = {
    "azure_openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-35-turbo"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"],
    "anthropic": ["claude-opus-4-20250514", "claude-sonnet-4-20250514", "claude-sonnet-3-5-20241022", "claude-haiku-3-5-20241022"],
    "copilot_sdk": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "template-only": [],
}

# Provider display names
PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "azure_openai": "Azure OpenAI",
    "openai": "OpenAI",
    "anthropic": "Anthropic (Claude)",
    "copilot_sdk": "GitHub Copilot SDK",
    "template-only": "Template-Only (no LLM)",
}


def _load_env() -> None:
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


_load_env()


def _resolve_provider() -> str:
    """Resolve LLM provider from env var or auto-detect from available credentials."""
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit and explicit in SUPPORTED_PROVIDERS:
        return explicit

    # Auto-detect from available credentials
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        return "azure_openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GITHUB_TOKEN"):
        return "copilot_sdk"
    return "template-only"


def _resolve_model(provider: str) -> str:
    """Resolve the model to use. Explicit LLM_MODEL env var takes priority."""
    explicit = os.getenv("LLM_MODEL", "").strip()
    if explicit:
        return explicit

    # Provider-specific defaults
    defaults: dict[str, str] = {
        "azure_openai": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        "openai": "gpt-4o",
        "anthropic": "claude-opus-4-20250514",
        "copilot_sdk": "gpt-4o",
        "template-only": "none",
    }
    return defaults.get(provider, "gpt-4o")


@dataclass(frozen=True)
class AzureConfig:
    """Azure-specific configuration."""

    subscription_id: str = field(default_factory=lambda: os.getenv("AZURE_SUBSCRIPTION_ID", ""))
    resource_group: str = field(
        default_factory=lambda: os.getenv("AZURE_RESOURCE_GROUP", "rg-enterprise-devex-orchestrator-dev")
    )
    location: str = field(default_factory=lambda: os.getenv("AZURE_LOCATION", "eastus2"))


@dataclass(frozen=True)
class CopilotConfig:
    """GitHub Copilot SDK configuration."""

    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))


@dataclass(frozen=True)
class LLMConfig:
    """LLM backend configuration -- supports Azure OpenAI, OpenAI, Anthropic (Claude), and GitHub Copilot SDK."""

    # Provider selection (auto-detected if not set)
    provider: str = field(default_factory=_resolve_provider)
    model: str = ""  # Resolved after provider

    # Azure OpenAI
    azure_openai_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    azure_openai_api_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    azure_openai_deployment: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"))

    # OpenAI
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_org_id: str = field(default_factory=lambda: os.getenv("OPENAI_ORG_ID", ""))

    # Anthropic (Claude)
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # Common
    temperature: float = 0.0  # Deterministic output

    def __post_init__(self) -> None:
        # Resolve model after provider is known (frozen dataclass workaround)
        if not self.model:
            object.__setattr__(self, "model", _resolve_model(self.provider))

    @property
    def provider_display_name(self) -> str:
        return PROVIDER_DISPLAY_NAMES.get(self.provider, self.provider)

    @property
    def is_template_only(self) -> bool:
        return self.provider == "template-only"


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
