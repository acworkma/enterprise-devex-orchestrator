# Architecture Overview

> **Enterprise DevEx Orchestrator** -- 4-Agent Chain Architecture
> Transforms business intent into production-ready Azure workloads

---

## High-Level Flow

```mermaid
graph TD
    A[User Intent] --> B[CLI / devex command]
    B --> C[Intent Parser Agent]
    C --> D[IntentSpec Schema]
    D --> E[Architecture Planner Agent]
    E --> F[PlanOutput + ADRs + Threat Model]
    F --> G[Governance Reviewer Agent]
    G -->|PASS| H[Infrastructure Generator Agent]
    G -->|FAIL| E
    H --> I[Generated Scaffold]

    I --> J[infra/bicep/]
    I --> K[.github/workflows/]
    I --> L[src/app/]
    I --> M[docs/]
    I --> N[tests/]

    subgraph "MCP Tool Servers"
        T1[azure-validator]
        T2[policy-engine]
        T3[template-renderer]
    end

    E -.-> T1
    E -.-> T2
    G -.-> T2
    H -.-> T3
```

## Component Architecture

```mermaid
graph LR
    subgraph "Orchestrator Agent"
        CLI[CLI Entrypoint<br>8 commands]
        RT[Agent Runtime]
        IP[Intent Parser]
        AP[Architecture Planner]
        GR[Governance Reviewer<br>+ WAF Assessor]
        IG[Infrastructure Generator]
    end

    subgraph "Generators (6)"
        BG[Bicep Generator<br>7 modules]
        CG[CI/CD Generator<br>4 workflows]
        AG[App Generator<br>FastAPI + Docker]
        DG[Docs Generator<br>7 doc files]
        TG[Test Generator<br>5 test files]
        ALG[Alert Generator<br>Bicep alerts + runbook]
    end

    subgraph "Enterprise Standards"
        NE[Naming Engine<br>20 types, 34 regions]
        TE[Tagging Engine<br>7 required + 5 optional]
        SC[Standards Config<br>standards.yaml]
        SM[State Manager<br>Drift Detection]
    end

    subgraph "Advanced Patterns"
        SK[Skills Registry<br>9 skills, 12 categories]
        SD[Subagent Dispatcher<br>6 subagents, parallel fan-out]
        PP[Persistent Planner<br>13-task DAG]
        PG[Prompt Generator<br>Repo-aware prompts]
        DO[Deploy Orchestrator<br>4-stage deployment]
    end

    subgraph "MCP Tools (9)"
        AV[validate_bicep]
        VD[validate_deployment]
        RA[check_region_availability]
        CP[check_policy]
        LP[list_policies]
        EP[explain_policy]
        RT2[render_template]
        LT[list_templates]
        PO[preview_output]
    end

    subgraph "Azure Resources"
        CA[Container Apps]
        KV[Key Vault]
        LA[Log Analytics]
        MI[Managed Identity]
        ACR[Container Registry]
    end

    CLI --> RT
    RT --> IP --> AP --> GR --> IG

    IG --> BG & CG & AG & DG & TG & ALG

    SC --> NE & TE
    BG --> NE & TE
    BG --> CA & KV & LA & MI & ACR

    AP --> AV & CP
    GR --> CP & LP
    IG --> RT2

    RT --> SK & SD & PP
    RT --> PG & DO
```

## Data Flow

| Stage | Input | Processing | Output |
|-------|-------|-----------|--------|
| 1. Parse | Plain-text intent or `intent.md` | LLM extraction + rule-based fallback | `IntentSpec` (Pydantic) |
| 2. Plan | `IntentSpec` | Component selection, 6 ADRs, STRIDE threat model, Mermaid diagram | `PlanOutput` |
| 3. Review | `IntentSpec` + `PlanOutput` | 25-policy validation, WAF 5-pillar assessment (26 principles) | `GovernanceReport` + `WAFAlignmentReport` |
| 4. Generate | All above | 6 generators produce Bicep, workflows, app, docs, tests, alerts | `dict[str, str]` file map |
| 5. Record | Generated files | SHA-256 manifest, drift detection, audit trail | `.devex/state.json` |
| 6. Deploy | Output directory | 4-stage: validate -> what-if -> deploy -> verify | Deployment result |

## Security Architecture

```mermaid
graph TD
    subgraph "Identity & Access"
        MI[Managed Identity<br>project-env-id]
        RBAC[RBAC Assignments]
    end

    subgraph "Secrets Management"
        KV[Key Vault<br>projectenvkv]
    end

    subgraph "Compute"
        CA[Container App<br>project-env]
        ACR[Container Registry<br>projectenvacr]
    end

    subgraph "Observability"
        LA[Log Analytics<br>project-env-law]
    end

    subgraph "CI/CD"
        GH[GitHub Actions]
        OIDC[OIDC Federation]
    end

    MI -->|Key Vault Secrets User| KV
    MI -->|AcrPull| ACR
    CA -->|Uses| MI
    CA -->|Reads secrets via| KV
    CA -->|Sends logs to| LA
    KV -->|Diagnostics to| LA
    ACR -->|Diagnostics to| LA
    GH -->|OIDC token| OIDC
    OIDC -->|Federated auth| Entra[Microsoft Entra ID]
```

## Design Principles

| # | Principle | Implementation |
|---|-----------|---------------|
| 1 | Deterministic Structure | File layout, naming, and module organization are always the same |
| 2 | Controlled Variability | LLM adds context-specific content within deterministic boundaries |
| 3 | Governance by Default | Every scaffold passes 25-policy governance validation before output |
| 4 | Defense in Depth | Identity, encryption, networking, scanning -- multiple security layers |
| 5 | Observable from Day 1 | Log Analytics + diagnostics configured for all resources |
| 6 | Enterprise Standards | Azure CAF naming (20 types) + tagging (12 tags) enforced via YAML |
| 7 | State Awareness | Every generation tracked with drift detection between runs |
| 8 | WAF Aligned | 26/26 Azure Well-Architected Framework principles covered |

## Agent Capabilities Summary

| Agent | Tools | Fallback | Key Output |
|-------|-------|----------|-----------|
| Intent Parser | None (pure LLM) | Rule-based keyword extraction | `IntentSpec` |
| Architecture Planner | `check_policy`, `check_region_availability` | Template-based component builder | `PlanOutput` with ADRs + threat model |
| Governance Reviewer | `check_policy`, `list_policies`, `validate_bicep` | Policy catalog evaluation | `GovernanceReport` + `WAFAlignmentReport` |
| Infrastructure Generator | `render_template`, `preview_output`, `validate_bicep` | Direct file generation | Complete file tree |

---

*4-agent chain | 9 MCP tools | 6 generators | 25 policies | 486 tests*
*Azure CAF naming + enterprise tagging + WAF 5-pillar alignment*


