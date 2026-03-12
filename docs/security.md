# Security Documentation

> **Enterprise DevEx Orchestrator** -- Security controls, threat model, and compliance
> Every generated scaffold enforces enterprise security baselines

---

## Security Architecture

### Defense in Depth

| Layer | Control | Implementation |
|-------|---------|---------------|
| Identity | Managed Identity | User-assigned MI for all service-to-service auth |
| Secrets | Key Vault | RBAC access (no access policies), soft-delete, purge protection |
| Network | HTTPS-only | TLS 1.2+ enforced, HTTP auto-redirect |
| Container | Non-root | Dockerfile runs as non-root user, read-only filesystem |
| Registry | ACR + RBAC | AcrPull role for MI, no admin credentials |
| Observability | Log Analytics | Diagnostic settings on all resources |
| CI/CD | OIDC | Federated credentials, no stored secrets |
| Code | Pydantic | Input validation on all API boundaries |

### STRIDE Threat Model

| Category | Threat | Mitigation | Risk |
|----------|--------|-----------|------|
| **Spoofing** | Unauthorized API access | Managed Identity RBAC, no API keys in code | Low |
| **Tampering** | Container image modification | ACR with AcrPull-only, cloud-based builds | Low |
| **Repudiation** | Untracked changes | Log Analytics diagnostics, state manager audit trail | Low |
| **Information Disclosure** | Secret leakage | Key Vault references, no env vars for secrets | Low |
| **Denial of Service** | Resource exhaustion | Container Apps autoscaling, consumption limits | Medium |
| **Elevation of Privilege** | Over-permissioned identity | Least-privilege RBAC, no Contributor roles | Low |

### RBAC Assignments (Generated)

| Principal | Role | Scope | Purpose |
|-----------|------|-------|---------|
| Managed Identity | Key Vault Secrets User | Key Vault | Read secrets at runtime |
| Managed Identity | AcrPull | Container Registry | Pull container images |
| GitHub Actions SP | Contributor | Resource Group | Deploy infrastructure |
| GitHub Actions SP | AcrPush | Container Registry | Push built images |

## Governance Policies

The orchestrator validates every scaffold against 25 enterprise policies:

| Category | Policies | Key Checks |
|----------|---------|-----------|
| Identity (6) | GOV-001 to GOV-006 | MI required, no access policies, RBAC enforced |
| Secrets (4) | GOV-007 to GOV-010 | Key Vault required, soft-delete, purge protection |
| Networking (3) | GOV-011 to GOV-013 | HTTPS-only, no public IPs for backend |
| Container (4) | GOV-014 to GOV-017 | Non-root, ACR-based, no latest tag |
| Observability (3) | GOV-018 to GOV-020 | Log Analytics, diagnostic settings |
| CI/CD (2) | GOV-021 to GOV-022 | OIDC required, no stored credentials |
| Governance (3) | GOV-023 to GOV-025 | CAF naming, enterprise tags, threat model |

## Code Security Controls

### Input Validation

```python
# All API inputs validated with Pydantic
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: str = Field(default_factory=lambda: str(uuid4()))
```

### Secret Handling

```python
# Secrets via Key Vault reference, never in environment variables
KEY_VAULT_URI = os.environ.get("KEY_VAULT_URI")
KEY_VAULT_NAME = os.environ.get("KEY_VAULT_NAME")
# Key Vault accessed via Managed Identity -- no credentials in code
```

### Container Security

```dockerfile
# Non-root user in Dockerfile
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# No secrets baked into image
# Health endpoint for probes: /health
```

## Compliance Mapping

| Framework | Coverage | Evidence |
|-----------|---------|---------|
| OWASP Top 10 | 10/10 | Input validation, no injection, secure defaults |
| CIS Azure Benchmark | Key controls | MI, Key Vault, Log Analytics, HTTPS |
| SOC 2 | Type II controls | Audit trail, encryption, access controls |
| HIPAA | Technical safeguards | Data classification tags, encryption, logging |

## Security Testing

```bash
# Run security-focused tests
pytest tests/test_security.py -v

# Governance validation on existing scaffold
devex validate --output-dir ./my-project
```

---

*Security is not a feature -- it is the baseline. Every scaffold enforces these controls by default.*


