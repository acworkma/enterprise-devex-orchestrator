"""Enterprise Standards Configuration — configurable governance baselines.

Provides a unified configuration model for enterprise standards including
naming conventions, tagging policies, and governance baselines. Supports
loading from YAML/JSON files or environment variables, allowing each
enterprise to customize standards without code changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.orchestrator.logging import get_logger
from src.orchestrator.standards.naming import (
    NamingConvention,
    NamingEngine,
    ResourceType,
)
from src.orchestrator.standards.tagging import TaggingEngine

logger = get_logger(__name__)


@dataclass
class NamingStandardsConfig:
    """Configuration for naming conventions."""

    # Pattern template per resource type (overrides defaults)
    custom_patterns: dict[str, str] = field(default_factory=dict)
    # Whether to include region abbreviation in names
    include_region: bool = True
    # Whether to include instance suffix for uniqueness
    include_instance: bool = False
    # Custom region abbreviations
    region_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class TaggingStandardsConfig:
    """Configuration for tagging standards."""

    # Default cost center if not provided
    default_cost_center: str = "DEFAULT-001"
    # Default owner if not provided
    default_owner: str = "platform-team@contoso.com"
    # Default data sensitivity level
    default_data_sensitivity: str = "confidential"
    # Default compliance scope
    default_compliance_scope: str = "general"
    # Whether to include optional tags by default
    include_optional: bool = True
    # Additional custom required tags (name → description)
    custom_required_tags: dict[str, str] = field(default_factory=dict)
    # Default criticality
    default_criticality: str = "medium"
    # Department name
    department: str = ""
    # Team name
    team: str = ""


@dataclass
class GovernanceConfig:
    """Configuration for governance baselines."""

    # Maximum allowed iterations for planner–reviewer feedback loop
    max_remediation_iterations: int = 2
    # Minimum number of STRIDE categories required
    min_stride_categories: int = 3
    # Minimum number of ADRs required
    min_adrs: int = 3
    # Whether to enforce naming convention validation
    enforce_naming: bool = True
    # Whether to enforce tagging validation
    enforce_tagging: bool = True
    # Severity level that causes a FAIL (error, warning, info)
    fail_on_severity: str = "error"
    # Required Bicep modules that must be present
    required_modules: list[str] = field(
        default_factory=lambda: [
            "key-vault",
            "log-analytics",
            "managed-identity",
        ]
    )


@dataclass
class EnterpriseStandardsConfig:
    """Root configuration for all enterprise standards.

    Can be loaded from a standards.yaml file in the project root
    or instantiated with defaults.

    Usage:
        config = EnterpriseStandardsConfig.load("standards.yaml")
        naming_engine = config.create_naming_engine("my-project", "dev", "eastus2")
        tagging_engine = config.create_tagging_engine("my-project", "dev")
    """

    naming: NamingStandardsConfig = field(default_factory=NamingStandardsConfig)
    tagging: TaggingStandardsConfig = field(default_factory=TaggingStandardsConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)

    def create_naming_engine(
        self,
        workload: str,
        environment: str = "dev",
        region: str = "eastus2",
        instance: str = "",
    ) -> NamingEngine:
        """Create a NamingEngine with this configuration applied.

        Args:
            workload: Project/workload name.
            environment: Deployment environment.
            region: Azure region.
            instance: Optional instance suffix.

        Returns:
            Configured NamingEngine.
        """
        # Build custom conventions from config overrides
        custom_conventions: dict[ResourceType, NamingConvention] = {}
        for rt_key, pattern in self.naming.custom_patterns.items():
            try:
                rt = ResourceType(rt_key)
                custom_conventions[rt] = NamingConvention(rt, pattern)
            except ValueError:
                logger.warning("naming.unknown_resource_type", resource_type=rt_key)

        return NamingEngine(
            workload=workload,
            environment=environment,
            region=region,
            instance=instance,
            conventions=custom_conventions,
        )

    def create_tagging_engine(
        self,
        project: str,
        environment: str = "dev",
        owner: str | None = None,
        cost_center: str | None = None,
        custom_tags: dict[str, str] | None = None,
    ) -> TaggingEngine:
        """Create a TaggingEngine with this configuration applied.

        Args:
            project: Project name.
            environment: Deployment environment.
            owner: Resource owner email (uses config default if None).
            cost_center: Cost center code (uses config default if None).
            custom_tags: Additional custom tags.

        Returns:
            Configured TaggingEngine.
        """
        return TaggingEngine(
            project=project,
            environment=environment,
            owner=owner or self.tagging.default_owner,
            cost_center=cost_center or self.tagging.default_cost_center,
            data_sensitivity=self.tagging.default_data_sensitivity,
            compliance_scope=self.tagging.default_compliance_scope,
            department=self.tagging.department,
            team=self.tagging.team,
            criticality=self.tagging.default_criticality,
            custom_tags=custom_tags,
        )

    @classmethod
    def load(cls, path: str | Path) -> EnterpriseStandardsConfig:
        """Load standards configuration from a YAML or JSON file.

        Args:
            path: Path to the configuration file.

        Returns:
            Loaded EnterpriseStandardsConfig.
        """
        filepath = Path(path)
        if not filepath.exists():
            logger.info("standards.config_not_found", path=str(filepath))
            return cls()

        content = filepath.read_text(encoding="utf-8")

        if filepath.suffix in (".yaml", ".yml"):
            try:
                import yaml

                data = yaml.safe_load(content) or {}
            except ImportError:
                logger.warning("standards.yaml_not_available")
                return cls()
        elif filepath.suffix == ".json":
            data = json.loads(content)
        else:
            logger.warning("standards.unsupported_format", suffix=filepath.suffix)
            return cls()

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnterpriseStandardsConfig:
        """Create config from a dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            Populated EnterpriseStandardsConfig.
        """
        naming_data = data.get("naming", {})
        tagging_data = data.get("tagging", {})
        governance_data = data.get("governance", {})

        naming = NamingStandardsConfig(
            custom_patterns=naming_data.get("custom_patterns", {}),
            include_region=naming_data.get("include_region", True),
            include_instance=naming_data.get("include_instance", False),
            region_overrides=naming_data.get("region_overrides", {}),
        )

        tagging = TaggingStandardsConfig(
            default_cost_center=tagging_data.get("default_cost_center", "DEFAULT-001"),
            default_owner=tagging_data.get("default_owner", "platform-team@contoso.com"),
            default_data_sensitivity=tagging_data.get("default_data_sensitivity", "confidential"),
            default_compliance_scope=tagging_data.get("default_compliance_scope", "general"),
            include_optional=tagging_data.get("include_optional", True),
            custom_required_tags=tagging_data.get("custom_required_tags", {}),
            default_criticality=tagging_data.get("default_criticality", "medium"),
            department=tagging_data.get("department", ""),
            team=tagging_data.get("team", ""),
        )

        governance = GovernanceConfig(
            max_remediation_iterations=governance_data.get("max_remediation_iterations", 2),
            min_stride_categories=governance_data.get("min_stride_categories", 3),
            min_adrs=governance_data.get("min_adrs", 3),
            enforce_naming=governance_data.get("enforce_naming", True),
            enforce_tagging=governance_data.get("enforce_tagging", True),
            fail_on_severity=governance_data.get("fail_on_severity", "error"),
            required_modules=governance_data.get(
                "required_modules",
                ["key-vault", "log-analytics", "managed-identity"],
            ),
        )

        return cls(naming=naming, tagging=tagging, governance=governance)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for YAML/JSON output."""
        return {
            "naming": {
                "custom_patterns": self.naming.custom_patterns,
                "include_region": self.naming.include_region,
                "include_instance": self.naming.include_instance,
                "region_overrides": self.naming.region_overrides,
            },
            "tagging": {
                "default_cost_center": self.tagging.default_cost_center,
                "default_owner": self.tagging.default_owner,
                "default_data_sensitivity": self.tagging.default_data_sensitivity,
                "default_compliance_scope": self.tagging.default_compliance_scope,
                "include_optional": self.tagging.include_optional,
                "custom_required_tags": self.tagging.custom_required_tags,
                "default_criticality": self.tagging.default_criticality,
                "department": self.tagging.department,
                "team": self.tagging.team,
            },
            "governance": {
                "max_remediation_iterations": self.governance.max_remediation_iterations,
                "min_stride_categories": self.governance.min_stride_categories,
                "min_adrs": self.governance.min_adrs,
                "enforce_naming": self.governance.enforce_naming,
                "enforce_tagging": self.governance.enforce_tagging,
                "fail_on_severity": self.governance.fail_on_severity,
                "required_modules": self.governance.required_modules,
            },
        }
