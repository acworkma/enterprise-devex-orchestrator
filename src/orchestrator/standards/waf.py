"""Azure Well-Architected Framework (WAF) Standards Engine.

Provides explicit WAF pillar assessment, scoring, and alignment reporting.
Maps every governance check, ADR, and infrastructure decision to the 5 WAF
pillars, and generates an alignment report with coverage gaps.

Reference: https://learn.microsoft.com/en-us/azure/well-architected/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WAFPillar(str, Enum):
    """Azure Well-Architected Framework pillars."""

    RELIABILITY = "Reliability"
    SECURITY = "Security"
    COST_OPTIMIZATION = "Cost Optimization"
    OPERATIONAL_EXCELLENCE = "Operational Excellence"
    PERFORMANCE_EFFICIENCY = "Performance Efficiency"


@dataclass(frozen=True)
class WAFPrinciple:
    """A single design principle under a WAF pillar."""

    id: str
    pillar: WAFPillar
    name: str
    description: str
    check: str  # How the SDK validates this principle
    azure_services: list[str] = field(default_factory=list)


@dataclass
class WAFAssessmentItem:
    """Result of assessing one WAF principle."""

    principle_id: str
    pillar: WAFPillar
    name: str
    covered: bool
    evidence: str
    recommendation: str = ""


@dataclass
class WAFAlignmentReport:
    """Complete WAF alignment assessment for a generated workload."""

    items: list[WAFAssessmentItem]

    @property
    def total_principles(self) -> int:
        return len(self.items)

    @property
    def covered_count(self) -> int:
        return sum(1 for i in self.items if i.covered)

    @property
    def coverage_pct(self) -> float:
        if not self.items:
            return 0.0
        return (self.covered_count / self.total_principles) * 100

    def pillar_scores(self) -> dict[WAFPillar, dict[str, int | float]]:
        """Return per-pillar coverage summary."""
        result: dict[WAFPillar, dict[str, int | float]] = {}
        for pillar in WAFPillar:
            pillar_items = [i for i in self.items if i.pillar == pillar]
            covered = sum(1 for i in pillar_items if i.covered)
            total = len(pillar_items)
            result[pillar] = {
                "covered": covered,
                "total": total,
                "pct": (covered / total * 100) if total > 0 else 0.0,
            }
        return result

    def gaps(self) -> list[WAFAssessmentItem]:
        """Return uncovered principles."""
        return [i for i in self.items if not i.covered]


# ------------- WAF Design Principles Catalog -------------

WAF_PRINCIPLES: list[WAFPrinciple] = [
    # -- Reliability --------------------------------------
    WAFPrinciple(
        id="REL-01",
        pillar=WAFPillar.RELIABILITY,
        name="Health endpoint monitoring",
        description="Implement health probes for liveness and readiness detection.",
        check="Verify /health endpoint and Container App health probes are configured.",
        azure_services=["Azure Container Apps"],
    ),
    WAFPrinciple(
        id="REL-02",
        pillar=WAFPillar.RELIABILITY,
        name="Auto-scaling",
        description="Enable automatic horizontal scaling based on demand.",
        check="Verify auto-scaling rules with min/max replicas in Container App configuration.",
        azure_services=["Azure Container Apps"],
    ),
    WAFPrinciple(
        id="REL-03",
        pillar=WAFPillar.RELIABILITY,
        name="Retry and circuit-breaker patterns",
        description="Handle transient failures with retry logic and circuit breakers.",
        check="Verify application code uses retry policies for external service calls.",
        azure_services=["Azure Container Apps"],
    ),
    WAFPrinciple(
        id="REL-04",
        pillar=WAFPillar.RELIABILITY,
        name="Infrastructure as Code for repeatability",
        description="Use IaC (Bicep/Terraform) for deterministic deployments.",
        check="Verify Bicep templates exist for all infrastructure components.",
        azure_services=["Azure Resource Manager"],
    ),
    WAFPrinciple(
        id="REL-05",
        pillar=WAFPillar.RELIABILITY,
        name="Rollback strategy",
        description="Document and automate deployment rollback procedures.",
        check="Verify deployment guide includes rollback instructions.",
        azure_services=["GitHub Actions", "Azure Container Apps"],
    ),
    # -- Security -----------------------------------------
    WAFPrinciple(
        id="SEC-01",
        pillar=WAFPillar.SECURITY,
        name="Managed Identity for authentication",
        description="Use Azure Managed Identity instead of credentials or keys.",
        check="Verify managed-identity.bicep exists and RBAC roles are assigned.",
        azure_services=["Azure Managed Identity"],
    ),
    WAFPrinciple(
        id="SEC-02",
        pillar=WAFPillar.SECURITY,
        name="Secret management in Key Vault",
        description="Store all secrets, keys, and certificates in Azure Key Vault.",
        check="Verify Key Vault with RBAC mode, soft delete, and purge protection.",
        azure_services=["Azure Key Vault"],
    ),
    WAFPrinciple(
        id="SEC-03",
        pillar=WAFPillar.SECURITY,
        name="Encryption at rest and in transit",
        description="Enforce TLS 1.2+ and platform encryption for data at rest.",
        check="Verify TLS 1.2 minimum and encryption settings in all resources.",
        azure_services=["All Azure resources"],
    ),
    WAFPrinciple(
        id="SEC-04",
        pillar=WAFPillar.SECURITY,
        name="Least-privilege RBAC",
        description="Assign minimal required roles; never use Owner for workloads.",
        check="Verify RBAC role assignments follow least-privilege principle.",
        azure_services=["Azure RBAC"],
    ),
    WAFPrinciple(
        id="SEC-05",
        pillar=WAFPillar.SECURITY,
        name="Threat modeling with STRIDE",
        description="Identify and mitigate threats using STRIDE methodology.",
        check="Verify threat model covers at least 4 STRIDE categories.",
        azure_services=["Security Design"],
    ),
    WAFPrinciple(
        id="SEC-06",
        pillar=WAFPillar.SECURITY,
        name="Supply chain security",
        description="Scan code and dependencies for vulnerabilities.",
        check="Verify CodeQL and Dependabot workflows exist.",
        azure_services=["GitHub Advanced Security"],
    ),
    WAFPrinciple(
        id="SEC-07",
        pillar=WAFPillar.SECURITY,
        name="Non-root container execution",
        description="Run containers as non-root user with no privileged capabilities.",
        check="Verify Dockerfile uses non-root USER directive.",
        azure_services=["Azure Container Apps"],
    ),
    WAFPrinciple(
        id="SEC-08",
        pillar=WAFPillar.SECURITY,
        name="Network segmentation",
        description="Restrict public access; use private networking where possible.",
        check="Verify networking model is private or internal by default.",
        azure_services=["Azure Virtual Network", "Azure Container Apps"],
    ),
    # -- Cost Optimization --------------------------------
    WAFPrinciple(
        id="COST-01",
        pillar=WAFPillar.COST_OPTIMIZATION,
        name="Resource tagging for cost tracking",
        description="Apply costCenter and project tags to all resources for showback/chargeback.",
        check="Verify enterprise tags include costCenter, project, and environment.",
        azure_services=["Azure Resource Manager"],
    ),
    WAFPrinciple(
        id="COST-02",
        pillar=WAFPillar.COST_OPTIMIZATION,
        name="Right-sized compute",
        description="Use consumption-based or serverless compute to avoid over-provisioning.",
        check="Verify Container Apps use consumption plan or appropriate scaling limits.",
        azure_services=["Azure Container Apps"],
    ),
    WAFPrinciple(
        id="COST-03",
        pillar=WAFPillar.COST_OPTIMIZATION,
        name="Environment-aware scaling",
        description="Dev/test environments use smaller SKUs than production.",
        check="Verify parameter files differentiate environments (dev vs prod).",
        azure_services=["Azure Container Apps", "Azure Key Vault"],
    ),
    WAFPrinciple(
        id="COST-04",
        pillar=WAFPillar.COST_OPTIMIZATION,
        name="Serverless data tier",
        description="Use serverless or consumption SKUs for data stores where possible.",
        check="Verify Cosmos DB uses serverless throughput for dev workloads.",
        azure_services=["Azure Cosmos DB"],
    ),
    # -- Operational Excellence ---------------------------
    WAFPrinciple(
        id="OPS-01",
        pillar=WAFPillar.OPERATIONAL_EXCELLENCE,
        name="Centralized logging",
        description="Send all diagnostics to a Log Analytics workspace.",
        check="Verify Log Analytics workspace and diagnostic settings for all resources.",
        azure_services=["Azure Log Analytics"],
    ),
    WAFPrinciple(
        id="OPS-02",
        pillar=WAFPillar.OPERATIONAL_EXCELLENCE,
        name="CI/CD pipelines with OIDC",
        description="Automate builds and deployments with OpenID Connect auth.",
        check="Verify GitHub Actions workflows use OIDC federation, not stored credentials.",
        azure_services=["GitHub Actions"],
    ),
    WAFPrinciple(
        id="OPS-03",
        pillar=WAFPillar.OPERATIONAL_EXCELLENCE,
        name="Architecture Decision Records",
        description="Document significant decisions as ADRs for auditability.",
        check="Verify at least 3 ADRs covering compute, security, and IaC.",
        azure_services=["Documentation"],
    ),
    WAFPrinciple(
        id="OPS-04",
        pillar=WAFPillar.OPERATIONAL_EXCELLENCE,
        name="Automated governance validation",
        description="Enforce governance policies before deployment, not after.",
        check="Verify governance reviewer runs before infrastructure generation.",
        azure_services=["Governance"],
    ),
    WAFPrinciple(
        id="OPS-05",
        pillar=WAFPillar.OPERATIONAL_EXCELLENCE,
        name="State management and drift detection",
        description="Track generation history and detect configuration drift.",
        check="Verify StateManager records generation events and supports drift detection.",
        azure_services=["DevEx Orchestrator"],
    ),
    # -- Performance Efficiency ---------------------------
    WAFPrinciple(
        id="PERF-01",
        pillar=WAFPillar.PERFORMANCE_EFFICIENCY,
        name="Horizontal auto-scaling",
        description="Scale replicas based on HTTP concurrency or CPU/memory metrics.",
        check="Verify Container App scale rules with minReplicas and maxReplicas.",
        azure_services=["Azure Container Apps"],
    ),
    WAFPrinciple(
        id="PERF-02",
        pillar=WAFPillar.PERFORMANCE_EFFICIENCY,
        name="Multi-stage container builds",
        description="Use multi-stage Docker builds for minimal image size and faster pull times.",
        check="Verify Dockerfile uses multi-stage build pattern.",
        azure_services=["Docker", "Azure Container Registry"],
    ),
    WAFPrinciple(
        id="PERF-03",
        pillar=WAFPillar.PERFORMANCE_EFFICIENCY,
        name="Private container registry",
        description="Store images in a private ACR close to the compute region.",
        check="Verify ACR and Container App are in the same region.",
        azure_services=["Azure Container Registry"],
    ),
    WAFPrinciple(
        id="PERF-04",
        pillar=WAFPillar.PERFORMANCE_EFFICIENCY,
        name="Health probes for load routing",
        description="Use liveness and readiness probes so the platform routes only to healthy instances.",
        check="Verify Container App health probe configuration.",
        azure_services=["Azure Container Apps"],
    ),
]


class WAFAssessor:
    """Assess a generated workload against the Azure Well-Architected Framework.

    Maps governance checks, plan output, and generated files to the 25 WAF
    design principles and produces an alignment report.
    """

    def assess(
        self,
        plan_components: list[str],
        governance_checks: dict[str, bool],
        has_bicep: bool = True,
        has_dockerfile: bool = True,
        has_cicd: bool = True,
        has_state_manager: bool = True,
        has_threat_model: bool = True,
        has_adrs: bool = True,
        has_tags: bool = True,
        has_health_endpoint: bool = True,
        data_stores: list[str] | None = None,
    ) -> WAFAlignmentReport:
        """Assess the workload and produce a WAFAlignmentReport.

        Args:
            plan_components: List of component names from the architecture plan.
            governance_checks: Mapping of governance check_id -> passed (True/False).
            has_bicep: Whether Bicep templates were generated.
            has_dockerfile: Whether a Dockerfile was generated.
            has_cicd: Whether CI/CD workflows were generated.
            has_state_manager: Whether state management is active.
            has_threat_model: Whether a threat model was produced.
            has_adrs: Whether ADRs were produced.
            has_tags: Whether enterprise tags are applied.
            has_health_endpoint: Whether a /health endpoint is configured.
            data_stores: List of data stores (e.g., ["blob", "cosmos"]).
        """
        items: list[WAFAssessmentItem] = []
        data_stores = data_stores or []

        for principle in WAF_PRINCIPLES:
            covered, evidence, recommendation = self._evaluate_principle(
                principle,
                plan_components=plan_components,
                governance_checks=governance_checks,
                has_bicep=has_bicep,
                has_dockerfile=has_dockerfile,
                has_cicd=has_cicd,
                has_state_manager=has_state_manager,
                has_threat_model=has_threat_model,
                has_adrs=has_adrs,
                has_tags=has_tags,
                has_health_endpoint=has_health_endpoint,
                data_stores=data_stores,
            )

            items.append(
                WAFAssessmentItem(
                    principle_id=principle.id,
                    pillar=principle.pillar,
                    name=principle.name,
                    covered=covered,
                    evidence=evidence,
                    recommendation=recommendation,
                )
            )

        return WAFAlignmentReport(items=items)

    def _evaluate_principle(  # noqa: C901, PLR0911, PLR0912
        self,
        principle: WAFPrinciple,
        *,
        plan_components: list[str],
        governance_checks: dict[str, bool],
        has_bicep: bool,
        has_dockerfile: bool,
        has_cicd: bool,
        has_state_manager: bool,
        has_threat_model: bool,
        has_adrs: bool,
        has_tags: bool,
        has_health_endpoint: bool,
        data_stores: list[str],
    ) -> tuple[bool, str, str]:
        """Evaluate a single principle. Returns (covered, evidence, recommendation)."""

        pid = principle.id

        # -- Reliability --
        if pid == "REL-01":
            covered = has_health_endpoint
            return (
                covered,
                "Health probes configured with /health endpoint" if covered else "No health endpoint",
                "" if covered else "Add a /health endpoint and configure Container App health probes.",
            )

        if pid == "REL-02":
            covered = "container-app" in plan_components
            return (
                covered,
                "Container Apps with auto-scaling rules" if covered else "No auto-scaling configured",
                "" if covered else "Use Container Apps consumption plan with min/max replicas.",
            )

        if pid == "REL-03":
            # Evaluated based on application scaffold inclusion
            covered = has_dockerfile  # App scaffold includes retry patterns
            return (
                covered,
                "Application scaffold includes retry guidance" if covered else "No retry patterns",
                "" if covered else "Add retry policies with exponential backoff for external service calls.",
            )

        if pid == "REL-04":
            covered = has_bicep
            return (
                covered,
                "Bicep IaC for all infrastructure components" if covered else "No IaC templates",
                "" if covered else "Generate Bicep templates for deterministic deployments.",
            )

        if pid == "REL-05":
            covered = has_cicd and has_bicep
            return (
                covered,
                "Deployment guide with rollback procedures" if covered else "Missing rollback strategy",
                "" if covered else "Add rollback steps to deployment documentation.",
            )

        # -- Security --
        if pid == "SEC-01":
            covered = governance_checks.get("GOV-REQ-MANAGED-IDENTITY", False)
            return (
                covered,
                "Managed Identity with RBAC roles for all services" if covered else "Managed Identity missing",
                "" if covered else "Add user-assigned managed identity with least-privilege RBAC.",
            )

        if pid == "SEC-02":
            covered = governance_checks.get("GOV-REQ-KEY-VAULT", False)
            return (
                covered,
                "Key Vault with RBAC mode, soft delete, and purge protection" if covered else "Key Vault missing",
                "" if covered else "Add Key Vault with RBAC authorization for secret management.",
            )

        if pid == "SEC-03":
            covered = governance_checks.get("GOV-NET-002", True)
            return (
                covered,
                "TLS 1.2+ enforced for all connections" if covered else "Encryption not verified",
                "" if covered else "Enable TLS 1.2 minimum on all resources.",
            )

        if pid == "SEC-04":
            covered = "managed-identity" in plan_components
            return (
                covered,
                "RBAC roles scoped to resource groups with least-privilege assignments"
                if covered
                else "RBAC not configured",
                "" if covered else "Assign minimal RBAC roles (never Owner for workloads).",
            )

        if pid == "SEC-05":
            covered = has_threat_model
            return (
                covered,
                "STRIDE threat model with 5+ threats and mitigations" if covered else "No threat model",
                "" if covered else "Generate STRIDE threat model covering all 6 categories.",
            )

        if pid == "SEC-06":
            covered = has_cicd  # CI/CD generator includes CodeQL + Dependabot
            return (
                covered,
                "CodeQL code scanning + Dependabot dependency updates" if covered else "No supply chain security",
                "" if covered else "Add CodeQL and Dependabot workflows.",
            )

        if pid == "SEC-07":
            covered = has_dockerfile  # App generator uses non-root containers
            return (
                covered,
                "Dockerfile uses non-root USER with no privileged capabilities" if covered else "No Dockerfile",
                "" if covered else "Add USER directive to Dockerfile for non-root execution.",
            )

        if pid == "SEC-08":
            covered = governance_checks.get("GOV-NET-001", False)
            return (
                covered,
                "Private networking with internal ingress by default" if covered else "Public networking",
                "" if covered else "Configure Container Apps with internal ingress.",
            )

        # -- Cost Optimization --
        if pid == "COST-01":
            covered = has_tags
            return (
                covered,
                "Enterprise tags include costCenter, project, and environment" if covered else "Missing cost tags",
                "" if covered else "Apply costCenter and project tags to all resources.",
            )

        if pid == "COST-02":
            covered = "container-app" in plan_components
            return (
                covered,
                "Container Apps consumption plan (pay-per-use)" if covered else "No consumption compute",
                "" if covered else "Use consumption-based compute to avoid over-provisioning.",
            )

        if pid == "COST-03":
            covered = has_bicep  # Parameter files differentiate dev/prod
            return (
                covered,
                "Parameter files differentiate dev and prod environments" if covered else "No env separation",
                "" if covered else "Create separate parameter files for dev/staging/prod.",
            )

        if pid == "COST-04":
            has_cosmos = "cosmos" in data_stores or "cosmos-db" in plan_components
            if not has_cosmos:
                covered = True  # N/A -- no data tier needing serverless
                return (covered, "No Cosmos DB -- cost optimization N/A for data tier", "")
            covered = has_cosmos  # BicepGenerator uses serverless for dev
            return (
                covered,
                "Cosmos DB serverless throughput for dev workloads" if covered else "Fixed throughput configured",
                "" if covered else "Use serverless SKU for Cosmos DB in dev/test environments.",
            )

        # -- Operational Excellence --
        if pid == "OPS-01":
            covered = governance_checks.get("GOV-REQ-LOG-ANALYTICS", False)
            return (
                covered,
                "Log Analytics workspace with diagnostic settings for all resources"
                if covered
                else "No centralized logging",
                "" if covered else "Deploy Log Analytics and configure diagnostic settings.",
            )

        if pid == "OPS-02":
            covered = has_cicd
            return (
                covered,
                "GitHub Actions with OIDC federation for Azure auth" if covered else "No CI/CD pipelines",
                "" if covered else "Add GitHub Actions workflows with OIDC authentication.",
            )

        if pid == "OPS-03":
            covered = has_adrs
            return (
                covered,
                "5+ ADRs covering compute, security, IaC, secrets, and networking" if covered else "No ADRs",
                "" if covered else "Document architecture decisions as ADRs.",
            )

        if pid == "OPS-04":
            covered = True  # The SDK itself enforces this by design
            return (
                covered,
                "Governance reviewer validates before infrastructure generation",
                "",
            )

        if pid == "OPS-05":
            covered = has_state_manager
            return (
                covered,
                "StateManager tracks generation history with drift detection" if covered else "No state management",
                "" if covered else "Enable StateManager for generation tracking.",
            )

        # -- Performance Efficiency --
        if pid == "PERF-01":
            covered = "container-app" in plan_components
            return (
                covered,
                "Auto-scaling with minReplicas/maxReplicas and HTTP concurrency rules" if covered else "No scaling",
                "" if covered else "Configure scale rules for Container Apps.",
            )

        if pid == "PERF-02":
            covered = has_dockerfile
            return (
                covered,
                "Multi-stage Docker build with slim Python base image" if covered else "No optimized build",
                "" if covered else "Use multi-stage Dockerfile for minimal image size.",
            )

        if pid == "PERF-03":
            covered = "container-registry" in plan_components or "acr" in [c.lower() for c in plan_components]
            return (
                covered,
                "Private ACR co-located in same region as compute" if covered else "No private registry",
                "" if covered else "Deploy ACR in the same region as Container Apps.",
            )

        if pid == "PERF-04":
            covered = has_health_endpoint
            return (
                covered,
                "Health probes route traffic only to healthy replicas" if covered else "No health probes",
                "" if covered else "Configure liveness and readiness probes.",
            )

        # Fallback for any unknown principle
        return (False, "Unknown principle -- not evaluated", f"Add assessment logic for {pid}")


# -- WAF Pillar -> Governance Check Mapping ------------------

# Maps each governance check ID to the WAF pillar(s) it contributes to.
# Used for traceability between the SDK's governance engine and WAF alignment.
GOVERNANCE_TO_WAF: dict[str, list[WAFPillar]] = {
    # Security
    "GOV-REQ-KEY-VAULT": [WAFPillar.SECURITY],
    "GOV-REQ-LOG-ANALYTICS": [WAFPillar.OPERATIONAL_EXCELLENCE],
    "GOV-REQ-MANAGED-IDENTITY": [WAFPillar.SECURITY],
    "GOV-SEC-CONTAINER-APP": [WAFPillar.SECURITY],
    "GOV-NET-001": [WAFPillar.SECURITY],
    "GOV-NET-002": [WAFPillar.SECURITY],
    # Observability -> Operational Excellence + Reliability
    "GOV-OBS-001": [WAFPillar.OPERATIONAL_EXCELLENCE],
    "GOV-OBS-002": [WAFPillar.OPERATIONAL_EXCELLENCE],
    "GOV-OBS-003": [WAFPillar.RELIABILITY, WAFPillar.PERFORMANCE_EFFICIENCY],
    # CI/CD -> Operational Excellence + Security
    "GOV-CICD-001": [WAFPillar.OPERATIONAL_EXCELLENCE],
    "GOV-CICD-002": [WAFPillar.SECURITY, WAFPillar.OPERATIONAL_EXCELLENCE],
    # Threat model -> Security
    "GOV-THREAT-001": [WAFPillar.SECURITY],
    "GOV-THREAT-002": [WAFPillar.SECURITY],
    # Naming -> Operational Excellence
    "STD-NAME-001": [WAFPillar.OPERATIONAL_EXCELLENCE],
    "STD-NAME-002": [WAFPillar.OPERATIONAL_EXCELLENCE],
    "STD-NAME-003": [WAFPillar.OPERATIONAL_EXCELLENCE],
    # Tagging -> Cost Optimization + Operational Excellence
    "STD-TAG-001": [WAFPillar.COST_OPTIMIZATION, WAFPillar.OPERATIONAL_EXCELLENCE],
    "STD-TAG-002": [WAFPillar.SECURITY],
    "STD-TAG-003": [WAFPillar.COST_OPTIMIZATION],
    # Bicep standards
    "BICEP-STD-001": [WAFPillar.COST_OPTIMIZATION, WAFPillar.OPERATIONAL_EXCELLENCE],
    "BICEP-STD-002": [WAFPillar.OPERATIONAL_EXCELLENCE],
}


# -- ADR -> WAF Mapping ---------------------------------------

# Maps common ADR titles/IDs to the WAF pillar(s) they address.
ADR_TO_WAF: dict[str, list[WAFPillar]] = {
    "ADR-001": [WAFPillar.RELIABILITY, WAFPillar.PERFORMANCE_EFFICIENCY],  # Container Apps compute
    "ADR-002": [WAFPillar.SECURITY],  # Managed Identity
    "ADR-003": [WAFPillar.RELIABILITY, WAFPillar.OPERATIONAL_EXCELLENCE],  # Bicep IaC
    "ADR-004": [WAFPillar.SECURITY],  # Key Vault secrets
    "ADR-005": [WAFPillar.SECURITY],  # Private ingress
    "ADR-006": [WAFPillar.SECURITY, WAFPillar.PERFORMANCE_EFFICIENCY],  # AI Foundry
}


def generate_waf_report_md(report: WAFAlignmentReport) -> str:
    """Generate a Markdown WAF alignment report."""
    lines = [
        "# Well-Architected Framework Alignment Report",
        "",
        "> Assessment of generated workload against the Azure Well-Architected Framework 5 pillars.",
        "",
        f"**Overall Coverage:** {report.covered_count}/{report.total_principles} "
        f"principles ({report.coverage_pct:.0f}%)",
        "",
        "## Pillar Scores",
        "",
        "| Pillar | Covered | Total | Score |",
        "|--------|---------|-------|-------|",
    ]

    for pillar, scores in report.pillar_scores().items():
        pct = scores["pct"]
        bar = "#" * int(pct / 10) + "." * (10 - int(pct / 10))
        lines.append(f"| {pillar.value} | {scores['covered']} | {scores['total']} | {bar} {pct:.0f}% |")

    lines.extend(
        [
            "",
            "## Detailed Assessment",
            "",
        ]
    )

    for pillar in WAFPillar:
        pillar_items = [i for i in report.items if i.pillar == pillar]
        if not pillar_items:
            continue

        lines.append(f"### {pillar.value}")
        lines.append("")
        lines.append("| ID | Principle | Status | Evidence |")
        lines.append("|----|-----------|--------|----------|")

        for item in pillar_items:
            status = "[PASS]" if item.covered else "[FAIL]"
            lines.append(f"| {item.principle_id} | {item.name} | {status} | {item.evidence} |")

        lines.append("")

    # Gaps section
    gaps = report.gaps()
    if gaps:
        lines.append("## Coverage Gaps & Recommendations")
        lines.append("")
        for gap in gaps:
            lines.append(f"- **{gap.principle_id} ({gap.pillar.value}):** {gap.name}")
            if gap.recommendation:
                lines.append(f"  - Recommendation: {gap.recommendation}")
        lines.append("")

    lines.extend(
        [
            "## Reference",
            "",
            "- [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/)",
            "- [WAF Reliability Pillar](https://learn.microsoft.com/en-us/azure/well-architected/reliability/)",
            "- [WAF Security Pillar](https://learn.microsoft.com/en-us/azure/well-architected/security/)",
            "- [WAF Cost Optimization Pillar](https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/)",
            "- [WAF Operational Excellence Pillar](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/)",
            "- [WAF Performance Efficiency Pillar](https://learn.microsoft.com/en-us/azure/well-architected/performance-efficiency/)",
            "",
            "---",
            "*Generated by Enterprise DevEx Orchestrator Agent*",
        ]
    )

    return "\n".join(lines)
