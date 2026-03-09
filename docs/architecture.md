# Architecture Overview

> Enterprise DevEx Orchestrator Agent -- System Architecture

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
        CLI[CLI Entrypoint]
        RT[Agent Runtime]
        IP[Intent Parser]
        AP[Architecture Planner]
        GR[Governance Reviewer]
        IG[Infrastructure Generator]
    end
    
    subgraph "Generators"
        BG[Bicep Generator]
        CG[CI/CD Generator]
        AG[App Generator]
        DG[Docs Generator]
    end
    
    subgraph "Enterprise Standards"
        NE[Naming Engine - Azure CAF]
        TE[Tagging Engine - 12 Tags]
        SC[Standards Config - YAML]
        SM[State Manager - Drift Detection]
    end
    
    subgraph "MCP Tools"
        AV[Azure Validator]
        PE[Policy Engine - 15 Policies]
        TR[Template Renderer]
    end
    
    subgraph "Azure Resources"
        CA[Container Apps]
        KV[Key Vault]
        LA[Log Analytics]
        MI[Managed Identity]
        ACR[Container Registry]
    end
    
    CLI --> RT
    RT --> IP
    RT --> AP
    RT --> GR
    RT --> IG
    
    IG --> BG
    IG --> CG
    IG --> AG
    IG --> DG
    
    SC --> NE
    SC --> TE
    BG --> NE
    BG --> TE
    GR --> NE
    GR --> TE
    CLI --> SM
    
    AP --> AV
    AP --> PE
    GR --> PE
    IG --> TR
    
    BG --> CA
    BG --> KV
    BG --> LA
    BG --> MI
    BG --> ACR
```

## Data Flow

| Stage | Input | Processing | Output |
|-------|-------|-----------|--------|
| 1. Parse | Plain-text intent | LLM structured extraction + rule-based fallback | `IntentSpec` |
| 2. Plan | `IntentSpec` | Component selection, ADR generation, STRIDE threat model | `PlanOutput` |
| 3. Review | `IntentSpec` + `PlanOutput` | 15-policy validation, naming/tagging standards check, security scanning | `GovernanceReport` |
| 4. Generate | `IntentSpec` + `PlanOutput` + `GovernanceReport` | Template rendering, Azure CAF naming, enterprise tagging, file generation | File tree |
| 5. Record | Generated files | SHA-256 file manifest, drift detection, audit trail | `.devex/state.json` |

## Security Architecture

```mermaid
graph TD
    subgraph "Identity"
        MI[Managed Identity]
    end
    
    subgraph "Secrets"
        KV[Key Vault]
    end
    
    subgraph "Compute"
        CA[Container App]
    end
    
    subgraph "Monitoring"
        LA[Log Analytics]
    end
    
    subgraph "CI/CD"
        GH[GitHub Actions]
        OIDC[OIDC Federation]
    end
    
    MI -->|RBAC: Secrets User| KV
    MI -->|RBAC: AcrPull| ACR[Container Registry]
    CA -->|Uses| MI
    CA -->|Reads secrets| KV
    CA -->|Sends logs| LA
    KV -->|Diagnostics| LA
    GH -->|OIDC token| OIDC
    OIDC -->|Federated auth| Azure[Azure AD]
```

## Design Principles

1. **Deterministic Structure**: File layout, naming, and module organization are always the same
2. **Controlled Variability**: LLM adds context-specific content within deterministic boundaries
3. **Governance by Default**: Every scaffold passes governance validation before output
4. **Defense in Depth**: Multiple security layers -- identity, encryption, networking, scanning
5. **Observable from Day 1**: Log Analytics and diagnostics configured for all resources
6. **Enterprise Standards**: Azure CAF naming conventions and enterprise tagging enforced via YAML config
7. **State Awareness**: Every generation is tracked with drift detection between runs
