# agent365

> We are building a validation enviroment for building a sample MCP server, exposing through API Management, connecting to it from Copilot Studio, with the necessary RBAC permissions. 

---

## Problem Statement

There is no validated reference architecture for exposing an MCP server through Azure API Management and consuming it from Copilot Studio with proper EntraID-based identity (including the new Agent Identity feature). Teams attempting this today must piece together documentation across multiple services, leading to insecure or incomplete implementations. Without a proven pattern, adoption of MCP-based extensibility in Copilot Studio stalls.

## Business Goals

- Deliver a working end-to-end proof-of-concept in a single sprint
- Validate that Copilot Studio can invoke an MCP server through APIM with EntraID RBAC
- Produce a reusable reference architecture that other teams can clone
- KPI: successful round-trip call from Copilot Studio → APIM → MCP Server and back

## Target Users

- **Platform Engineer**: Deploys and configures the lab environment (MCP server, APIM, identity). Weekly use. Expert-level Azure and IaC knowledge.
- **AI Developer**: Connects Copilot Studio to the MCP server via APIM to test agent extensibility scenarios. On-demand use. Intermediate Azure proficiency.
- **Security Reviewer**: Validates that RBAC, Managed Identity, and Agent Identity are correctly configured. On-demand use. Expert-level EntraID knowledge.

## Functional Requirements

### Core Application
  - MCP Server hosted on Azure Container Apps
  - Azure API Management (APIM) exposing the MCP server
  - Copilot Studio calling APIM
  - RBAC through EntraID with the new Agent Identity

### Required Azure Infrastructure Components
The following Azure resources MUST be provisioned in the Bicep templates.
The architecture plan MUST include every resource below as a named component:

  | Resource | Azure Type | Purpose | WAF Pillar |
  |----------|-----------|---------|------------|
  | **Azure Key Vault** | `Microsoft.KeyVault/vaults` | Secret management — all secrets, connection strings, API keys, and certificates MUST be stored here. No secrets in app settings or environment variables. | Security |
  | **Azure Log Analytics workspace** | `Microsoft.OperationalInsights/workspaces` | Observability — all resources MUST send diagnostics and telemetry here. Single pane of glass for monitoring. | Operational Excellence |
  | **Azure Managed Identity (system-assigned)** | (system-assigned on each resource) | Passwordless auth — every service (Container App, APIM, Key Vault) MUST use Managed Identity. No service principal secrets. | Security |
  | **Azure Container Registry (ACR)** | `Microsoft.ContainerRegistry/registries` | Private container registry to store the MCP server image. | Performance Efficiency |
  | **Azure Redis Cache** | `Microsoft.Cache/redis` | Response caching and session management (Basic C0 tier). | Performance Efficiency |
  | **Azure Cosmos DB** | `Microsoft.DocumentDB/databaseAccounts` | Persistent state and low-latency data access (serverless tier). | Reliability |

### Monitoring & Security
  - Azure Monitor alert rules for proactive monitoring of failures, latency, and resource utilisation
  - **Azure Monitor dashboard** (`Microsoft.Portal/dashboards`) MUST be provisioned for real-time visibility into application health (WAF: Operational Excellence)
  - Web Application Firewall (WAF) policy on APIM for public-facing endpoint protection

Copilot Studio is SaaS. If necessary simply provide a readme on how to configure it.



## Scalability Requirements
This is a demonstration lab to prove out connecting. It does not need high scalability. If higher SKUs are necessary for features, use them.
- **[WAF/Cost Optimization]** Right-size all compute SKUs to the minimum tier that supports the required feature set (cost-optimised). Do not over-provision.
- **[WAF/Performance Efficiency]** Enable horizontal auto-scaling (minReplicas: 1, maxReplicas: 3) on the Container App so the pattern can be validated under light load
- **[WAF/Performance Efficiency]** Use Azure Container Registry (ACR) as the private container registry for the MCP server image

## Security & Compliance
The solution must use EntraID, Managed Identities, and the new Agent Identity feature of EntraID.
- **[WAF/Security] Azure Key Vault** is REQUIRED -- all secrets, certificates, and connection strings stored in Key Vault with soft-delete and purge protection enabled. The architecture plan MUST include Key Vault as a component.
- **[WAF/Security] Managed Identity** is REQUIRED -- system-assigned managed identity on every Azure resource for passwordless authentication. The architecture plan MUST include Managed Identity as a component.
- **[WAF/Security] Least-privilege RBAC** is REQUIRED -- every role assignment must use the narrowest built-in role (e.g., Key Vault Secrets User, not Contributor). The architecture plan MUST reflect least-privilege RBAC.
- Web Application Firewall (WAF) enabled on public-facing APIM endpoints
- **[WAF/Operational Excellence] Log Analytics** is REQUIRED -- all diagnostic settings must route to the Log Analytics workspace. The architecture plan MUST include Log Analytics as a component.

## Performance Requirements
This is a demonstration lab. No strict performance requirements.
- Azure Redis Cache MUST be provisioned for response caching and session management
- Use Basic tier (C0) for cost efficiency in the demo environment

## Integration Requirements

- APIM must connect to the MCP server via Managed Identity
- Copilot Studio must connect to APIM
- Azure Cosmos DB MUST be provisioned for persistent state and low-latency data access (serverless tier for cost efficiency)

## Configuration

- **App Type**: api
- **Data Stores**: blob, redis, cosmos
- **Region**: eastus2
- **Environment**: dev
- **Auth**: managed-identity
- **Compliance**: SOC2

## Acceptance Criteria

- Copilot Studio successfully calls the MCP server through APIM and receives a valid response
- All services authenticate via Managed Identity (no stored credentials)
- Key Vault is provisioned and all secrets are referenced from it
- Log Analytics workspace receives telemetry from all deployed resources
- Azure Monitor alerts are configured for failures and latency
- Azure Monitor dashboard is provisioned for real-time application health visibility
- WAF policy is active on the APIM public endpoint
- RBAC roles follow least-privilege principle
- Azure Container Registry is provisioned as a private image registry
- Azure Redis Cache is provisioned for response caching
- Horizontal auto-scaling is enabled on the Container App
- CI/CD pipeline deploys automatically on merge to main
- Zero critical findings in security scan
- Deployment and configuration documentation exists for both infra and Copilot Studio setup

## Version

- **Version**: 4
- **Based On**: 3
- **Changes**: v4 -- Added Azure resource types to infrastructure table for planner clarity. Tagged each requirement with WAF pillar (Security, Cost Optimization, Performance Efficiency, Operational Excellence). Added explicit "architecture plan MUST include" directives for Key Vault, Log Analytics, and Managed Identity. Expanded Acceptance Criteria with dashboard, ACR, Redis, and auto-scaling checks.

## Notes

- CI/CD should enable automatic deployment on merge to main for faster feedback loops
- This is a lab/demo environment; cost optimization matters more than high availability
- The orchestrator uses every section to analyse requirements, design architecture, generate infrastructure, produce tests, and suggest improvements. Each re-run with updated content brings the solution closer to production readiness.
