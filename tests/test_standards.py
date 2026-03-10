"""Tests for enterprise standards -- Naming, Tagging, and Configuration."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.orchestrator.standards.config import (
    EnterpriseStandardsConfig,
    GovernanceConfig,
    NamingStandardsConfig,
    TaggingStandardsConfig,
)
from src.orchestrator.standards.naming import (
    REGION_ABBREVIATIONS,
    RESOURCE_CONSTRAINTS,
    NamingEngine,
    ResourceType,
)
from src.orchestrator.standards.tagging import (
    ALL_TAGS,
    OPTIONAL_TAGS,
    REQUIRED_TAGS,
    TaggingEngine,
)

# =====================================================================
# Naming Engine Tests
# =====================================================================


class TestNamingEngineBasics:
    """Test basic NamingEngine functionality."""

    def setup_method(self) -> None:
        self.engine = NamingEngine(workload="myapi", environment="dev", region="eastus2")

    def test_generate_key_vault_name(self) -> None:
        name = self.engine.generate(ResourceType.KEY_VAULT)
        assert name.startswith("kv")
        assert "myapi" in name
        assert "dev" in name

    def test_generate_storage_account_alphanumeric(self) -> None:
        name = self.engine.generate(ResourceType.STORAGE_ACCOUNT)
        # Storage accounts must be alphanumeric only
        assert name.isalnum()
        assert name.islower()

    def test_generate_container_registry_alphanumeric(self) -> None:
        name = self.engine.generate(ResourceType.CONTAINER_REGISTRY)
        assert name.isalnum()

    def test_generate_log_analytics(self) -> None:
        name = self.engine.generate(ResourceType.LOG_ANALYTICS)
        assert name.startswith("law-")
        assert "myapi" in name

    def test_generate_managed_identity(self) -> None:
        name = self.engine.generate(ResourceType.MANAGED_IDENTITY)
        assert name.startswith("id-")

    def test_generate_container_app(self) -> None:
        name = self.engine.generate(ResourceType.CONTAINER_APP)
        assert name.startswith("ca-")

    def test_generate_container_app_env(self) -> None:
        name = self.engine.generate(ResourceType.CONTAINER_APP_ENV)
        assert name.startswith("cae-")

    def test_generate_resource_group(self) -> None:
        name = self.engine.generate(ResourceType.RESOURCE_GROUP)
        assert name.startswith("rg-")

    def test_generate_with_suffix(self) -> None:
        name = self.engine.generate(ResourceType.KEY_VAULT, suffix="app")
        assert "app" in name

    def test_generate_all_returns_all_common_types(self) -> None:
        names = self.engine.generate_all()
        assert ResourceType.RESOURCE_GROUP in names
        assert ResourceType.KEY_VAULT in names
        assert ResourceType.LOG_ANALYTICS in names
        assert ResourceType.MANAGED_IDENTITY in names
        assert ResourceType.CONTAINER_REGISTRY in names
        assert ResourceType.CONTAINER_APP in names
        assert ResourceType.CONTAINER_APP_ENV in names
        assert ResourceType.STORAGE_ACCOUNT in names


class TestNamingEngineRegions:
    """Test region abbreviation logic."""

    def test_eastus2_abbreviation(self) -> None:
        engine = NamingEngine(workload="test", region="eastus2")
        assert engine._abbreviate_region("eastus2") == "eus2"

    def test_westeurope_abbreviation(self) -> None:
        engine = NamingEngine(workload="test", region="westeurope")
        assert engine._abbreviate_region("westeurope") == "weu"

    def test_unknown_region_truncates(self) -> None:
        engine = NamingEngine(workload="test", region="someregion")
        abbrev = engine._abbreviate_region("someregion")
        assert len(abbrev) == 4  # Falls back to first 4 chars

    def test_region_appears_in_name(self) -> None:
        engine = NamingEngine(workload="myapi", environment="dev", region="westus2")
        name = engine.generate(ResourceType.KEY_VAULT)
        assert "wus2" in name

    def test_all_documented_regions_have_abbreviations(self) -> None:
        assert len(REGION_ABBREVIATIONS) >= 30


class TestNamingEngineValidation:
    """Test name validation."""

    def test_valid_key_vault_name(self) -> None:
        engine = NamingEngine(workload="test", region="eastus2")
        errors = engine.validate_name("kv-test-dev-eus2", ResourceType.KEY_VAULT)
        assert len(errors) == 0

    def test_too_short_name(self) -> None:
        engine = NamingEngine(workload="test", region="eastus2")
        errors = engine.validate_name("kv", ResourceType.KEY_VAULT)
        assert any("too short" in e for e in errors)

    def test_too_long_storage_name(self) -> None:
        engine = NamingEngine(workload="test", region="eastus2")
        long_name = "a" * 25  # Max 24
        errors = engine.validate_name(long_name, ResourceType.STORAGE_ACCOUNT)
        assert any("too long" in e for e in errors)

    def test_storage_rejects_hyphens(self) -> None:
        engine = NamingEngine(workload="test", region="eastus2")
        errors = engine.validate_name("st-test-dev", ResourceType.STORAGE_ACCOUNT)
        assert any("pattern" in e for e in errors)

    def test_generated_names_pass_validation(self) -> None:
        """All generated names should pass their own validation."""
        engine = NamingEngine(workload="myapi", environment="dev", region="eastus2")
        for rt, name in engine.generate_all().items():
            errors = engine.validate_name(name, rt)
            assert len(errors) == 0, f"{rt.value}: {name} failed: {errors}"

    def test_no_constraints_returns_empty(self) -> None:
        engine = NamingEngine(workload="test")
        errors = engine.validate_name("anything", ResourceType.APP_SERVICE)
        assert len(errors) == 0  # No constraints defined for APP_SERVICE


class TestNamingEngineBicep:
    """Test Bicep variable generation."""

    def test_to_bicep_variables_has_all_vars(self) -> None:
        engine = NamingEngine(workload="myapi", environment="dev", region="eastus2")
        output = engine.to_bicep_variables()
        assert "lawName" in output
        assert "kvName" in output
        assert "crName" in output
        assert "caName" in output
        assert "caeName" in output
        assert "identityName" in output
        assert "stName" in output

    def test_to_bicep_variables_has_region_abbrev(self) -> None:
        engine = NamingEngine(workload="test", region="eastus2")
        output = engine.to_bicep_variables()
        assert "eus2" in output

    def test_to_bicep_variables_has_caf_comment(self) -> None:
        engine = NamingEngine(workload="test")
        output = engine.to_bicep_variables()
        assert "CAF" in output


class TestNamingEngineConstraints:
    """Test constraint enforcement."""

    def test_storage_name_truncated_to_24(self) -> None:
        engine = NamingEngine(
            workload="verylongprojectname",
            environment="development",
            region="australiasoutheast",
        )
        name = engine.generate(ResourceType.STORAGE_ACCOUNT)
        assert len(name) <= 24

    def test_key_vault_name_truncated_to_24(self) -> None:
        engine = NamingEngine(
            workload="verylongprojectname",
            environment="development",
            region="australiasoutheast",
        )
        name = engine.generate(ResourceType.KEY_VAULT)
        assert len(name) <= 24

    def test_resource_constraints_defined(self) -> None:
        assert ResourceType.STORAGE_ACCOUNT in RESOURCE_CONSTRAINTS
        assert ResourceType.KEY_VAULT in RESOURCE_CONSTRAINTS
        assert ResourceType.CONTAINER_REGISTRY in RESOURCE_CONSTRAINTS


# =====================================================================
# Tagging Engine Tests
# =====================================================================


class TestTaggingEngineGeneration:
    """Test tag generation."""

    def setup_method(self) -> None:
        self.engine = TaggingEngine(
            project="my-api",
            environment="dev",
            owner="team@contoso.com",
            cost_center="ENG-001",
        )

    def test_generate_required_tags(self) -> None:
        tags = self.engine.generate_tags(include_optional=False)
        assert tags["project"] == "my-api"
        assert tags["environment"] == "dev"
        assert tags["costCenter"] == "ENG-001"
        assert tags["owner"] == "team@contoso.com"
        assert tags["managedBy"] == "bicep"
        assert tags["createdBy"] == "enterprise-devex-orchestrator"
        assert "dataSensitivity" in tags

    def test_generate_includes_optional_by_default(self) -> None:
        tags = self.engine.generate_tags()
        assert "complianceScope" in tags
        assert "criticality" in tags
        assert "createdDate" in tags

    def test_generate_excludes_optional_when_asked(self) -> None:
        tags = self.engine.generate_tags(include_optional=False)
        assert "complianceScope" not in tags
        assert "criticality" not in tags
        assert "createdDate" not in tags

    def test_custom_tags_merged(self) -> None:
        engine = TaggingEngine(
            project="test",
            custom_tags={"myCustomTag": "myValue"},
        )
        tags = engine.generate_tags()
        assert tags["myCustomTag"] == "myValue"

    def test_enterprise_tags_take_precedence(self) -> None:
        """Custom tags should not override enterprise tags."""
        engine = TaggingEngine(
            project="test",
            custom_tags={"project": "override-attempt"},
        )
        tags = engine.generate_tags()
        assert tags["project"] == "test"  # Enterprise value wins

    def test_department_included_when_set(self) -> None:
        engine = TaggingEngine(project="test", department="engineering")
        tags = engine.generate_tags()
        assert tags["department"] == "engineering"

    def test_team_included_when_set(self) -> None:
        engine = TaggingEngine(project="test", team="platform")
        tags = engine.generate_tags()
        assert tags["team"] == "platform"

    def test_required_tags_count(self) -> None:
        assert len(REQUIRED_TAGS) == 7

    def test_optional_tags_exist(self) -> None:
        assert len(OPTIONAL_TAGS) > 0

    def test_all_tags_is_union(self) -> None:
        assert len(ALL_TAGS) == len(REQUIRED_TAGS) + len(OPTIONAL_TAGS)


class TestTaggingEngineValidation:
    """Test tag validation."""

    def setup_method(self) -> None:
        self.engine = TaggingEngine(
            project="my-api",
            environment="dev",
            owner="team@contoso.com",
            cost_center="ENG-001",
        )

    def test_valid_tags_pass(self) -> None:
        tags = self.engine.generate_tags()
        result = self.engine.validate_tags(tags)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_required_tag_fails(self) -> None:
        tags = self.engine.generate_tags()
        del tags["project"]
        result = self.engine.validate_tags(tags)
        assert result.valid is False
        assert "project" in result.missing_required

    def test_invalid_environment_value(self) -> None:
        tags = self.engine.generate_tags()
        tags["environment"] = "invalid-env"
        result = self.engine.validate_tags(tags)
        assert result.valid is False
        assert "environment" in result.invalid_values

    def test_invalid_owner_email(self) -> None:
        tags = self.engine.generate_tags()
        tags["owner"] = "not-an-email"
        result = self.engine.validate_tags(tags)
        assert result.valid is False
        assert "owner" in result.invalid_values

    def test_invalid_cost_center_format(self) -> None:
        tags = self.engine.generate_tags()
        tags["costCenter"] = "lowercase"
        result = self.engine.validate_tags(tags)
        assert result.valid is False
        assert "costCenter" in result.invalid_values

    def test_empty_tags_fails(self) -> None:
        result = self.engine.validate_tags({})
        assert result.valid is False
        assert len(result.missing_required) == 7

    def test_validation_result_has_warnings_for_optional(self) -> None:
        """When optional tags are missing, warnings should be raised."""
        tags = self.engine.generate_tags(include_optional=False)
        result = self.engine.validate_tags(tags)
        assert result.valid is True  # Only required matters for validity
        assert len(result.warnings) > 0  # Optional missing = warnings


class TestTaggingEngineBicep:
    """Test Bicep variable generation."""

    def test_to_bicep_variable_has_required_tags(self) -> None:
        engine = TaggingEngine(project="test", environment="dev")
        output = engine.to_bicep_variable()
        assert "project:" in output
        assert "environment:" in output
        assert "costCenter:" in output
        assert "owner:" in output
        assert "managedBy:" in output
        assert "createdBy:" in output
        assert "dataSensitivity:" in output

    def test_to_bicep_variable_has_optional_tags(self) -> None:
        engine = TaggingEngine(project="test")
        output = engine.to_bicep_variable(include_optional=True)
        assert "complianceScope:" in output
        assert "criticality:" in output

    def test_to_bicep_variable_without_optional(self) -> None:
        engine = TaggingEngine(project="test")
        output = engine.to_bicep_variable(include_optional=False)
        assert "complianceScope:" not in output

    def test_to_bicep_variable_has_var_tags(self) -> None:
        engine = TaggingEngine(project="test")
        output = engine.to_bicep_variable()
        assert "var tags = {" in output


class TestTagCatalog:
    """Test the tag catalog for documentation."""

    def test_get_tag_catalog_returns_all(self) -> None:
        catalog = TaggingEngine.get_tag_catalog()
        assert len(catalog) == len(ALL_TAGS)

    def test_catalog_entries_have_required_fields(self) -> None:
        catalog = TaggingEngine.get_tag_catalog()
        for entry in catalog:
            assert "name" in entry
            assert "description" in entry
            assert "requirement" in entry
            assert entry["requirement"] in ("required", "optional")


# =====================================================================
# Enterprise Standards Config Tests
# =====================================================================


class TestEnterpriseStandardsConfig:
    """Test configuration loading and factory methods."""

    def test_default_config_creates_cleanly(self) -> None:
        config = EnterpriseStandardsConfig()
        assert config.naming is not None
        assert config.tagging is not None
        assert config.governance is not None

    def test_create_naming_engine(self) -> None:
        config = EnterpriseStandardsConfig()
        engine = config.create_naming_engine("myapi", "dev", "eastus2")
        assert isinstance(engine, NamingEngine)
        assert engine.workload == "myapi"
        assert engine.environment == "dev"

    def test_create_tagging_engine(self) -> None:
        config = EnterpriseStandardsConfig()
        engine = config.create_tagging_engine("myapi", "dev")
        assert isinstance(engine, TaggingEngine)
        assert engine.project == "myapi"

    def test_tagging_engine_uses_config_defaults(self) -> None:
        config = EnterpriseStandardsConfig()
        config.tagging.default_owner = "custom@example.com"
        config.tagging.default_cost_center = "CUSTOM-001"
        engine = config.create_tagging_engine("test", "dev")
        assert engine.owner == "custom@example.com"
        assert engine.cost_center == "CUSTOM-001"

    def test_tagging_engine_override_owner(self) -> None:
        config = EnterpriseStandardsConfig()
        engine = config.create_tagging_engine("test", "dev", owner="override@example.com")
        assert engine.owner == "override@example.com"

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        config = EnterpriseStandardsConfig()
        data = config.to_dict()
        restored = EnterpriseStandardsConfig.from_dict(data)
        assert restored.to_dict() == data

    def test_governance_defaults(self) -> None:
        config = EnterpriseStandardsConfig()
        assert config.governance.max_remediation_iterations == 2
        assert config.governance.min_stride_categories == 3
        assert config.governance.enforce_naming is True
        assert config.governance.enforce_tagging is True

    def test_required_modules_default(self) -> None:
        config = EnterpriseStandardsConfig()
        assert "key-vault" in config.governance.required_modules
        assert "log-analytics" in config.governance.required_modules
        assert "managed-identity" in config.governance.required_modules


class TestConfigLoading:
    """Test loading config from files."""

    def test_load_json_config(self) -> None:
        data = {
            "naming": {"include_region": False},
            "tagging": {"default_cost_center": "TEST-001"},
            "governance": {"max_remediation_iterations": 5},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()

            config = EnterpriseStandardsConfig.load(f.name)
            assert config.naming.include_region is False
            assert config.tagging.default_cost_center == "TEST-001"
            assert config.governance.max_remediation_iterations == 5

    def test_load_nonexistent_file_returns_defaults(self) -> None:
        config = EnterpriseStandardsConfig.load("/nonexistent/path.yaml")
        assert config.governance.max_remediation_iterations == 2  # default

    def test_load_yaml_config(self) -> None:
        """Test loading from YAML (may skip if pyyaml not installed)."""
        try:
            import yaml
        except ImportError:
            return  # Skip if yaml not available

        data = {
            "naming": {"include_region": True},
            "tagging": {"default_owner": "yaml-test@example.com"},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            yaml.dump(data, f)
            f.flush()

            config = EnterpriseStandardsConfig.load(f.name)
            assert config.tagging.default_owner == "yaml-test@example.com"

    def test_load_project_standards_yaml(self) -> None:
        """Test loading the actual standards.yaml from the project root."""
        project_yaml = Path(__file__).parent.parent / "standards.yaml"
        if project_yaml.exists():
            config = EnterpriseStandardsConfig.load(str(project_yaml))
            assert config is not None
            assert isinstance(config.naming, NamingStandardsConfig)
            assert isinstance(config.tagging, TaggingStandardsConfig)
            assert isinstance(config.governance, GovernanceConfig)


# =====================================================================
# Integration Tests -- Standards + Generators
# =====================================================================


class TestStandardsIntegration:
    """Test that standards integrate correctly with generators."""

    def test_bicep_generator_uses_naming(self) -> None:
        """BicepGenerator output should contain CAF naming variables."""
        from src.orchestrator.generators.bicep_generator import BicepGenerator
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
        )

        spec = IntentSpec(
            project_name="test-project",
            app_type=AppType.API,
            description="A test API",
            raw_intent="Build a test API",
            data_stores=[],
            security=SecurityRequirements(
                auth_model=AuthModel.MANAGED_IDENTITY,
                compliance_framework=ComplianceFramework.GENERAL,
                data_classification="internal",
                networking=NetworkingModel.PRIVATE,
            ),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
            azure_region="eastus2",
            environment="dev",
        )

        plan = PlanOutput(
            title="Test",
            summary="Test",
            components=[
                ComponentSpec(
                    name="container-app",
                    azure_service="Microsoft.App/containerApps",
                    purpose="Run app",
                    bicep_module="container-app.bicep",
                    security_controls=["MI"],
                ),
            ],
            decisions=[],
            threat_model=[],
            diagram_mermaid="graph TD; A-->B;",
        )

        gen = BicepGenerator()
        files = gen.generate(spec, plan)
        main_bicep = files["infra/bicep/main.bicep"]

        # Verify CAF naming variables are present
        assert "lawName" in main_bicep
        assert "kvName" in main_bicep
        assert "crName" in main_bicep
        assert "caName" in main_bicep

        # Verify enterprise tags variable is present
        assert "var tags = {" in main_bicep
        assert "costCenter" in main_bicep
        assert "dataSensitivity" in main_bicep
        assert "createdBy" in main_bicep

    def test_bicep_generator_produces_standards_doc(self) -> None:
        """BicepGenerator should output docs/standards.md."""
        from src.orchestrator.generators.bicep_generator import BicepGenerator
        from src.orchestrator.intent_schema import (
            AppType,
            AuthModel,
            CICDRequirements,
            ComplianceFramework,
            IntentSpec,
            NetworkingModel,
            ObservabilityRequirements,
            PlanOutput,
            SecurityRequirements,
        )

        spec = IntentSpec(
            project_name="test-project",
            app_type=AppType.API,
            description="Test",
            raw_intent="Test",
            data_stores=[],
            security=SecurityRequirements(
                auth_model=AuthModel.MANAGED_IDENTITY,
                compliance_framework=ComplianceFramework.GENERAL,
                data_classification="internal",
                networking=NetworkingModel.PRIVATE,
            ),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
            azure_region="eastus2",
            environment="dev",
        )

        plan = PlanOutput(
            title="Test",
            summary="Test",
            components=[],
            decisions=[],
            threat_model=[],
            diagram_mermaid="graph TD; A-->B;",
        )

        gen = BicepGenerator()
        files = gen.generate(spec, plan)
        assert "docs/standards.md" in files
        standards_doc = files["docs/standards.md"]
        assert "Naming Convention" in standards_doc
        assert "Tagging Standard" in standards_doc

    def test_governance_includes_naming_checks(self) -> None:
        """Governance reviewer should run naming standard checks."""
        from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent
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

        spec = IntentSpec(
            project_name="test-project",
            app_type=AppType.API,
            description="Test",
            raw_intent="Test",
            data_stores=[],
            security=SecurityRequirements(
                auth_model=AuthModel.MANAGED_IDENTITY,
                compliance_framework=ComplianceFramework.GENERAL,
                data_classification="internal",
                networking=NetworkingModel.PRIVATE,
            ),
            observability=ObservabilityRequirements(log_analytics=True),
            cicd=CICDRequirements(oidc_auth=True),
            azure_region="eastus2",
            resource_group_name="rg-test-project-dev",
            environment="dev",
        )

        plan = PlanOutput(
            title="Test",
            summary="Test",
            components=[
                ComponentSpec(
                    name="key-vault",
                    azure_service="Microsoft.KeyVault/vaults",
                    purpose="Secrets",
                    bicep_module="keyvault.bicep",
                    security_controls=["RBAC"],
                ),
                ComponentSpec(
                    name="log-analytics",
                    azure_service="Microsoft.OperationalInsights/workspaces",
                    purpose="Logging",
                    bicep_module="log-analytics.bicep",
                    security_controls=[],
                ),
                ComponentSpec(
                    name="managed-identity",
                    azure_service="Microsoft.ManagedIdentity/userAssignedIdentities",
                    purpose="Auth",
                    bicep_module="managed-identity.bicep",
                    security_controls=["RBAC"],
                ),
            ],
            decisions=[],
            threat_model=[
                ThreatEntry(id="T-001", category="Spoofing", description="T1", mitigation="M1", residual_risk="Low"),
                ThreatEntry(id="T-002", category="Tampering", description="T2", mitigation="M2", residual_risk="Low"),
                ThreatEntry(id="T-003", category="DoS", description="T3", mitigation="M3", residual_risk="Low"),
                ThreatEntry(id="T-004", category="Info Disc.", description="T4", mitigation="M4", residual_risk="Low"),
            ],
            diagram_mermaid="graph TD; A-->B;",
        )

        reviewer = GovernanceReviewerAgent()
        report = reviewer.validate_plan(spec, plan)

        # Verify naming checks exist
        naming_checks = [c for c in report.checks if c.check_id.startswith("STD-NAME")]
        assert len(naming_checks) == 3

        # Verify tagging checks exist
        tagging_checks = [c for c in report.checks if c.check_id.startswith("STD-TAG")]
        assert len(tagging_checks) == 3

    def test_governance_bicep_checks_tags_and_naming(self) -> None:
        """Bicep validation should check for enterprise tags and naming vars."""
        from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent

        reviewer = GovernanceReviewerAgent()

        # Bicep with all standards
        clean_bicep = {
            "main.bicep": """
var lawName = 'law-test-dev-eus2'
var kvName = 'kv-test-dev-eus2'
var crName = 'crtestdeveus2'
var caName = 'ca-test-dev-eus2'
var identityName = 'id-test-dev-eus2'
var tags = {
  costCenter: 'ENG-001'
  owner: 'team@contoso.com'
  dataSensitivity: 'internal'
  createdBy: 'enterprise-devex-orchestrator'
}
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  tags: { managedBy: 'UserAssigned' }
}
resource diag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {}
""",
        }
        report = reviewer.validate_bicep(clean_bicep)
        # Should find naming vars and tags
        std_checks = [c for c in report.checks if c.check_id.startswith("BICEP-STD")]
        assert len(std_checks) == 2
        assert all(c.passed for c in std_checks)

    def test_policy_engine_has_standards_policies(self) -> None:
        """Policy engine should include naming, tagging, and region policies."""
        from src.orchestrator.tools.policy_engine import check_policy, list_policies

        # Check standards policies exist via list
        all_policies = list_policies("Standards")
        assert "STD-001" in all_policies
        assert "STD-002" in all_policies

        # Check policy matching for naming/tagging keywords
        naming_result = check_policy("naming conventions")
        assert len(naming_result) > 0

        tagging_result = check_policy("tagging standard")
        assert len(tagging_result) > 0
