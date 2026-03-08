"""Documentation Generator — produces all project documentation.

Generates:
    - docs/plan.md: Architecture plan with ADRs and diagrams
    - docs/security.md: Security controls and threat model
    - docs/deployment.md: Deployment and rollback instructions
    - docs/rai-notes.md: Responsible AI considerations
    - docs/demo-script.md: Step-by-step demo script
    - docs/scorecard.md: Challenge scoring alignment matrix
    - docs/governance-report.md: Governance validation results
    - docs/waf-report.md: Well-Architected Framework alignment report
"""

from __future__ import annotations

from src.orchestrator.intent_schema import (
    GovernanceReport,
    IntentSpec,
    PlanOutput,
)
from src.orchestrator.logging import get_logger
from src.orchestrator.standards.waf import (
    WAFAlignmentReport,
    generate_waf_report_md,
)

logger = get_logger(__name__)


class DocsGenerator:
    """Generates project documentation."""

    def generate(
        self,
        spec: IntentSpec,
        plan: PlanOutput,
        governance: GovernanceReport | None = None,
        waf_report: WAFAlignmentReport | None = None,
    ) -> dict[str, str]:
        """Generate all documentation files."""
        logger.info("docs_generator.start", project=spec.project_name)

        files: dict[str, str] = {}

        files["docs/plan.md"] = self._plan_md(spec, plan)
        files["docs/security.md"] = self._security_md(spec, plan)
        files["docs/deployment.md"] = self._deployment_md(spec)
        files["docs/rai-notes.md"] = self._rai_notes_md(spec)
        files["docs/demo-script.md"] = self._demo_script_md(spec)
        files["docs/scorecard.md"] = self._scorecard_md(spec)

        if governance:
            files["docs/governance-report.md"] = self._governance_report_md(governance)

        if waf_report:
            files["docs/waf-report.md"] = generate_waf_report_md(waf_report)

        # Always generate improvement suggestions for the next iteration
        suggestions = self.generate_improvement_suggestions(spec, plan, governance, waf_report)
        files["docs/improvement-suggestions.md"] = self._improvement_suggestions_md(
            spec, suggestions
        )

        logger.info("docs_generator.complete", file_count=len(files))
        return files

    # ── Improvement Suggestions Engine ──────────────────────────

    def generate_improvement_suggestions(
        self,
        spec: IntentSpec,
        plan: PlanOutput,
        governance: GovernanceReport | None = None,
        waf_report: WAFAlignmentReport | None = None,
    ) -> list[str]:
        """Analyse the current plan and produce actionable improvement suggestions.

        Examines governance findings, WAF coverage gaps, architecture
        completeness, security posture, and observability coverage to
        generate a prioritised list of improvements the user can
        incorporate into the next version of their intent file.

        Returns:
            A list of plain-English improvement suggestions.
        """
        suggestions: list[str] = []

        # ── Governance-derived suggestions ────────────────────────
        if governance:
            for check in governance.checks:
                if not check.passed:
                    suggestions.append(
                        f"[Governance] {check.name}: {check.details}"
                    )
            for rec in governance.recommendations:
                if rec not in suggestions:
                    suggestions.append(f"[Governance] {rec}")

        # ── WAF gap suggestions ───────────────────────────────────
        if waf_report:
            scores = waf_report.pillar_scores()
            for pillar, info in scores.items():
                pct = info["pct"]
                if pct < 80.0:
                    gap_items = [
                        item for item in waf_report.gaps()
                        if item.pillar == pillar
                    ]
                    gap_names = [g.name for g in gap_items[:3]]
                    if gap_names:
                        suggestions.append(
                            f"[WAF/{pillar.value}] Coverage {pct:.0f}% — "
                            f"add coverage for: {', '.join(gap_names)}"
                        )

        # ── Security posture suggestions ──────────────────────────
        sec = spec.security
        if not sec.enable_waf:
            suggestions.append(
                "[Security] Consider enabling Web Application Firewall (WAF) "
                "for public-facing endpoints"
            )
        if sec.networking.value == "public_restricted":
            suggestions.append(
                "[Security] Consider moving to private networking with "
                "private endpoints for production workloads"
            )
        if sec.data_classification == "public":
            suggestions.append(
                "[Security] Verify data classification — public classification "
                "disables certain encryption and access controls"
            )

        # ── Observability suggestions ─────────────────────────────
        obs = spec.observability
        if not obs.alerts:
            suggestions.append(
                "[Observability] Enable alert rules for proactive monitoring "
                "of failures, latency, and resource utilisation"
            )
        if not obs.dashboard:
            suggestions.append(
                "[Observability] Add an Azure Monitor dashboard for real-time "
                "visibility into application health"
            )

        # ── Architecture suggestions ──────────────────────────────
        component_names = {c.azure_service.lower() for c in plan.components}

        if "azure redis cache" not in component_names and len(spec.data_stores) > 0:
            suggestions.append(
                "[Performance] Consider adding Azure Redis Cache for response "
                "caching and session management"
            )

        if len(plan.threat_model) < 4:
            suggestions.append(
                "[Security] Expand threat model to cover at least 4 STRIDE "
                "categories for comprehensive risk coverage"
            )

        # ── CI/CD suggestions ─────────────────────────────────────
        if not spec.cicd.deploy_on_merge:
            suggestions.append(
                "[CI/CD] Consider enabling automatic deployment on merge "
                "to main for faster feedback loops"
            )

        # ── Data store suggestions ────────────────────────────────
        store_values = {d.value for d in spec.data_stores}
        if "cosmos_db" not in store_values and spec.app_type.value in ("api", "web"):
            suggestions.append(
                "[Data] Consider Cosmos DB for globally distributed "
                "low-latency data access"
            )

        logger.info("improvement_suggestions.generated", count=len(suggestions))
        return suggestions

    def _improvement_suggestions_md(
        self,
        spec: IntentSpec,
        suggestions: list[str],
    ) -> str:
        """Render improvement suggestions as a markdown document."""
        if not suggestions:
            items = "No improvements identified — architecture is well-defined."
        else:
            items = "\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions))

        return f"""# Improvement Suggestions — {spec.project_name}

> Review these suggestions and incorporate them into your intent file.
> Then re-run `devex scaffold --file intent.md -o ./{spec.project_name}`
> to generate an improved version of your solution.

## How to Use This Document

1. **Review** each suggestion below
2. **Update** `intent.md` — add details to the relevant section
   (Problem Statement, Security, Scalability, etc.)
3. **Increment** the version number in the Version section
4. **Re-run** the orchestrator to generate the improved scaffold
5. **Repeat** until you reach production readiness

---

## Suggestions

{items}

---

## Next Steps

```bash
# 1. Update your intent file based on the suggestions above
# 2. Re-generate with the improved intent:
devex scaffold --file intent.md -o ./{spec.project_name}

# Or create a new version explicitly:
devex new-version ./{spec.project_name}
# Edit the generated intent.v2.md, then:
devex upgrade --file intent.v2.md -o ./{spec.project_name}
```

---
*Generated by Enterprise DevEx Orchestrator Agent — Improvement Analysis*
"""

    def _plan_md(self, spec: IntentSpec, plan: PlanOutput) -> str:
        # Components table
        components_table = "| Component | Azure Service | Purpose | Bicep Module |\n"
        components_table += "|-----------|--------------|---------|-------------|\n"
        for c in plan.components:
            components_table += f"| {c.name} | {c.azure_service} | {c.purpose} | `{c.bicep_module}` |\n"

        # ADRs
        adrs = ""
        for d in plan.decisions:
            adrs += f"""
### {d.id}: {d.title}

- **Status:** {d.status}
- **Context:** {d.context}
- **Decision:** {d.decision}
- **Consequences:** {d.consequences}
"""

        return f"""# Architecture Plan: {spec.project_name}

> {plan.summary}

## Intent

```
{spec.raw_intent}
```

## Executive Summary

{plan.summary}

## Components

{components_table}

## Architecture Diagram

```mermaid
{plan.diagram_mermaid}
```

## Architecture Decision Records

{adrs}

## Assumptions

{chr(10).join(f"- {a}" for a in spec.assumptions)}

## Open Risks

{chr(10).join(f"- {r}" for r in spec.open_risks)}

## Agent Confidence

**Confidence Level:** {spec.confidence:.0%}

---
*Generated by Enterprise DevEx Orchestrator Agent*
"""

    def _security_md(self, spec: IntentSpec, plan: PlanOutput) -> str:
        # Threat model table
        threat_table = "| ID | Category | Threat | Mitigation | Residual Risk |\n"
        threat_table += "|----|----------|--------|------------|---------------|\n"
        for t in plan.threat_model:
            threat_table += f"| {t.id} | {t.category} | {t.description} | {t.mitigation} | {t.residual_risk} |\n"

        # Security controls per component
        controls = ""
        for c in plan.components:
            if c.security_controls:
                controls += f"\n### {c.name} ({c.azure_service})\n"
                for ctrl in c.security_controls:
                    controls += f"- {ctrl}\n"

        return f"""# Security Documentation: {spec.project_name}

## Security Posture Summary

| Control | Setting |
|---------|---------|
| Authentication | {spec.security.auth_model.value} |
| Compliance Framework | {spec.security.compliance_framework.value} |
| Network Model | {spec.security.networking.value} |
| Data Classification | {spec.security.data_classification} |
| Encryption at Rest | {"Enabled" if spec.security.encryption_at_rest else "Disabled"} |
| Encryption in Transit | {"Enabled" if spec.security.encryption_in_transit else "Disabled"} |
| Secret Management | {"Key Vault" if spec.security.secret_management else "None"} |

## STRIDE Threat Model

{threat_table}

## Security Controls by Component

{controls}

## RBAC Role Assignments

| Principal | Resource | Role | Justification |
|-----------|----------|------|---------------|
| Managed Identity | Key Vault | Key Vault Secrets User | Read application secrets |
| Managed Identity | Storage Account | Storage Blob Data Contributor | Read/write blob data |
| Managed Identity | Container Registry | AcrPull | Pull container images |
| GitHub Actions (OIDC) | Subscription | Contributor | Deploy infrastructure |

## Least Privilege Guidance

1. **Never use Owner role** for service principals or managed identities
2. **Scope roles to resource groups**, not subscriptions, where possible
3. **Use custom roles** if built-in roles are too broad
4. **Review access quarterly** and remove unused assignments
5. **Enable PIM** for just-in-time privileged access

## Supply Chain Security

- **CodeQL**: Automated code scanning on every PR and weekly schedule
- **Dependabot**: Automated dependency updates for pip, GitHub Actions, and Docker
- **Non-root containers**: Application runs as unprivileged user
- **Multi-stage Docker builds**: Minimal attack surface in production image

---
*Generated by Enterprise DevEx Orchestrator Agent*
"""

    def _deployment_md(self, spec: IntentSpec) -> str:
        return f"""# Deployment Guide: {spec.project_name}

## Prerequisites

- Azure CLI >= 2.55.0
- Bicep CLI >= 0.24.0
- Docker >= 24.0
- Python >= 3.11
- GitHub CLI (optional)
- An Azure subscription with Contributor access

## Environment Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd {spec.project_name}

# Copy environment config
cp .env.example .env
# Edit .env with your values
```

## Infrastructure Deployment

### Step 1: Login to Azure

```bash
az login
az account set --subscription {spec.azure_region}
```

### Step 2: Create Resource Group

```bash
az group create \\
  --name {spec.resource_group_name} \\
  --location {spec.azure_region} \\
  --tags project={spec.project_name} environment={spec.environment}
```

### Step 3: Deploy Infrastructure

```bash
az deployment group create \\
  --resource-group {spec.resource_group_name} \\
  --template-file infra/bicep/main.bicep \\
  --parameters infra/bicep/parameters/dev.parameters.json \\
  --verbose
```

### Step 4: Build and Push Container

```bash
# Get ACR login server
ACR_NAME=$(echo "{spec.project_name}" | tr -d '-')acr
ACR_LOGIN=$(az acr show --name $ACR_NAME --query loginServer --output tsv)

# Login to ACR
az acr login --name $ACR_NAME

# Build and push
docker build -t $ACR_LOGIN/{spec.project_name}:latest -f src/app/Dockerfile src/app/
docker push $ACR_LOGIN/{spec.project_name}:latest
```

### Step 5: Update Container App

```bash
az containerapp update \\
  --name {spec.project_name} \\
  --resource-group {spec.resource_group_name} \\
  --image $ACR_LOGIN/{spec.project_name}:latest
```

### Step 6: Verify Deployment

```bash
# Get the FQDN
FQDN=$(az containerapp show \\
  --name {spec.project_name} \\
  --resource-group {spec.resource_group_name} \\
  --query properties.configuration.ingress.fqdn \\
  --output tsv)

# Test health endpoint
curl https://$FQDN/health
```

## Rollback Instructions

### Rollback Application

```bash
# List revisions
az containerapp revision list \\
  --name {spec.project_name} \\
  --resource-group {spec.resource_group_name} \\
  --output table

# Activate previous revision
az containerapp revision activate \\
  --name {spec.project_name} \\
  --resource-group {spec.resource_group_name} \\
  --revision <previous-revision-name>

# Shift traffic to previous revision
az containerapp ingress traffic set \\
  --name {spec.project_name} \\
  --resource-group {spec.resource_group_name} \\
  --revision-weight <previous-revision-name>=100
```

### Rollback Infrastructure

```bash
# Revert to previous Bicep commit
git log --oneline infra/bicep/
git checkout <commit-hash> -- infra/bicep/

# Redeploy
az deployment group create \\
  --resource-group {spec.resource_group_name} \\
  --template-file infra/bicep/main.bicep \\
  --parameters infra/bicep/parameters/dev.parameters.json
```

## Teardown

```bash
# Delete all resources
az group delete \\
  --name {spec.resource_group_name} \\
  --yes --no-wait

# Verify deletion
az group show --name {spec.resource_group_name} 2>/dev/null || echo "Deleted"
```

## Troubleshooting

### Check Container App Logs

```bash
az containerapp logs show \\
  --name {spec.project_name} \\
  --resource-group {spec.resource_group_name} \\
  --type system
```

### Query Log Analytics

```bash
az monitor log-analytics query \\
  --workspace <workspace-id> \\
  --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == '{spec.project_name}' | top 50 by TimeGenerated"
```

---
*Generated by Enterprise DevEx Orchestrator Agent*
"""

    def _rai_notes_md(self, spec: IntentSpec) -> str:
        ai_section = ""
        if spec.uses_ai:
            ai_section = """
## AI-Specific Considerations

### Content Safety
- Azure AI Foundry content safety filters are enabled by default
- All AI inputs are validated and sanitized before processing
- AI outputs are logged for audit and review

### Prompt Injection Protection
- System prompts are hardened against injection attacks
- User inputs are treated as untrusted data
- Output validation prevents data exfiltration via AI responses

### Bias and Fairness
- AI models are evaluated for bias in the target use case
- Regular fairness audits are recommended
- Feedback mechanisms allow users to report issues

### Data Handling
- No training data is derived from user inputs
- AI processing logs are retained per data retention policy
- PII is never included in AI prompts without explicit consent
"""

        return f"""# Responsible AI Notes: {spec.project_name}

## Overview

This document outlines the Responsible AI (RAI) considerations for the
{spec.project_name} workload, as required by Microsoft's Responsible AI
Standard and enterprise governance policies.

## Principles Applied

### 1. Fairness
- The system treats all users equitably
- No discriminatory features or biased processing

### 2. Reliability & Safety
- Health checks ensure system availability
- Rollback procedures documented for failure recovery
- Auto-scaling prevents resource exhaustion

### 3. Privacy & Security
- No PII stored in logs (structured logging only)
- Managed Identity eliminates credential exposure
- Data encrypted at rest and in transit
- Key Vault for all secret management

### 4. Inclusiveness
- API endpoints follow REST conventions for broad accessibility
- Documentation provided in clear, accessible language

### 5. Transparency
- Architecture decisions are documented (ADRs)
- All security controls are enumerated
- Governance reports provide clear pass/fail criteria

### 6. Accountability
- Deployment requires explicit manual trigger
- Audit trails via Log Analytics
- RBAC enforces least-privilege access
{ai_section}
## Limitations

- This system provides governance **guidance**, not certification
- Compliance frameworks (HIPAA, SOC2, etc.) require additional organizational controls
- AI-generated content should be reviewed by authorized personnel before production use

## Contact

For RAI concerns, contact the Enterprise DevEx team or your organization's
Responsible AI office.

---
*Generated by Enterprise DevEx Orchestrator Agent*
"""

    def _demo_script_md(self, spec: IntentSpec) -> str:
        return f"""# Demo Script: {spec.project_name}

> Duration: 3 minutes | No improvisation — follow this script exactly.

## Setup (Before Recording)

1. Ensure Azure subscription is active
2. Ensure `.env` is configured
3. Have a terminal open in the project root
4. Have Azure Portal open in a browser tab
5. (Optional) Have backup screenshots in `docs/screenshots/`

## Demo Flow

### Minute 0:00 — 0:30 | Introduction

**Say:** "We built an Enterprise DevEx Orchestrator — a Copilot SDK-powered
agent that transforms plain-English business intent into production-ready,
secure, deployable Azure workloads."

**Show:** README.md in the repo

### Minute 0:30 — 1:30 | Agent in Action

**Run:**
```bash
python -m src.orchestrator.main plan \\
  --intent "Build a secure API that processes documents, stores metadata, \\
  and exposes a REST endpoint. Must use managed identity, secrets in Key Vault, \\
  logging, and CI/CD."
```

**Show:**
- Intent parsing output (structured schema)
- Architecture plan (`docs/plan.md`)
- Mermaid diagram rendering
- Governance validation report

**Say:** "The agent parsed our intent, generated an architecture plan with
ADRs and threat model, validated it against governance policies, and produced
deployable infrastructure."

### Minute 1:30 — 2:15 | Generated Artifacts

**Show:**
- `infra/bicep/main.bicep` — Infrastructure as Code
- `infra/bicep/modules/` — Modular Bicep files
- `.github/workflows/` — CI/CD pipelines
- `src/app/main.py` — Application with health endpoint
- `docs/security.md` — Security controls and threat model
- `docs/governance-report.md` — Governance validation results

**Say:** "Every artifact is production-grade: private networking, managed
identity, Key Vault secrets, Log Analytics, and CI/CD with OIDC — all
generated from a single sentence."

### Minute 2:15 — 2:45 | Live Deployment

**Option A (Live):**
```bash
az deployment group create \\
  --resource-group {spec.resource_group_name} \\
  --template-file infra/bicep/main.bicep \\
  --parameters infra/bicep/parameters/dev.parameters.json
```

**Option B (Pre-deployed):**
- Switch to Azure Portal
- Show Resource Group with all resources
- Click into Container App → show health endpoint response
- Click into Log Analytics → run sample KQL query

### Minute 2:45 — 3:00 | Wrap Up

**Say:** "Enterprises don't need faster code. They need safe, compliant,
repeatable architecture. We built a Copilot SDK-powered orchestrator that
turns intent into governed infrastructure — with security, observability,
and CI/CD built in from the start."

## Backup Plan

If live demo fails:
1. Show pre-recorded terminal output
2. Show Azure Portal screenshots in `docs/screenshots/`
3. Walk through generated code in the repo

## Azure Portal Locations to Show

| Resource | What to Click |
|----------|--------------|
| Resource Group | Overview → see all resources |
| Container App | Overview → FQDN, Revisions |
| Key Vault | Access policies → RBAC |
| Log Analytics | Logs → run KQL query |
| Container Registry | Repositories → image |

## Sample KQL Query

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "{spec.project_name}"
| project TimeGenerated, Log_s, RevisionName_s
| order by TimeGenerated desc
| take 20
```

---
*Generated by Enterprise DevEx Orchestrator Agent*
"""

    def _scorecard_md(self, spec: IntentSpec) -> str:
        return """# Challenge Scoring Alignment Matrix

> Maps each judging criterion to concrete artifacts, validation methods, and demo proof points.

## Core Criteria (100 pts)

| Criteria | Max Pts | Artifact | Validation | Demo Proof |
|----------|---------|----------|------------|------------|
| Enterprise Applicability | 30 | ADR + deterministic scaffold + IntentSpec schema | CI validates structure | Live: parse intent → full scaffold |
| Azure Integration | 25 | Bicep + OIDC + Container Apps + Key Vault + Log Analytics + ACR | `az deployment group validate` | Portal: show deployed resources |
| Operational Readiness | 15 | CI/CD workflows + Log Analytics + health endpoint + rollback docs | CI green badge | Live: health endpoint + log query |
| Security & RAI | 15 | Key Vault + MI + governance report + threat model + CodeQL + Dependabot | Governance validator PASS | `security.md` + `governance-report.md` |
| Storytelling | 15 | README + demo script + architecture diagram + pitch deck | N/A | 3-min video following demo-script.md |

## Bonus Criteria (35 pts)

| Criteria | Max Pts | How We Address It |
|----------|---------|-------------------|
| Work IQ / Fabric IQ / Foundry IQ | 15 | Azure AI Foundry as model backend; extensibility for Work IQ context grounding |
| Customer Validation | 10 | Customer testimonial form (if obtained) |
| Copilot SDK Feedback | 10 | Feedback posted to SDK team channel with screenshots |

## Artifact Checklist

- [x] `/src` — Working orchestrator + generated app code
- [x] `/docs` — README, plan.md, security.md, deployment.md, rai-notes.md
- [x] `AGENTS.md` — Agent role definitions and instructions
- [x] `mcp.json` — MCP server declarations
- [x] `.github/workflows/` — CI/CD validate + deploy
- [x] `/infra/bicep/` — Deployable Azure infrastructure
- [x] `/presentations/` — Pitch deck
- [x] Demo video (3 min max)

---
*Generated by Enterprise DevEx Orchestrator Agent*
"""

    def _governance_report_md(self, report: GovernanceReport) -> str:
        checks_table = "| ID | Check | Status | Severity | Details |\n"
        checks_table += "|----|-------|--------|----------|--------|\n"
        for c in report.checks:
            status_icon = "✅" if c.passed else "❌"
            checks_table += f"| {c.check_id} | {c.name} | {status_icon} | {c.severity} | {c.details} |\n"

        recommendations = ""
        if report.recommendations:
            recommendations = "## Recommendations\n\n"
            for r in report.recommendations:
                recommendations += f"- {r}\n"

        return f"""# Governance Validation Report

## Status: **{report.status}**

> {report.summary}

## Checks

{checks_table}

## Summary

- **Total Checks:** {len(report.checks)}
- **Passed:** {len([c for c in report.checks if c.passed])}
- **Failed:** {len([c for c in report.checks if not c.passed])}

{recommendations}

---
*Generated by Enterprise DevEx Orchestrator Agent — Governance Reviewer*
"""
