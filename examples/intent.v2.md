# secure-document-api

> Build a secure REST API for enterprise document management with blob storage,
> Cosmos DB for metadata, Redis cache for search performance, role-based access
> control, and full audit logging.

## Problem Statement

Our engineering teams manually share project documents through email and shared
drives. There is no central repository, no access control, and no audit trail.
v1 resolved the core problem; v2 addresses performance bottlenecks identified
in load testing -- search latency exceeds p95 targets under sustained load, and
session management relies on stateless tokens without server-side caching.

## Business Goals

- Reduce document retrieval time from ~15 minutes to <5 seconds (carried from v1)
- Achieve SOC2 audit readiness for document management by end of quarter
- Reduce search latency by 60% via Redis caching layer
- Support 1,000 concurrent users (up from 500 in v1 -- doubled target)
- KPI: p95 search latency < 200ms with cache hits (was 500ms target in v1)

## Target Users

- **Engineering Lead** -- uploads and organises project documents daily; intermediate technical proficiency
- **Developer** -- searches and downloads documents multiple times per day; high technical proficiency
- **Compliance Officer** -- reviews audit logs weekly; low technical proficiency
- **External Auditor** -- read-only access to audit reports quarterly; non-technical
- **Platform SRE** -- monitors cache hit rates and performance dashboards; high technical proficiency (new in v2)

## Functional Requirements

- All v1 endpoints preserved: upload, download, search, delete, audit log
- Redis-backed search result caching with 5-minute TTL and cache invalidation on document change
- Session caching: authenticated user context cached in Redis to reduce token validation overhead
- Full-text search improvements: weighted scoring (title > tags > description)
- New endpoint: `GET /api/v1/health/deep` -- checks blob, Cosmos, Redis, Key Vault connectivity
- Cache statistics endpoint: `GET /api/v1/admin/cache-stats` (admin role only)

## Scalability Requirements

- 1,000 concurrent users during peak (doubled from v1)
- 400 requests/second sustained, 1,000 requests/second burst
- Redis cache: 2 GB Standard tier, ~50,000 cached entries at peak
- Data volume: 100,000 documents (~1 TB blob storage) -- year-2 projection
- Auto-scale from 2 to 20 container instances based on CPU/request metrics

## Security & Compliance

- All v1 security controls carried forward (managed identity, Key Vault, RBAC, TLS, private endpoints)
- Redis: private endpoint, TLS-only connections, AAD-based authentication
- Redis data: no PII stored in cache -- only document metadata and search results
- Data classification: same as v1 (Internal, Confidential, Public)
- Compliance: SOC2 Type II -- Redis cache does not store data at rest beyond TTL

## Performance Requirements

- Search latency: p50 < 30ms (cache hit), p95 < 200ms (cache miss), p99 < 500ms
- Other API latency targets unchanged from v1
- Redis cache hit rate target: >80% during steady-state operation
- Availability SLA: 99.9% (unchanged)
- RTO: 4 hours, RPO: 1 hour (unchanged)

## Integration Requirements

- All v1 integrations carried forward
- Redis integration: Azure Cache for Redis, Standard C1 tier
- Cache invalidation: Event Grid subscription triggers cache purge on document create/update/delete
- Monitoring: Redis metrics (cache hits, misses, connected clients, memory) in Application Insights

## Configuration

- **App Type**: api
- **Data Stores**: blob, cosmos, redis
- **Region**: eastus2
- **Environment**: dev
- **Auth**: managed-identity
- **Compliance**: SOC2

## Acceptance Criteria

- All v1 acceptance criteria still pass (regression)
- Search with warm cache returns results in < 200ms at p95
- Cache invalidation occurs within 2 seconds of document change
- Deep health endpoint validates all 4 backing services
- Redis connection uses private endpoint and TLS -- verified in Bicep template
- Cache statistics endpoint returns hit rate, miss rate, eviction count
- Load test: 1,000 concurrent users sustained for 10 minutes without errors

## Improvement Suggestions from v1

The following were identified by the orchestrator after the v1 scaffold run:

1. Consider adding Redis cache for frequently accessed search results
2. Add dashboard alerts for cache hit ratios and Cosmos RU consumption
3. Enable WAF pillar coverage for Performance Efficiency -- add latency benchmarks
4. Add deep health check endpoint that validates all backing service connectivity
5. Consider private endpoints for all data-plane services

## Version

- **Version**: 2
- **Based On**: 1
- **Changes**: Add Redis cache for search performance, increase scale targets, deep health endpoint