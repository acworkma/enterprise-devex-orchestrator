# AGENTS.md -- Enterprise DevEx Orchestrator Agent

> This file defines the agent roles, tool bindings, and orchestration flow
> for the Enterprise DevEx Orchestrator -- a GitHub Copilot SDK powered agent
> that transforms business intent into production-ready Azure workloads.

## System Overview

The orchestrator uses a **4-agent chain** architecture where each agent has a
distinct role, instruction set, and tool access. The chain executes sequentially
with a governance feedback loop between the reviewer and planner.

```
Intent -> [Intent Parser] -> [Architecture Planner] -> [Governance Reviewer] -> [Infrastructure Generator]
                                      ^                       |
                                      \-- feedback loop ------/
```

---

## Agent 1: Intent Parser

**Role:** Parse natural-language business intent into a structured `IntentSpec` schema.

**System Instructions:**
```
You are an enterprise architecture intent parser. Given a user's business
description, extract:
- Project name (kebab-case)
- Application type (api, web, worker, event-driven)
- Data stores (blob, cosmos, sql, redis, table)
- Security requirements (auth model, compliance, data classification)
- Observability needs
- CI/CD preferences

Return a complete IntentSpec JSON object. Ask clarifying questions only if
critical information is genuinely ambiguous.
```

**Tools:** None (pure LLM reasoning with structured output)

**Fallback:** Rule-based keyword extraction when LLM is unavailable.

**Input:** Plain-English business intent string  
**Output:** `IntentSpec` (Pydantic model)

---

## Agent 2: Architecture Planner

**Role:** Transform parsed intent into a concrete Azure architecture plan with
components, ADRs, threat model, and Mermaid diagram.

**System Instructions:**
```
You are an Azure Solutions Architect. Given an IntentSpec, produce:
1. Component list with Azure services, Bicep module names, and security controls
2. Architecture Decision Records (ADRs) covering compute, security, IaC, data, and networking
3. STRIDE threat model with mitigations
4. Mermaid architecture diagram

Always include: Container Apps, Managed Identity, Key Vault, Log Analytics,
Container Registry. Add data stores based on the spec.
```

**Tools:**
- `check_policy` -- Validate components against enterprise policies
- `check_region_availability` -- Verify Azure service availability

**Fallback:** Deterministic component builder with template ADRs and threat model.

**Input:** `IntentSpec`  
**Output:** `PlanOutput` (Pydantic model)

---

## Agent 3: Governance Reviewer

**Role:** Validate the architecture plan against enterprise governance policies.
If violations are found, provide actionable recommendations for the planner.

**System Instructions:**
```
You are an enterprise governance reviewer. Evaluate the architecture plan against:
1. Required components (Key Vault, Managed Identity, Log Analytics)
2. Security anti-patterns in Bicep templates
3. Networking controls
4. Observability coverage
5. CI/CD security (OIDC, no stored credentials)
6. Threat model completeness (minimum 4 STRIDE categories)
7. Azure Well-Architected Framework (WAF) 5-pillar alignment

Return a GovernanceReport with PASS, FAIL, or PASS_WITH_WARNINGS status.
Perform WAF assessment against 26 design principles across 5 pillars
(Reliability, Security, Cost Optimization, Operational Excellence,
Performance Efficiency) and return a WAFAlignmentReport.
```

**Tools:**
- `check_policy` -- Evaluate against policy catalog
- `list_policies` -- Retrieve applicable policies
- `validate_bicep` -- Validate Bicep syntax

**Input:** `IntentSpec` + `PlanOutput` (+ optional Bicep files)  
**Output:** `GovernanceReport` (Pydantic model) + `WAFAlignmentReport` (dataclass)

**WAF Assessment:** Evaluates the architecture against 26 Azure Well-Architected
Framework design principles across all 5 pillars. Produces per-pillar coverage
scores, evidence for covered principles, and actionable recommendations for gaps.
Maps governance checks and ADRs to WAF pillars via `GOVERNANCE_TO_WAF` and
`ADR_TO_WAF` lookup tables.

**Feedback Loop:** If status is FAIL, recommendations are fed back to the
Architecture Planner for remediation (max 2 iterations).

---

## Agent 4: Infrastructure Generator

**Role:** Generate all deployable artifacts -- Bicep IaC, CI/CD workflows,
application scaffold, and documentation.

**System Instructions:**
```
You are an infrastructure code generator. Given the validated plan, produce:
1. Bicep templates (main.bicep + modules) with parameters
2. GitHub Actions workflows (validate, deploy, dependabot, codeql)
3. Application scaffold (FastAPI + Dockerfile)
4. Documentation (plan, security, deployment, RAI, demo script)

All generated code must follow enterprise security baselines:
- RBAC over access policies
- Soft delete and purge protection for Key Vault
- Non-root Docker containers
- OIDC for CI/CD authentication
```

**Tools:**
- `render_template` -- Render specific template categories
- `preview_output` -- Preview file manifest before writing
- `validate_bicep` -- Validate generated Bicep syntax

**Sub-generators:**
- `BicepGenerator` -- 7 Bicep modules + parameters + enterprise naming/tagging
- `CICDGenerator` -- 4 GitHub Actions workflows
- `AppGenerator` -- FastAPI app + Docker + requirements
- `DocsGenerator` -- 7 documentation files + standards reference + improvement suggestions
- `TestGenerator` -- Auto-generated pytest test suite (health, API, security, config, storage)
- `AlertGenerator` -- Azure Monitor alert rules (Bicep) + action groups + alerting runbook

**Input:** `IntentSpec` + `PlanOutput` + `GovernanceReport`  
**Output:** `dict[str, str]` -- file path -> content mapping

---

## Tool Registry

| Tool | Category | Agent(s) | Description |
|------|----------|----------|-------------|
| `validate_bicep` | Azure | Reviewer, Generator | Validate Bicep template syntax |
| `validate_deployment` | Azure | Generator | Run az deployment group validate |
| `check_region_availability` | Azure | Planner | Check service availability in region |
| `check_policy` | Governance | Planner, Reviewer | Evaluate against 20-policy catalog |
| `list_policies` | Governance | Reviewer | List all governance policies |
| `explain_policy` | Governance | Reviewer | Get policy details and remediation |
| `render_template` | Generation | Generator | Render a template category |
| `list_templates` | Generation | Generator | List available templates |
| `preview_output` | Generation | Generator | Preview files without writing |

---

## Enterprise Standards Engine

| Component | Description |
|-----------|-------------|
| `NamingEngine` | Azure CAF naming conventions (20 resource types, 34 region abbreviations) |
| `TaggingEngine` | Enterprise tagging (7 required + 5 optional tags with regex validation) |
| `EnterpriseStandardsConfig` | YAML-driven config (`standards.yaml`) for naming, tagging, governance |
| `StateManager` | Persistent state in `.devex/state.json` -- drift detection, file manifests, audit trail |
| `WAFAssessor` | Azure Well-Architected Framework assessment (5 pillars, 26 principles, per-pillar scoring) |

---

## Advanced Patterns

### Skills Registry

**Module:** `src/orchestrator/skills/registry.py`

Pluggable skill system with dynamic discovery, priority-based routing, and execution
tracking. 12 skill categories, 9 built-in skills.

| Skill | Category | Capabilities |
|-------|----------|--------------|
| GovernanceSkill | GOVERNANCE | policy validation, compliance check |
| WAFSkill | GOVERNANCE | WAF assessment, well-architected review |
| ThreatModelSkill | SECURITY | STRIDE analysis, threat modeling |
| NamingSkill | STANDARDS | Azure CAF naming, resource naming |
| TaggingSkill | STANDARDS | enterprise tagging, tag validation |
| BicepGenerationSkill | INFRASTRUCTURE | Bicep templates, IaC generation |
| CICDSkill | CICD | GitHub Actions, CI/CD pipelines |
| AppScaffoldSkill | APPLICATION | FastAPI scaffold, app generation |
| DocumentationSkill | DOCUMENTATION | docs generation, ADR writing |

### Subagent Dispatcher

**Module:** `src/orchestrator/agents/subagent_dispatcher.py`

Dynamic subagent spawning with parallel fan-out (ThreadPoolExecutor) and structured
result aggregation. 6 built-in subagents: Bicep Module, Compliance Check, Cost
Estimation, Security Scan, Doc Writer, Alert Rule.

```
Dispatcher.fan_out([task1, task2, task3]) -> parallel execution -> aggregate results
```

### Persistent Planning

**Module:** `src/orchestrator/planning/__init__.py`

Manus-style persistent, resumable, checkpoint-based task execution. Creates a
13-task dependency graph with retry logic, duration tracking, and plan history.

State persisted to `.devex/plan_state.json` with history in `.devex/plan_history.json`.

### Prompt Generator

**Module:** `src/orchestrator/prompts/generator.py`

Scans user repositories to detect languages, frameworks, security patterns, and
CI/CD configuration. Generates context-enriched prompts for each agent adapted
to the project's technology stack.

### Deploy Orchestrator

**Module:** `src/orchestrator/agents/deploy_orchestrator.py`

Staged Azure deployment engine: validate -> what-if -> deploy-infra -> verify.
8 error categories with regex matching, automatic retry for transient errors,
and actionable remediation suggestions.

---

## Orchestration Model

```python
# Simplified orchestration flow
spec = intent_parser.parse(user_intent)
plan = architecture_planner.plan(spec)

for attempt in range(max_iterations):
    report = governance_reviewer.validate_plan(spec, plan)
    if report.status != "FAIL":
        break
    plan = architecture_planner.remediate(spec, plan, report)

files = infrastructure_generator.generate(spec, plan, report)
write_to_disk(files, output_directory)

# Intent file workflow -- zero-prompt scaffold
from src.orchestrator.intent_file import IntentFileParser
parser = IntentFileParser()
result = parser.parse("intent.md")
spec = intent_parser.parse(result.full_intent)
# ... pipeline continues as above

# Version management -- track, upgrade, rollback
from src.orchestrator.versioning import VersionManager
vm = VersionManager(output_directory)
vm.record_version(parsed_intent, file_count, governance_status)
plan = vm.plan_upgrade(new_intent)
vm.rollback(version_number)
history = vm.get_history()

# Persistent planning -- checkpoint-based execution
planner = PersistentPlanner(output_directory)
planner.create_pipeline_plan(intent, intent_hash)
for task_id in ["parse-intent", "plan-architecture", ...]:
    planner.execute_task(task_id)  # auto-saved to .devex/plan_state.json

# Skills -- pluggable capability routing
registry = create_default_registry()
result = registry.execute("governance", spec=spec, plan=plan)

# Subagents -- parallel fan-out
dispatcher = create_default_dispatcher()
results = dispatcher.fan_out(tasks, max_workers=4)

# State management -- track and detect drift
state_manager = StateManager(output_directory)
state_manager.record_generation(intent, spec, report, files)
drift = state_manager.detect_drift(new_intent)

# Deploy -- staged deployment with error recovery
orchestrator = DeployOrchestrator(output_dir, resource_group, region)
result = orchestrator.deploy()
```

---

## Intent File System

**Module:** `src/orchestrator/intent_file.py`

Markdown-based declarative intent files that force comprehensive enterprise
requirement definition. The parser extracts project name, business description,
9 enterprise requirement sections, configuration, and version metadata.

**Key Components:**
- `IntentFileParser` -- Parses intent.md files including enterprise sections
- `IntentFileResult` -- Parsed result with 9 enterprise fields, full_intent, version_info, config
- `IntentFileVersion` -- Version metadata (version number, based_on, changes)
- `generate_intent_template()` -- Creates a structured enterprise requirements template
- `generate_upgrade_template()` -- Creates upgrade template with improvement suggestions from previous run

**9 Enterprise Requirement Sections:**

| Section | Parsed Field | Purpose |
|---------|-------------|---------|
| Problem Statement | `problem_statement` | Business problem, affected users, cost of inaction |
| Business Goals | `business_goals` | Measurable KPIs, revenue/cost impact |
| Target Users | `target_users` | User personas with roles and proficiency |
| Functional Requirements | `functional_requirements` | Features, endpoints, workflows |
| Scalability Requirements | `scalability_requirements` | Concurrent users, RPS, data volume |
| Security & Compliance | `security_compliance` | Auth, RBAC, encryption, compliance frameworks |
| Performance Requirements | `performance_requirements` | p50/p95/p99 latency, SLA, RTO/RPO |
| Integration Requirements | `integration_requirements` | Upstream/downstream systems, events |
| Acceptance Criteria | `acceptance_criteria` | Functional tests, benchmarks, security scans |

**Heading Aliases:** 28 heading name aliases mapped via `_ENTERPRISE_SECTIONS`
(e.g., "goals" -> `business_goals`, "scaling" -> `scalability_requirements`).

**Completeness Tracking:**
- `enterprise_sections_filled` -- `dict[str, bool]` of which sections have content
- `completeness_pct` -- Percentage of sections filled (0-100%)

**Improvement Suggestions Loop:**
- `generate_upgrade_template()` accepts `improvement_suggestions: list[str]`
- Suggestions from `DocsGenerator.generate_improvement_suggestions()` are embedded
  in the upgrade template's "Improvement Suggestions from vN" section
- Users review, incorporate, and re-run -- each cycle converges toward production

**Supported Configuration:**

| Markdown Field | IntentSpec Field | Values |
|---------------|-----------------|--------|
| App Type | app_type | api, web, worker, event-driven |
| Data Stores | data_stores | blob, cosmos, sql, redis, table |
| Region | region | Any Azure region |
| Environment | environment | dev, staging, prod |
| Auth | auth_model | managed-identity, entra-id, api-key |
| Compliance | compliance | SOC2, HIPAA, PCI, FedRAMP, ISO27001 |

---

## Version Management

**Module:** `src/orchestrator/versioning.py`

Tracks scaffold versions, manages upgrades, and supports rollback.
State is persisted in `.devex/versions.json`.

**Key Components:**
- `VersionManager` -- Core version tracking (record, upgrade, rollback, history)
- `VersionRecord` -- Individual version entry (version, intent, status, file_count)
- `VersionState` -- Full state container (project_name, versions list)
- `UpgradePlan` -- Upgrade diff with summary and notes

**Version Statuses:** `active`, `superseded`, `rolled-back`

**CI/CD Integration:** When upgrading to v2+, the CICDGenerator produces
promotion and rollback GitHub Actions workflows that deploy as Container Apps
revisions with traffic shifting (0% -> health check -> 100%).

---

## CLI Commands

**Module:** `src/orchestrator/main.py`

8 commands accessible via the `devex` CLI entry point:

| Command | Purpose |
|---------|---------|
| `devex init` | Create an intent.md template |
| `devex plan` | Preview architecture plan (no files) |
| `devex scaffold` | Generate full production scaffold |
| `devex validate` | Validate existing scaffold against policies |
| `devex deploy` | Deploy to Azure (staged) |
| `devex upgrade` | Upgrade existing scaffold with new version |
| `devex history` | View version history |
| `devex new-version` | Generate upgrade intent template |
| `devex version` | Show orchestrator version info |

## Security Boundaries

- Agents cannot access external networks during generation
- All secrets are referenced, never embedded in generated code
- Bicep templates use parameter references for sensitive values
- Generated CI/CD workflows use OIDC, never stored credentials
- Tool execution is sandboxed -- no arbitrary code execution
- State files (`.devex/state.json`) contain only hashes, never raw secrets or credentials
- Enterprise tags enforce data-sensitivity classification on every generated resource
