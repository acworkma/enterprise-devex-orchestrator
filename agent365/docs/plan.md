# Architecture Plan: agent365

> This architecture plan outlines the components and design for a validation environment to expose an MCP server via Azure API Management (APIM) with EntraID-based RBAC, enabling integration with Copilot Studio. The solution adheres to SOC2 compliance, cost optimization, and security best practices.

## Intent

```
We are building a validation enviroment for building a sample MCP server, exposing through API Management, connecting to it from Copilot Studio, with the necessary RBAC permissions. Problem Statement: There is no validated reference architecture for exposing an MCP server through Azure API Management and consuming it from Copilot Studio with proper EntraID-based identity (including the new Agent Identity feature). Teams attempting this today must piece together documentation across multiple services, leading to insecure or incomplete implementations. Without a proven pattern, adoption of MCP-based extensibility in Copilot Studio stalls. Business Goals: - Deliver a working end-to-end proof-of-concept in a single sprint
- Validate that Copilot Studio can invoke an MCP server through APIM with EntraID RBAC
- Produce a reusable reference architecture that other teams can clone
- KPI: successful round-trip call from Copilot Studio → APIM → MCP Server and back Target Users: - **Platform Engineer**: Deploys and configures the lab environment (MCP server, APIM, identity). Weekly use. Expert-level Azure and IaC knowledge.
- **AI Developer**: Connects Copilot Studio to the MCP server via APIM to test agent extensibility scenarios. On-demand use. Intermediate Azure proficiency.
- **Security Reviewer**: Validates that RBAC, Managed Identity, and Agent Identity are correctly configured. On-demand use. Expert-level EntraID knowledge. Scalability Requirements: This is a demonstration lab to prove out connecting. It does not need high scalability. If higher SKUs are necessary for features, use them.
- **[WAF/Cost Optimization]** Right-size all compute SKUs to the minimum tier that supports the required feature set (cost-optimised). Do not over-provision.
- **[WAF/Performance Efficiency]** Enable horizontal auto-scaling (minReplicas: 1, maxReplicas: 3) on the Container App so the pattern can be validated under light load
- **[WAF/Performance Efficiency]** Use Azure Container Registry (ACR) as the private container registry for the MCP server image Security & Compliance: The solution must use EntraID, Managed Identities, and the new Agent Identity feature of EntraID.
- **[WAF/Security] Azure Key Vault** is REQUIRED -- all secrets, certificates, and connection strings stored in Key Vault with soft-delete and purge protection enabled. The architecture plan MUST include Key Vault as a component.
- **[WAF/Security] Managed Identity** is REQUIRED -- system-assigned managed identity on every Azure resource for passwordless authentication. The architecture plan MUST include Managed Identity as a component.
- **[WAF/Security] Least-privilege RBAC** is REQUIRED -- every role assignment must use the narrowest built-in role (e.g., Key Vault Secrets User, not Contributor). The architecture plan MUST reflect least-privilege RBAC.
- Web Application Firewall (WAF) enabled on public-facing APIM endpoints
- **[WAF/Operational Excellence] Log Analytics** is REQUIRED -- all diagnostic settings must route to the Log Analytics workspace. The architecture plan MUST include Log Analytics as a component. Performance Requirements: This is a demonstration lab. No strict performance requirements.
- Azure Redis Cache MUST be provisioned for response caching and session management
- Use Basic tier (C0) for cost efficiency in the demo environment Integration Requirements: - APIM must connect to the MCP server via Managed Identity
- Copilot Studio must connect to APIM
- Azure Cosmos DB MUST be provisioned for persistent state and low-latency data access (serverless tier for cost efficiency) Acceptance Criteria: - Copilot Studio successfully calls the MCP server through APIM and receives a valid response
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
- Deployment and configuration documentation exists for both infra and Copilot Studio setup Application type: api. Data stores: blob, redis, cosmos. Azure region: eastus2. Environment: dev. Authentication: managed-identity. Compliance framework: SOC2. - CI/CD should enable automatic deployment on merge to main for faster feedback loops
- This is a lab/demo environment; cost optimization matters more than high availability
- The orchestrator uses every section to analyse requirements, design architecture, generate infrastructure, produce tests, and suggest improvements. Each re-run with updated content brings the solution closer to production readiness.
```

## Executive Summary

This architecture plan outlines the components and design for a validation environment to expose an MCP server via Azure API Management (APIM) with EntraID-based RBAC, enabling integration with Copilot Studio. The solution adheres to SOC2 compliance, cost optimization, and security best practices.

## Components

| Component | Azure Service | Purpose | Bicep Module |
|-----------|--------------|---------|-------------|
| Azure Container Apps | Azure Container Apps | Host the MCP server in a containerized environment with horizontal auto-scaling. | `container-apps.bicep` |
| Azure API Management | Azure API Management | Expose the MCP server APIs with WAF-enabled public endpoints and EntraID-based RBAC. | `api-management.bicep` |
| Azure Key Vault | Azure Key Vault | Store secrets, certificates, and connection strings securely with soft-delete and purge protection. | `key-vault.bicep` |
| Azure Log Analytics | Azure Monitor Log Analytics | Centralized telemetry and diagnostics for all deployed resources. | `log-analytics.bicep` |
| Azure Redis Cache | Azure Cache for Redis | Provide response caching and session management for the MCP server. | `redis-cache.bicep` |
| Azure Cosmos DB | Azure Cosmos DB | Store persistent state and provide low-latency data access in serverless mode. | `cosmos-db.bicep` |
| Azure Blob Storage | Azure Blob Storage | Store unstructured data such as logs or artifacts. | `blob-storage.bicep` |
| Azure Container Registry | Azure Container Registry | Host the container image for the MCP server. | `container-registry.bicep` |


## Architecture Diagram

```mermaid
graph TD
    A[Copilot Studio] -->|EntraID Authentication| B[Azure API Management]
    B -->|Managed Identity| C[Azure Container Apps (MCP Server)]
    C --> D[Azure Redis Cache]
    C --> E[Azure Cosmos DB]
    C --> F[Azure Blob Storage]
    B --> G[Azure Key Vault]
    C --> G
    B --> H[Azure Log Analytics]
    C --> H
    D --> H
    E --> H
    F --> H
```

## Architecture Decision Records


### ADR-001: Use Azure Container Apps for MCP Server Deployment

- **Status:** Accepted
- **Context:** The MCP server needs to be containerized and support horizontal auto-scaling.
- **Decision:** Azure Container Apps was chosen for its serverless container hosting and auto-scaling capabilities.
- **Consequences:** Simplifies deployment and scaling, but requires configuration for private networking and managed identity.

### ADR-002: Enable WAF on Azure API Management

- **Status:** Accepted
- **Context:** Public-facing endpoints require protection against common web vulnerabilities.
- **Decision:** WAF was enabled on APIM to meet security requirements.
- **Consequences:** Adds a layer of security but increases cost slightly.

### ADR-003: Use Azure Key Vault for Secrets Management

- **Status:** Accepted
- **Context:** SOC2 compliance requires secure storage of secrets with soft-delete and purge protection.
- **Decision:** Azure Key Vault was selected to manage secrets securely.
- **Consequences:** Ensures compliance but requires integration with managed identities.

### ADR-004: Provision Azure Redis Cache for Response Caching

- **Status:** Accepted
- **Context:** Caching is required to improve response times and session management.
- **Decision:** Azure Redis Cache was chosen for its low-latency caching capabilities.
- **Consequences:** Improves performance but adds a small cost overhead.

### ADR-005: Use Azure Cosmos DB in Serverless Mode

- **Status:** Accepted
- **Context:** Persistent state storage is required with cost efficiency.
- **Decision:** Azure Cosmos DB in serverless mode was selected for its scalability and low cost.
- **Consequences:** Provides low-latency data access but requires careful cost monitoring.


## Assumptions

- The MCP server will be containerized and deployed using Azure Container Apps.
- Azure Key Vault will be used for all secrets management with soft-delete and purge protection enabled.
- Azure API Management will have a WAF policy enabled for public-facing endpoints.
- Horizontal auto-scaling will be configured for the Container App with minReplicas: 1 and maxReplicas: 3.
- Azure Redis Cache will be used for response caching and session management.
- Azure Cosmos DB will be provisioned in serverless mode for cost efficiency.
- Log Analytics workspace will be used for telemetry and diagnostics.
- RBAC roles will follow the principle of least privilege.

## Open Risks

- Potential complexity in configuring EntraID Agent Identity with APIM and MCP server.
- Ensuring cost optimization while meeting all feature requirements.

## Agent Confidence

**Confidence Level:** 95%

---
*Generated by Enterprise DevEx Orchestrator Agent*
