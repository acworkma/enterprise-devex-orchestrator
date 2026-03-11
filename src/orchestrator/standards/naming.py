"""Naming Standards Engine -- Azure Cloud Adoption Framework compliant.

Generates resource names that follow enterprise naming conventions based
on the Azure CAF recommended patterns:
  {resourceType}-{workload}-{environment}-{region}-{instance}

Handles resource-specific constraints:
  - Storage Accounts: 3-24 chars, lowercase alphanumeric only
  - Key Vault: 3-24 chars, alphanumeric and hyphens
  - Container Registry: 5-50 chars, alphanumeric only
  - Resource Groups: 1-90 chars

Reference: https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


class ResourceType(str, Enum):
    """Azure resource types with their CAF abbreviations."""

    RESOURCE_GROUP = "rg"
    LOG_ANALYTICS = "law"
    MANAGED_IDENTITY = "id"
    KEY_VAULT = "kv"
    CONTAINER_REGISTRY = "cr"
    CONTAINER_APP = "ca"
    CONTAINER_APP_ENV = "cae"
    STORAGE_ACCOUNT = "st"
    COSMOS_DB = "cosmos"
    SQL_SERVER = "sql"
    SQL_DATABASE = "sqldb"
    REDIS_CACHE = "redis"
    APP_SERVICE = "app"
    FUNCTION_APP = "func"
    VIRTUAL_NETWORK = "vnet"
    SUBNET = "snet"
    NSG = "nsg"
    PUBLIC_IP = "pip"
    APP_INSIGHTS = "appi"
    ACTION_GROUP = "ag"


# Region abbreviation lookup -- Azure CAF recommended short codes
REGION_ABBREVIATIONS: dict[str, str] = {
    "eastus": "eus",
    "eastus2": "eus2",
    "westus": "wus",
    "westus2": "wus2",
    "westus3": "wus3",
    "centralus": "cus",
    "northcentralus": "ncus",
    "southcentralus": "scus",
    "westcentralus": "wcus",
    "canadacentral": "cac",
    "canadaeast": "cae",
    "northeurope": "neu",
    "westeurope": "weu",
    "uksouth": "uks",
    "ukwest": "ukw",
    "francecentral": "frc",
    "francesouth": "frs",
    "germanywestcentral": "gwc",
    "norwayeast": "noe",
    "switzerlandnorth": "szn",
    "swedencentral": "sec",
    "australiaeast": "aue",
    "australiasoutheast": "ause",
    "japaneast": "jpe",
    "japanwest": "jpw",
    "southeastasia": "sea",
    "eastasia": "ea",
    "koreacentral": "krc",
    "koreasouth": "krs",
    "centralindia": "cin",
    "southindia": "sin",
    "brazilsouth": "brs",
    "southafricanorth": "san",
    "uaenorth": "uan",
}

# Resource-specific naming constraints
RESOURCE_CONSTRAINTS: dict[ResourceType, dict[str, Any]] = {
    ResourceType.RESOURCE_GROUP: {
        "min_length": 1,
        "max_length": 90,
        "pattern": r"^[a-zA-Z0-9._()-]+$",
        "alphanumeric_only": False,
    },
    ResourceType.STORAGE_ACCOUNT: {
        "min_length": 3,
        "max_length": 24,
        "pattern": r"^[a-z0-9]+$",
        "alphanumeric_only": True,
    },
    ResourceType.KEY_VAULT: {
        "min_length": 3,
        "max_length": 24,
        "pattern": r"^[a-zA-Z][a-zA-Z0-9-]+$",
        "alphanumeric_only": False,
    },
    ResourceType.CONTAINER_REGISTRY: {
        "min_length": 5,
        "max_length": 50,
        "pattern": r"^[a-zA-Z0-9]+$",
        "alphanumeric_only": True,
    },
    ResourceType.CONTAINER_APP: {
        "min_length": 2,
        "max_length": 32,
        "pattern": r"^[a-z][a-z0-9-]+$",
        "alphanumeric_only": False,
    },
    ResourceType.CONTAINER_APP_ENV: {
        "min_length": 1,
        "max_length": 60,
        "pattern": r"^[a-zA-Z][a-zA-Z0-9-]+$",
        "alphanumeric_only": False,
    },
    ResourceType.LOG_ANALYTICS: {
        "min_length": 4,
        "max_length": 63,
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]+$",
        "alphanumeric_only": False,
    },
    ResourceType.MANAGED_IDENTITY: {
        "min_length": 3,
        "max_length": 128,
        "pattern": r"^[a-zA-Z0-9-_]+$",
        "alphanumeric_only": False,
    },
    ResourceType.COSMOS_DB: {
        "min_length": 3,
        "max_length": 44,
        "pattern": r"^[a-z][a-z0-9-]+$",
        "alphanumeric_only": False,
    },
}


@dataclass
class NamingConvention:
    """Defines the naming pattern for a specific resource type."""

    resource_type: ResourceType
    pattern: str  # e.g. "{prefix}-{workload}-{env}-{region}"
    separator: str = "-"
    include_instance: bool = False


# Default Azure CAF naming conventions
DEFAULT_CONVENTIONS: dict[ResourceType, NamingConvention] = {
    ResourceType.RESOURCE_GROUP: NamingConvention(ResourceType.RESOURCE_GROUP, "{prefix}-{workload}-{env}-{region}"),
    ResourceType.LOG_ANALYTICS: NamingConvention(ResourceType.LOG_ANALYTICS, "{prefix}-{workload}-{env}-{region}"),
    ResourceType.MANAGED_IDENTITY: NamingConvention(
        ResourceType.MANAGED_IDENTITY, "{prefix}-{workload}-{env}-{region}"
    ),
    ResourceType.KEY_VAULT: NamingConvention(ResourceType.KEY_VAULT, "{prefix}-{workload}-{env}-{region}"),
    ResourceType.CONTAINER_REGISTRY: NamingConvention(
        ResourceType.CONTAINER_REGISTRY,
        "{prefix}{workload}{env}{region}",
        separator="",
    ),
    ResourceType.CONTAINER_APP: NamingConvention(ResourceType.CONTAINER_APP, "{prefix}-{workload}-{env}-{region}"),
    ResourceType.CONTAINER_APP_ENV: NamingConvention(
        ResourceType.CONTAINER_APP_ENV, "{prefix}-{workload}-{env}-{region}"
    ),
    ResourceType.STORAGE_ACCOUNT: NamingConvention(
        ResourceType.STORAGE_ACCOUNT,
        "{prefix}{workload}{env}{region}",
        separator="",
    ),
    ResourceType.COSMOS_DB: NamingConvention(ResourceType.COSMOS_DB, "{prefix}-{workload}-{env}-{region}"),
    ResourceType.SQL_SERVER: NamingConvention(ResourceType.SQL_SERVER, "{prefix}-{workload}-{env}-{region}"),
    ResourceType.REDIS_CACHE: NamingConvention(ResourceType.REDIS_CACHE, "{prefix}-{workload}-{env}-{region}"),
    ResourceType.APP_INSIGHTS: NamingConvention(ResourceType.APP_INSIGHTS, "{prefix}-{workload}-{env}-{region}"),
}


@dataclass
class NamingEngine:
    """Enterprise naming convention engine.

    Generates resource names following Azure Cloud Adoption Framework
    conventions with configurable patterns per resource type.

    Usage:
        engine = NamingEngine(workload="myapi", environment="dev", region="eastus2")
        kv_name = engine.generate(ResourceType.KEY_VAULT)
        # -> "kv-myapi-dev-eus2"
    """

    workload: str
    environment: str = "dev"
    region: str = "eastus2"
    instance: str = ""
    conventions: dict[ResourceType, NamingConvention] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize with default conventions, then apply overrides."""
        merged = dict(DEFAULT_CONVENTIONS)
        merged.update(self.conventions)
        self.conventions = merged

    def generate(self, resource_type: ResourceType, suffix: str = "") -> str:
        """Generate a compliant resource name.

        Args:
            resource_type: The Azure resource type.
            suffix: Optional suffix to append (e.g., for sub-resources).

        Returns:
            A naming-convention-compliant resource name.

        Raises:
            ValueError: If the generated name violates constraints.
        """
        convention = self.conventions.get(resource_type)
        if not convention:
            # Fall back to a generic pattern
            convention = NamingConvention(resource_type, "{prefix}-{workload}-{env}-{region}")

        region_abbrev = self._abbreviate_region(self.region)
        workload_clean = self._sanitize_workload(self.workload, resource_type)

        name = convention.pattern.format(
            prefix=resource_type.value,
            workload=workload_clean,
            env=self.environment,
            region=region_abbrev,
            instance=self.instance,
        )

        if suffix:
            sep = convention.separator
            name = f"{name}{sep}{suffix}"

        # Apply resource-specific constraints
        name = self._apply_constraints(name, resource_type)

        logger.debug(
            "naming.generated",
            resource_type=resource_type.value,
            name=name,
        )

        return name

    def generate_all(self) -> dict[ResourceType, str]:
        """Generate names for all common resource types.

        Returns:
            Dict mapping ResourceType to generated name.
        """
        common_types = [
            ResourceType.RESOURCE_GROUP,
            ResourceType.LOG_ANALYTICS,
            ResourceType.MANAGED_IDENTITY,
            ResourceType.KEY_VAULT,
            ResourceType.CONTAINER_REGISTRY,
            ResourceType.CONTAINER_APP,
            ResourceType.CONTAINER_APP_ENV,
            ResourceType.STORAGE_ACCOUNT,
        ]

        return {rt: self.generate(rt) for rt in common_types}

    def validate_name(self, name: str, resource_type: ResourceType) -> list[str]:
        """Validate that a resource name meets Azure naming constraints.

        Args:
            name: The resource name to validate.
            resource_type: The Azure resource type.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors: list[str] = []
        constraints = RESOURCE_CONSTRAINTS.get(resource_type)

        if not constraints:
            return errors  # No constraints defined for this resource type

        if len(name) < constraints["min_length"]:
            errors.append(
                f"{resource_type.value}: Name '{name}' is too short "
                f"(min {constraints['min_length']} chars, got {len(name)})"
            )

        if len(name) > constraints["max_length"]:
            errors.append(
                f"{resource_type.value}: Name '{name}' is too long "
                f"(max {constraints['max_length']} chars, got {len(name)})"
            )

        if not re.match(constraints["pattern"], name):
            errors.append(f"{resource_type.value}: Name '{name}' does not match pattern {constraints['pattern']}")

        return errors

    def _abbreviate_region(self, region: str) -> str:
        """Convert full region name to abbreviation."""
        return REGION_ABBREVIATIONS.get(region.lower(), region[:4])

    def _sanitize_workload(self, workload: str, resource_type: ResourceType) -> str:
        """Clean workload name for the target resource type."""
        constraints = RESOURCE_CONSTRAINTS.get(resource_type)
        if constraints and constraints["alphanumeric_only"]:
            return re.sub(r"[^a-z0-9]", "", workload.lower())
        return workload.lower()

    def _apply_constraints(self, name: str, resource_type: ResourceType) -> str:
        """Truncate or adjust name to fit resource constraints."""
        constraints = RESOURCE_CONSTRAINTS.get(resource_type)
        if not constraints:
            return name

        if constraints["alphanumeric_only"]:
            name = re.sub(r"[^a-z0-9]", "", name.lower())
        else:
            name = name.lower()

        max_length = constraints["max_length"]
        if len(name) > max_length:
            name = name[:max_length]

        return name

    def to_bicep_variables(self) -> str:
        """Generate Bicep variable declarations for resource names.

        Returns computed names as Bicep variables for use in templates.
        """
        region_abbrev = self._abbreviate_region(self.region)

        lines = [
            "// -- Enterprise Naming Convention (Azure CAF) -------------------",
            "// Resource names follow: {type}-{workload}-{env}-{region}",
            f"var lawName = 'law-${{projectName}}-${{environment}}-{region_abbrev}'",
            f"var identityName = 'id-${{projectName}}-${{environment}}-{region_abbrev}'",
            f"var kvName = take('kv-${{projectName}}-${{environment}}-{region_abbrev}', 24)",
            f"var crName = replace('cr${{projectName}}${{environment}}{region_abbrev}', '-', '')",
            f"var caeName = take('cae-${{projectName}}-${{environment}}-{region_abbrev}', 32)",
            f"var caName = take('ca-${{projectName}}-${{environment}}-{region_abbrev}', 32)",
            f"var stName = take(replace(toLower('st${{projectName}}${{environment}}{region_abbrev}'), '-', ''), 24)",
        ]

        return "\n".join(lines)
