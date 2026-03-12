# Enterprise DevEx Orchestrator

Transform business intent into production-ready Azure infrastructure using a 4-agent orchestration pipeline.

---

## What This Does

Give the orchestrator a business description (plain text or a structured intent file) and it generates a complete, deployable enterprise scaffold:

- **Azure Bicep infrastructure** (5-7 modules per scaffold)
- **Multi-language application** scaffold (Python/FastAPI, Node.js/Express, .NET/ASP.NET Core) with enterprise dashboard UI
- **GitHub Actions CI/CD** (validate, deploy, CodeQL, Dependabot)
- **Pytest test suite** (5 auto-generated test files per scaffold)
- **Governance validation** (25 enterprise policies)
- **WAF assessment** (26 Azure Well-Architected Framework principles)
- **Azure Monitor alerts** with action groups and alerting runbook
- **Cost estimation** for Azure resource consumption
- **Operations documentation** (7+ files including threat model, deployment guide, alerting runbook)

Every scaffold enforces enterprise security baselines: Managed Identity, Key Vault with RBAC, non-root containers, OIDC for CI/CD, and HTTPS-only with TLS 1.2+.

Generated applications include a **production-grade enterprise dashboard** with live health monitoring, Key Vault status, architecture & compliance badges, and API endpoint directory -- all rendered dynamically from the intent specification.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- PowerShell (Windows) or a Unix shell

### Install

```powershell
git clone https://github.com/Oluseyi-Kofoworola/enterprise-devex-orchestrator.git
cd enterprise-devex-orchestrator

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

### Verify

```powershell
devex --help
devex version
```

### Run Tests

```powershell
pytest tests/ -v
```

---

## Usage

### Preview a plan (no files written)

```powershell
devex plan --file examples/intent.md
```

### Generate a scaffold

```powershell
devex scaffold --file examples/intent.md -o ./my-output
```

### Validate a generated scaffold

```powershell
devex validate ./my-output
```

### Create your own intent file

```powershell
devex init -o ./my-project -p my-api-name
# Edit my-project/intent.md with your requirements
devex scaffold --file my-project/intent.md -o ./my-project
```

### Upgrade with a new intent version

```powershell
devex new-version ./my-output
# Edit the generated intent.v2.md
devex upgrade --file ./my-output/intent.v2.md -o ./my-output
devex history ./my-output
```

---

## Example Intent Files

Ready-to-run examples are in [`examples/`](examples/):

| File | Description |
|------|-------------|
| [`intent.md`](examples/intent.md) | Healthcare voice agent (v1) |
| [`intent.v2.md`](examples/intent.v2.md) | Voice agent upgrade (v2) |
| [`contract-review-intent.md`](examples/contract-review-intent.md) | Legal contract review AI |
| [`doc-intelligence-intent.md`](examples/doc-intelligence-intent.md) | Document processing service |

See [`examples/README.md`](examples/README.md) for details on each example.

---

## Output Structure

Each generated scaffold contains:

```
output-dir/
  .devex/                     # State, versioning, and metadata
  .github/workflows/          # CI/CD pipelines (validate, deploy, codeql, dependabot)
  infra/bicep/                # Azure Bicep templates (main + modules + parameters)
  src/app/                    # FastAPI application + Dockerfile
  tests/                      # Auto-generated test suite (5 files)
  docs/                       # Architecture, security, WAF, governance, deployment docs
```

---

## CLI Reference

| Command | Purpose |
|---------|---------|
| `devex init` | Create a structured `intent.md` template |
| `devex plan` | Preview architecture plan without generating files |
| `devex scaffold` | Run full pipeline and generate scaffold |
| `devex validate` | Validate a scaffold against 25 governance policies |
| `devex deploy` | Deploy generated Bicep to Azure (staged) |
| `devex upgrade` | Upgrade an existing scaffold from a versioned intent file |
| `devex history` | Show scaffold version history |
| `devex new-version` | Create next intent template from existing output |
| `devex version` | Show CLI and runtime details |

---

## Architecture

The orchestrator uses a **4-agent chain** with a governance feedback loop:

```
Intent --> [Intent Parser] --> [Architecture Planner] --> [Governance Reviewer] --> [Infrastructure Generator]
                                        ^                         |
                                        \--- feedback loop -------/
```

Each agent has a distinct role, instruction set, and tool access. See [`AGENTS.md`](AGENTS.md) for the full specification.

### Enterprise Standards Engine

| Component | Description |
|-----------|-------------|
| NamingEngine | Azure CAF naming conventions (20 resource types, 34 region abbreviations) |
| TaggingEngine | Enterprise tagging (7 required + 5 optional tags with regex validation) |
| WAFAssessor | Azure Well-Architected Framework assessment (5 pillars, 26 principles) |
| StateManager | Persistent state with drift detection, file manifests, audit trail |

### Advanced Patterns

| Pattern | Module |
|---------|--------|
| Skills registry | `src/orchestrator/skills/registry.py` -- 9 pluggable skills, 12 categories |
| Subagent dispatcher | `src/orchestrator/agents/subagent_dispatcher.py` -- parallel fan-out |
| Persistent planner | `src/orchestrator/planning/` -- 13-task DAG with checkpoints |
| Deploy orchestrator | `src/orchestrator/agents/deploy_orchestrator.py` -- staged deployment |
| Enterprise dashboard | `src/orchestrator/generators/app_generator.py` -- multi-language enterprise UI |

---

## Project Structure

```
src/orchestrator/
  agent.py                # 4-agent chain runtime
  config.py               # Configuration management
  intent_file.py          # Markdown intent file parser (9 enterprise sections)
  intent_schema.py        # Pydantic schemas (IntentSpec, PlanOutput, GovernanceReport)
  main.py                 # CLI entry point (9 commands)
  state.py                # State management and drift detection
  versioning.py           # Version tracking, upgrade, and rollback
  agents/
    architecture_planner.py
    deploy_orchestrator.py
    governance_reviewer.py
    intent_parser.py
    subagent_dispatcher.py
  generators/
    alert_generator.py    # Azure Monitor alert rules and runbook
    app_generator.py      # Multi-language application (Python, Node.js, .NET) with enterprise dashboard UI
    bicep_generator.py    # Bicep IaC (7 modules)
    cicd_generator.py     # GitHub Actions workflows (4 files)
    cost_estimator.py     # Cost estimation
    dashboard_generator.py # Azure Monitor dashboard queries
    docs_generator.py     # Documentation (7+ files)
    test_generator.py     # Pytest test suite (5 files)
  planning/               # Persistent planner (13-task DAG)
  prompts/                # Repo-aware prompt generation
  skills/                 # Pluggable skills registry
  standards/              # NamingEngine, TaggingEngine, WAFAssessor
  tools/                  # Azure validation, governance policies, template rendering

tests/                    # Framework test suite (15 files, 543 tests)
examples/                 # Example intent files
docs/                     # Framework documentation
standards.yaml            # Enterprise standards configuration
```

---

## Security

- **Managed Identity** for all service-to-service auth (no credentials in code)
- **Key Vault** with RBAC, soft-delete, and purge protection
- **HTTPS-only** with TLS 1.2+ enforcement
- **Non-root containers** with read-only filesystem
- **OIDC** for CI/CD (no stored secrets)
- **Pydantic validation** on all API inputs
- **STRIDE threat model** generated for every scaffold
- **25 governance policies** validated automatically

---

## Deploy to Azure (Optional)

Deployment requires Azure CLI and an active subscription:

```powershell
az login
az group create --name rg-my-project-dev --location eastus2
devex deploy ./my-output -g rg-my-project-dev -r eastus2
```

For a safe preview:

```powershell
devex deploy ./my-output -g rg-my-project-dev -r eastus2 --dry-run
```

See [`QUICKSTART.md`](QUICKSTART.md) for the full deployment workflow including OIDC setup.

---

## Quality

```powershell
pytest tests/ -v          # Run all tests
ruff check src/ tests/    # Lint
ruff format --check src/  # Format check
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`QUICKSTART.md`](QUICKSTART.md) | Step-by-step installation, scaffolding, and deployment guide |
| [`AGENTS.md`](AGENTS.md) | Agent architecture, tool bindings, and orchestration flow |
| [`examples/README.md`](examples/README.md) | Example intent files and usage |
| [`docs/architecture.md`](docs/architecture.md) | Framework architecture overview |
| [`docs/security.md`](docs/security.md) | Security controls and compliance |
| [`docs/deployment.md`](docs/deployment.md) | Deployment patterns and procedures |
| [`docs/scorecard.md`](docs/scorecard.md) | Enterprise challenge scorecard |

---

## Contributing

All changes must pass:

```powershell
pytest tests/ -v
ruff check src/ tests/
```

Extension points:

- **New generator** -- Add to `src/orchestrator/generators/`
- **New skill** -- Register in `src/orchestrator/skills/registry.py`
- **New governance policy** -- Update `src/orchestrator/tools/governance.py`
- **New example** -- Add an intent file to `examples/`

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| UnicodeEncodeError with Rich spinner on Windows | Set `$env:PYTHONIOENCODING="utf-8"` before running commands |
| `devex deploy` hangs or times out | Verify `az login` session is active and subscription has quota |

---

## Changelog

### v1.2.0

- **Feature**: Enterprise dashboard UI for all generated applications (Python, Node.js, .NET)
  - Gradient topbar, hero header, status cards, live health polling
  - Dynamic architecture & compliance badges from intent specification
  - API endpoint directory with method badges
  - JavaScript live polling for health and Key Vault status
- **Feature**: Multi-language application scaffold (Python/FastAPI, Node.js/Express, .NET/ASP.NET Core)
- **Feature**: `pydantic-settings` added to generated Python requirements
- **Fix**: Node.js and .NET generators now produce HTML landing pages with KEY_VAULT_URI support
- **Tests**: 543 tests across 15 test files (up from 486/14)

### v1.1.1

- **Fix**: `devex deploy` now works on Windows (resolves `az.cmd` via `shutil.which`)
- **Fix**: Deploy default Bicep paths match generated scaffold structure (`infra/bicep/`)
- **Fix**: Container Registry uses Premium SKU with public network access disabled
- **Fix**: Cosmos DB role assignment uses correct `sqlRoleAssignments` resource type
- **Fix**: Redis uses `Redis Cache Contributor` role (available in all subscriptions)
- **Fix**: Container App and Environment names truncated to 32-character limit

---

## License

MIT

---

*Enterprise DevEx Orchestrator v1.2.0*



