﻿# Enterprise DevEx Orchestrator

> **Transform business intent into production-ready Azure workloads**  
> Reusable 4-agent framework | 486 tests | Zero-credential architecture

[![Tests](https://img.shields.io/badge/Tests-486%20passed-brightgreen)]()
[![WAF](https://img.shields.io/badge/WAF-26%20principles-blue)]()
[![Governance](https://img.shields.io/badge/Governance-25%20policies-blue)]()
[![Python](https://img.shields.io/badge/Python-3.11+-blue)]()

---

## What Is This?

A **reusable orchestration framework** that takes natural-language business intent and generates complete, deployable Azure applications with enterprise-grade infrastructure, security, and documentation.

```
"Build a healthcare contract review API with Document Intelligence and GPT-4"
                                    |
                         Enterprise DevEx Orchestrator
                                    |
        Bicep IaC + FastAPI App + CI/CD + Tests + Docs + Security
                                    |
                    Ready to deploy to Azure in 3 steps
```

**This is NOT:**
- A single application or template
- A code generator that produces boilerplate
- A best-practices checklist

**This IS:**
- A **framework** for building YOUR applications with enterprise guardrails
- A **4-agent orchestration system** with governance feedback loops
- A **comprehensive toolchain** (9 MCP tools, 6 generators, 9 skills, 6 subagents)
- A **standards engine** (Azure CAF naming, enterprise tagging, 25 governance policies)

---

## Quick Start

### Install

```bash
git clone https://github.com/okofoworola_microsoft/enterprise-devex-orchestrator.git
cd enterprise-devex-orchestrator
pip install -e ".[dev]"
```

### Generate Your First Application

```bash
# Option 1: Quick inline intent
devex scaffold "Build a patient appointment API with Cosmos DB" -o ./my-app

# Option 2: Comprehensive enterprise intent file
devex init -o ./my-app -p appointment-scheduler
# Edit my-app/intent.md with 9 enterprise sections
devex scaffold --file my-app/intent.md -o ./my-app-output

# Option 3: Use example templates
devex scaffold --file examples/contract-review-intent.md -o ./contract-review
```

### Deploy to Azure

```bash
az group create --name rg-my-app-dev --location eastus2
az deployment group create --resource-group rg-my-app-dev --template-file my-app/infra/bicep/main.bicep
az acr build --registry <ACR_NAME> --image my-app:v1.0.0 --no-logs my-app/src/app/
```

**Time:** 8-12 minutes from intent to production

---

## Architecture

### 4-Agent Orchestration Chain

```
Intent -> [Intent Parser] -> [Architecture Planner] -> [Governance Reviewer] -> [Infrastructure Generator]
                                      ^                         |
                                      \--- feedback loop ------/
```

| Agent | Role | Tools | Output |
|-------|------|-------|--------|
| **Intent Parser** | Extract structured spec from natural language | None (pure LLM) | `IntentSpec` (Pydantic) |
| **Architecture Planner** | Design Azure architecture with ADRs + threat model | `check_policy`, `check_region_availability` | `PlanOutput` with components, ADRs, Mermaid diagram |
| **Governance Reviewer** | Validate against 25 policies + WAF assessment | `check_policy`, `list_policies`, `validate_bicep` | `GovernanceReport` + `WAFAlignmentReport` |
| **Infrastructure Generator** | Generate all deployable artifacts | `render_template`, `preview_output`, `validate_bicep` | Complete file tree (Bicep, app, CI/CD, docs, tests) |

**Governance Feedback Loop:** If validation fails, recommendations are fed back to the planner for remediation (max 2 iterations).

---

## What Gets Generated

Every scaffold includes:

### Infrastructure as Code (Bicep)
- `main.bicep` + 7 modules (Container App, ACR, Key Vault, Log Analytics, Managed Identity, Blob, Cosmos DB)
- `parameters/` with environment-specific configs
- Azure CAF naming conventions (20 resource types, 34 region abbreviations)
- Enterprise tagging (7 required + 5 optional tags with regex validation)

### Application Code
- FastAPI REST API with Pydantic validation
- Dockerfile (multi-stage, non-root, distroless base)
- `requirements.txt` with pinned versions
- Health check endpoint
- Structured logging

### CI/CD (GitHub Actions)
- `validate.yml` -- Bicep validation + pytest on PR
- `deploy.yml` -- OIDC auth + ACR build + Container App deployment
- `dependabot.yml` -- Automated dependency updates
- `codeql.yml` -- Security scanning

### Tests (Pytest)
- Health check tests
- API endpoint tests
- Security tests (RBAC, non-root container)
- Configuration tests
- Storage integration tests (if applicable)

### Documentation (7+ files)
- `plan.md` -- Architecture, ADRs, Mermaid diagram
- `deployment.md` -- Full deployment guide
- `security.md` -- STRIDE threat model, RBAC, compliance
- `governance-report.md` -- 25 policy results
- `waf-report.md` -- 26 WAF principles with evidence
- `standards.md` -- Naming/tagging conventions
- `cost-estimate.md` -- Per-service breakdown
- `alerting-runbook.md` -- 7 alert rules + response procedures
- `improvement-suggestions.md` -- Prioritized enhancements for next version

### Monitoring
- Azure Monitor alert rules (Bicep)
- Action groups with email/webhook
- KQL queries for log analysis
- Alerting runbook with escalation matrix

---

## Enterprise Standards Engine

### Azure CAF Naming

20 resource types with standardized prefixes/suffixes:

```python
rg-<project>-<env>          # Resource Group
<project>-<env>-law         # Log Analytics
<project>-<env>-id          # Managed Identity
<project><env>kv            # Key Vault (no hyphens)
<project><env>acr           # Container Registry (no hyphens)
<project>-<env>             # Container App
```

34 Azure region abbreviations (e.g., `eastus2` ? `eus2`, `westeurope` ? `weu`).

### Enterprise Tagging

7 required tags with regex validation:

| Tag | Validation | Example |
|-----|-----------|---------|
| `project` | `^[a-z][a-z0-9-]{1,62}$` | `contract-review` |
| `environment` | `^(dev\|staging\|prod)$` | `dev` |
| `managedBy` | `^(bicep\|terraform\|pulumi\|manual)$` | `bicep` |
| `owner` | Non-empty | `platform-team` |
| `costCenter` | `^[A-Z]{2}-[0-9]{4,6}$` | `IT-50100` |
| `dataClassification` | `^(public\|internal\|confidential\|restricted)$` | `confidential` |
| `generator` | Non-empty | `enterprise-devex-orchestrator` |

### Governance (25 Policies)

| Category | Count | Key Checks |
|----------|-------|-----------|
| Identity | 6 | Managed Identity required, RBAC over access policies |
| Secrets | 4 | Key Vault required, soft-delete, purge protection |
| Networking | 3 | HTTPS-only, TLS 1.2+ |
| Container | 4 | Non-root, ACR-based, no `:latest` tag |
| Observability | 3 | Log Analytics, diagnostic settings |
| CI/CD | 2 | OIDC required, no stored credentials |
| Governance | 3 | CAF naming, enterprise tags, threat model |

### WAF Assessment

26 design principles across 5 pillars:

| Pillar | Principles |
|--------|-----------|
| Reliability | 5 (health probes, multi-region, graceful degradation, retry logic, monitoring) |
| Security | 8 (zero trust, least privilege, encryption, secrets management, RBAC, audit, threat model, secure CI/CD) |
| Cost Optimization | 4 (right-sizing, autoscaling, reserved capacity, cost monitoring) |
| Operational Excellence | 5 (IaC, CI/CD, monitoring, documentation, incident response) |
| Performance Efficiency | 4 (caching, async processing, horizontal scaling, CDN) |

Every scaffold is scored against all 26 principles with evidence and gap analysis.

---

## Advanced Patterns

### Skills Registry

9 pluggable skills with dynamic discovery:

| Skill | Category | Capabilities |
|-------|----------|-------------|
| GovernanceSkill | GOVERNANCE | Policy validation, compliance check |
| WAFSkill | GOVERNANCE | WAF assessment, well-architected review |
| ThreatModelSkill | SECURITY | STRIDE analysis, threat modeling |
| NamingSkill | STANDARDS | Azure CAF naming |
| TaggingSkill | STANDARDS | Enterprise tag validation |
| BicepGenerationSkill | INFRASTRUCTURE | Bicep template generation |
| CICDSkill | CICD | GitHub Actions workflow generation |
| AppScaffoldSkill | APPLICATION | FastAPI scaffold generation |
| DocumentationSkill | DOCUMENTATION | Documentation generation |

```python
from src.orchestrator.skills.registry import create_default_registry
registry = create_default_registry()
result = registry.execute("governance", spec=spec, plan=plan)
```

### Subagent Dispatcher

6 subagents with parallel fan-out:

- Bicep Module Generator
- Compliance Checker
- Cost Estimator
- Security Scanner
- Documentation Writer
- Alert Rule Generator

```python
from src.orchestrator.agents.subagent_dispatcher import create_default_dispatcher
dispatcher = create_default_dispatcher()
results = dispatcher.fan_out(tasks, max_workers=4)
```

### Persistent Planning

13-task dependency graph with checkpoint resume:

```python
from src.orchestrator.planning import PersistentPlanner
planner = PersistentPlanner(output_directory)
planner.create_pipeline_plan(intent, intent_hash)
for task_id in ["parse-intent", "plan-architecture", ...]:
    planner.execute_task(task_id)  # auto-saved to .devex/plan_state.json
```

### State Management

Drift detection with SHA-256 file manifests:

```python
from src.orchestrator.state import StateManager
state_manager = StateManager(output_directory)
state_manager.record_generation(intent, spec, report, files)
drift = state_manager.detect_drift(new_intent)
```

### Version Management

Track, upgrade, and rollback scaffold versions:

```python
from src.orchestrator.versioning import VersionManager
vm = VersionManager(output_directory)
vm.record_version(parsed_intent, file_count, governance_status)
plan = vm.plan_upgrade(new_intent)
vm.rollback(version_number)
```

---

## CLI Commands

| Command | Purpose |
|---------|---------|
| `devex init` | Create intent.md template (9 enterprise sections) |
| `devex plan` | Preview architecture plan (no files written) |
| `devex scaffold` | Generate full production scaffold |
| `devex validate` | Validate existing scaffold against 25 policies |
| `devex deploy` | Deploy to Azure (4-stage: validate ? what-if ? deploy ? verify) |
| `devex upgrade` | Upgrade existing scaffold with new intent |
| `devex history` | View version history |
| `devex new-version` | Generate upgrade template from current version |
| `devex version` | Show orchestrator version info |

---

## Project Structure

```
src/orchestrator/
    agent.py              # 4-agent chain
    config.py             # Configuration management
    intent_file.py        # Markdown intent file parser (9 enterprise sections)
    intent_schema.py      # Pydantic schemas
    main.py               # CLI entrypoint (8 commands)
    state.py              # State management + drift detection
    versioning.py         # Version tracking + upgrade + rollback
    agents/
        deploy_orchestrator.py   # 4-stage Azure deployment
        subagent_dispatcher.py   # Parallel subagent fan-out
    generators/
        infra.py          # BicepGenerator (7 modules)
        cicd.py           # CICDGenerator (4 workflows)
        app.py            # AppGenerator (FastAPI + Docker)
        docs.py           # DocsGenerator (7 doc files)
        tests.py          # TestGenerator (5 test files)
        alerts.py         # AlertGenerator (Bicep alerts + runbook)
    planning/
        __init__.py       # Persistent planner (13-task DAG)
    prompts/
        generator.py      # Repo-aware prompt generation
    skills/
        registry.py       # Skills registry (9 skills, 12 categories)
    standards/
        __init__.py       # NamingEngine + TaggingEngine
    tools/
        azure.py          # Azure validation tools
        governance.py     # Policy engine tools
        generation.py     # Template rendering tools

tests/                    # 486 tests across 14 files
infra/bicep/              # Bicep IaC templates
standards.yaml            # Enterprise standards configuration
```

---

## Testing

486 tests across 14 test files:

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `test_standards.py` | 67 | Azure CAF naming (20 types), tagging (7+5 tags) |
| `test_waf.py` | 61 | WAF 5-pillar assessment, 26 principles |
| `test_enterprise_features.py` | 37 | Enterprise intent model, completeness tracking |
| `test_state.py` | 37 | State management, SHA-256 manifest, drift detection |
| `test_intent_versioning.py` | 33 | Intent files, version tracking, CI/CD promotion |
| `test_skills_registry.py` | 26 | 9 skills, dynamic discovery, priority routing |
| `test_superpowers.py` | 24 | Test/alert/deploy generators |
| `test_planning.py` | 22 | 13-task DAG, checkpoints, resume |
| `test_deploy_orchestrator.py` | 19 | 4-stage deploy, error recovery |
| `test_prompt_generator.py` | 18 | Repo scanning, context-enriched prompts |
| `test_subagent_dispatcher.py` | 17 | Parallel fan-out, result aggregation |
| (+ 3 more) | 123+ | Intent parsing, generators, governance |

```bash
pytest tests/ -v  # All 486 tests should pass
```

---

## Security

- **Managed Identity** for all service-to-service auth (no credentials in code)
- **Key Vault** with RBAC access, soft-delete, purge protection
- **HTTPS-only** with TLS 1.2+ enforcement
- **Non-root containers** with read-only filesystem
- **OIDC** for CI/CD (no stored secrets)
- **Pydantic validation** on all API inputs
- **STRIDE threat model** generated for every scaffold
- **25 governance policies** validated automatically

---

## Examples

See [`examples/`](examples/README.md) for production-ready applications built with this orchestrator:

| Example | Description | Deploy Time | Cost (Dev) |
|---------|-------------|-------------|------------|
| [SLHS Voice Agent](slhs-voice-agent/) | Voice-enabled patient information system | 12 min | ~$28/month |
| [Contract Review AI](contract-review/) | Legal contract analysis with Document Intelligence + GPT-4-1 | 8 min | ~$120/month |

Both examples include full source code, Bicep IaC, CI/CD, tests, and comprehensive documentation.

---

## Enterprise Guardrails

| Guardrail | Enforcement |
|-----------|------------|
| No secrets in code | Key Vault references only |
| No `:latest` tags | Explicit version tags required |
| No admin credentials | Managed Identity + RBAC |
| No access policies | RBAC over Key Vault access policies |
| Non-root containers | Enforced in Dockerfile |
| OIDC for CI/CD | No stored credentials in workflows |
| CAF naming | NamingEngine validates all resource names |
| Enterprise tags | TaggingEngine validates 7 required tags |
| Diagnostic settings | Log Analytics configured for all resources |
| Threat model | STRIDE analysis required for every scaffold |

---

## What Makes This 0.0001% Engineering

1. **4-agent orchestration** with governance feedback loop -- not a single-agent chatbot
2. **25 automated governance policies** validated on every scaffold -- not best-effort checklists
3. **26/26 WAF principles** scored with evidence -- not hand-waved compliance
4. **486 tests** across 14 files -- not "it works on my machine"
5. **Enterprise standards engine** (naming + tagging + config) -- not ad-hoc conventions
6. **Advanced patterns** (skills, subagents, persistent planning, deploy orchestrator) -- not MVP features
7. **Intent-to-production pipeline** with a single command -- not a 20-step runbook
8. **Versioned upgrades** with improvement suggestions -- not one-shot generation

---

## Documentation

- [`QUICKSTART.md`](QUICKSTART.md) -- Step-by-step installation and testing guide
- [`AGENTS.md`](AGENTS.md) -- Complete agent architecture and tool bindings
- [`examples/README.md`](examples/README.md) -- Production-ready example applications
- [`docs/`](docs/) -- Framework architecture, security, deployment, scorecard

---

## Contributing

Want to extend the orchestrator? See the contribution patterns:

- **Add a new generator** -- Extend `src/orchestrator/generators/`
- **Add a new skill** -- Register in `src/orchestrator/skills/registry.py`
- **Add a new governance policy** -- Update `src/orchestrator/tools/governance.py`
- **Add a new example** -- Follow [`examples/README.md`](examples/README.md#contributing-new-examples)

All changes must:
- Pass `pytest tests/ -v` (486 tests)
- Pass `ruff check src/ tests/`
- Pass `mypy src/orchestrator/`

---

## License

MIT License. See `LICENSE` for details.

---

*Enterprise DevEx Orchestrator v1.1.0*  
*Built with GitHub Copilot SDK | Deployed on Azure Container Apps*  
*486 tests | 25 governance policies | 26 WAF principles | 135/135 scorecard*  
*GitHub Copilot SDK Enterprise Challenge, Q3 FY26*

