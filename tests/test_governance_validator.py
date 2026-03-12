"""Tests for GovernanceReviewerAgent -- policy validation."""

from __future__ import annotations

from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent
from src.orchestrator.config import AppConfig, AzureConfig, CopilotConfig, LLMConfig
from src.orchestrator.intent_schema import (
    AppType,
    AuthModel,
    CICDRequirements,
    ComplianceFramework,
    ComponentSpec,
    IntentSpec,
    NetworkingModel,
    ObservabilityRequirements,
    PlanOutput,
    SecurityRequirements,
    ThreatEntry,
)


def _make_config() -> AppConfig:
    return AppConfig(
        azure=AzureConfig(
            subscription_id="00000000-0000-0000-0000-000000000000",
            resource_group="rg-test",
            location="eastus2",
        ),
        copilot=CopilotConfig(github_token=""),
        llm=LLMConfig(
            provider="template-only",
            model="none",
            azure_openai_endpoint="",
            azure_openai_api_key="",
            azure_openai_deployment="gpt-4o",
        ),
        log_level="WARNING",
    )


def _make_spec() -> IntentSpec:
    return IntentSpec(
        project_name="test-project",
        app_type=AppType.API,
        description="Test API",
        raw_intent="Build a test API",
        data_stores=[],
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
        confidence=0.8,
    )


def _make_plan(include_all: bool = True) -> PlanOutput:
    components = [
        ComponentSpec(
            name="container-app",
            azure_service="Microsoft.App/containerApps",
            purpose="Run application",
            bicep_module="container-app.bicep",
            security_controls=["Managed Identity", "Private ingress"],
        ),
    ]
    if include_all:
        components.extend(
            [
                ComponentSpec(
                    name="key-vault",
                    azure_service="Microsoft.KeyVault/vaults",
                    purpose="Secret management",
                    bicep_module="keyvault.bicep",
                    security_controls=["RBAC", "Soft delete"],
                ),
                ComponentSpec(
                    name="log-analytics",
                    azure_service="Microsoft.OperationalInsights/workspaces",
                    purpose="Centralized logging",
                    bicep_module="log-analytics.bicep",
                    security_controls=[],
                ),
                ComponentSpec(
                    name="managed-identity",
                    azure_service="Microsoft.ManagedIdentity/userAssignedIdentities",
                    purpose="Authentication",
                    bicep_module="managed-identity.bicep",
                    security_controls=["RBAC"],
                ),
                ComponentSpec(
                    name="container-registry",
                    azure_service="Microsoft.ContainerRegistry/registries",
                    purpose="Container images",
                    bicep_module="container-registry.bicep",
                    security_controls=["AcrPull role"],
                ),
            ]
        )

    return PlanOutput(
        title="Test Architecture Plan",
        summary="Test architecture plan",
        components=components,
        decisions=[],
        threat_model=[
            ThreatEntry(
                id="T-001",
                category="Spoofing",
                description="Test threat",
                mitigation="Test mitigation",
                residual_risk="Low",
            ),
            ThreatEntry(
                id="T-002",
                category="Tampering",
                description="Test threat 2",
                mitigation="Test mitigation 2",
                residual_risk="Low",
            ),
            ThreatEntry(
                id="T-003",
                category="Denial of Service",
                description="Test threat 3",
                mitigation="Test mitigation 3",
                residual_risk="Medium",
            ),
            ThreatEntry(
                id="T-004",
                category="Information Disclosure",
                description="Test threat 4",
                mitigation="Test mitigation 4",
                residual_risk="Low",
            ),
        ],
        diagram_mermaid="graph TD; A-->B;",
    )


class TestGovernanceReviewer:
    """Test governance review logic."""

    def setup_method(self) -> None:
        self.reviewer = GovernanceReviewerAgent(_make_config())

    def test_validate_plan_full_components_passes(self) -> None:
        spec = _make_spec()
        plan = _make_plan(include_all=True)
        report = self.reviewer.validate_plan(spec, plan)
        assert report.status in ("PASS", "PASS_WITH_WARNINGS")

    def test_validate_plan_missing_components_fails(self) -> None:
        spec = _make_spec()
        plan = _make_plan(include_all=False)
        report = self.reviewer.validate_plan(spec, plan)
        # Missing key-vault, log-analytics, managed-identity should cause failures
        failed = [c for c in report.checks if not c.passed]
        assert len(failed) > 0

    def test_validate_plan_has_checks(self) -> None:
        spec = _make_spec()
        plan = _make_plan()
        report = self.reviewer.validate_plan(spec, plan)
        assert len(report.checks) > 0

    def test_validate_plan_has_summary(self) -> None:
        spec = _make_spec()
        plan = _make_plan()
        report = self.reviewer.validate_plan(spec, plan)
        assert report.summary is not None
        assert len(report.summary) > 0

    def test_validate_bicep_clean(self) -> None:
        bicep_files = {
            "infra/bicep/main.bicep": """
targetScope = 'resourceGroup'
param environment string
param location string = resourceGroup().location

module diagnostics 'modules/diagnostics.bicep' = {
  name: 'diagnosticSettings'
}
""",
            "infra/bicep/modules/keyvault.bicep": """
param keyVaultName string
param enableRbacAuthorization bool = true
param enableSoftDelete bool = true
param enablePurgeProtection bool = true
""",
            "infra/bicep/modules/managed-identity.bicep": """
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'mi-app'
  location: location
  tags: { managedBy: 'UserAssigned' }
}
""",
        }
        report = self.reviewer.validate_bicep(bicep_files)
        # Clean files should not have critical failures
        assert report.status in ("PASS", "PASS_WITH_WARNINGS")

    def test_validate_bicep_detects_admin_password(self) -> None:
        bicep_files = {
            "main.bicep": """
param adminPassword string = 'Password123!'
""",
        }
        report = self.reviewer.validate_bicep(bicep_files)
        failed = [c for c in report.checks if not c.passed]
        assert len(failed) > 0

    def test_validate_bicep_detects_public_access(self) -> None:
        bicep_files = {
            "storage.bicep": """
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  properties: {
    allowBlobPublicAccess: true
  }
}
""",
        }
        report = self.reviewer.validate_bicep(bicep_files)
        failed = [c for c in report.checks if not c.passed]
        assert len(failed) > 0

    def test_governance_report_status_types(self) -> None:
        spec = _make_spec()
        plan = _make_plan()
        report = self.reviewer.validate_plan(spec, plan)
        assert report.status in ("PASS", "FAIL", "PASS_WITH_WARNINGS")


class TestGovernanceReviewerEdgeCases:
    """Test governance reviewer edge cases."""

    def setup_method(self) -> None:
        self.reviewer = GovernanceReviewerAgent(_make_config())

    def test_empty_bicep_files(self) -> None:
        report = self.reviewer.validate_bicep({})
        assert report is not None
        assert report.status in ("PASS", "FAIL", "PASS_WITH_WARNINGS")

    def test_minimal_threat_model(self) -> None:
        spec = _make_spec()
        plan = _make_plan()
        plan.threat_model = [
            ThreatEntry(
                id="T-001",
                category="Spoofing",
                description="Minimal",
                mitigation="None",
                residual_risk="High",
            )
        ]
        report = self.reviewer.validate_plan(spec, plan)
        # Should warn about insufficient threat coverage
        assert report.status in ("FAIL", "PASS_WITH_WARNINGS")
