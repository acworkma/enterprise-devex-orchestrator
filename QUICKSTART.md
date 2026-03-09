# Quick Start Guide -- Test Everything Step by Step

> Follow this guide to install, run, and test every feature of the
> Enterprise DevEx Orchestrator. No Azure account needed for local testing.

---

## Step 1: Install

Open a terminal in the project root directory.

```powershell
# Create virtual environment
python -m venv .venv

# Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Install project + dev dependencies
pip install -e ".[dev]"
```

Verify the installation:

```powershell
devex --help
```

You should see a list of commands: `init`, `plan`, `scaffold`, `validate`,
`deploy`, `upgrade`, `history`, `new-version`, `version`.

---

## Step 2: Check Version Info

```powershell
devex version
```

Shows the orchestrator version, Python version, platform, and LLM backend.
If no `.env` file exists, it shows "Config not loaded" -- that's fine.

---

## Step 3: Plan from the Enterprise Example (No Files Generated)

```powershell
devex plan --file examples/intent.md
```

This runs the intent parser, architecture planner, and governance reviewer
against the fully defined enterprise intent file. You will see:
- **Requirements completeness** -- percentage of enterprise sections filled
- **Architecture plan** -- Azure services, ADRs, Mermaid diagram
- **Governance report** -- PASS/FAIL with policy results
- **WAF assessment** -- 5-pillar scores with principle-level detail

No files are written -- this is a preview only.

For a quick inline test:

```powershell
devex plan "Build a secure REST API with blob storage and Cosmos DB"
```

---

## Step 4: Scaffold from the Enterprise Intent File

```powershell
devex scaffold --file examples/intent.md -o ./test-enterprise
```

This generates a full production scaffold in `./test-enterprise/`. You should see
~36 files created. The console shows requirements completeness, the architecture
plan, governance results, WAF assessment, and **improvement suggestions**.

Explore the output:

```powershell
# List top-level directories
Get-ChildItem ./test-enterprise -Directory

# Read the improvement suggestions -- what to refine for the next iteration
Get-Content ./test-enterprise/docs/improvement-suggestions.md

# Check the Bicep infrastructure
Get-ChildItem ./test-enterprise/infra/bicep -Recurse

# Check the GitHub Actions workflows
Get-ChildItem ./test-enterprise/.github/workflows

# Read the generated FastAPI app
Get-Content ./test-enterprise/src/app/main.py

# Read the architecture plan
Get-Content ./test-enterprise/docs/plan.md

# Check governance results
Get-Content ./test-enterprise/.devex/governance.json

# Check state tracking
Get-Content ./test-enterprise/.devex/state.json
```

---

## Step 5: Validate the Scaffold

```powershell
devex validate ./test-enterprise
```

This re-runs governance validation against the generated scaffold. You should
see policy results and a WAF assessment with pillar-by-pillar scores.

---

## Step 6: Create Your Own Enterprise Intent File

This is the **define-then-run** workflow.

```powershell
# Step 6a: Generate the enterprise requirements template
devex init -o ./my-test -p my-cool-api

# Step 6b: Look at the generated template (note the 9 enterprise sections)
Get-Content ./my-test/intent.md

# Step 6c: Fill in every section -- problem, goals, users, requirements, etc.
# (Each section has guidance comments explaining what to write)

# Step 6d: Scaffold from it
devex scaffold --file ./my-test/intent.md -o ./test-from-template

# Step 6e: Review improvement suggestions
Get-Content ./test-from-template/docs/improvement-suggestions.md
```

For a quick inline test (skips enterprise sections):

```powershell
devex scaffold "Build a secure REST API with blob storage" -o ./test-inline
```

---

## Step 7: Dry Run (Preview Without Writing)

```powershell
devex scaffold "Build a secure API" --dry-run
```

Shows what files would be generated, but doesn't write anything to disk.

---

## Step 8: Plan from an Intent File

```powershell
devex plan --file examples/intent.md
```

Runs the pipeline in plan-only mode using the intent file. Shows architecture,
governance, and WAF results without generating files.

You can also get JSON output:

```powershell
devex plan --file examples/intent.md -F json
```

---

## Step 9: Versioned Upgrades (Iterative Improvement)

This tests the full upgrade workflow with improvement suggestions:

```powershell
# Step 9a: Scaffold v1
devex scaffold --file examples/intent.md -o ./test-upgrade

# Step 9b: Review the improvement suggestions from v1
Get-Content ./test-upgrade/docs/improvement-suggestions.md

# Step 9c: Check version history (should show v1)
devex history ./test-upgrade

# Step 9d: Generate a v2 upgrade template (embeds v1 suggestions)
devex new-version ./test-upgrade

# Step 9e: Look at the generated template -- note the carried-forward
# enterprise sections and the "Improvement Suggestions from v1" section
Get-Content ./test-upgrade/intent.v2.md

# Step 9f: Or use the pre-made v2 example with enterprise sections
devex upgrade --file examples/intent.v2.md -o ./test-upgrade

# Step 9g: Review v2 improvement suggestions (should show fewer gaps)
Get-Content ./test-upgrade/docs/improvement-suggestions.md

# Step 9h: Check version history (should show v1 superseded + v2 active)
devex history ./test-upgrade
```

---

## Step 10: Run All Tests

```powershell
# Run the full test suite (433 tests)
pytest tests/ -v
```

All 433 tests should pass. Key test files:

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_standards.py` | 67 | Azure CAF naming, tagging, config |
| `test_waf.py` | 61 | WAF 5-pillar assessment |
| `test_state.py` | 37 | State management, drift detection |
| `test_intent_versioning.py` | 33 | Intent files, versioning, CI/CD promotion |
| `test_skills_registry.py` | 26 | Skill routing, execution |
| `test_superpowers.py` | 24 | Test/alert/deploy generators |
| `test_planning.py` | 22 | Persistent planning, checkpoints |
| `test_deploy_orchestrator.py` | 19 | Deploy stages, error recovery |
| `test_prompt_generator.py` | 18 | Codebase scanning, prompts |
| `test_subagent_dispatcher.py` | 17 | Parallel fan-out, aggregation |
| `test_enterprise_features.py` | 37 | Enterprise intent model, completeness |

Run a specific test file:

```powershell
pytest tests/test_intent_versioning.py -v
```

---

## Step 11: Lint and Type Check

```powershell
# Lint (should pass clean)
ruff check src/ tests/

# Format check
ruff format --check src/ tests/

# Type check
mypy src/orchestrator/
```

---

## Step 12: Deploy to Azure (Optional)

This step requires an Azure subscription and Azure CLI.

```powershell
# Login to Azure
az login

# Create a resource group
az group create --name rg-my-test --location eastus2

# Deploy (staged: validate -> what-if -> deploy -> verify)
devex deploy ./test-inline -g rg-my-test -r eastus2

# Or dry-run (validate + what-if only, no actual deployment)
devex deploy ./test-inline -g rg-my-test -r eastus2 --dry-run
```

---

## Cleanup

Remove test output directories when you're done:

```powershell
Remove-Item -Recurse -Force ./test-enterprise -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ./test-inline -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ./test-from-template -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ./test-upgrade -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ./my-test -ErrorAction SilentlyContinue
```

---

## Summary of All Commands

| Command | What It Does |
|---------|-------------|
| `devex --help` | Show all available commands |
| `devex version` | Show version and environment info |
| `devex init` | Create an intent.md template |
| `devex plan "..."` | Preview architecture plan (no files) |
| `devex plan --file intent.md` | Plan from an intent file |
| `devex scaffold "..." -o ./out` | Generate full scaffold from inline intent |
| `devex scaffold --file intent.md -o ./out` | Generate full scaffold from intent file |
| `devex scaffold "..." --dry-run` | Preview without writing files |
| `devex validate ./out` | Validate scaffold against policies |
| `devex deploy ./out -g rg -r region` | Deploy to Azure (staged) |
| `devex upgrade --file v2.md -o ./out` | Upgrade scaffold to new version |
| `devex history ./out` | View version history |
| `devex new-version ./out` | Generate upgrade template from current version |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `devex` not found | Activate venv: `.venv\Scripts\Activate.ps1` |
| "No intent provided" | Quote the intent string: `devex scaffold "Build a secure API" -o ./out` |
| "No .devex metadata found" | Run `devex scaffold` first before `validate`/`deploy`/`upgrade` |
| LLM connection error | Expected -- system auto-falls back to template-only mode |
| pip install fails | Check Python version: `python --version` (need 3.11+) |

---

*Built for the GitHub Copilot SDK Enterprise Challenge, Q3 FY26*
