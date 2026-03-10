"""Tagging Standards Engine -- enterprise resource tagging enforcement.

Ensures all Azure resources include required metadata tags per enterprise
policy. Supports configurable required/optional tags with validation rules
and default value generation.

Enterprise tagging enables:
  - Cost management and chargeback
  - Ownership and accountability tracking
  - Environment and compliance classification
  - Operations and automation support

Reference: https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-tagging
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


class TagRequirement(str, Enum):
    """Whether a tag is required or optional."""

    REQUIRED = "required"
    OPTIONAL = "optional"


class DataSensitivity(str, Enum):
    """Data classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class TagSpec:
    """Specification for an enterprise tag."""

    name: str
    description: str
    requirement: TagRequirement
    default: str = ""
    validation_pattern: str = ""  # Regex pattern for value validation
    example: str = ""
    category: str = "general"  # cost, operations, security, governance


# -- Enterprise Tag Catalog ------------------------------------------

REQUIRED_TAGS: list[TagSpec] = [
    TagSpec(
        name="project",
        description="Project or workload identifier matching the resource group naming",
        requirement=TagRequirement.REQUIRED,
        validation_pattern=r"^[a-z][a-z0-9-]{2,38}$",
        example="my-api-project",
        category="governance",
    ),
    TagSpec(
        name="environment",
        description="Deployment environment (dev, staging, prod)",
        requirement=TagRequirement.REQUIRED,
        validation_pattern=r"^(dev|staging|prod|test|sandbox)$",
        example="dev",
        category="operations",
    ),
    TagSpec(
        name="costCenter",
        description="Financial cost center for chargeback and billing",
        requirement=TagRequirement.REQUIRED,
        validation_pattern=r"^[A-Z0-9-]{3,20}$",
        example="ENG-001",
        category="cost",
    ),
    TagSpec(
        name="owner",
        description="Email of the team or individual responsible for this resource",
        requirement=TagRequirement.REQUIRED,
        validation_pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        example="platform-team@contoso.com",
        category="governance",
    ),
    TagSpec(
        name="managedBy",
        description="Tool or process that manages this resource lifecycle",
        requirement=TagRequirement.REQUIRED,
        default="bicep",
        validation_pattern=r"^[a-z][a-z0-9-]+$",
        example="bicep",
        category="operations",
    ),
    TagSpec(
        name="createdBy",
        description="Generator or agent that created this resource definition",
        requirement=TagRequirement.REQUIRED,
        default="enterprise-devex-orchestrator",
        example="enterprise-devex-orchestrator",
        category="operations",
    ),
    TagSpec(
        name="dataSensitivity",
        description="Data classification level per enterprise data policy",
        requirement=TagRequirement.REQUIRED,
        default="confidential",
        validation_pattern=r"^(public|internal|confidential|restricted)$",
        example="confidential",
        category="security",
    ),
]

OPTIONAL_TAGS: list[TagSpec] = [
    TagSpec(
        name="complianceScope",
        description="Applicable compliance framework (general, hipaa, soc2, fedramp)",
        requirement=TagRequirement.OPTIONAL,
        default="general",
        validation_pattern=r"^[a-z][a-z0-9_-]+$",
        example="soc2",
        category="security",
    ),
    TagSpec(
        name="department",
        description="Business department that owns this workload",
        requirement=TagRequirement.OPTIONAL,
        example="engineering",
        category="cost",
    ),
    TagSpec(
        name="team",
        description="Specific team within the department",
        requirement=TagRequirement.OPTIONAL,
        example="platform-engineering",
        category="governance",
    ),
    TagSpec(
        name="application",
        description="Application the resource belongs to (for multi-app groups)",
        requirement=TagRequirement.OPTIONAL,
        example="order-processing",
        category="governance",
    ),
    TagSpec(
        name="criticality",
        description="Business criticality level for SLA and incident prioritization",
        requirement=TagRequirement.OPTIONAL,
        default="medium",
        validation_pattern=r"^(low|medium|high|critical)$",
        example="high",
        category="operations",
    ),
    TagSpec(
        name="createdDate",
        description="ISO 8601 date when the resource definition was generated",
        requirement=TagRequirement.OPTIONAL,
        example="2025-03-07",
        category="operations",
    ),
]

ALL_TAGS: list[TagSpec] = REQUIRED_TAGS + OPTIONAL_TAGS


@dataclass
class TagValidationResult:
    """Result of tag validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    invalid_values: list[str] = field(default_factory=list)


class TaggingEngine:
    """Enterprise tagging standards engine.

    Generates and validates resource tags according to enterprise policy.

    Usage:
        engine = TaggingEngine(
            project="my-api",
            environment="dev",
            owner="team@contoso.com",
            cost_center="ENG-001",
        )
        tags = engine.generate_tags()
        result = engine.validate_tags(tags)
    """

    def __init__(
        self,
        project: str,
        environment: str = "dev",
        owner: str = "platform-team@contoso.com",
        cost_center: str = "DEFAULT-001",
        data_sensitivity: str = "confidential",
        compliance_scope: str = "general",
        department: str = "",
        team: str = "",
        criticality: str = "medium",
        custom_tags: dict[str, str] | None = None,
    ) -> None:
        self.project = project
        self.environment = environment
        self.owner = owner
        self.cost_center = cost_center
        self.data_sensitivity = data_sensitivity
        self.compliance_scope = compliance_scope
        self.department = department
        self.team = team
        self.criticality = criticality
        self.custom_tags = custom_tags or {}

    def generate_tags(self, include_optional: bool = True) -> dict[str, str]:
        """Generate a complete set of enterprise-compliant tags.

        Args:
            include_optional: Include optional tags with defaults.

        Returns:
            Dict of tag name -> value.
        """
        tags: dict[str, str] = {
            "project": self.project,
            "environment": self.environment,
            "costCenter": self.cost_center,
            "owner": self.owner,
            "managedBy": "bicep",
            "createdBy": "enterprise-devex-orchestrator",
            "dataSensitivity": self.data_sensitivity,
        }

        if include_optional:
            tags["complianceScope"] = self.compliance_scope
            tags["criticality"] = self.criticality
            tags["createdDate"] = datetime.now(tz=UTC).strftime("%Y-%m-%d")

            if self.department:
                tags["department"] = self.department
            if self.team:
                tags["team"] = self.team

        # Merge custom tags (enterprise tags take precedence)
        for key, value in self.custom_tags.items():
            if key not in tags:
                tags[key] = value

        logger.debug("tagging.generated", tag_count=len(tags))
        return tags

    def validate_tags(self, tags: dict[str, str]) -> TagValidationResult:
        """Validate tags against enterprise tagging standards.

        Args:
            tags: Dict of tag name -> value to validate.

        Returns:
            TagValidationResult with errors and warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []
        missing_required: list[str] = []
        invalid_values: list[str] = []

        # Check required tags
        for spec in REQUIRED_TAGS:
            if spec.name not in tags:
                missing_required.append(spec.name)
                errors.append(f"Missing required tag: '{spec.name}' -- {spec.description}")
            elif spec.validation_pattern and not re.match(spec.validation_pattern, tags[spec.name]):
                invalid_values.append(spec.name)
                errors.append(
                    f"Invalid value for tag '{spec.name}': '{tags[spec.name]}' "
                    f"does not match pattern {spec.validation_pattern} "
                    f"(example: {spec.example})"
                )

        # Check optional tags
        for spec in OPTIONAL_TAGS:
            if spec.name in tags and spec.validation_pattern:
                if not re.match(spec.validation_pattern, tags[spec.name]):
                    invalid_values.append(spec.name)
                    warnings.append(
                        f"Invalid value for optional tag '{spec.name}': '{tags[spec.name]}' "
                        f"(expected pattern: {spec.validation_pattern})"
                    )
            elif spec.name not in tags:
                warnings.append(f"Optional tag not set: '{spec.name}' -- {spec.description}")

        valid = len(errors) == 0
        return TagValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            missing_required=missing_required,
            invalid_values=invalid_values,
        )

    def to_bicep_variable(self, include_optional: bool = True) -> str:
        """Generate a Bicep variable block for enterprise tags.

        Returns:
            Bicep variable declaration for standard tags.
        """
        lines = [
            "// -- Enterprise Tagging Standard ---------------------------------",
            "// Required: project, environment, costCenter, owner, managedBy,",
            "//           createdBy, dataSensitivity",
            "// Optional: complianceScope, department, team, criticality, createdDate",
            "var tags = {",
            "  // Required tags (enterprise governance policy)",
            "  project: projectName",
            "  environment: environment",
            "  costCenter: costCenter",
            "  owner: ownerEmail",
            "  managedBy: 'bicep'",
            "  createdBy: 'enterprise-devex-orchestrator'",
            f"  dataSensitivity: '{self.data_sensitivity}'",
        ]

        if include_optional:
            lines.extend(
                [
                    "  // Optional tags (recommended)",
                    f"  complianceScope: '{self.compliance_scope}'",
                    f"  criticality: '{self.criticality}'",
                ]
            )
            if self.department:
                lines.append(f"  department: '{self.department}'")
            if self.team:
                lines.append(f"  team: '{self.team}'")

        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def get_tag_catalog() -> list[dict[str, str]]:
        """Return the full tag catalog for documentation generation.

        Returns:
            List of tag specifications as dicts.
        """
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "requirement": spec.requirement.value,
                "category": spec.category,
                "example": spec.example,
                "default": spec.default,
                "pattern": spec.validation_pattern,
            }
            for spec in ALL_TAGS
        ]
