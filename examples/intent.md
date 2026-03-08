# secure-document-api

> Build a secure REST API for enterprise document management with blob storage,
> Cosmos DB for metadata, role-based access control, and full audit logging.

## Problem Statement

Our engineering teams manually share project documents through email and shared
drives. There is no central repository, no access control, and no audit trail.
Sensitive design documents are accessible to anyone with a network drive link.
Compliance (SOC2) requires us to demonstrate controlled access to documents
and a full audit log of every read, write, and delete — we currently cannot.
The lack of a proper system costs ~40 engineer-hours/month in document hunting
and creates audit findings every quarter.

## Business Goals

- Reduce document retrieval time from ~15 minutes (searching email/shares) to <5 seconds
- Achieve SOC2 audit readiness for document management by end of quarter
- Centralise 100% of project documents into a managed, access-controlled store
- Provide real-time audit trail visible to compliance officers
- KPI: Zero audit findings related to document access control within 6 months

## Target Users

- **Engineering Lead** — uploads and organises project documents daily; intermediate technical proficiency
- **Developer** — searches and downloads documents multiple times per day; high technical proficiency
- **Compliance Officer** — reviews audit logs weekly; low technical proficiency, needs a clear UI/API
- **External Auditor** — read-only access to audit reports quarterly; non-technical

## Functional Requirements

- REST API endpoints: upload document (multipart), download by ID, search by metadata, delete (soft)
- Metadata storage in Cosmos DB: document name, owner, tags, created/modified timestamps, classification
- Binary storage in Azure Blob: immutable tier for compliance, standard tier for working docs
- Full-text search across document metadata (name, tags, description)
- Role-based access: admin (full), editor (upload/download/search), viewer (download/search), auditor (read audit logs)
- Audit log for every API call: who, what, when, outcome (success/failure)
- Batch upload support (up to 50 documents per request)
- Webhook notifications on document upload and classification change

## Scalability Requirements

- 500 concurrent users during peak hours (9am-5pm business hours)
- 200 requests/second sustained, 500 requests/second burst
- Initial data volume: 50,000 documents (~500 GB blob storage)
- Growth: 20% year-over-year in document count and storage
- Single region initially (eastus2), with multi-region readiness in architecture
- Auto-scale from 2 to 10 container instances based on CPU/request metrics

## Security & Compliance

- Authentication: Azure AD (Entra ID) via managed identity for service-to-service, OAuth2 for users
- Authorisation: RBAC with 4 roles (admin, editor, viewer, auditor) enforced at API layer
- Data classification: Internal (default), Confidential (restricted download), Public (no restrictions)
- Encryption: TLS 1.2+ in transit, AES-256 at rest (platform-managed keys)
- Network: Private endpoints for blob and Cosmos, no public internet access to data stores
- Compliance frameworks: SOC2 Type II
- Secret management: Azure Key Vault with RBAC access policy, soft delete, purge protection
- No secrets in code, config, or CI/CD — all via managed identity or Key Vault references

## Performance Requirements

- API response latency: p50 < 100ms, p95 < 300ms, p99 < 1s (metadata operations)
- Document upload latency: p95 < 5s for files up to 100MB
- Search latency: p95 < 500ms for queries returning up to 100 results
- Availability SLA: 99.9% uptime
- RTO: 4 hours, RPO: 1 hour (geo-redundant blob storage)
- Cold start time: < 3 seconds for container instances

## Integration Requirements

- Upstream: Azure AD for authentication tokens, corporate SAML IdP federation
- Downstream: Notification service (webhook POST on document events)
- Third-party: None in v1 (future: SharePoint sync, Teams notification bot)
- Event-driven: Document upload triggers classification pipeline via Event Grid
- Monitoring: Application Insights for telemetry, Log Analytics for audit queries

## Configuration

- **App Type**: api
- **Data Stores**: blob, cosmos
- **Region**: eastus2
- **Environment**: dev
- **Auth**: managed-identity
- **Compliance**: SOC2

## Acceptance Criteria

- All CRUD endpoints return correct HTTP status codes and JSON responses
- RBAC enforcement: viewer cannot upload, auditor cannot delete — verified by integration tests
- Audit log captures 100% of API calls with correct metadata
- Upload handles files from 1 KB to 100 MB without timeout or data corruption
- Search returns relevant results within p95 latency target
- Infrastructure deploys successfully via `az deployment group create` with zero manual steps
- CI/CD pipeline passes: lint, unit tests, integration tests, security scan (CodeQL), Bicep validation
- Governance validation passes with no FAIL status
- SOC2-required controls (access control, audit logging, encryption at rest) are demonstrably present

## Version

- **Version**: 1
- **Based On**: none
- **Changes**: Initial scaffold — enterprise document management API