"""Tests for IntentParserAgent -- rule-based parsing."""

from __future__ import annotations

from src.orchestrator.agents.intent_parser import IntentParserAgent
from src.orchestrator.config import AppConfig, AzureConfig, CopilotConfig, LLMConfig
from src.orchestrator.intent_schema import AppType, DataStore


def _make_config() -> AppConfig:
    """Create a test config with no real LLM backend."""
    return AppConfig(
        azure=AzureConfig(
            subscription_id="00000000-0000-0000-0000-000000000000",
            resource_group="rg-test",
            location="eastus2",
        ),
        copilot=CopilotConfig(github_token=""),
        llm=LLMConfig(
            azure_openai_endpoint="",
            azure_openai_api_key="",
            azure_openai_deployment="gpt-4o",
        ),
        log_level="WARNING",
    )


class TestIntentParser:
    """Test intent parsing with rule-based fallback."""

    def setup_method(self) -> None:
        self.parser = IntentParserAgent(_make_config())

    def test_parse_returns_intent_spec(self) -> None:
        spec = self.parser.parse("Build a secure REST API with blob storage and cosmos DB")
        assert spec.project_name is not None
        assert len(spec.project_name) > 0

    def test_detects_api_app_type(self) -> None:
        spec = self.parser.parse("Build a REST API microservice")
        assert spec.app_type == AppType.API

    def test_detects_web_app_type(self) -> None:
        spec = self.parser.parse("Build a web application with dashboard")
        assert spec.app_type == AppType.WEB

    def test_detects_worker_app_type(self) -> None:
        spec = self.parser.parse("Build a background worker that processes queue messages")
        assert spec.app_type == AppType.WORKER

    def test_detects_blob_storage(self) -> None:
        spec = self.parser.parse("Build an API with blob storage for file uploads")
        assert DataStore.BLOB_STORAGE in spec.data_stores

    def test_detects_cosmos_db(self) -> None:
        spec = self.parser.parse("Build a service with Cosmos DB for metadata")
        assert DataStore.COSMOS_DB in spec.data_stores

    def test_detects_sql(self) -> None:
        spec = self.parser.parse("Build an app with SQL database for users")
        assert DataStore.SQL in spec.data_stores

    def test_detects_redis(self) -> None:
        spec = self.parser.parse("Build an API with Redis cache for sessions")
        assert DataStore.REDIS in spec.data_stores
        # Redis should also be detected via 'cache' keyword

    def test_default_security_settings(self) -> None:
        spec = self.parser.parse("Build a simple API")
        assert spec.security.encryption_at_rest is True
        assert spec.security.encryption_in_transit is True
        assert spec.security.secret_management is True

    def test_hipaa_compliance_detected(self) -> None:
        spec = self.parser.parse("Build a HIPAA compliant healthcare API")
        from src.orchestrator.intent_schema import ComplianceFramework

        assert spec.security.compliance_framework == ComplianceFramework.HIPAA_GUIDANCE

    def test_soc2_compliance_detected(self) -> None:
        spec = self.parser.parse("Build a SOC2 compliant service")
        from src.orchestrator.intent_schema import ComplianceFramework

        assert spec.security.compliance_framework == ComplianceFramework.SOC2_GUIDANCE

    def test_raw_intent_preserved(self) -> None:
        intent = "Build a magical unicorn service"
        spec = self.parser.parse(intent)
        assert spec.raw_intent == intent

    def test_confidence_is_valid(self) -> None:
        spec = self.parser.parse("Build an API")
        assert 0.0 <= spec.confidence <= 1.0

    def test_azure_region_from_config(self) -> None:
        spec = self.parser.parse("Build an API")
        assert spec.azure_region == "eastus2"

    def test_resource_group_from_config(self) -> None:
        spec = self.parser.parse("Build an API")
        assert spec.resource_group_name == "rg-test"

    def test_environment_from_config(self) -> None:
        spec = self.parser.parse("Build an API")
        assert spec.environment == "dev"

    def test_project_name_extracted(self) -> None:
        spec = self.parser.parse("Build a document-processor service")
        # Should extract a reasonable project name
        assert spec.project_name is not None
        assert " " not in spec.project_name  # Should be slug-friendly

    def test_complex_intent(self) -> None:
        spec = self.parser.parse(
            "Build a secure document processing API that stores files in blob storage, "
            "metadata in Cosmos DB, uses managed identity, secrets in Key Vault, "
            "with CI/CD pipelines and HIPAA compliance"
        )
        assert spec.app_type == AppType.API
        assert DataStore.BLOB_STORAGE in spec.data_stores
        assert DataStore.COSMOS_DB in spec.data_stores
        from src.orchestrator.intent_schema import ComplianceFramework

        assert spec.security.compliance_framework == ComplianceFramework.HIPAA_GUIDANCE
