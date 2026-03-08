# Responsible AI Notes

> Enterprise DevEx Orchestrator — Responsible AI Considerations

## Overview

The Enterprise DevEx Orchestrator uses AI (GitHub Copilot SDK / Azure OpenAI)
to parse business intent and generate architecture plans. This document
outlines the Responsible AI considerations for this system.

## How AI Is Used

| Feature | AI Role | Non-AI Fallback |
|---------|---------|-----------------|
| Intent Parsing | LLM extracts structured data from natural language | Rule-based keyword extraction |
| Architecture Planning | LLM generates context-specific ADRs and threat descriptions | Template-based ADRs with standard content |
| Governance Review | Policy rules are deterministic (no LLM) | N/A — always rule-based |
| Code Generation | Templates are deterministic (no LLM) | N/A — always template-based |

## Key Principle: Deterministic Where It Matters

The system is designed so that **security-critical decisions are never delegated
to the LLM**:

- **Infrastructure structure** (which Azure services, which Bicep modules) is deterministic
- **Security controls** (RBAC, soft delete, encryption) are hard-coded in templates
- **Governance policies** (required components, anti-patterns) are rule-based
- **CI/CD workflows** (OIDC, CodeQL, Dependabot) are template-generated

The LLM only influences:
- How natural language is parsed into structured fields
- The prose content of ADR descriptions and threat narratives
- Project naming suggestions

## Fairness
- The system treats all input equally regardless of source
- No user profiling or discriminatory processing
- Output quality depends on input specificity, not user characteristics

## Reliability & Safety
- Rule-based fallback ensures the system works without LLM access
- All generated infrastructure passes governance validation
- Health probes and auto-scaling ensure deployed workloads are resilient
- Rollback procedures are documented for every deployment

## Privacy & Security
- No PII is stored in logs (structlog with sanitized fields)
- User intent text is processed in-memory, not persisted beyond the session
- Managed Identity eliminates credential exposure
- Key Vault for all secret management

## Transparency
- Every architecture decision is documented as an ADR
- Governance validation results are surfaced with specific check IDs
- Generated code is human-readable and auditable
- The system never hides what it generates

## Accountability
- Deployment requires explicit manual trigger
- Log Analytics provides full audit trail
- RBAC enforces least-privilege access
- GitHub Actions workflows are version-controlled and reviewable

## Limitations

1. **Not a compliance certification tool** — governance checks provide guidance, not legal compliance
2. **LLM outputs should be reviewed** — ADR prose and threat descriptions are AI-generated
3. **Template coverage is bounded** — the system covers common Azure patterns, not all possible architectures
4. **Intent parsing has limits** — very ambiguous or contradictory intents may produce unexpected results

## Contact

For RAI concerns, contact the Enterprise DevEx team or your organization's
Responsible AI office.

---
*Enterprise DevEx Orchestrator Agent*
