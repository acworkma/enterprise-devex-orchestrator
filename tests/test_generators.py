"""Tests for generators -- Bicep, CI/CD, App, Docs."""

from __future__ import annotations

from src.orchestrator.generators.app_generator import AppGenerator
from src.orchestrator.generators.bicep_generator import BicepGenerator
from src.orchestrator.generators.cicd_generator import CICDGenerator
from src.orchestrator.generators.docs_generator import DocsGenerator
from src.orchestrator.intent_schema import (
    AppType,
    AuthModel,
    CICDRequirements,
    ComplianceFramework,
    ComponentSpec,
    DataStore,
    GovernanceCheck,
    GovernanceReport,
    IntentSpec,
    NetworkingModel,
    ObservabilityRequirements,
    PlanOutput,
    SecurityRequirements,
    ThreatEntry,
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


def _make_plan() -> PlanOutput:
    return PlanOutput(
        title="Test Architecture Plan",
        summary="Test architecture plan",
        components=[
            ComponentSpec(
                name="container-app",
                azure_service="Microsoft.App/containerApps",
                purpose="Run application",
                bicep_module="container-app.bicep",
                security_controls=["Managed Identity"],
            ),
            ComponentSpec(
                name="key-vault",
                azure_service="Microsoft.KeyVault/vaults",
                purpose="Secret management",
                bicep_module="keyvault.bicep",
                security_controls=["RBAC"],
            ),
        ],
        decisions=[],
        threat_model=[
            ThreatEntry(
                id="T-001",
                category="Spoofing",
                description="Identity spoofing",
                mitigation="Managed Identity",
                residual_risk="Low",
            ),
        ],
        diagram_mermaid="graph TD; A-->B;",
    )


class TestBicepGenerator:
    """Test Bicep template generation."""

    def setup_method(self) -> None:
        self.gen = BicepGenerator()

    def test_generate_returns_files(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert len(files) > 0

    def test_generates_main_bicep(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "infra/bicep/main.bicep" in files

    def test_generates_parameter_file(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "infra/bicep/parameters/dev.parameters.json" in files

    def test_main_bicep_has_target_scope(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        main = files["infra/bicep/main.bicep"]
        assert "targetScope" in main

    def test_main_bicep_has_modules(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        main = files["infra/bicep/main.bicep"]
        assert "module" in main

    def test_generates_keyvault_module(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "infra/bicep/modules/keyvault.bicep" in files

    def test_keyvault_has_rbac(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        kv = files["infra/bicep/modules/keyvault.bicep"]
        assert "enableRbacAuthorization" in kv

    def test_keyvault_has_soft_delete(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        kv = files["infra/bicep/modules/keyvault.bicep"]
        assert "enableSoftDelete" in kv

    def test_generates_container_app_module(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "infra/bicep/modules/container-app.bicep" in files

    def test_container_app_has_health_probes(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        ca = files["infra/bicep/modules/container-app.bicep"]
        assert "probes" in ca or "healthProbe" in ca or "/health" in ca

    def test_generates_managed_identity(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "infra/bicep/modules/managed-identity.bicep" in files

    def test_generates_storage_when_blob(self) -> None:
        spec = _make_spec(data_stores=[DataStore.BLOB_STORAGE])
        files = self.gen.generate(spec, _make_plan())
        assert "infra/bicep/modules/storage.bicep" in files

    def test_storage_has_private_access(self) -> None:
        spec = _make_spec(data_stores=[DataStore.BLOB_STORAGE])
        files = self.gen.generate(spec, _make_plan())
        storage = files["infra/bicep/modules/storage.bicep"]
        assert "allowBlobPublicAccess" in storage


class TestCICDGenerator:
    """Test CI/CD workflow generation."""

    def setup_method(self) -> None:
        self.gen = CICDGenerator()

    def test_generate_returns_files(self) -> None:
        files = self.gen.generate(_make_spec())
        assert len(files) > 0

    def test_generates_validate_workflow(self) -> None:
        files = self.gen.generate(_make_spec())
        assert ".github/workflows/validate.yml" in files

    def test_generates_deploy_workflow(self) -> None:
        files = self.gen.generate(_make_spec())
        assert ".github/workflows/deploy.yml" in files

    def test_generates_dependabot(self) -> None:
        files = self.gen.generate(_make_spec())
        assert ".github/dependabot.yml" in files

    def test_generates_codeql(self) -> None:
        files = self.gen.generate(_make_spec())
        assert ".github/workflows/codeql.yml" in files

    def test_deploy_uses_oidc(self) -> None:
        files = self.gen.generate(_make_spec())
        deploy = files[".github/workflows/deploy.yml"]
        assert "id-token" in deploy

    def test_validate_has_tests(self) -> None:
        files = self.gen.generate(_make_spec())
        validate = files[".github/workflows/validate.yml"]
        assert "pytest" in validate or "test" in validate.lower()


class TestAppGenerator:
    """Test application scaffold generation."""

    def setup_method(self) -> None:
        self.gen = AppGenerator()

    def test_generate_returns_files(self) -> None:
        files = self.gen.generate(_make_spec())
        assert len(files) > 0

    def test_generates_main_py(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "src/app/main.py" in files

    def test_generates_dockerfile(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "src/app/Dockerfile" in files

    def test_generates_requirements(self) -> None:
        files = self.gen.generate(_make_spec())
        assert "src/app/requirements.txt" in files

    def test_main_has_health_endpoint(self) -> None:
        files = self.gen.generate(_make_spec())
        main = files["src/app/main.py"]
        assert "/health" in main

    def test_main_has_html_root_response(self) -> None:
        files = self.gen.generate(_make_spec())
        main = files["src/app/main.py"]
        assert "HTMLResponse" in main
        assert "<!DOCTYPE html>" in main

    def test_main_supports_key_vault_uri(self) -> None:
        files = self.gen.generate(_make_spec())
        main = files["src/app/main.py"]
        assert "KEY_VAULT_URI" in main
        assert "KEY_VAULT_NAME" in main

    def test_dockerfile_has_nonroot_user(self) -> None:
        files = self.gen.generate(_make_spec())
        dockerfile = files["src/app/Dockerfile"]
        assert "USER" in dockerfile

    def test_dockerfile_has_healthcheck(self) -> None:
        files = self.gen.generate(_make_spec())
        dockerfile = files["src/app/Dockerfile"]
        assert "HEALTHCHECK" in dockerfile


class TestDocsGenerator:
    """Test documentation generation."""

    def setup_method(self) -> None:
        self.gen = DocsGenerator()

    def test_generate_returns_files(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert len(files) > 0

    def test_generates_plan_md(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "docs/plan.md" in files

    def test_generates_security_md(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "docs/security.md" in files

    def test_generates_deployment_md(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "docs/deployment.md" in files

    def test_generates_rai_notes(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "docs/rai-notes.md" in files

    def test_generates_demo_script(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "docs/demo-script.md" in files

    def test_generates_scorecard(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        assert "docs/scorecard.md" in files

    def test_plan_md_includes_components(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        plan = files["docs/plan.md"]
        assert "container-app" in plan

    def test_security_md_includes_threat_model(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan())
        sec = files["docs/security.md"]
        assert "STRIDE" in sec

    def test_governance_report_generated_when_provided(self) -> None:
        gov = GovernanceReport(
            status="PASS",
            summary="All checks passed",
            checks=[
                GovernanceCheck(
                    check_id="GOV-001",
                    name="Test",
                    passed=True,
                    severity="warning",
                    details="OK",
                )
            ],
            recommendations=[],
        )
        files = self.gen.generate(_make_spec(), _make_plan(), gov)
        assert "docs/governance-report.md" in files

    def test_governance_report_not_generated_when_none(self) -> None:
        files = self.gen.generate(_make_spec(), _make_plan(), None)
        assert "docs/governance-report.md" not in files
