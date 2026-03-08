# Enterprise DevEx Orchestrator Agent

> **GitHub Copilot SDK Enterprise Challenge — Q3 FY26**

A GitHub Copilot SDK powered agent that transforms structured business requirements
into production-ready, secure, deployable Azure workloads — with governance validation,
threat modeling, and CI/CD built in from the start.

**Define. Generate. Improve. Repeat until production-ready.**

---

## Table of Contents

- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start — Try It in 2 Minutes](#quick-start--try-it-in-2-minutes)
- [Complete CLI Reference](#complete-cli-reference)
- [Describe → Run → Iterate Workflow](#describe--run--iterate-workflow)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Advanced Patterns](#advanced-patterns)
- [Enterprise Guardrails](#enterprise-guardrails)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Challenge Alignment](#challenge-alignment)

---

## The Problem

Enterprise teams spend **weeks** translating business requirements into production
infrastructure. The gap between "we need a secure API" and a deployable, compliant
Azure workload involves:

- Architecture decisions buried in meetings
- Security reviews that happen too late
- Infrastructure that doesn't match the docs
- CI/CD pipelines bolted on as an afterthought
- Governance violations caught in production

## The Solution

**Define requirements once. Generate everything. Improve iteratively.**

Enterprise solutions require structured, comprehensive requirement definition —
not a one-liner. The orchestrator forces you to clearly define every stage of
your solution, then analyses, designs, implements, tests, and suggests
improvements in a single run. Each re-run with updated requirements brings
the solution closer to production readiness.

```bash
# Step 1: Create a comprehensive requirements template
devex init

# Step 2: Fill in every section — problem, goals, users, security, scalability, etc.
# (The template guides you through each enterprise-standard requirement)

# Step 3: Generate, test, and get improvement suggestions — one command
devex scaffold --file intent.md -o ./my-project

# Step 4: Review docs/improvement-suggestions.md
# Step 5: Update intent.md with improvements, re-run — each run converges toward production
```

The orchestrator runs a **4-agent chain** powered by GitHub Copilot SDK:

```
Intent Parser → Architecture Planner → Governance Reviewer → Infrastructure Generator
                        ↑                       |
                        └── feedback loop ──────┘
```

### What You Get

From a single command, you receive **36+ production files**:

| Category | Artifacts |
|----------|-----------|
| **Infrastructure** | Modular Bicep templates (main + 6 modules), parameter files |
| **Security** | Managed Identity, Key Vault (RBAC + soft delete), STRIDE threat model |
| **CI/CD** | GitHub Actions with OIDC auth, CodeQL, Dependabot |
| **Application** | FastAPI scaffold with health endpoint, non-root Docker container |
| **Testing** | Auto-generated pytest suite (health, API, security, config, storage tests) |
| **Alerting** | Azure Monitor alert rules (Bicep), action groups, alerting runbook |
| **Documentation** | Architecture plan, ADRs, security docs, RAI notes, deployment guide, standards reference |
| **Governance** | 15-policy validation with actionable remediation |
| **Enterprise Standards** | Azure CAF naming conventions, 12-tag tagging standard, YAML-driven config |
| **State Management** | Drift detection, generation history, file manifest with SHA-256 hashing |
| **Skills Registry** | Pluggable skill system with dynamic discovery, routing, and execution |
| **Subagent Dispatch** | Parallel fan-out subagent spawning with result aggregation |
| **Persistent Planning** | Checkpoint-based task execution with resume, retry, and history |
| **Prompt Engineering** | Codebase-aware prompt generation that adapts to the user's project |
| **Improvement Suggestions** | Per-run analysis of gaps in governance, security, WAF, observability — fed back into the next iteration |

---

## Prerequisites

| Requirement | Version | Check Command |
|------------|---------|---------------|
| **Python** | 3.11 or higher | `python --version` |
| **pip** | Latest | `pip --version` |
| **Azure CLI** | Latest (for deploy only) | `az --version` |
| **Git** | Any | `git --version` |

> **Note:** Azure CLI and an Azure subscription are only needed if you want to
> deploy the generated infrastructure. All scaffold generation works offline.

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd "GitHub Copilot SDK Enterprise Challenge"

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Windows (CMD):
.venv\Scripts\activate.bat
# On macOS/Linux:
source .venv/bin/activate

# 4. Install the project and dev dependencies
pip install -e ".[dev]"

# 5. Configure environment (optional — works without it)
copy .env.example .env
# Edit .env with your credentials (see .env.example for details)
```

After installation, the `devex` command is available in your terminal:

```bash
devex --help
```

---

## Quick Start — Try It in 2 Minutes

### Option A: Structured Enterprise Workflow (Recommended)

```bash
# Step 1: Generate the enterprise requirements template
devex init

# Step 2: Open intent.md and fill in every section:
#   - Problem Statement: What business problem does this solve?
#   - Business Goals: Measurable outcomes
#   - Target Users: Who uses it and how?
#   - Functional Requirements: What it must do
#   - Scalability: Load expectations and growth targets
#   - Security & Compliance: Auth, data classification, frameworks
#   - Performance: Latency, throughput, SLA targets
#   - Integration: External systems and APIs
#   - Acceptance Criteria: Conditions for "done"
#   - Configuration: App type, data stores, region, auth

# Step 3: Run the full pipeline — analyse, design, implement, test, suggest
devex scaffold --file intent.md -o ./my-project

# Step 4: Review docs/improvement-suggestions.md for what to refine
# Step 5: Update intent.md, increment the version, re-run
```

### Option B: Quick Inline Scaffold

For quick prototyping, you can still pass intent inline:

```bash
devex scaffold "Build a secure REST API with blob storage" -o ./my-project
```

### Option C: Plan Only (No Files Generated)

```bash
devex plan --file intent.md
```

This runs the analysis and shows the architecture plan, governance report,
and WAF assessment without generating files.

### Explore the Output

After scaffolding, explore what was generated:

```
my-project/
├── .devex/                  # Metadata (spec, plan, governance, state, versions)
├── .github/workflows/       # CI/CD pipelines (validate, deploy, codeql, dependabot)
├── infra/bicep/             # Azure Bicep IaC (main + 6 modules + parameters)
├── src/app/                 # FastAPI application + Dockerfile
├── tests/                   # Auto-generated pytest test suite
├── docs/                    # Architecture, security, deployment, RAI docs
├── monitoring/              # Azure Monitor alert rules + runbook
└── ...
```

---

## Complete CLI Reference

The `devex` CLI provides 8 commands. Here is every command with all flags:

### `devex init` — Create an Intent File Template

```bash
devex init                           # Creates intent.md in current directory
devex init -o ./my-project           # Creates intent.md in specified directory
devex init -p my-cool-api            # Sets project name in the template
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--output` | `-o` | `.` (current dir) | Directory to create intent.md in |
| `--project` | `-p` | `my-secure-api` | Default project name in template |

### `devex plan` — Preview Architecture Plan (No Files)

```bash
devex plan "Build a secure REST API with blob storage"
devex plan --file intent.md
devex plan --file intent.md -F json          # JSON output format
devex plan "Build an API" -o ./docs-only     # Save plan docs to directory
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--file` | `-f` | none | Path to intent .md file (overrides inline intent) |
| `--output` | `-o` | `./out` | Output directory for plan docs |
| `--format` | `-F` | `text` | Output format: `text` or `json` |

### `devex scaffold` — Generate Full Production Scaffold

```bash
devex scaffold "Build a secure REST API with blob storage" -o ./my-project
devex scaffold --file intent.md -o ./my-project
devex scaffold --file intent.md --dry-run    # Preview without writing files
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--file` | `-f` | none | Path to intent .md file (overrides inline intent) |
| `--output` | `-o` | `./out` | Output directory for all generated artifacts |
| `--dry-run` | — | false | Show what would be generated without writing files |

### `devex validate` — Validate Existing Scaffold

```bash
devex validate ./my-project
```

Validates a previously generated scaffold against governance policies, checks
for drift, and re-runs the governance reviewer on the existing plan.

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Directory of a generated scaffold (must have `.devex/` metadata) |

### `devex deploy` — Deploy to Azure

```bash
devex deploy ./my-project -g my-resource-group -r eastus2
devex deploy ./my-project -g my-rg -r eastus2 --dry-run        # Validate + what-if only
devex deploy ./my-project -g my-rg -r eastus2 -s <subscription-id>
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--resource-group` | `-g` | (required) | Azure resource group name |
| `--region` | `-r` | `eastus2` | Azure region |
| `--subscription` | `-s` | `""` | Azure subscription ID |
| `--dry-run` | — | false | Validate and what-if only (no deploy) |

### `devex upgrade` — Upgrade Existing Scaffold

```bash
devex upgrade --file intent.v2.md -o ./my-project
devex upgrade --file intent.v2.md -o ./my-project --dry-run
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--file` | `-f` | (required) | Path to upgrade intent .md file |
| `--output` | `-o` | `./out` | Output directory of existing scaffold |
| `--dry-run` | — | false | Show upgrade plan without executing |

### `devex history` — View Version History

```bash
devex history ./my-project
```

Shows a table of all versions (version number, status, changes, file count,
governance result, timestamp).

| Argument | Required | Description |
|----------|----------|-------------|
| `PATH` | Yes | Directory of a generated scaffold |

### `devex new-version` — Generate Upgrade Template

```bash
devex new-version ./my-project                  # Creates intent.v2.md in the scaffold dir
devex new-version ./my-project -o ./intent.v2.md  # Custom output path
```

Pre-fills an upgrade intent template from the current version's data so you
only describe what's changing.

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--output` | `-o` | `<path>/intent.v<N>.md` | Where to write the new intent file |

### `devex version` — Show Version Info

```bash
devex version
```

Shows the orchestrator version, Python version, platform, LLM backend, and region.

---

## Describe → Run → Iterate Workflow

Define your enterprise requirements once in a structured markdown file, run one
command to get a full production scaffold, then refine iteratively based on
automated improvement suggestions.

### Step 1: Initialize an Intent File

```bash
devex init
# Creates intent.md — a structured enterprise requirements template
```

### Step 2: Fill In Every Section of `intent.md`

The template contains **9 enterprise requirement sections** — each with guidance
comments that explain exactly what to write. Fill in all of them:

| Section | What to Define |
|---------|---------------|
| **Problem Statement** | The business problem, who is affected, cost of inaction |
| **Business Goals** | Measurable outcomes, KPIs, revenue/cost impact |
| **Target Users** | User personas with roles, frequency, technical proficiency |
| **Functional Requirements** | Core features, API endpoints, error handling, workflows |
| **Scalability Requirements** | Concurrent users, requests/sec, data volume, growth plan |
| **Security & Compliance** | Auth model, RBAC, data classification, compliance frameworks |
| **Performance Requirements** | p50/p95/p99 latency, SLA targets, RTO/RPO |
| **Integration Requirements** | Upstream/downstream systems, third-party APIs, event flows |
| **Acceptance Criteria** | Functional tests, performance benchmarks, security scans |

Plus the existing **Configuration** (app type, data stores, region, auth, compliance)
and **Version** sections.

**Tip:** The more detail you provide, the better the generated architecture,
security controls, and infrastructure. Sections left empty still produce valid
output but with generic defaults.

**Supported configuration values:**

| Field | Allowed Values |
|-------|---------------|
| **App Type** | `api`, `web`, `worker`, `event-driven` |
| **Data Stores** | `blob`, `cosmos`, `sql`, `redis`, `table` (comma-separated) |
| **Region** | Any Azure region (e.g., `eastus2`, `westus3`, `uksouth`) |
| **Environment** | `dev`, `staging`, `prod` |
| **Auth** | `managed-identity`, `entra-id`, `api-key` |
| **Compliance** | `SOC2`, `HIPAA`, `PCI`, `FedRAMP`, `ISO27001` (comma-separated) |

### Step 3: Scaffold Everything

```bash
devex scaffold --file intent.md -o ./my-project
```

This runs the full pipeline (parse → plan → govern → generate) and writes all
artifacts to `./my-project`. The console shows:

- **Requirements completeness** — percentage of sections filled
- **Architecture plan** — Azure services and ADRs
- **Governance report** — policy compliance status
- **WAF assessment** — Well-Architected Framework alignment
- **Improvement suggestions** — what to refine in the next iteration

### Step 4: Review Suggestions & Iterate

Every run produces `docs/improvement-suggestions.md` — a prioritised list of
gaps in governance, security, observability, and architecture. Use it:

```bash
# 1. Review suggestions
cat ./my-project/docs/improvement-suggestions.md

# 2. Update intent.md based on what the suggestions say
# 3. Increment the version number in intent.md
# 4. Re-run scaffold — the improved requirements produce a better scaffold
devex scaffold --file intent.md -o ./my-project
```

Each cycle tightens the gap between requirements and production readiness.

### Step 5: Versioned Upgrades

When your requirements change significantly, create a dedicated v2 intent:

```bash
# Generate a pre-filled upgrade template carrying forward v1 sections
# and embedding improvement suggestions from the previous run
devex new-version ./my-project

# Edit intent.v2.md with your changes, then upgrade
devex upgrade --file intent.v2.md -o ./my-project
```

The upgrade deploys as a new Container Apps **revision** with 0% traffic, runs
health checks, then promotes to 100% — your v1 stays running until v2 is verified.

### Step 6: View History & Rollback

```bash
# View all versions
devex history ./my-project

# If something goes wrong, roll back instantly
# (uses the generated rollback.yml workflow)
```

### How Versioned Deployment Works

```
v1 (active, 100% traffic)
  └─ devex upgrade --file intent.v2.md
       ├─ Deploy v2 revision (0% traffic)
       ├─ Health check v2 revision
       ├─ Promote v2 → 100% traffic
       └─ v1 revision kept (instant rollback available)
```

See [examples/intent.md](examples/intent.md) and [examples/intent.v2.md](examples/intent.v2.md) for complete examples.

### Deploy to Azure

After scaffolding, you can deploy the generated infrastructure:

```bash
# Option 1: Use the devex CLI (staged: validate → what-if → deploy → verify)
devex deploy ./my-project -g my-resource-group -r eastus2

# Option 2: Use Azure CLI directly
cd my-project
az deployment group validate \
  --resource-group my-resource-group \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/parameters/dev.parameters.json

az deployment group create \
  --resource-group my-resource-group \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/parameters/dev.parameters.json
```

> **Note:** Deployment requires Azure CLI logged in (`az login`) and an Azure subscription.
> You can verify scaffold generation works fully without Azure.

---

## Architecture

### Agent Chain

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **Intent Parser** | Parse business intent → structured schema | Plain text | `IntentSpec` |
| **Architecture Planner** | Design Azure architecture with ADRs + threat model | `IntentSpec` | `PlanOutput` |
| **Governance Reviewer** | Validate against enterprise policies + WAF assessment | `IntentSpec` + `PlanOutput` | `GovernanceReport` + `WAFAlignmentReport` |
| **Infrastructure Generator** | Generate all deployable artifacts | `IntentSpec` + `PlanOutput` + `GovernanceReport` + `WAFAlignmentReport` | Files |

### MCP Tool Servers

| Server | Tools | Purpose |
|--------|-------|---------|
| `azure-validator` | `validate_bicep`, `validate_deployment`, `check_region_availability` | Azure resource validation |
| `policy-engine` | `check_policy`, `list_policies`, `explain_policy` | Enterprise governance |
| `template-renderer` | `render_template`, `list_templates`, `preview_output` | Template generation |

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ |
| LLM Backend | GitHub Copilot SDK / Azure OpenAI |
| CLI | Click + Rich |
| Schema | Pydantic v2 |
| IaC | Azure Bicep |
| Compute | Azure Container Apps |
| CI/CD | GitHub Actions (OIDC) |
| Logging | structlog (JSON) |
| Testing | pytest |
| Linting | Ruff + mypy |

---

## Project Structure

```
├── AGENTS.md                          # Agent role definitions
├── mcp.json                           # MCP server declarations
├── pyproject.toml                     # Project config + dependencies
├── .env.example                       # Environment template
├── README.md                          # This file
│
├── src/
│   └── orchestrator/
│       ├── main.py                    # CLI entrypoint (devex command)
│       ├── config.py                  # Configuration dataclasses
│       ├── logging.py                 # Structured logging setup
│       ├── intent_schema.py           # Pydantic models (IntentSpec, PlanOutput, etc.)
│       ├── intent_file.py             # Markdown intent file parser + templates
│       ├── versioning.py              # Version management (record, upgrade, rollback)
│       ├── agent.py                   # AgentRuntime (Copilot SDK integration)
│       │
│       ├── agents/
│       │   ├── intent_parser.py       # Agent 1: Intent → IntentSpec
│       │   ├── architecture_planner.py # Agent 2: IntentSpec → PlanOutput
│       │   ├── governance_reviewer.py  # Agent 3: Plan → GovernanceReport
│       │   ├── infra_generator.py     # Agent 4: Plan → Files
│       │   ├── subagent_dispatcher.py # Parallel fan-out subagent spawning
│       │   └── deploy_orchestrator.py # Staged Azure deployment engine
│       │
│       ├── generators/
│       │   ├── bicep_generator.py     # Bicep IaC templates
│       │   ├── cicd_generator.py      # GitHub Actions workflows
│       │   ├── app_generator.py       # FastAPI application scaffold
│       │   ├── docs_generator.py      # Documentation (plan, security, RAI)
│       │   ├── test_generator.py      # Auto-generated pytest test suite
│       │   └── alert_generator.py     # Azure Monitor alerts + action groups
│       │
│       ├── skills/
│       │   └── registry.py            # Pluggable skill registry (9 built-in skills)
│       │
│       ├── planning/
│       │   └── __init__.py            # Persistent planner (checkpoint, resume, retry)
│       │
│       ├── prompts/
│       │   └── generator.py           # Codebase scanner + context-aware prompts
│       │
│       ├── standards/                 # Enterprise standards engine
│       │   ├── naming.py              # Azure CAF naming conventions
│       │   ├── tagging.py             # Enterprise tagging standard (12 tags)
│       │   ├── config.py              # YAML-driven standards config
│       │   └── waf.py                 # Azure Well-Architected Framework (5 pillars, 26 principles)
│       │
│       ├── state.py                   # State management + drift detection
│       │
│       └── tools/
│           ├── azure_validator.py     # MCP: Bicep + deployment validation
│           ├── policy_engine.py       # MCP: Governance policy engine (20 policies)
│           └── template_renderer.py   # MCP: Template rendering
│
├── standards.yaml                     # Enterprise standards configuration
├── tests/
│   ├── test_intent_parser.py
│   ├── test_governance_validator.py
│   ├── test_generators.py
│   ├── test_standards.py              # 67 tests for naming/tagging/config
│   ├── test_state.py                  # 37 tests for state management
│   ├── test_waf.py                    # 61 tests for WAF 5-pillar assessment
│   ├── test_skills_registry.py        # 26 tests for skill routing/execution
│   ├── test_subagent_dispatcher.py    # 17 tests for subagent spawning/fan-out
│   ├── test_planning.py               # 22 tests for persistent planning
│   ├── test_prompt_generator.py       # 18 tests for codebase scanning
│   ├── test_superpowers.py            # 24 tests for test/alert generators
│   ├── test_deploy_orchestrator.py    # 19 tests for deploy orchestration
│   ├── test_intent_versioning.py      # 33 tests for intent files + versioning
│   └── test_enterprise_features.py    # 37 tests for enterprise intent model
│
├── examples/
│   ├── intent.md                      # Sample v1 intent file
│   └── intent.v2.md                   # Sample v2 upgrade intent file
│
└── docs/                              # (Generated by the agent)
    ├── plan.md
    ├── security.md
    ├── deployment.md
    ├── rai-notes.md
    ├── demo-script.md
    ├── scorecard.md
    ├── governance-report.md
    └── waf-report.md
```

---

## Advanced Patterns

### 1. Skills Registry

A pluggable skill system with dynamic discovery, priority-based routing, and execution
tracking. **9 built-in skills** covering governance, WAF, threat modeling, naming,
tagging, Bicep generation, CI/CD, app scaffolding, and documentation.

```python
registry = create_default_registry()
matches = registry.route("validate governance")   # → GovernanceSkill
result = registry.execute("governance", spec=spec, plan=plan)
```

### 2. Subagent Dispatcher

Dynamic subagent spawning with **parallel fan-out** via `ThreadPoolExecutor` and
structured result aggregation. **6 built-in subagents**: Bicep Module, Compliance
Check, Cost Estimation, Security Scan, Doc Writer, Alert Rule.

```python
dispatcher = create_default_dispatcher()
results = dispatcher.fan_out([task1, task2, task3], max_workers=4)
merged = dispatcher.aggregate(results)
```

### 3. Persistent Planning

Manus-style persistent, resumable, checkpoint-based task execution. Creates a
**13-task dependency graph** for the full pipeline with automatic retry logic,
duration tracking, and plan history (last 10 runs).

```python
planner = PersistentPlanner(Path("./out"))
planner.create_pipeline_plan("Build a secure API", "abc123")
planner.execute_task("parse-intent")  # checkpointed to .devex/plan_state.json
```

### 4. Prompt Generator

Scans the user's repository to detect languages, frameworks, security patterns,
and CI/CD configuration — then generates **context-enriched prompts** for each
agent that adapt to the project's existing technology stack.

```python
gen = PromptGenerator()
gen.scan(Path("./my-project"))
prompt = gen.generate_prompt("intent_parser", "Parse intent.")
# → includes language, framework, security context
```

### 5. Superpowers (Test + Alert + Deploy)

- **TestGenerator**: Auto-generates a pytest suite for the scaffolded FastAPI app
  (conftest, health, API, security, config, conditional storage tests)
- **AlertGenerator**: Produces Azure Monitor alert rules as Bicep, action groups,
  and an alerting runbook with severity tables and escalation procedures
- **DeployOrchestrator**: Staged Azure deployment (validate → what-if → deploy → verify)
  with error classification (8 categories), retry logic, and remediation suggestions

---

## Enterprise Guardrails

Every generated scaffold enforces:

| Control | Implementation |
|---------|---------------|
| **Identity** | User-assigned Managed Identity — no connection strings |
| **Secrets** | Azure Key Vault with RBAC, soft delete, purge protection |
| **Networking** | Private ingress, no public blob access |
| **Encryption** | TLS 1.2+, encryption at rest for storage + Key Vault |
| **Observability** | Log Analytics + diagnostic settings on all resources |
| **CI/CD** | OIDC federation — no stored credentials |
| **Supply Chain** | CodeQL scanning, Dependabot, non-root containers |
| **Governance** | ADRs + STRIDE threat model + 20 governance policies + naming/tagging standards |
| **Well-Architected** | Azure WAF 5-pillar assessment (Reliability, Security, Cost, Ops, Perf) with 26 principles |

---

## Testing

```bash
# Run all tests (433 tests)
pytest tests/ -v

# Run specific test suites
pytest tests/test_intent_versioning.py -v     # Intent file parsing + versioning
pytest tests/test_generators.py -v             # All generators (Bicep, CI/CD, app, docs)
pytest tests/test_governance_validator.py -v   # Governance policies
pytest tests/test_standards.py -v              # Naming/tagging/config (67 tests)
pytest tests/test_waf.py -v                    # WAF 5-pillar assessment (61 tests)
pytest tests/test_state.py -v                  # State management (37 tests)

# Run advanced pattern tests
pytest tests/test_skills_registry.py tests/test_subagent_dispatcher.py tests/test_planning.py tests/test_prompt_generator.py tests/test_superpowers.py tests/test_deploy_orchestrator.py -v

# Run with coverage
pytest tests/ -v --cov=src/orchestrator --cov-report=term-missing

# Lint
ruff check src/ tests/
ruff format --check src/ tests/

# Type check
mypy src/orchestrator/
```

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_standards.py` | 67 | Azure CAF naming, tagging, config engine |
| `test_waf.py` | 61 | WAF 5-pillar assessment (26 principles) |
| `test_state.py` | 37 | State management, drift detection |
| `test_intent_versioning.py` | 33 | Intent files, versioning, CI/CD promotion |
| `test_skills_registry.py` | 26 | Skill routing, execution tracking |
| `test_superpowers.py` | 24 | Test/alert/deploy generators |
| `test_planning.py` | 22 | Persistent planning, checkpoints |
| `test_deploy_orchestrator.py` | 19 | Deploy stages, error recovery |
| `test_prompt_generator.py` | 18 | Codebase scanning, prompt generation |
| `test_subagent_dispatcher.py` | 17 | Parallel fan-out, aggregation |
| `test_generators.py` | varies | Bicep, CI/CD, app, docs generators |
| `test_governance_validator.py` | varies | 15 governance policies |
| `test_enterprise_features.py` | 37 | Enterprise intent model, completeness, suggestions |
| `test_intent_parser.py` | varies | Intent parsing |

---

## Troubleshooting

### "No intent provided" error

You must provide intent either as a quoted string argument or via `--file`:
```bash
# Correct:
devex scaffold "Build a secure API" -o ./out
devex scaffold --file intent.md -o ./out

# Wrong (missing quotes):
devex scaffold Build a secure API -o ./out
```

### Copilot SDK / LLM connection errors

The system works **without** a Copilot SDK or Azure OpenAI connection. When no
LLM is available, it uses **template-only mode** (rule-based parsing). This
produces the same output quality — the LLM only enhances intent parsing.

If you see errors like `Personal Access Tokens are not supported`, this is
expected — the system automatically falls back to template mode.

### "No .devex metadata found"

The `validate`, `deploy`, `upgrade`, `history`, and `new-version` commands
require a scaffold generated by `devex scaffold` first. The `.devex/` directory
contains the metadata these commands need.

```bash
# First, scaffold:
devex scaffold "Build a secure API" -o ./my-project

# Then you can validate, deploy, etc.:
devex validate ./my-project
devex deploy ./my-project -g my-rg -r eastus2
```

### Virtual environment issues

Ensure you activated the virtual environment before running `devex`:
```bash
# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Windows CMD:
.venv\Scripts\activate.bat

# macOS/Linux:
source .venv/bin/activate

# Verify:
devex --help
```

### pip install fails

Make sure you're using Python 3.11+:
```bash
python --version    # Should show 3.11.x or higher
pip install -e ".[dev]"
```

---

## Challenge Alignment

| Criterion | Points | How We Address It |
|-----------|--------|-------------------|
| Enterprise Applicability | 30 | Deterministic scaffold + governance feedback loop + ADRs + WAF 5-pillar assessment + Skills Registry + Persistent Planning |
| Azure Integration | 25 | Bicep + Container Apps + Key Vault + Log Analytics + ACR + OIDC + Azure Monitor alerts + staged deploy |
| Operational Readiness | 15 | CI/CD + health probes + Log Analytics + auto-generated tests + alerting runbook + deploy orchestrator |
| Security & RAI | 15 | Managed Identity + STRIDE + governance report + RAI notes + CodeQL + subagent security scan |
| Storytelling | 15 | Demo script + 3-min video + clear README |

---

## License

Internal — Microsoft Confidential

---

*Built for the GitHub Copilot SDK Enterprise Challenge, Q3 FY26*
