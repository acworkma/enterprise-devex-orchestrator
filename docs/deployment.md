# Deployment Guide

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Azure CLI | ≥ 2.55 | `az version` |
| Bicep CLI | ≥ 0.24 | `az bicep version` |
| Python | ≥ 3.11 | `python --version` |
| Docker | ≥ 24.0 | `docker --version` |
| GitHub CLI | ≥ 2.40 | `gh --version` |

## Authentication

```bash
# Login to Azure
az login

# Set subscription
az account set --subscription e47370c7-8804-46b9-86f9-a96f5e950535

# Verify
az account show --query "{name:name, id:id}" -o table
```

## Step 1 — Create Resource Group

```bash
az group create \
  --name rg-devex-orchestrator \
  --location eastus2 \
  --tags project=devex-orchestrator environment=dev costCenter=ENG-001 \
         owner=team@microsoft.com managedBy=bicep dataSensitivity=internal \
         createdBy=devex-orchestrator
```

## Step 2 — Validate Bicep Templates

```bash
# Syntax validation
az bicep build --file infra/bicep/main.bicep

# Deployment validation (what-if)
az deployment group what-if \
  --resource-group rg-devex-orchestrator \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/parameters/dev.parameters.json
```

## Step 3 — Deploy Infrastructure

```bash
az deployment group create \
  --name devex-deploy-$(date +%Y%m%d-%H%M%S) \
  --resource-group rg-devex-orchestrator \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/parameters/dev.parameters.json \
  --verbose
```

Expected resources created:
- Log Analytics Workspace (`law-{project}-{env}-{region}`)
- User-assigned Managed Identity (`id-{project}-{env}-{region}`)
- Azure Key Vault (RBAC, soft delete, purge protection) (`kv-{project}-{env}-{region}`)
- Azure Container Registry (`cr{project}{env}{region}`)
- Container Apps Environment + Container App (`cae-/ca-{project}-{env}-{region}`)

> All resource names follow [Azure CAF naming conventions](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming).
> All resources are tagged with 7 required enterprise tags (project, environment, costCenter, owner, managedBy, createdBy, dataSensitivity).

## Step 4 — Build and Push Container Image

```bash
# Get ACR name from deployment output
ACR_NAME=$(az deployment group show \
  --resource-group rg-devex-orchestrator \
  --name <deployment-name> \
  --query properties.outputs.containerRegistryName.value -o tsv)

# Login to ACR
az acr login --name $ACR_NAME

# Build and push
docker build -t ${ACR_NAME}.azurecr.io/devex-orchestrator:latest .
docker push ${ACR_NAME}.azurecr.io/devex-orchestrator:latest
```

## Step 5 — Update Container App Image

```bash
CONTAINER_APP_NAME=$(az deployment group show \
  --resource-group rg-devex-orchestrator \
  --name <deployment-name> \
  --query properties.outputs.containerAppName.value -o tsv)

az containerapp update \
  --name $CONTAINER_APP_NAME \
  --resource-group rg-devex-orchestrator \
  --image ${ACR_NAME}.azurecr.io/devex-orchestrator:latest
```

## Step 6 — Verify Deployment

```bash
# Get the FQDN
FQDN=$(az deployment group show \
  --resource-group rg-devex-orchestrator \
  --name <deployment-name> \
  --query properties.outputs.containerAppFqdn.value -o tsv)

# Health check
curl https://${FQDN}/health

# Expected response:
# {"status": "healthy", "version": "0.1.0"}
```

## Step 7 — Configure GitHub Actions (OIDC)

### Create Azure AD App Registration

```bash
# Create app registration
az ad app create --display-name devex-orchestrator-cicd

# Get App ID
APP_ID=$(az ad app list --display-name devex-orchestrator-cicd --query "[0].appId" -o tsv)

# Create service principal
az ad sp create --id $APP_ID

# Get subscription ID
SUB_ID=$(az account show --query id -o tsv)

# Assign Contributor role
az role assignment create \
  --assignee $APP_ID \
  --role Contributor \
  --scope /subscriptions/$SUB_ID/resourceGroups/rg-devex-orchestrator

# Add federated credential for GitHub Actions
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-actions-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<org>/<repo>:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

### Set GitHub Repository Secrets

```bash
gh secret set AZURE_CLIENT_ID --body "$APP_ID"
gh secret set AZURE_TENANT_ID --body "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID --body "$SUB_ID"
```

## Rollback

```bash
# List deployments
az deployment group list \
  --resource-group rg-devex-orchestrator \
  --query "[].{name:name, timestamp:properties.timestamp, state:properties.provisioningState}" \
  -o table

# Redeploy previous version
az deployment group create \
  --resource-group rg-devex-orchestrator \
  --template-file infra/bicep/main.bicep \
  --parameters infra/bicep/parameters/dev.parameters.json \
  --name rollback-$(date +%Y%m%d-%H%M%S)
```

## Teardown

```bash
# Delete all resources
az group delete \
  --name rg-devex-orchestrator \
  --yes --no-wait

# Clean up app registration
az ad app delete --id $APP_ID
```

> **Warning:** Key Vault has purge protection enabled with 90-day retention. After
> deleting the resource group, the Key Vault will remain in a soft-deleted state.
> To fully remove: `az keyvault purge --name <vault-name>`

## Troubleshooting

| Symptom | Check | Fix |
|---|---|---|
| Bicep build fails | `az bicep version` | `az bicep upgrade` |
| Deployment fails with quota error | `az vm list-usage --location eastus2` | Change `location` parameter |
| Container App not starting | `az containerapp logs show` | Check image name and ACR credentials |
| Key Vault access denied | `az role assignment list` | Verify Managed Identity has `Key Vault Secrets User` role |
| Health endpoint returns 503 | Container App logs | Check `AZURE_CLIENT_ID` env var is set correctly |

---
*Enterprise DevEx Orchestrator Agent*
