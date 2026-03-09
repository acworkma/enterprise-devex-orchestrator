"""Strict intent schema for Enterprise DevEx Orchestrator.

Every business intent is normalized into an IntentSpec before any planning
or generation occurs. This ensures deterministic, reproducible output.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AppType(str, Enum):
    """Supported application types."""

    API = "api"
    WEB = "web"
    WORKER = "worker"
    FUNCTION = "function"


class ComputeTarget(str, Enum):
    """Supported Azure compute targets."""

    CONTAINER_APPS = "container_apps"
    APP_SERVICE = "app_service"
    FUNCTIONS = "functions"


class Language(str, Enum):
    """Supported programming languages."""

    PYTHON = "python"
    NODE = "node"
    DOTNET = "dotnet"


# Language → default framework mapping
LANGUAGE_FRAMEWORKS: dict[str, str] = {
    "python": "fastapi",
    "node": "express",
    "dotnet": "aspnet",
}


class DataStore(str, Enum):
    """Supported data stores."""

    BLOB_STORAGE = "blob_storage"
    COSMOS_DB = "cosmos_db"
    SQL = "sql"
    TABLE_STORAGE = "table_storage"
    REDIS = "redis"
    NONE = "none"


class AuthModel(str, Enum):
    """Authentication model."""

    MANAGED_IDENTITY = "managed_identity"
    ENTRA_ID = "entra_id"
    API_KEY = "api_key"


class ComplianceFramework(str, Enum):
    """Compliance guidance framework (guidance only, not certification)."""

    GENERAL = "general"
    HIPAA_GUIDANCE = "hipaa_guidance"
    SOC2_GUIDANCE = "soc2_guidance"
    FEDRAMP_GUIDANCE = "fedramp_guidance"


class NetworkingModel(str, Enum):
    """Networking model."""

    PRIVATE = "private"
    INTERNAL = "internal"
    PUBLIC_RESTRICTED = "public_restricted"


class SecurityRequirements(BaseModel):
    """Security requirements extracted from intent."""

    auth_model: AuthModel = Field(default=AuthModel.MANAGED_IDENTITY, description="Authentication model")
    compliance_framework: ComplianceFramework = Field(
        default=ComplianceFramework.GENERAL, description="Compliance guidance to follow"
    )
    networking: NetworkingModel = Field(default=NetworkingModel.PRIVATE, description="Network exposure model")
    data_classification: str = Field(default="confidential", description="Data sensitivity level")
    encryption_at_rest: bool = Field(default=True, description="Require encryption at rest")
    encryption_in_transit: bool = Field(default=True, description="Require encryption in transit (HTTPS)")
    secret_management: bool = Field(default=True, description="Store secrets in Key Vault")
    enable_waf: bool = Field(default=False, description="Enable Web Application Firewall")


class ObservabilityRequirements(BaseModel):
    """Observability requirements."""

    log_analytics: bool = Field(default=True, description="Enable Log Analytics workspace")
    diagnostic_settings: bool = Field(default=True, description="Enable diagnostic settings on all resources")
    health_endpoint: bool = Field(default=True, description="Include health check endpoint")
    alerts: bool = Field(default=False, description="Configure alert rules")
    dashboard: bool = Field(default=False, description="Generate Azure Monitor dashboard")


class CICDRequirements(BaseModel):
    """CI/CD pipeline requirements."""

    validate_on_pr: bool = Field(default=True, description="Run validation on pull requests")
    deploy_on_merge: bool = Field(default=False, description="Auto-deploy on merge to main")
    manual_deploy: bool = Field(default=True, description="Support manual deployment trigger")
    oidc_auth: bool = Field(default=True, description="Use OIDC for Azure authentication in CI")
    artifact_upload: bool = Field(default=True, description="Upload scaffold as CI artifact")


class IntentSpec(BaseModel):
    """Strict schema representing a parsed business intent.

    Every field has a secure, enterprise-grade default. The intent parser
    fills in values from the user's natural language description, and the
    user can override any field.
    """

    # ── Core Identity ─────────────────────────────────────────────
    project_name: str = Field(..., description="Short kebab-case project name", pattern=r"^[a-z][a-z0-9-]{2,38}$")
    description: str = Field(..., description="One-sentence project description", max_length=200)
    raw_intent: str = Field(..., description="Original user intent text as provided")

    # ── Application ───────────────────────────────────────────────
    app_type: AppType = Field(default=AppType.API, description="Type of application to scaffold")
    language: str = Field(default="python", description="Primary programming language")
    framework: str = Field(default="fastapi", description="Application framework")
    compute_target: ComputeTarget = Field(
        default=ComputeTarget.CONTAINER_APPS,
        description="Azure compute target (container_apps, app_service, functions)",
    )
    data_stores: list[DataStore] = Field(
        default_factory=lambda: [DataStore.BLOB_STORAGE], description="Required data stores"
    )
    uses_ai: bool = Field(default=False, description="Whether the workload uses AI/ML services")

    # ── Security ──────────────────────────────────────────────────
    security: SecurityRequirements = Field(default_factory=SecurityRequirements)

    # ── Observability ─────────────────────────────────────────────
    observability: ObservabilityRequirements = Field(default_factory=ObservabilityRequirements)

    # ── CI/CD ─────────────────────────────────────────────────────
    cicd: CICDRequirements = Field(default_factory=CICDRequirements)

    # ── Azure Deployment Target ───────────────────────────────────
    azure_region: str = Field(default="eastus2", description="Azure deployment region")
    resource_group_name: str = Field(default="", description="Target resource group (auto-generated if empty)")
    environment: str = Field(default="dev", description="Deployment environment")

    # ── Agent Metadata ────────────────────────────────────────────
    assumptions: list[str] = Field(default_factory=list, description="Assumptions made during parsing")
    decisions: list[str] = Field(default_factory=list, description="Decisions made during planning")
    open_risks: list[str] = Field(default_factory=list, description="Identified open risks")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Agent confidence in interpretation")

    def model_post_init(self, __context: object) -> None:
        """Auto-generate resource group name if not provided."""
        if not self.resource_group_name:
            object.__setattr__(self, "resource_group_name", f"rg-{self.project_name}-{self.environment}")


class PlanOutput(BaseModel):
    """Output of the Architecture Planner agent."""

    title: str = Field(..., description="Architecture plan title")
    summary: str = Field(..., description="Executive summary of the architecture")
    components: list[ComponentSpec] = Field(..., description="Azure components in the architecture")
    decisions: list[ArchitectureDecision] = Field(..., description="Architecture Decision Records")
    threat_model: list[ThreatEntry] = Field(default_factory=list, description="Top threats identified")
    diagram_mermaid: str = Field(default="", description="Mermaid diagram source")


class ComponentSpec(BaseModel):
    """Specification for a single Azure component."""

    name: str = Field(..., description="Component name")
    azure_service: str = Field(..., description="Azure service (e.g., 'Azure Container Apps')")
    purpose: str = Field(..., description="Why this component exists")
    bicep_module: str = Field(..., description="Bicep module file name")
    security_controls: list[str] = Field(default_factory=list, description="Applied security controls")


class ArchitectureDecision(BaseModel):
    """An Architecture Decision Record (ADR) entry."""

    id: str = Field(..., description="Decision ID (e.g., ADR-001)")
    title: str = Field(..., description="Decision title")
    status: str = Field(default="Accepted", description="Status (Proposed, Accepted, Deprecated)")
    context: str = Field(..., description="Why this decision was needed")
    decision: str = Field(..., description="What was decided")
    consequences: str = Field(..., description="Impact of this decision")


class ThreatEntry(BaseModel):
    """A threat model entry."""

    id: str = Field(..., description="Threat ID (e.g., THREAT-001)")
    category: str = Field(..., description="STRIDE category")
    description: str = Field(..., description="Threat description")
    mitigation: str = Field(..., description="Mitigation strategy")
    residual_risk: str = Field(default="Low", description="Residual risk after mitigation")


class GovernanceReport(BaseModel):
    """Output of the Governance Reviewer agent."""

    status: str = Field(..., description="PASS or FAIL")
    checks: list[GovernanceCheck] = Field(..., description="Individual governance checks")
    summary: str = Field(..., description="Summary of governance findings")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations")


class GovernanceCheck(BaseModel):
    """Single governance validation check."""

    check_id: str = Field(..., description="Check ID")
    name: str = Field(..., description="Check name")
    passed: bool = Field(..., description="Whether the check passed")
    details: str = Field(..., description="Check details")
    severity: str = Field(default="medium", description="low, medium, high, critical")
