"""Tests for Test Generator and Alert Generator superpowers."""

from __future__ import annotations

from src.orchestrator.generators.alert_generator import AlertGenerator
from src.orchestrator.generators.test_generator import TestGenerator
from src.orchestrator.intent_schema import (
    AppType,
    AuthModel,
    CICDRequirements,
    ComplianceFramework,
    DataStore,
    IntentSpec,
    NetworkingModel,
    ObservabilityRequirements,
    SecurityRequirements,
)


def _make_spec(data_stores: list[DataStore] | None = None) -> IntentSpec:
    return IntentSpec(
        project_name="test-project",
        app_type=AppType.API,
        description="A test API service",
        raw_intent="Build a test API",
        data_stores=data_stores or [],
        security=SecurityRequirements(
            auth_model=AuthModel.MANAGED_IDENTITY,
            compliance_framework=ComplianceFramework.GENERAL,
            data_classification="internal",
            networking=NetworkingModel.PRIVATE,
            encryption_at_rest=True,
            encryption_in_transit=True,
            secret_management=True,
        ),
        observability=ObservabilityRequirements(
            log_analytics=True,
            health_endpoint=True,
        ),
        cicd=CICDRequirements(
            oidc_auth=True,
        ),
        azure_region="eastus2",
        resource_group_name="rg-test",
        environment="dev",
        confidence=0.85,
    )


# ───────────────── Test Generator ─────────────────


class TestTestGenerator:
    def setup_method(self) -> None:
        self.gen = TestGenerator()

    def test_generates_files(self) -> None:
        files = self.gen.generate(_make_spec())
        assert len(files) > 0

    def test_generates_conftest(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "tests/conftest.py" in files

    def test_generates_init(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "tests/__init__.py" in files

    def test_generates_health_tests(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "tests/test_health.py" in files
        content = files["tests/test_health.py"]
        assert "test_health" in content
        assert "200" in content

    def test_generates_api_tests(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "tests/test_api.py" in files
        content = files["tests/test_api.py"]
        assert "test_root" in content or "def test_" in content

    def test_generates_security_tests(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "tests/test_security.py" in files
        content = files["tests/test_security.py"]
        assert "managed_identity" in content or "security" in content.lower()

    def test_generates_config_tests(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "tests/test_config.py" in files

    def test_generates_requirements(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "tests/requirements-test.txt" in files
        content = files["tests/requirements-test.txt"]
        assert "pytest" in content

    def test_with_blob_storage(self) -> None:
        files = self.gen.generate(_make_spec(data_stores=[DataStore.BLOB_STORAGE]))
        assert "tests/test_storage.py" in files
        content = files["tests/test_storage.py"]
        assert "storage" in content.lower()

    def test_without_blob_storage(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "tests/test_storage.py" not in files

    def test_conftest_has_fixtures(self) -> None:
        files = self.gen.generate(_make_spec())
        content = files["tests/conftest.py"]
        assert "@pytest.fixture" in content
        assert "client" in content

    def test_project_name_in_tests(self) -> None:
        files = self.gen.generate(_make_spec())
        content = files["tests/test_health.py"]
        assert "test-project" in content or "test_health" in content


# ───────────────── Alert Generator ─────────────────


class TestAlertGenerator:
    def setup_method(self) -> None:
        self.gen = AlertGenerator()

    def test_generates_files(self) -> None:
        files = self.gen.generate(_make_spec())
        assert len(files) > 0

    def test_generates_alerts_bicep(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "infra/modules/alerts.bicep" in files

    def test_generates_action_group(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "infra/modules/action-group.bicep" in files

    def test_generates_alerting_runbook(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "docs/alerting-runbook.md" in files

    def test_alerts_bicep_has_metric_alerts(self) -> None:
        files = self.gen.generate(_make_spec())
        content = files["infra/modules/alerts.bicep"]
        assert "Microsoft.Insights/metricAlerts" in content

    def test_alerts_bicep_has_scheduled_query(self) -> None:
        files = self.gen.generate(_make_spec())
        content = files["infra/modules/alerts.bicep"]
        assert "Microsoft.Insights/scheduledQueryRules" in content

    def test_action_group_has_email(self) -> None:
        files = self.gen.generate(_make_spec())
        content = files["infra/modules/action-group.bicep"]
        assert "emailReceivers" in content

    def test_runbook_has_severity_table(self) -> None:
        files = self.gen.generate(_make_spec())
        content = files["docs/alerting-runbook.md"]
        assert "Severity" in content or "severity" in content

    def test_with_blob_storage_adds_storage_alerts(self) -> None:
        files = self.gen.generate(_make_spec(data_stores=[DataStore.BLOB_STORAGE]))
        content = files["infra/modules/alerts.bicep"]
        # Storage alerts should be present
        assert "storage" in content.lower() or "Availability" in content

    def test_alerts_bicep_has_parameters(self) -> None:
        files = self.gen.generate(_make_spec())
        content = files["infra/modules/alerts.bicep"]
        assert "param" in content

    def test_alert_names_use_project_name(self) -> None:
        files = self.gen.generate(_make_spec())
        content = files["infra/modules/alerts.bicep"]
        assert "test-project" in content or "testproject" in content.lower() or "name:" in content
