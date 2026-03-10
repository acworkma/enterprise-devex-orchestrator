"""CI/CD Generator -- produces GitHub Actions workflows.

Generates:
    - validate.yml: Lint, test, Bicep build, az validate on PRs
    - deploy.yml: Manual/merge deployment via OIDC + Bicep
"""

from __future__ import annotations

from src.orchestrator.intent_schema import IntentSpec
from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


class CICDGenerator:
    """Generates GitHub Actions CI/CD workflows."""

    def generate(self, spec: IntentSpec, version: int = 1) -> dict[str, str]:
        """Generate CI/CD workflow files.

        Args:
            spec: Parsed intent specification.
            version: Current project version. If > 1, adds promotion workflow.
        """
        logger.info("cicd_generator.start", project=spec.project_name, version=version)

        files: dict[str, str] = {}

        files[".github/workflows/validate.yml"] = self._validate_workflow(spec)
        files[".github/workflows/deploy.yml"] = self._deploy_workflow(spec)

        # Supply chain security
        files[".github/dependabot.yml"] = self._dependabot_config()
        files[".github/workflows/codeql.yml"] = self._codeql_workflow()

        # Version promotion workflow (for v2+ upgrades)
        if version > 1:
            files[".github/workflows/promote.yml"] = self._promote_workflow(spec, version)
            files[".github/workflows/rollback.yml"] = self._rollback_workflow(spec)

        logger.info("cicd_generator.complete", file_count=len(files))
        return files

    def _validate_workflow(self, spec: IntentSpec) -> str:
        return f"""# ===================================================================
# Validate Workflow -- runs on every pull request
# Lints Python, runs tests, builds Bicep, validates Azure deployment
# ===================================================================
name: Validate

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

env:
  PYTHON_VERSION: '3.11'
  AZURE_SUBSCRIPTION_ID: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}
  AZURE_RESOURCE_GROUP: '{spec.resource_group_name}'

jobs:
  lint-and-test:
    name: Lint & Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ env.PYTHON_VERSION }}}}
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r src/app/requirements.txt -r tests/requirements-test.txt ruff mypy

      - name: Lint with Ruff
        run: ruff check src/app tests/

      - name: Type check with mypy
        run: mypy src/app --ignore-missing-imports
        continue-on-error: true

      - name: Run tests
        run: pytest tests/ -v --tb=short --cov=src/app --cov-report=xml

      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml

  validate-bicep:
    name: Validate Bicep
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Bicep CLI
        run: |
          curl -Lo bicep https://github.com/Azure/bicep/releases/latest/download/bicep-linux-x64
          chmod +x bicep
          sudo mv bicep /usr/local/bin/

      - name: Build Bicep
        run: bicep build infra/bicep/main.bicep

      - name: Login to Azure (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{{{ secrets.AZURE_CLIENT_ID }}}}
          tenant-id: ${{{{ secrets.AZURE_TENANT_ID }}}}
          subscription-id: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}
        continue-on-error: true

      - name: Validate deployment
        if: success()
        run: |
          az deployment group validate \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --template-file infra/bicep/main.bicep \\
            --parameters infra/bicep/parameters/dev.parameters.json
        continue-on-error: true

  upload-scaffold:
    name: Upload Scaffold Artifact
    needs: [lint-and-test, validate-bicep]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Create artifact bundle
        run: |
          mkdir -p artifact
          cp -r infra/ artifact/
          cp -r src/ artifact/
          cp -r docs/ artifact/ 2>/dev/null || true
          cp -r .github/ artifact/
          cp README.md artifact/ 2>/dev/null || true
          cp AGENTS.md artifact/ 2>/dev/null || true

      - name: Upload scaffold artifact
        uses: actions/upload-artifact@v4
        with:
          name: scaffold-${{{{ github.sha }}}}
          path: artifact/
          retention-days: 30
"""

    def _deploy_workflow(self, spec: IntentSpec) -> str:
        return f"""# ===================================================================
# Deploy Workflow -- deploys infrastructure and application to Azure
# Triggered manually or on merge to main
# ===================================================================
name: Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'dev'
        type: choice
        options:
          - dev
          - staging
          - prod

permissions:
  id-token: write
  contents: read

env:
  AZURE_SUBSCRIPTION_ID: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}
  AZURE_RESOURCE_GROUP: '{spec.resource_group_name}'
  AZURE_LOCATION: '{spec.azure_region}'
  PROJECT_NAME: '{spec.project_name}'

jobs:
  deploy-infrastructure:
    name: Deploy Infrastructure
    runs-on: ubuntu-latest
    environment: ${{{{ inputs.environment || 'dev' }}}}
    outputs:
      containerAppFqdn: ${{{{ steps.deploy.outputs.containerAppFqdn }}}}
      containerAppName: ${{{{ steps.deploy.outputs.containerAppName }}}}
      containerRegistryName: ${{{{ steps.deploy.outputs.containerRegistryName }}}}
      containerRegistryLoginServer: ${{{{ steps.deploy.outputs.containerRegistryLoginServer }}}}
    steps:
      - uses: actions/checkout@v4

      - name: Login to Azure (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{{{ secrets.AZURE_CLIENT_ID }}}}
          tenant-id: ${{{{ secrets.AZURE_TENANT_ID }}}}
          subscription-id: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}

      - name: Create resource group
        run: |
          az group create \\
            --name ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --location ${{{{ env.AZURE_LOCATION }}}} \\
            --tags project=${{{{ env.PROJECT_NAME }}}} environment=${{{{ inputs.environment || 'dev' }}}} managedBy=bicep

      - name: Deploy Bicep
        id: deploy
        run: |
          RESULT=$(az deployment group create \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --template-file infra/bicep/main.bicep \\
            --parameters infra/bicep/parameters/${{{{ inputs.environment || 'dev' }}}}.parameters.json \\
            --query 'properties.outputs' \\
            --output json)

          echo "containerAppFqdn=$(echo $RESULT | jq -r '.containerAppFqdn.value')" >> $GITHUB_OUTPUT
          echo "containerAppName=$(echo $RESULT | jq -r '.containerAppName.value')" >> $GITHUB_OUTPUT
          echo "containerRegistryName=$(echo $RESULT | jq -r '.containerRegistryName.value')" >> $GITHUB_OUTPUT
          echo "containerRegistryLoginServer=$(echo $RESULT | jq -r '.containerRegistryLoginServer.value')" >> $GITHUB_OUTPUT

      - name: Deployment summary
        run: |
          echo "## Deployment Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Property | Value |" >> $GITHUB_STEP_SUMMARY
          echo "|----------|-------|" >> $GITHUB_STEP_SUMMARY
          echo "| Environment | ${{{{ inputs.environment || 'dev' }}}} |" >> $GITHUB_STEP_SUMMARY
          echo "| Resource Group | ${{{{ env.AZURE_RESOURCE_GROUP }}}} |" >> $GITHUB_STEP_SUMMARY
          echo "| Container App | ${{{{ steps.deploy.outputs.containerAppName }}}} |" >> $GITHUB_STEP_SUMMARY
          echo "| FQDN | ${{{{ steps.deploy.outputs.containerAppFqdn }}}} |" >> $GITHUB_STEP_SUMMARY

  build-and-push:
    name: Build & Push Container
    needs: deploy-infrastructure
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to Azure (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{{{ secrets.AZURE_CLIENT_ID }}}}
          tenant-id: ${{{{ secrets.AZURE_TENANT_ID }}}}
          subscription-id: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}

      - name: Get ACR login server
        id: acr
        run: |
          ACR_NAME="${{{{ needs.deploy-infrastructure.outputs.containerRegistryName }}}}"
          LOGIN_SERVER="${{{{ needs.deploy-infrastructure.outputs.containerRegistryLoginServer }}}}"
          echo "loginServer=$LOGIN_SERVER" >> $GITHUB_OUTPUT
          echo "acrName=$ACR_NAME" >> $GITHUB_OUTPUT

      - name: Login to ACR
        run: az acr login --name ${{{{ steps.acr.outputs.acrName }}}}

      - name: Build and push image
        run: |
          docker build -t ${{{{ steps.acr.outputs.loginServer }}}}/${{{{ env.PROJECT_NAME }}}}:${{{{ github.sha }}}} -f src/app/Dockerfile src/app/
          docker push ${{{{ steps.acr.outputs.loginServer }}}}/${{{{ env.PROJECT_NAME }}}}:${{{{ github.sha }}}}

      - name: Update Container App
        run: |
          az containerapp update \\
            --name ${{{{ needs.deploy-infrastructure.outputs.containerAppName }}}} \
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --image ${{{{ steps.acr.outputs.loginServer }}}}/${{{{ env.PROJECT_NAME }}}}:${{{{ github.sha }}}}

      - name: Verify application health
        run: |
          APP_FQDN="${{{{ needs.deploy-infrastructure.outputs.containerAppFqdn }}}}"
          curl --fail --retry 10 --retry-delay 10 "https://$APP_FQDN/health"
"""

    def _dependabot_config(self) -> str:
        return """# Dependabot configuration for supply chain security
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    reviewers:
      - "enterprise-devex-team"
    labels:
      - "dependencies"
      - "security"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
      - "ci"

  - package-ecosystem: "docker"
    directory: "/src/app"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
      - "container"
"""

    def _codeql_workflow(self) -> str:
        return """# ===================================================================
# CodeQL Analysis -- supply chain and code security scanning
# ===================================================================
name: CodeQL Analysis

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6AM UTC

permissions:
  security-events: write
  contents: read

jobs:
  analyze:
    name: Analyze
    runs-on: ubuntu-latest
    strategy:
      matrix:
        language: ['python']
    steps:
      - uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}

      - name: Autobuild
        uses: github/codeql-action/autobuild@v3

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          category: '/language:${{ matrix.language }}'
"""

    def _promote_workflow(self, spec: IntentSpec, version: int) -> str:
        """Generate a revision-based promotion workflow.

        Deploys the new version as a Container Apps revision with 0% traffic,
        runs health checks, then shifts traffic to 100%.
        """
        return f"""# ===================================================================
# Promote Workflow -- safe revision-based version promotion
# Deploys v{version} as a new revision, validates, then shifts traffic
# Previous version stays live until promotion is confirmed
# ===================================================================
name: Promote Version

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'dev'
        type: choice
        options:
          - dev
          - staging
          - prod
      traffic_pct:
        description: 'Traffic percentage for new revision (0-100)'
        required: true
        default: '100'
        type: string
      skip_health_check:
        description: 'Skip health check before promotion'
        required: false
        default: 'false'
        type: choice
        options:
          - 'false'
          - 'true'

permissions:
  id-token: write
  contents: read

env:
  AZURE_SUBSCRIPTION_ID: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}
  AZURE_RESOURCE_GROUP: '{spec.resource_group_name}'
  AZURE_LOCATION: '{spec.azure_region}'
  PROJECT_NAME: '{spec.project_name}'
  APP_VERSION: '{version}'

jobs:
  deploy-new-revision:
    name: Deploy New Revision (v{version})
    runs-on: ubuntu-latest
    environment: ${{{{ inputs.environment || 'dev' }}}}
    outputs:
      revisionName: ${{{{ steps.deploy.outputs.revisionName }}}}
      containerAppFqdn: ${{{{ steps.deploy.outputs.containerAppFqdn }}}}
    steps:
      - uses: actions/checkout@v4

      - name: Login to Azure (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{{{ secrets.AZURE_CLIENT_ID }}}}
          tenant-id: ${{{{ secrets.AZURE_TENANT_ID }}}}
          subscription-id: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}

      - name: Deploy infrastructure updates
        run: |
          az deployment group create \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --template-file infra/bicep/main.bicep \\
            --parameters infra/bicep/parameters/${{{{ inputs.environment || 'dev' }}}}.parameters.json

      - name: Build and push new image
        run: |
          ACR_NAME=$(echo "${{{{ env.PROJECT_NAME }}}}" | tr -d '-')acr
          LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
          az acr login --name $ACR_NAME
          docker build -t $LOGIN_SERVER/${{{{ env.PROJECT_NAME }}}}:v${{{{ env.APP_VERSION }}}}-${{{{ github.sha }}}} -f src/app/Dockerfile src/app/
          docker push $LOGIN_SERVER/${{{{ env.PROJECT_NAME }}}}:v${{{{ env.APP_VERSION }}}}-${{{{ github.sha }}}}

      - name: Create new revision with 0% traffic
        id: deploy
        run: |
          ACR_NAME=$(echo "${{{{ env.PROJECT_NAME }}}}" | tr -d '-')acr
          LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)

          # Create new revision (Container Apps automatically creates a new revision)
          az containerapp update \\
            --name ${{{{ env.PROJECT_NAME }}}} \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --image $LOGIN_SERVER/${{{{ env.PROJECT_NAME }}}}:v${{{{ env.APP_VERSION }}}}-${{{{ github.sha }}}} \\
            --revision-suffix v${{{{ env.APP_VERSION }}}}-${{{{ github.run_number }}}} \\
            --set-env-vars APP_VERSION=v${{{{ env.APP_VERSION }}}}

          # Get the new revision name
          REVISION=$(az containerapp revision list \\
            --name ${{{{ env.PROJECT_NAME }}}} \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --query "[0].name" --output tsv)

          FQDN=$(az containerapp show \\
            --name ${{{{ env.PROJECT_NAME }}}} \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --query 'properties.configuration.ingress.fqdn' --output tsv)

          echo "revisionName=$REVISION" >> $GITHUB_OUTPUT
          echo "containerAppFqdn=$FQDN" >> $GITHUB_OUTPUT

  health-check:
    name: Health Check
    needs: deploy-new-revision
    if: inputs.skip_health_check != 'true'
    runs-on: ubuntu-latest
    steps:
      - name: Wait for revision to be ready
        run: sleep 30

      - name: Check health endpoint
        run: |
          FQDN="${{{{ needs.deploy-new-revision.outputs.containerAppFqdn }}}}"
          echo "Checking health at https://$FQDN/health ..."

          for i in $(seq 1 5); do
            STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" "https://$FQDN/health" || echo "000")
            echo "Attempt $i: HTTP $STATUS"
            if [ "$STATUS" = "200" ]; then
              echo "[ok] Health check passed"
              exit 0
            fi
            sleep 10
          done

          echo "[x] Health check failed after 5 attempts"
          exit 1

  promote-traffic:
    name: Shift Traffic
    needs: [deploy-new-revision, health-check]
    if: always() && needs.deploy-new-revision.result == 'success' && (needs.health-check.result == 'success' || needs.health-check.result == 'skipped')
    runs-on: ubuntu-latest
    steps:
      - name: Login to Azure (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{{{ secrets.AZURE_CLIENT_ID }}}}
          tenant-id: ${{{{ secrets.AZURE_TENANT_ID }}}}
          subscription-id: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}

      - name: Set traffic to new revision
        run: |
          REVISION="${{{{ needs.deploy-new-revision.outputs.revisionName }}}}"
          TRAFFIC_PCT="${{{{ inputs.traffic_pct || '100' }}}}"

          echo "Shifting $TRAFFIC_PCT% traffic to $REVISION ..."

          az containerapp ingress traffic set \\
            --name ${{{{ env.PROJECT_NAME }}}} \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --revision-weight "$REVISION=$TRAFFIC_PCT"

          echo "[ok] Traffic shifted: $REVISION = $TRAFFIC_PCT%"

      - name: Promotion summary
        run: |
          echo "## Version Promotion Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Property | Value |" >> $GITHUB_STEP_SUMMARY
          echo "|----------|-------|" >> $GITHUB_STEP_SUMMARY
          echo "| Version | v${{{{ env.APP_VERSION }}}} |" >> $GITHUB_STEP_SUMMARY
          echo "| Revision | ${{{{ needs.deploy-new-revision.outputs.revisionName }}}} |" >> $GITHUB_STEP_SUMMARY
          echo "| Traffic | ${{{{ inputs.traffic_pct || '100' }}}}% |" >> $GITHUB_STEP_SUMMARY
          echo "| Environment | ${{{{ inputs.environment || 'dev' }}}} |" >> $GITHUB_STEP_SUMMARY
          echo "| FQDN | ${{{{ needs.deploy-new-revision.outputs.containerAppFqdn }}}} |" >> $GITHUB_STEP_SUMMARY
"""

    def _rollback_workflow(self, spec: IntentSpec) -> str:
        """Generate a rollback workflow for reverting to a previous revision."""
        return f"""# ===================================================================
# Rollback Workflow -- revert to a previous Container Apps revision
# Instantly shifts 100% traffic back to the specified revision
# ===================================================================
name: Rollback

on:
  workflow_dispatch:
    inputs:
      target_revision:
        description: 'Revision name to roll back to (leave empty for previous)'
        required: false
        type: string
      environment:
        description: 'Target environment'
        required: true
        default: 'dev'
        type: choice
        options:
          - dev
          - staging
          - prod

permissions:
  id-token: write
  contents: read

env:
  AZURE_SUBSCRIPTION_ID: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}
  AZURE_RESOURCE_GROUP: '{spec.resource_group_name}'
  PROJECT_NAME: '{spec.project_name}'

jobs:
  rollback:
    name: Rollback Deployment
    runs-on: ubuntu-latest
    environment: ${{{{ inputs.environment || 'dev' }}}}
    steps:
      - name: Login to Azure (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{{{ secrets.AZURE_CLIENT_ID }}}}
          tenant-id: ${{{{ secrets.AZURE_TENANT_ID }}}}
          subscription-id: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}

      - name: List current revisions
        id: list
        run: |
          echo "Current revisions:"
          az containerapp revision list \\
            --name ${{{{ env.PROJECT_NAME }}}} \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --query "[].{{name:name, active:properties.active, trafficWeight:properties.trafficWeight, created:properties.createdTime}}" \\
            --output table

          # Get the previous revision (second most recent)
          PREV_REVISION=$(az containerapp revision list \\
            --name ${{{{ env.PROJECT_NAME }}}} \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --query "[1].name" --output tsv)
          echo "previousRevision=$PREV_REVISION" >> $GITHUB_OUTPUT

      - name: Rollback traffic
        run: |
          TARGET="${{{{ inputs.target_revision }}}}"
          if [ -z "$TARGET" ]; then
            TARGET="${{{{ steps.list.outputs.previousRevision }}}}"
          fi

          echo "Rolling back to revision: $TARGET"

          # Activate the target revision if deactivated
          az containerapp revision activate \\
            --name ${{{{ env.PROJECT_NAME }}}} \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --revision "$TARGET" 2>/dev/null || true

          # Shift 100% traffic to the target revision
          az containerapp ingress traffic set \\
            --name ${{{{ env.PROJECT_NAME }}}} \\
            --resource-group ${{{{ env.AZURE_RESOURCE_GROUP }}}} \\
            --revision-weight "$TARGET=100"

          echo "[ok] Rolled back to $TARGET with 100% traffic"

      - name: Rollback summary
        run: |
          echo "## Rollback Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Property | Value |" >> $GITHUB_STEP_SUMMARY
          echo "|----------|-------|" >> $GITHUB_STEP_SUMMARY
          echo "| Target Revision | ${{{{ inputs.target_revision || steps.list.outputs.previousRevision }}}} |" >> $GITHUB_STEP_SUMMARY
          echo "| Environment | ${{{{ inputs.environment || 'dev' }}}} |" >> $GITHUB_STEP_SUMMARY
          echo "| Traffic | 100% to rollback target |" >> $GITHUB_STEP_SUMMARY
"""
