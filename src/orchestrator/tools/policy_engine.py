"""Policy Engine Tool — enterprise governance policy evaluation.

Provides tools for the agent runtime to enforce organizational policies:
    - check_policy: Evaluate a component against policy rules
    - list_policies: List all active governance policies
    - explain_policy: Get detailed explanation of a policy
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


class Severity(str, Enum):
    """Policy violation severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class PolicyRule:
    """A single governance policy rule."""

    id: str
    name: str
    description: str
    severity: Severity
    category: str
    check: str  # Human-readable check description
    remediation: str


# ───────────── Enterprise Policy Catalog ─────────────

POLICY_CATALOG: list[PolicyRule] = [
    PolicyRule(
        id="SEC-001",
        name="Managed Identity Required",
        description="All Azure services must use Managed Identity for authentication. No connection strings or keys in application code.",
        severity=Severity.ERROR,
        category="Identity",
        check="Verify managed-identity.bicep exists and is referenced by all services.",
        remediation="Add a user-assigned managed identity and assign RBAC roles to each service.",
    ),
    PolicyRule(
        id="SEC-002",
        name="Key Vault for Secrets",
        description="All secrets, connection strings, and API keys must be stored in Azure Key Vault.",
        severity=Severity.ERROR,
        category="Secrets",
        check="Verify keyvault.bicep exists with RBAC authorization and soft delete enabled.",
        remediation="Deploy Key Vault with RBAC mode, soft delete, and purge protection.",
    ),
    PolicyRule(
        id="SEC-003",
        name="TLS 1.2 Minimum",
        description="All services must enforce TLS 1.2 or higher for inbound and outbound connections.",
        severity=Severity.ERROR,
        category="Encryption",
        check="Verify minTlsVersion is set to '1.2' in all applicable resources.",
        remediation="Set minTlsVersion: '1.2' in Container App, Storage Account, and Key Vault configurations.",
    ),
    PolicyRule(
        id="SEC-004",
        name="No Public Blob Access",
        description="Storage Accounts must not allow public blob access.",
        severity=Severity.ERROR,
        category="Networking",
        check="Verify allowBlobPublicAccess is false in storage.bicep.",
        remediation="Set allowBlobPublicAccess: false in storage account properties.",
    ),
    PolicyRule(
        id="OPS-001",
        name="Log Analytics Workspace",
        description="All workloads must send diagnostics to a Log Analytics workspace.",
        severity=Severity.ERROR,
        category="Observability",
        check="Verify log-analytics.bicep exists and diagnosticSettings are configured.",
        remediation="Deploy Log Analytics workspace and add diagnosticSettings to all resources.",
    ),
    PolicyRule(
        id="OPS-002",
        name="Health Endpoint Required",
        description="All services must expose a /health endpoint for monitoring and probes.",
        severity=Severity.ERROR,
        category="Observability",
        check="Verify application includes a /health endpoint and Container App has healthProbes configured.",
        remediation="Add a /health endpoint to the application and configure liveness/readiness probes.",
    ),
    PolicyRule(
        id="OPS-003",
        name="Container Registry Required",
        description="Container images must be stored in a private Azure Container Registry.",
        severity=Severity.WARNING,
        category="Supply Chain",
        check="Verify container-registry.bicep exists with AcrPull role assigned to managed identity.",
        remediation="Deploy ACR and assign AcrPull role to the workload's managed identity.",
    ),
    PolicyRule(
        id="CICD-001",
        name="OIDC Authentication for CI/CD",
        description="GitHub Actions must use OIDC federation for Azure authentication. No stored credentials.",
        severity=Severity.ERROR,
        category="CI/CD",
        check="Verify GitHub Actions workflows use azure/login with OIDC (no secrets for credentials).",
        remediation="Configure OIDC federation between GitHub and Azure AD for the deployment service principal.",
    ),
    PolicyRule(
        id="CICD-002",
        name="Deployment Requires Approval",
        description="Production deployments must require manual approval via GitHub environment protection.",
        severity=Severity.WARNING,
        category="CI/CD",
        check="Verify deploy workflow uses environment with protection rules.",
        remediation="Add environment protection rules in GitHub repository settings.",
    ),
    PolicyRule(
        id="CICD-003",
        name="Code Scanning Enabled",
        description="Repository must include CodeQL or equivalent code scanning.",
        severity=Severity.WARNING,
        category="Supply Chain",
        check="Verify codeql.yml workflow exists in .github/workflows/.",
        remediation="Add CodeQL analysis workflow with appropriate language configuration.",
    ),
    PolicyRule(
        id="GOV-001",
        name="Architecture Decision Records",
        description="All significant architecture decisions must be documented as ADRs.",
        severity=Severity.WARNING,
        category="Governance",
        check="Verify plan.md contains at least 3 ADRs covering compute, security, and IaC choices.",
        remediation="Document architecture decisions using ADR format in docs/plan.md.",
    ),
    PolicyRule(
        id="GOV-002",
        name="Threat Model Required",
        description="Every workload must include a STRIDE-based threat model.",
        severity=Severity.ERROR,
        category="Governance",
        check="Verify plan output includes threat_model with at least 4 entries covering major STRIDE categories.",
        remediation="Generate STRIDE threat model covering Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, and Elevation of Privilege.",
    ),
    PolicyRule(
        id="STD-001",
        name="Azure CAF Naming Convention",
        description="All Azure resources must follow Azure Cloud Adoption Framework naming conventions: {type}-{workload}-{env}-{region}.",
        severity=Severity.ERROR,
        category="Standards",
        check="Verify resource names follow the pattern: rg-, kv-, law-, id-, cr, ca-, cae-, st prefix conventions.",
        remediation="Use the NamingEngine to generate compliant names. See docs/standards.md for the full naming reference.",
    ),
    PolicyRule(
        id="STD-002",
        name="Enterprise Tagging Standard",
        description="All Azure resources must include required enterprise tags: project, environment, costCenter, owner, managedBy, createdBy, dataSensitivity.",
        severity=Severity.ERROR,
        category="Standards",
        check="Verify all Bicep templates include the 7 required enterprise tags in the tags variable.",
        remediation="Add all required tags to the Bicep tags variable. See docs/standards.md for the full tag catalog.",
    ),
    PolicyRule(
        id="STD-003",
        name="Region Abbreviation Standard",
        description="Resource names must use standard Azure region abbreviations (e.g., eastus2 → eus2).",
        severity=Severity.WARNING,
        category="Standards",
        check="Verify resource names include recognized region abbreviations.",
        remediation="Use the NamingEngine region abbreviation lookup for consistent short codes.",
    ),
    PolicyRule(
        id="WAF-001",
        name="Well-Architected Reliability",
        description="Workload must address WAF Reliability pillar: health probes, auto-scaling, IaC repeatability, and rollback strategy.",
        severity=Severity.WARNING,
        category="Well-Architected",
        check="Verify health endpoints, auto-scaling rules, Bicep IaC, and rollback documentation exist.",
        remediation="Run WAF assessment and address all Reliability pillar gaps. See docs/waf-report.md.",
    ),
    PolicyRule(
        id="WAF-002",
        name="Well-Architected Security",
        description="Workload must address WAF Security pillar: Managed Identity, Key Vault, STRIDE threat model, supply chain security, non-root containers.",
        severity=Severity.ERROR,
        category="Well-Architected",
        check="Verify Managed Identity, Key Vault RBAC, STRIDE model, CodeQL, and Dockerfile non-root USER.",
        remediation="Run WAF assessment and address all Security pillar gaps. See docs/waf-report.md.",
    ),
    PolicyRule(
        id="WAF-003",
        name="Well-Architected Cost Optimization",
        description="Workload must address WAF Cost Optimization pillar: resource tagging, consumption compute, environment-aware sizing.",
        severity=Severity.WARNING,
        category="Well-Architected",
        check="Verify enterprise tags with costCenter, consumption-based compute, and environment-specific parameters.",
        remediation="Run WAF assessment and address all Cost Optimization pillar gaps. See docs/waf-report.md.",
    ),
    PolicyRule(
        id="WAF-004",
        name="Well-Architected Operational Excellence",
        description="Workload must address WAF Operational Excellence pillar: centralized logging, CI/CD with OIDC, ADRs, governance validation.",
        severity=Severity.WARNING,
        category="Well-Architected",
        check="Verify Log Analytics, GitHub Actions OIDC, ADRs, and governance reviewer integration.",
        remediation="Run WAF assessment and address all Operational Excellence pillar gaps. See docs/waf-report.md.",
    ),
    PolicyRule(
        id="WAF-005",
        name="Well-Architected Performance Efficiency",
        description="Workload must address WAF Performance Efficiency pillar: auto-scaling, multi-stage builds, private registry, health probes.",
        severity=Severity.WARNING,
        category="Well-Architected",
        check="Verify Container App scaling rules, multi-stage Dockerfile, ACR, and health probe configuration.",
        remediation="Run WAF assessment and address all Performance Efficiency pillar gaps. See docs/waf-report.md.",
    ),
]


def check_policy(component_description: str, policy_id: str | None = None) -> str:
    """Evaluate a component against governance policies.

    Args:
        component_description: Description of the component or architecture to check.
        policy_id: Specific policy ID to check (optional, checks all if omitted).

    Returns:
        JSON string with policy evaluation results.
    """
    logger.info("tool.check_policy", policy_id=policy_id)

    policies = POLICY_CATALOG
    if policy_id:
        policies = [p for p in policies if p.id == policy_id]
        if not policies:
            return json.dumps({"error": f"Policy {policy_id} not found."})

    results = []
    desc_lower = component_description.lower()

    for policy in policies:
        # Simple keyword-based evaluation
        compliant = False

        if policy.category == "Identity":
            compliant = "managed identity" in desc_lower or "managed-identity" in desc_lower
        elif policy.category == "Secrets":
            compliant = "key vault" in desc_lower or "keyvault" in desc_lower
        elif policy.category == "Encryption":
            compliant = "tls" in desc_lower or "encryption" in desc_lower
        elif policy.category == "Networking":
            compliant = "private" in desc_lower or "no public" in desc_lower
        elif policy.category == "Observability":
            compliant = "log analytics" in desc_lower or "health" in desc_lower or "diagnostics" in desc_lower
        elif policy.category == "Supply Chain":
            compliant = "container registry" in desc_lower or "codeql" in desc_lower or "acr" in desc_lower
        elif policy.category == "CI/CD":
            compliant = "oidc" in desc_lower or "github actions" in desc_lower
        elif policy.category == "Governance":
            compliant = "adr" in desc_lower or "threat model" in desc_lower
        elif policy.category == "Standards":
            compliant = (
                "naming" in desc_lower
                or "caf" in desc_lower
                or "tagging" in desc_lower
                or "costcenter" in desc_lower
                or "datasensitivity" in desc_lower
            )

        results.append(
            {
                "policy_id": policy.id,
                "name": policy.name,
                "severity": policy.severity.value,
                "compliant": compliant,
                "remediation": policy.remediation if not compliant else None,
            }
        )

    violations = [r for r in results if not r["compliant"]]
    return json.dumps(
        {
            "total_policies": len(results),
            "compliant": len(results) - len(violations),
            "violations": len(violations),
            "results": results,
        },
        indent=2,
    )


def list_policies(category: str | None = None) -> str:
    """List all active governance policies.

    Args:
        category: Filter by category (optional).

    Returns:
        JSON string with policy list.
    """
    policies = POLICY_CATALOG
    if category:
        policies = [p for p in policies if p.category.lower() == category.lower()]

    return json.dumps(
        {
            "total": len(policies),
            "policies": [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "severity": p.severity.value,
                    "description": p.description,
                }
                for p in policies
            ],
        },
        indent=2,
    )


def explain_policy(policy_id: str) -> str:
    """Get detailed explanation of a specific policy.

    Args:
        policy_id: The policy ID (e.g., 'SEC-001').

    Returns:
        JSON string with full policy details.
    """
    for p in POLICY_CATALOG:
        if p.id == policy_id:
            return json.dumps(
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "severity": p.severity.value,
                    "category": p.category,
                    "check": p.check,
                    "remediation": p.remediation,
                },
                indent=2,
            )

    return json.dumps({"error": f"Policy {policy_id} not found."})


# Tool definitions for agent registration
POLICY_ENGINE_TOOLS = [
    {
        "name": "check_policy",
        "description": "Evaluate an architecture component against enterprise governance policies.",
        "parameters": {
            "type": "object",
            "properties": {
                "component_description": {
                    "type": "string",
                    "description": "Description of the component or architecture to evaluate.",
                },
                "policy_id": {
                    "type": "string",
                    "description": "Specific policy ID to check (optional, checks all if omitted).",
                },
            },
            "required": ["component_description"],
        },
        "function": check_policy,
    },
    {
        "name": "list_policies",
        "description": "List all active enterprise governance policies, optionally filtered by category.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by policy category (Identity, Secrets, Encryption, Networking, Observability, Supply Chain, CI/CD, Governance).",
                },
            },
            "required": [],
        },
        "function": list_policies,
    },
    {
        "name": "explain_policy",
        "description": "Get a detailed explanation of a specific governance policy including its check criteria and remediation guidance.",
        "parameters": {
            "type": "object",
            "properties": {
                "policy_id": {
                    "type": "string",
                    "description": "The policy identifier (e.g., 'SEC-001').",
                },
            },
            "required": ["policy_id"],
        },
        "function": explain_policy,
    },
]
