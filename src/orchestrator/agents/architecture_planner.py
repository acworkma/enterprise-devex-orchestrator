"""Architecture Planner Agent.

Takes an IntentSpec and produces a PlanOutput with:
    - Component list (Azure services to deploy)
    - Architecture Decision Records (ADRs)
    - Threat model (top 5 threats)
    - Mermaid architecture diagram
"""

from __future__ import annotations

import json

from src.orchestrator.agent import AgentRuntime
from src.orchestrator.config import AppConfig
from src.orchestrator.intent_schema import (
    ArchitectureDecision,
    ComponentSpec,
    DataStore,
    IntentSpec,
    PlanOutput,
    ThreatEntry,
)
from src.orchestrator.logging import get_logger

logger = get_logger(__name__)

ARCHITECTURE_PLANNER_SYSTEM_PROMPT = """\
You are an Enterprise Architecture Planner. Given a structured IntentSpec,
produce an architecture plan as a JSON object.

## Rules
1. Select Azure components based on the IntentSpec requirements.
2. Always include: Azure Container Apps, Key Vault, Log Analytics, Managed Identity.
3. Add data stores based on IntentSpec.data_stores.
4. Write Architecture Decision Records (ADRs) for key choices.
5. Produce a threat model with top 5 STRIDE-categorized threats.
6. Generate a Mermaid diagram showing component relationships.
7. Keep the plan actionable and enterprise-grade.

## Output Format
Return ONLY a JSON object matching this schema:
{
  "title": "string",
  "summary": "string",
  "components": [{"name": "string", "azure_service": "string", "purpose": "string", "bicep_module": "string", "security_controls": ["string"]}],
  "decisions": [{"id": "ADR-001", "title": "string", "status": "Accepted", "context": "string", "decision": "string", "consequences": "string"}],
  "threat_model": [{"id": "THREAT-001", "category": "string", "description": "string", "mitigation": "string", "residual_risk": "Low|Medium|High"}],
  "diagram_mermaid": "string (mermaid diagram source)"
}
"""


class ArchitecturePlannerAgent:
    """Generates architecture plan from IntentSpec."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.runtime = AgentRuntime(config)

    def plan(self, spec: IntentSpec) -> PlanOutput:
        """Generate architecture plan from intent specification."""
        logger.info("architecture_planner.start", project=spec.project_name)

        try:
            response = self.runtime.run_sync(
                system_prompt=ARCHITECTURE_PLANNER_SYSTEM_PROMPT,
                user_message=f"Generate architecture plan for:\n{spec.model_dump_json(indent=2)}",
                max_iterations=3,
            )
            plan = self._parse_response(response, spec)
        except Exception as e:
            logger.warning("architecture_planner.fallback", error=str(e))
            plan = self._default_plan(spec)

        logger.info("architecture_planner.complete", components=len(plan.components), decisions=len(plan.decisions))
        return plan

    def _parse_response(self, response: str, spec: IntentSpec) -> PlanOutput:
        """Parse LLM response into PlanOutput."""
        import re

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        json_str = json_match.group(1) if json_match else response.strip()

        try:
            data = json.loads(json_str)
            return PlanOutput(**data)
        except (json.JSONDecodeError, Exception):
            return self._default_plan(spec)

    def _default_plan(self, spec: IntentSpec) -> PlanOutput:
        """Deterministic default plan based on IntentSpec."""
        components = self._build_components(spec)
        decisions = self._build_decisions(spec)
        threats = self._build_threat_model(spec)
        diagram = self._build_diagram(spec, components)

        return PlanOutput(
            title=f"Architecture Plan: {spec.project_name}",
            summary=(
                f"Enterprise-grade {spec.app_type.value} workload deployed on Azure Container Apps "
                f"with managed identity, Key Vault secret management, Log Analytics observability, "
                f"and private networking. CI/CD via GitHub Actions with OIDC authentication."
            ),
            components=components,
            decisions=decisions,
            threat_model=threats,
            diagram_mermaid=diagram,
        )

    def _build_components(self, spec: IntentSpec) -> list[ComponentSpec]:
        """Build component list based on IntentSpec."""
        components = [
            ComponentSpec(
                name="container-app",
                azure_service="Azure Container Apps",
                purpose=f"Hosts the {spec.app_type.value} application with auto-scaling",
                bicep_module="container-app.bicep",
                security_controls=["Managed Identity", "HTTPS Only", "Private Ingress", "Min TLS 1.2"],
            ),
            ComponentSpec(
                name="key-vault",
                azure_service="Azure Key Vault",
                purpose="Centralized secret and certificate management",
                bicep_module="keyvault.bicep",
                security_controls=["RBAC Access", "Soft Delete", "Purge Protection", "Diagnostic Logging"],
            ),
            ComponentSpec(
                name="log-analytics",
                azure_service="Azure Log Analytics",
                purpose="Centralized logging, monitoring, and diagnostics",
                bicep_module="log-analytics.bicep",
                security_controls=["Data Retention Policy", "Access Control", "Diagnostic Settings"],
            ),
            ComponentSpec(
                name="managed-identity",
                azure_service="Azure Managed Identity",
                purpose="Passwordless authentication between Azure resources",
                bicep_module="managed-identity.bicep",
                security_controls=["Least Privilege RBAC", "No Credential Storage"],
            ),
            ComponentSpec(
                name="container-registry",
                azure_service="Azure Container Registry",
                purpose="Private container image registry for application images",
                bicep_module="container-registry.bicep",
                security_controls=["Managed Identity Pull", "Private Access", "Image Scanning"],
            ),
        ]

        # Add data store components
        for store in spec.data_stores:
            if store == DataStore.BLOB_STORAGE:
                components.append(
                    ComponentSpec(
                        name="storage-account",
                        azure_service="Azure Storage Account",
                        purpose="Blob storage for documents and data",
                        bicep_module="storage.bicep",
                        security_controls=[
                            "Managed Identity Access",
                            "HTTPS Only",
                            "Encryption at Rest",
                            "Private Endpoint (optional)",
                        ],
                    )
                )
            elif store == DataStore.COSMOS_DB:
                components.append(
                    ComponentSpec(
                        name="cosmos-db",
                        azure_service="Azure Cosmos DB",
                        purpose="NoSQL database for application data",
                        bicep_module="cosmos-db.bicep",
                        security_controls=["Managed Identity", "Encryption", "Private Endpoint"],
                    )
                )

        return components

    def _build_decisions(self, spec: IntentSpec) -> list[ArchitectureDecision]:
        """Build Architecture Decision Records."""
        decisions = [
            ArchitectureDecision(
                id="ADR-001",
                title="Use Azure Container Apps for compute",
                status="Accepted",
                context="Need a managed container platform that supports auto-scaling, managed identity, and integrated logging without Kubernetes operational overhead.",
                decision="Selected Azure Container Apps over AKS and App Service. Container Apps provides Kubernetes-based scaling with a serverless operational model.",
                consequences="Simpler operations than AKS. Some limitations on advanced networking compared to AKS. Acceptable for this workload.",
            ),
            ArchitectureDecision(
                id="ADR-002",
                title="Use Managed Identity for all service-to-service auth",
                status="Accepted",
                context="Enterprise security policy requires passwordless authentication. Credential rotation and secret sprawl are operational risks.",
                decision="All Azure resource access uses User-Assigned Managed Identity with least-privilege RBAC roles.",
                consequences="Eliminates credential management. Requires proper role assignments in Bicep. Slightly more complex initial setup.",
            ),
            ArchitectureDecision(
                id="ADR-003",
                title="Use Bicep for Infrastructure as Code",
                status="Accepted",
                context="Need Azure-native IaC that supports ARM validation, what-if analysis, and integrates with az CLI.",
                decision="Selected Bicep over Terraform for Azure-native tooling, no state file management, and direct ARM integration.",
                consequences="Azure-only (acceptable for this scope). Native az deployment group validate support.",
            ),
            ArchitectureDecision(
                id="ADR-004",
                title="Use Key Vault for all secrets",
                status="Accepted",
                context="No secrets should be stored in code, environment variables, or CI/CD configuration directly.",
                decision="All secrets stored in Azure Key Vault. Application accesses them via Managed Identity. CI/CD uses OIDC.",
                consequences="Additional Key Vault resource cost. Requires proper access policies. Eliminates secret exposure risk.",
            ),
            ArchitectureDecision(
                id="ADR-005",
                title="Private ingress by default",
                status="Accepted",
                context="Enterprise workloads should not be publicly accessible unless explicitly required.",
                decision="Container Apps environment configured with internal ingress. External access requires explicit configuration.",
                consequences="Requires VNet integration for access. More secure by default. May need adjustment for public-facing APIs.",
            ),
        ]

        if spec.uses_ai:
            decisions.append(
                ArchitectureDecision(
                    id="ADR-006",
                    title="Use Azure AI Foundry for AI/ML integration",
                    status="Accepted",
                    context="Workload requires AI capabilities. Need enterprise-grade AI platform with content safety and monitoring.",
                    decision="Use Azure AI Foundry (formerly Azure AI Studio) for model hosting and inference, with content safety filters enabled.",
                    consequences="Requires Azure AI Foundry resource provisioning. Content safety may filter edge cases. Provides audit trail.",
                )
            )

        return decisions

    def _build_threat_model(self, spec: IntentSpec) -> list[ThreatEntry]:
        """Build STRIDE threat model."""
        threats = [
            ThreatEntry(
                id="THREAT-001",
                category="Spoofing",
                description="Unauthorized entity impersonates a legitimate service or user to access resources.",
                mitigation="Managed Identity for service auth. Entra ID for user auth. No shared secrets.",
                residual_risk="Low",
            ),
            ThreatEntry(
                id="THREAT-002",
                category="Tampering",
                description="Malicious modification of data in transit or at rest.",
                mitigation="TLS 1.2+ enforced. Encryption at rest via Azure platform encryption. Immutable audit logs.",
                residual_risk="Low",
            ),
            ThreatEntry(
                id="THREAT-003",
                category="Information Disclosure",
                description="Sensitive data exposed through logs, error messages, or misconfigured access.",
                mitigation="Structured logging without PII. Key Vault for secrets. Private networking. RBAC enforcement.",
                residual_risk="Low",
            ),
            ThreatEntry(
                id="THREAT-004",
                category="Denial of Service",
                description="Resource exhaustion through excessive requests or payload abuse.",
                mitigation="Container Apps auto-scaling with max replica limits. Request size limits. Rate limiting at API layer.",
                residual_risk="Medium",
            ),
            ThreatEntry(
                id="THREAT-005",
                category="Elevation of Privilege",
                description="Attacker gains higher privileges than authorized through misconfigured RBAC or container escape.",
                mitigation="Least-privilege RBAC. Non-root containers. No privileged capabilities. Regular access reviews.",
                residual_risk="Low",
            ),
        ]

        if spec.uses_ai:
            threats.append(
                ThreatEntry(
                    id="THREAT-006",
                    category="Tampering",
                    description="Prompt injection attacks to manipulate AI behavior or extract training data.",
                    mitigation="Content safety filters. Input validation. Output sanitization. System prompt hardening.",
                    residual_risk="Medium",
                )
            )

        return threats

    def _build_diagram(self, spec: IntentSpec, components: list[ComponentSpec]) -> str:
        """Build Mermaid architecture diagram."""
        diagram = f"""graph TB
    subgraph "Client Layer"
        USER[User / Client]
    end

    subgraph "Azure Container Apps Environment"
        ACA["{spec.project_name}<br/>Container App"]
        HEALTH["/health endpoint"]
    end

    subgraph "Identity & Security"
        MI[Managed Identity]
        KV[Key Vault]
    end

    subgraph "Observability"
        LA[Log Analytics]
        DIAG[Diagnostic Settings]
    end

    subgraph "Container Registry"
        ACR[Azure Container Registry]
    end
"""

        # Add data store nodes
        for store in spec.data_stores:
            if store == DataStore.BLOB_STORAGE:
                diagram += """
    subgraph "Data Layer"
        SA[Storage Account]
    end
"""
            elif store == DataStore.COSMOS_DB:
                diagram += """
    subgraph "Data Layer"
        CDB[Cosmos DB]
    end
"""

        # Add connections
        diagram += """
    USER -->|HTTPS| ACA
    ACA --> HEALTH
    ACA -->|Managed Identity| MI
    MI -->|RBAC| KV
    ACA -->|Logs| LA
    DIAG -->|Metrics| LA
    ACR -->|Image Pull| ACA
"""

        for store in spec.data_stores:
            if store == DataStore.BLOB_STORAGE:
                diagram += "    MI -->|RBAC| SA\n"
            elif store == DataStore.COSMOS_DB:
                diagram += "    MI -->|RBAC| CDB\n"

        if spec.uses_ai:
            diagram += """
    subgraph "AI Services"
        AOAI[Azure AI Foundry]
    end
    MI -->|RBAC| AOAI
"""

        diagram += """
    subgraph "CI/CD"
        GHA[GitHub Actions]
        OIDC[OIDC Federation]
    end
    GHA -->|OIDC| OIDC
    GHA -->|Deploy| ACA
    GHA -->|Push| ACR
"""

        return diagram
