# Demo Script

> **Enterprise DevEx Orchestrator** -- 5-minute demonstration
> Shows the full pipeline: intent -> plan -> scaffold -> deploy

---

## Setup

```bash
# Ensure orchestrator is installed
pip install -e .
devex version

# Verify Azure CLI
az account show
```

---

## Segment 1: Intent to Plan (1 min)

**Narration:** "The orchestrator transforms natural language into enterprise architecture."

```bash
# Show the plan without generating files
devex plan --intent "Build a healthcare voice agent API with patient records, voice interaction, and HIPAA compliance"
```

**What to highlight:**
- IntentSpec extraction (project name, app type, data stores, auth model)
- Component selection (Container Apps, Key Vault, Managed Identity, ACR, Log Analytics)
- 6 Architecture Decision Records
- STRIDE threat model (6 categories)
- Mermaid architecture diagram

---

## Segment 2: Scaffold Generation (1 min)

**Narration:** "One command generates a production-ready scaffold with infrastructure, application, CI/CD, tests, and documentation."

```bash
# Generate full scaffold
devex scaffold --intent "Build a healthcare voice agent API" --output-dir ./demo-output
```

**What to highlight:**
- Bicep templates (main.bicep + 7 modules)
- GitHub Actions workflows (4 files)
- FastAPI application + Dockerfile
- Auto-generated pytest test suite (5 test files)
- Azure Monitor alert rules + runbook
- 7 documentation files
- Governance report with 25-policy validation

```bash
# Show generated file tree
find demo-output -type f | head -30

# Show governance passed
cat demo-output/docs/governance-report.md | head -20
```

---

## Segment 3: Enterprise Standards (1 min)

**Narration:** "Every resource follows Azure CAF naming, enterprise tagging, and WAF alignment."

```bash
# Show naming conventions in Bicep
grep "name:" demo-output/infra/bicep/main.bicep

# Show tags
grep -A 10 "tags:" demo-output/infra/bicep/main.bicep

# Show WAF coverage
cat demo-output/docs/waf-report.md | head -30
```

**What to highlight:**
- Azure CAF naming (20 resource types, 34 region abbreviations)
- Enterprise tagging (7 required + 5 optional tags with regex validation)
- WAF 5-pillar assessment (26/26 principles)
- Standards enforced via `standards.yaml` configuration

---

## Segment 4: Live Deployment (1.5 min)

**Narration:** "This exact pipeline deploys to Azure Container Apps with enterprise security."

```bash
# Deploy the generated scaffold
devex deploy --output-dir ./demo-output --resource-group $RG --region eastus2

# Show the live app
APP_URL=$(az containerapp show --name <project>-dev --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv)
curl https://$APP_URL/health
```

**Open in browser:** `https://$APP_URL`

**What to highlight:**
- Working health endpoint confirms deployment
- Non-root container, Managed Identity, HTTPS-only
- All infrastructure created from Bicep templates
- Observability configured from day one (Log Analytics, diagnostics)

---

## Segment 5: Advanced Patterns (30 sec)

**Narration:** "The orchestrator includes advanced enterprise patterns."

| Pattern | Module | Capability |
|---------|--------|-----------|
| Skills Registry | `src/orchestrator/skills/` | 9 pluggable skills, 12 categories |
| Subagent Dispatcher | `src/orchestrator/agents/` | Parallel fan-out with ThreadPoolExecutor |
| Persistent Planning | `src/orchestrator/planning/` | 13-task DAG with checkpoint resume |
| State Manager | `src/orchestrator/state.py` | Drift detection, SHA-256 manifests |
| Version Manager | `src/orchestrator/versioning.py` | Track, upgrade, rollback scaffolds |
| Deploy Orchestrator | `src/orchestrator/agents/` | 4-stage deployment with error recovery |

```bash
# Show test coverage
pytest tests/ -v --tb=short 2>&1 | tail -5
# 486 passed
```

---

## Backup Plan

If demo environment is unavailable:

1. Run `devex plan` locally (no Azure required)
2. Show a pre-generated scaffold directory
3. Walk through Bicep templates and governance report
4. Show test results: `pytest tests/ -v`

---

*Full pipeline: intent -> parse -> plan -> govern -> generate -> deploy*
*486 tests | 25 policies | 26 WAF principles | Live on Azure Container Apps*


