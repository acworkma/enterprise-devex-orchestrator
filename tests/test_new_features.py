"""Tests for new features -- multi-language, multi-compute, cost estimation, intent detection."""

from __future__ import annotations

from src.orchestrator.agents.intent_parser import IntentParserAgent
from src.orchestrator.config import AppConfig, AzureConfig, CopilotConfig, LLMConfig
from src.orchestrator.generators.app_generator import AppGenerator
from src.orchestrator.generators.bicep_generator import BicepGenerator
from src.orchestrator.generators.cost_estimator import CostEstimate, CostEstimator
from src.orchestrator.intent_schema import (
    LANGUAGE_FRAMEWORKS,
    AppType,
    AuthModel,
    CICDRequirements,
    ComplianceFramework,
    ComponentSpec,
    ComputeTarget,
    DataStore,
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
            azure_openai_endpoint="",
            azure_openai_api_key="",
            azure_openai_deployment="gpt-4o",
        ),
        log_level="WARNING",
    )


def _make_spec(
    language: str = "python",
    compute_target: ComputeTarget = ComputeTarget.CONTAINER_APPS,
    data_stores: list[DataStore] | None = None,
) -> IntentSpec:
    return IntentSpec(
        project_name="test-project",
        app_type=AppType.API,
        description="A test API service",
        raw_intent="Build a test API",
        language=language,
        framework=LANGUAGE_FRAMEWORKS.get(language, "fastapi"),
        compute_target=compute_target,
        data_stores=data_stores or [],
        security=SecurityRequirements(
            auth_model=AuthModel.MANAGED_IDENTITY,
            compliance_framework=ComplianceFramework.GENERAL,
            data_classification="internal",
            networking=NetworkingModel.PRIVATE,
        ),
        observability=ObservabilityRequirements(log_analytics=True, health_endpoint=True),
        cicd=CICDRequirements(oidc_auth=True),
        azure_region="eastus2",
        resource_group_name="rg-test",
        environment="dev",
        confidence=0.85,
    )


def _make_plan() -> PlanOutput:
    return PlanOutput(
        title="Test Architecture Plan",
        summary="Test plan",
        components=[
            ComponentSpec(
                name="compute",
                azure_service="Microsoft.App/containerApps",
                purpose="Run application",
                bicep_module="container-app.bicep",
                security_controls=["Managed Identity"],
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


# ===================================================================
# Multi-Language App Generator
# ===================================================================


class TestMultiLanguageAppGenerator:
    """Test that AppGenerator routes correctly by language."""

    def setup_method(self) -> None:
        self.gen = AppGenerator()

    # -- Python (default) --------------------------------------------

    def test_python_generates_main_py(self) -> None:
        files = self.gen.generate(_make_spec(language="python"))
        assert "src/app/main.py" in files

    def test_python_generates_requirements(self) -> None:
        files = self.gen.generate(_make_spec(language="python"))
        assert "src/app/requirements.txt" in files

    def test_python_main_has_fastapi(self) -> None:
        files = self.gen.generate(_make_spec(language="python"))
        assert "FastAPI" in files["src/app/main.py"]

    def test_python_dockerfile_has_python(self) -> None:
        files = self.gen.generate(_make_spec(language="python"))
        assert "python:" in files["src/app/Dockerfile"].lower()

    # -- Node.js -----------------------------------------------------

    def test_node_generates_index_js(self) -> None:
        files = self.gen.generate(_make_spec(language="node"))
        assert "src/app/index.js" in files

    def test_node_generates_package_json(self) -> None:
        files = self.gen.generate(_make_spec(language="node"))
        assert "src/app/package.json" in files

    def test_node_main_has_express(self) -> None:
        files = self.gen.generate(_make_spec(language="node"))
        assert "express" in files["src/app/index.js"]

    def test_node_has_health_endpoint(self) -> None:
        files = self.gen.generate(_make_spec(language="node"))
        assert "/health" in files["src/app/index.js"]

    def test_node_root_has_html_landing_page(self) -> None:
        files = self.gen.generate(_make_spec(language="node"))
        index_js = files["src/app/index.js"]
        assert "<!DOCTYPE html>" in index_js
        assert "res.send(html)" in index_js

    def test_node_supports_key_vault_uri(self) -> None:
        files = self.gen.generate(_make_spec(language="node"))
        index_js = files["src/app/index.js"]
        assert "KEY_VAULT_URI" in index_js
        assert "KEY_VAULT_NAME" in index_js

    def test_node_dockerfile_has_node(self) -> None:
        files = self.gen.generate(_make_spec(language="node"))
        assert "node:" in files["src/app/Dockerfile"].lower()

    # -- .NET --------------------------------------------------------

    def test_dotnet_generates_program_cs(self) -> None:
        files = self.gen.generate(_make_spec(language="dotnet"))
        assert "src/app/Program.cs" in files

    def test_dotnet_generates_csproj(self) -> None:
        files = self.gen.generate(_make_spec(language="dotnet"))
        csproj_files = [f for f in files if f.endswith(".csproj")]
        assert len(csproj_files) == 1

    def test_dotnet_has_health_endpoint(self) -> None:
        files = self.gen.generate(_make_spec(language="dotnet"))
        assert "/health" in files["src/app/Program.cs"]

    def test_dotnet_root_has_html_landing_page(self) -> None:
        files = self.gen.generate(_make_spec(language="dotnet"))
        program_cs = files["src/app/Program.cs"]
        assert "<!DOCTYPE html>" in program_cs
        assert 'Results.Content(html, "text/html")' in program_cs

    def test_dotnet_supports_key_vault_uri(self) -> None:
        files = self.gen.generate(_make_spec(language="dotnet"))
        program_cs = files["src/app/Program.cs"]
        assert "KEY_VAULT_URI" in program_cs
        assert "KEY_VAULT_NAME" in program_cs

    def test_dotnet_dockerfile_has_dotnet(self) -> None:
        files = self.gen.generate(_make_spec(language="dotnet"))
        assert "dotnet" in files["src/app/Dockerfile"].lower()

    def test_dotnet_generates_appsettings(self) -> None:
        files = self.gen.generate(_make_spec(language="dotnet"))
        assert "src/app/appsettings.json" in files


# ===================================================================
# Multi-Compute Target Bicep Generator
# ===================================================================


class TestMultiComputeBicepGenerator:
    """Test Bicep generator routes correctly by compute target."""

    def setup_method(self) -> None:
        self.gen = BicepGenerator()

    # -- Container Apps (default) ------------------------------------

    def test_container_apps_generates_ca_module(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.CONTAINER_APPS)
        files = self.gen.generate(spec, _make_plan())
        assert "infra/bicep/modules/container-app.bicep" in files

    def test_container_apps_generates_acr(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.CONTAINER_APPS)
        files = self.gen.generate(spec, _make_plan())
        assert "infra/bicep/modules/container-registry.bicep" in files

    def test_container_apps_main_mentions_container(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.CONTAINER_APPS)
        files = self.gen.generate(spec, _make_plan())
        assert "container" in files["infra/bicep/main.bicep"].lower()

    # -- App Service -------------------------------------------------

    def test_app_service_generates_module(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.APP_SERVICE)
        files = self.gen.generate(spec, _make_plan())
        assert "infra/bicep/modules/app-service.bicep" in files

    def test_app_service_no_container_registry(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.APP_SERVICE)
        files = self.gen.generate(spec, _make_plan())
        assert "infra/bicep/modules/container-registry.bicep" not in files

    def test_app_service_module_has_plan(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.APP_SERVICE)
        files = self.gen.generate(spec, _make_plan())
        bicep = files["infra/bicep/modules/app-service.bicep"]
        assert "serverfarms" in bicep

    def test_app_service_main_mentions_target(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.APP_SERVICE)
        files = self.gen.generate(spec, _make_plan())
        assert "app_service" in files["infra/bicep/main.bicep"]

    # -- Functions ---------------------------------------------------

    def test_functions_generates_module(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.FUNCTIONS)
        files = self.gen.generate(spec, _make_plan())
        assert "infra/bicep/modules/function-app.bicep" in files

    def test_functions_no_container_registry(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.FUNCTIONS)
        files = self.gen.generate(spec, _make_plan())
        assert "infra/bicep/modules/container-registry.bicep" not in files

    def test_functions_module_has_consumption(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.FUNCTIONS)
        files = self.gen.generate(spec, _make_plan())
        bicep = files["infra/bicep/modules/function-app.bicep"]
        assert "Dynamic" in bicep or "Y1" in bicep

    def test_functions_main_mentions_target(self) -> None:
        spec = _make_spec(compute_target=ComputeTarget.FUNCTIONS)
        files = self.gen.generate(spec, _make_plan())
        assert "functions" in files["infra/bicep/main.bicep"].lower()

    # -- Common modules always present -------------------------------

    def test_always_has_keyvault(self) -> None:
        for target in ComputeTarget:
            spec = _make_spec(compute_target=target)
            files = self.gen.generate(spec, _make_plan())
            assert "infra/bicep/modules/keyvault.bicep" in files, f"Missing keyvault for {target}"

    def test_always_has_log_analytics(self) -> None:
        for target in ComputeTarget:
            spec = _make_spec(compute_target=target)
            files = self.gen.generate(spec, _make_plan())
            assert "infra/bicep/modules/log-analytics.bicep" in files, f"Missing log analytics for {target}"

    def test_always_has_managed_identity(self) -> None:
        for target in ComputeTarget:
            spec = _make_spec(compute_target=target)
            files = self.gen.generate(spec, _make_plan())
            assert "infra/bicep/modules/managed-identity.bicep" in files, f"Missing identity for {target}"


# ===================================================================
# Cost Estimator
# ===================================================================


class TestCostEstimator:
    """Test cost estimation for different architectures."""

    def setup_method(self) -> None:
        self.est = CostEstimator()

    def test_returns_cost_estimate(self) -> None:
        result = self.est.estimate(_make_spec(), _make_plan())
        assert isinstance(result, CostEstimate)

    def test_has_items(self) -> None:
        result = self.est.estimate(_make_spec(), _make_plan())
        assert len(result.items) > 0

    def test_total_is_sum_of_items(self) -> None:
        result = self.est.estimate(_make_spec(), _make_plan())
        assert result.total_monthly == sum(i.monthly_usd for i in result.items)

    def test_container_apps_includes_acr(self) -> None:
        result = self.est.estimate(_make_spec(compute_target=ComputeTarget.CONTAINER_APPS), _make_plan())
        resources = [i.resource for i in result.items]
        assert "Container Registry" in resources

    def test_app_service_cheaper_than_container_apps(self) -> None:
        ca_cost = self.est.estimate(_make_spec(compute_target=ComputeTarget.CONTAINER_APPS), _make_plan()).total_monthly
        as_cost = self.est.estimate(_make_spec(compute_target=ComputeTarget.APP_SERVICE), _make_plan()).total_monthly
        assert as_cost < ca_cost

    def test_functions_cheapest(self) -> None:
        fn_cost = self.est.estimate(_make_spec(compute_target=ComputeTarget.FUNCTIONS), _make_plan()).total_monthly
        ca_cost = self.est.estimate(_make_spec(compute_target=ComputeTarget.CONTAINER_APPS), _make_plan()).total_monthly
        assert fn_cost < ca_cost

    def test_blob_storage_adds_cost(self) -> None:
        no_blob = self.est.estimate(_make_spec(data_stores=[]), _make_plan()).total_monthly
        with_blob = self.est.estimate(_make_spec(data_stores=[DataStore.BLOB_STORAGE]), _make_plan()).total_monthly
        assert with_blob > no_blob

    def test_multiple_data_stores_additive(self) -> None:
        one_store = self.est.estimate(_make_spec(data_stores=[DataStore.BLOB_STORAGE]), _make_plan()).total_monthly
        two_stores = self.est.estimate(
            _make_spec(data_stores=[DataStore.BLOB_STORAGE, DataStore.REDIS]), _make_plan()
        ).total_monthly
        assert two_stores > one_store

    def test_markdown_output(self) -> None:
        result = self.est.estimate(_make_spec(), _make_plan())
        md = result.to_markdown()
        assert "Estimated Monthly Cost" in md
        assert "$" in md

    def test_always_includes_core_infra(self) -> None:
        result = self.est.estimate(_make_spec(), _make_plan())
        resources = [i.resource for i in result.items]
        assert "Log Analytics" in resources
        assert "Key Vault" in resources
        assert "Managed Identity" in resources


# ===================================================================
# Intent Parser -- Language & Compute Detection
# ===================================================================


class TestIntentParserLanguageDetection:
    """Test that the rule-based parser detects language and compute target."""

    def setup_method(self) -> None:
        self.parser = IntentParserAgent(_make_config())

    # -- Language detection ------------------------------------------

    def test_detects_python_default(self) -> None:
        spec = self.parser.parse("Build a secure API with blob storage")
        assert spec.language == "python"

    def test_detects_node_from_nodejs(self) -> None:
        spec = self.parser.parse("Build a nodejs REST API with express")
        assert spec.language == "node"

    def test_detects_node_from_javascript(self) -> None:
        spec = self.parser.parse("Build a JavaScript API service")
        assert spec.language == "node"

    def test_detects_dotnet_from_csharp(self) -> None:
        spec = self.parser.parse("Build a csharp microservice with sql database")
        assert spec.language == "dotnet"

    def test_detects_dotnet_from_dotnet(self) -> None:
        spec = self.parser.parse("Build a dotnet API for data processing")
        assert spec.language == "dotnet"

    # -- Compute target detection ------------------------------------

    def test_defaults_to_container_apps(self) -> None:
        spec = self.parser.parse("Build a secure API with blob storage")
        assert spec.compute_target == ComputeTarget.CONTAINER_APPS

    def test_detects_app_service(self) -> None:
        spec = self.parser.parse("Build a web app using app service with SQL")
        assert spec.compute_target == ComputeTarget.APP_SERVICE

    def test_detects_functions_from_serverless(self) -> None:
        spec = self.parser.parse("Build a serverless event processor")
        assert spec.compute_target == ComputeTarget.FUNCTIONS

    def test_detects_functions_from_keyword(self) -> None:
        spec = self.parser.parse("Build an Azure function for image processing")
        assert spec.compute_target == ComputeTarget.FUNCTIONS

    # -- Framework follows language ----------------------------------

    def test_python_gets_fastapi(self) -> None:
        spec = self.parser.parse("Build a python API")
        assert spec.framework == "fastapi"

    def test_node_gets_express(self) -> None:
        spec = self.parser.parse("Build a nodejs API")
        assert spec.framework == "express"

    def test_dotnet_gets_aspnet(self) -> None:
        spec = self.parser.parse("Build a dotnet web service")
        assert spec.framework == "aspnet"


# ===================================================================
# Schema -- ComputeTarget and Language enums
# ===================================================================


class TestSchemaEnums:
    """Test the new enum types and mappings."""

    def test_compute_target_values(self) -> None:
        assert ComputeTarget.CONTAINER_APPS.value == "container_apps"
        assert ComputeTarget.APP_SERVICE.value == "app_service"
        assert ComputeTarget.FUNCTIONS.value == "functions"

    def test_language_framework_mapping(self) -> None:
        assert LANGUAGE_FRAMEWORKS["python"] == "fastapi"
        assert LANGUAGE_FRAMEWORKS["node"] == "express"
        assert LANGUAGE_FRAMEWORKS["dotnet"] == "aspnet"

    def test_intent_spec_defaults(self) -> None:
        spec = IntentSpec(
            project_name="test-defaults",
            description="Test defaults",
            raw_intent="test",
        )
        assert spec.language == "python"
        assert spec.framework == "fastapi"
        assert spec.compute_target == ComputeTarget.CONTAINER_APPS
