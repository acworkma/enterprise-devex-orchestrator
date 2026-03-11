"""Bicep Generator -- produces Azure infrastructure as code.

Generates modular Bicep files for all Azure components defined in the
architecture plan. Each module is independently deployable and follows
Azure Well-Architected Framework principles.

All resource names follow Azure Cloud Adoption Framework (CAF) naming
conventions and include enterprise-standard tags for cost management,
ownership tracking, and compliance classification.
"""

from __future__ import annotations

from src.orchestrator.intent_schema import ComputeTarget, DataStore, IntentSpec, NetworkingModel, PlanOutput
from src.orchestrator.logging import get_logger
from src.orchestrator.standards.config import EnterpriseStandardsConfig

logger = get_logger(__name__)


class BicepGenerator:
    """Generates Bicep infrastructure modules."""

    def __init__(self, standards: EnterpriseStandardsConfig | None = None) -> None:
        """Initialize with optional enterprise standards config."""
        self.standards = standards or EnterpriseStandardsConfig()

    def generate(self, spec: IntentSpec, plan: PlanOutput) -> dict[str, str]:
        """Generate all Bicep files for the architecture plan."""
        logger.info("bicep_generator.start", project=spec.project_name)

        # Create naming and tagging engines from standards config
        self.naming = self.standards.create_naming_engine(
            workload=spec.project_name,
            environment=spec.environment,
            region=spec.azure_region,
        )
        self.tagging = self.standards.create_tagging_engine(
            project=spec.project_name,
            environment=spec.environment,
        )

        files: dict[str, str] = {}

        # Main deployment file
        files["infra/bicep/main.bicep"] = self._main_bicep(spec)

        # Modules
        files["infra/bicep/modules/log-analytics.bicep"] = self._log_analytics_module()
        files["infra/bicep/modules/managed-identity.bicep"] = self._managed_identity_module()
        files["infra/bicep/modules/keyvault.bicep"] = self._keyvault_module()

        # Compute-target-specific modules
        compute = getattr(spec, "compute_target", ComputeTarget.CONTAINER_APPS)
        if compute == ComputeTarget.APP_SERVICE:
            files["infra/bicep/modules/app-service.bicep"] = self._app_service_module(spec)
        elif compute == ComputeTarget.FUNCTIONS:
            files["infra/bicep/modules/function-app.bicep"] = self._function_app_module(spec)
        else:
            files["infra/bicep/modules/container-registry.bicep"] = self._container_registry_module()
            files["infra/bicep/modules/container-app.bicep"] = self._container_app_module(spec)

        # Data stores
        if DataStore.BLOB_STORAGE in spec.data_stores:
            files["infra/bicep/modules/storage.bicep"] = self._storage_module()
        if DataStore.COSMOS_DB in spec.data_stores:
            files["infra/bicep/modules/cosmos-db.bicep"] = self._cosmos_db_module(spec)
        if DataStore.REDIS in spec.data_stores:
            files["infra/bicep/modules/redis.bicep"] = self._redis_module(spec)
        if DataStore.SQL in spec.data_stores:
            files["infra/bicep/modules/sql.bicep"] = self._sql_module(spec)

        # Parameters
        files["infra/bicep/parameters/dev.parameters.json"] = self._parameters(spec, "dev")

        # Bicep config with AVM registry alias
        files["infra/bicep/bicepconfig.json"] = self._bicep_avm_config()

        # Naming and tagging standards documentation
        files["docs/standards.md"] = self._standards_doc(spec)

        logger.info("bicep_generator.complete", file_count=len(files))
        return files

    def _main_bicep(self, spec: IntentSpec) -> str:
        # Generate naming convention variables
        naming_vars = self.naming.to_bicep_variables()
        # Generate tagging variable
        tagging_vars = self.tagging.to_bicep_variable(include_optional=self.standards.tagging.include_optional)

        # Compute-target-specific parameters and modules
        compute = getattr(spec, "compute_target", ComputeTarget.CONTAINER_APPS)
        if compute == ComputeTarget.APP_SERVICE:
            compute_params = """
@description('App Service plan SKU')
param appServicePlanSku string = 'B1'
"""
            compute_module = """
// -- App Service ----------------------------------------------------
module appService 'modules/app-service.bicep' = {
  name: 'app-service-deployment'
  params: {
    location: location
    appName: '${projectName}-app'
    appServicePlanName: '${projectName}-plan'
    appServicePlanSku: appServicePlanSku
    managedIdentityId: identity.outputs.identityId
    managedIdentityClientId: identity.outputs.clientId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    keyVaultName: keyVault.outputs.keyVaultName
    tags: tags
  }
}
"""
            compute_outputs = """
output appServiceDefaultHostName string = appService.outputs.defaultHostName
output appServiceName string = appService.outputs.appName
"""
        elif compute == ComputeTarget.FUNCTIONS:
            compute_params = """
@description('Function App runtime')
param functionRuntime string = 'python'
"""
            compute_module = """
// -- Function App ---------------------------------------------------
module functionApp 'modules/function-app.bicep' = {
  name: 'function-app-deployment'
  params: {
    location: location
    functionAppName: '${projectName}-func'
    appServicePlanName: '${projectName}-func-plan'
    functionRuntime: functionRuntime
    managedIdentityId: identity.outputs.identityId
    managedIdentityClientId: identity.outputs.clientId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    keyVaultName: keyVault.outputs.keyVaultName
    tags: tags
  }
}
"""
            compute_outputs = """
output functionAppDefaultHostName string = functionApp.outputs.defaultHostName
output functionAppName string = functionApp.outputs.appName
"""
        else:
            storage_module = ""
            if DataStore.BLOB_STORAGE in spec.data_stores:
                storage_module = """
// -- Storage Account ------------------------------------------------
module storage 'modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    location: location
    storageAccountName: stName
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}
"""
            cosmos_module = ""
            if DataStore.COSMOS_DB in spec.data_stores:
                cosmos_module = """
// -- Cosmos DB ------------------------------------------------------
module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'cosmos-db-deployment'
  params: {
    location: location
    accountName: '${projectName}-cosmos'
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}
"""
            redis_module = ""
            if DataStore.REDIS in spec.data_stores:
                redis_module = """
// -- Redis Cache ----------------------------------------------------
module redis 'modules/redis.bicep' = {
  name: 'redis-deployment'
  params: {
    location: location
    redisName: '${projectName}-redis'
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}
"""
            sql_module = ""
            if DataStore.SQL in spec.data_stores:
                sql_module = """
// -- SQL Database ---------------------------------------------------
module sqlDb 'modules/sql.bicep' = {
  name: 'sql-deployment'
  params: {
    location: location
    serverName: '${projectName}-sql'
    databaseName: '${projectName}-db'
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}
"""
            compute_params = """
@description('Container image to deploy')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Container app port')
param containerPort int = 8000
"""
            compute_module = f"""
// -- Container Registry ---------------------------------------------
module containerRegistry 'modules/container-registry.bicep' = {{
  name: 'acr-deployment'
  params: {{
    location: location
    registryName: crName
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }}
}}
{storage_module}{cosmos_module}{redis_module}{sql_module}
// -- Container App --------------------------------------------------
module containerApp 'modules/container-app.bicep' = {{
  name: 'container-app-deployment'
  params: {{
    location: location
    appName: caName
    environmentName: caeName
    containerImage: containerImage
    containerPort: containerPort
    managedIdentityId: identity.outputs.identityId
    managedIdentityClientId: identity.outputs.clientId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    keyVaultName: keyVault.outputs.keyVaultName
    tags: tags
  }}
}}
"""
            compute_outputs = """
output containerAppFqdn string = containerApp.outputs.fqdn
output containerAppName string = containerApp.outputs.appName
output containerRegistryName string = containerRegistry.outputs.registryName
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer
"""
        # For App Service and Functions, data stores go directly in main
        storage_section = ""
        if compute != ComputeTarget.CONTAINER_APPS and DataStore.BLOB_STORAGE in spec.data_stores:
            storage_section += """
// -- Storage Account ------------------------------------------------
module storage 'modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    location: location
    storageAccountName: stName
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}
"""
        if compute != ComputeTarget.CONTAINER_APPS and DataStore.COSMOS_DB in spec.data_stores:
            storage_section += """
// -- Cosmos DB ------------------------------------------------------
module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'cosmos-db-deployment'
  params: {
    location: location
    accountName: '${projectName}-cosmos'
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}
"""
        if compute != ComputeTarget.CONTAINER_APPS and DataStore.REDIS in spec.data_stores:
            storage_section += """
// -- Redis Cache ----------------------------------------------------
module redis 'modules/redis.bicep' = {
  name: 'redis-deployment'
  params: {
    location: location
    redisName: '${projectName}-redis'
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}
"""
        if compute != ComputeTarget.CONTAINER_APPS and DataStore.SQL in spec.data_stores:
            storage_section += """
// -- SQL Database ---------------------------------------------------
module sqlDb 'modules/sql.bicep' = {
  name: 'sql-deployment'
  params: {
    location: location
    serverName: '${projectName}-sql'
    databaseName: '${projectName}-db'
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}
"""

        return f"""// ===================================================================
// Enterprise DevEx Orchestrator -- Main Deployment
// Project: {spec.project_name}
// Compute Target: {compute.value}
// Generated by: Enterprise DevEx Orchestrator Agent
// Naming Standard: Azure Cloud Adoption Framework (CAF)
// Tagging Standard: Enterprise governance policy
// ===================================================================

targetScope = 'resourceGroup'

// -- Parameters -----------------------------------------------------
@description('Project name used for resource naming')
@minLength(3)
@maxLength(39)
param projectName string

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'
{compute_params}
@description('Resource owner email for tagging')
param ownerEmail string = '{self.tagging.owner}'

@description('Cost center for chargeback')
param costCenter string = '{self.tagging.cost_center}'

// -- Variables ------------------------------------------------------
{naming_vars}

{tagging_vars}

// -- Log Analytics (must deploy first for diagnostics) --------------
module logAnalytics 'modules/log-analytics.bicep' = {{
  name: 'log-analytics-deployment'
  params: {{
    location: location
    workspaceName: lawName
    tags: tags
  }}
}}

// -- Managed Identity -----------------------------------------------
module identity 'modules/managed-identity.bicep' = {{
  name: 'identity-deployment'
  params: {{
    location: location
    identityName: identityName
    tags: tags
  }}
}}

// -- Key Vault ------------------------------------------------------
module keyVault 'modules/keyvault.bicep' = {{
  name: 'keyvault-deployment'
  params: {{
    location: location
    keyVaultName: kvName
    managedIdentityPrincipalId: identity.outputs.principalId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }}
}}
{storage_section}{compute_module}
// -- Outputs --------------------------------------------------------
{compute_outputs}
output keyVaultName string = keyVault.outputs.keyVaultName
output logAnalyticsWorkspaceId string = logAnalytics.outputs.workspaceId
output managedIdentityClientId string = identity.outputs.clientId
output resourceGroupName string = resourceGroup().name
"""

    def _log_analytics_module(self) -> str:
        return """// ===================================================================
// Log Analytics Workspace Module  (AVM-aligned)
// Provides centralized logging and monitoring for all resources.
// AVM reference: br/public:avm/res/operational-insights/workspace:<version>
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/operational-insights/workspace
// ===================================================================

@description('Azure region')
param location string

@description('Workspace name')
param workspaceName string

@description('Resource tags')
param tags object = {}

@description('Data retention in days')
@minValue(30)
@maxValue(730)
param retentionInDays int = 90

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output workspaceId string = workspace.id
output workspaceName string = workspace.name
output customerId string = workspace.properties.customerId
"""

    def _managed_identity_module(self) -> str:
        return """// ===================================================================
// User-Assigned Managed Identity Module
// Provides passwordless authentication to Azure resources.
// ===================================================================

@description('Azure region')
param location string

@description('Identity name')
param identityName string

@description('Resource tags')
param tags object = {}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

output identityId string = managedIdentity.id
output principalId string = managedIdentity.properties.principalId
output clientId string = managedIdentity.properties.clientId
output identityName string = managedIdentity.name
"""

    def _keyvault_module(self) -> str:
        return """// ===================================================================
// Azure Key Vault Module  (AVM-aligned)
// Centralized secret, key, and certificate management.
// AVM reference: br/public:avm/res/key-vault/vault:<version>
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/key-vault/vault
// ===================================================================

@description('Azure region')
param location string

@description('Key Vault name')
@maxLength(24)
param keyVaultName string

@description('Managed Identity principal ID for access')
param managedIdentityPrincipalId string

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Resource tags')
param tags object = {}

// To switch to the AVM registry module, replace the resource block below with:
//   module keyVault 'br/public:avm/res/key-vault/vault:0.11.0' = { ... }

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

// Grant Managed Identity access to Key Vault secrets
resource kvSecretUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: keyVault
  name: guid(keyVault.id, managedIdentityPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Diagnostic settings
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: keyVault
  name: '${keyVaultName}-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultId string = keyVault.id
"""

    def _container_registry_module(self) -> str:
        return """// ===================================================================
// Azure Container Registry Module  (AVM-aligned)
// Private container image registry with managed identity pull.
// AVM reference: br/public:avm/res/container-registry/registry:<version>
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/container-registry/registry
// ===================================================================

@description('Azure region')
param location string

@description('Container registry name (alphanumeric only)')
@minLength(5)
@maxLength(50)
param registryName string

@description('Managed Identity principal ID for AcrPull')
param managedIdentityPrincipalId string

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Resource tags')
param tags object = {}

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Premium'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Disabled'
  }
}

// Grant AcrPull role to Managed Identity
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, managedIdentityPrincipalId, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Diagnostic settings
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: registry
  name: '${registryName}-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output registryName string = registry.name
output loginServer string = registry.properties.loginServer
output registryId string = registry.id
"""

    def _storage_module(self) -> str:
        return """// ===================================================================
// Azure Storage Account Module  (AVM-aligned)
// Blob storage with managed identity access and diagnostics.
// AVM reference: br/public:avm/res/storage/storage-account:<version>
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/storage/storage-account
// ===================================================================

@description('Azure region')
param location string

@description('Storage account name (lowercase alphanumeric, 3-24 chars)')
@maxLength(24)
param storageAccountName string

@description('Managed Identity principal ID for data access')
param managedIdentityPrincipalId string

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Resource tags')
param tags object = {}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Disabled'
    encryption: {
      services: {
        blob: { enabled: true, keyType: 'Account' }
        file: { enabled: true, keyType: 'Account' }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

// Grant Storage Blob Data Contributor to Managed Identity
resource storageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, managedIdentityPrincipalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Diagnostic settings for blob service
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: blobService
  name: '${storageAccountName}-blob-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'StorageRead'
        enabled: true
      }
      {
        category: 'StorageWrite'
        enabled: true
      }
      {
        category: 'StorageDelete'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'Transaction'
        enabled: true
      }
    ]
  }
}

output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
"""

    def _cosmos_db_module(self, spec: IntentSpec) -> str:
        """Generate Azure Cosmos DB Bicep module."""
        return """// ===================================================================
// Azure Cosmos DB Module
// NoSQL database with managed identity access and diagnostics.
// ===================================================================

@description('Azure region')
param location string

@description('Cosmos DB account name')
@maxLength(44)
param accountName string

@description('Managed Identity principal ID for data access')
param managedIdentityPrincipalId string

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Resource tags')
param tags object = {}

@description('Database name')
param databaseName string = 'appdb'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-02-15-preview' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    disableLocalAuth: true
    publicNetworkAccess: 'Disabled'
    minimalTlsVersion: 'Tls12'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-02-15-preview' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Grant Cosmos DB Built-in Data Contributor role to Managed Identity
resource cosmosDataRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-02-15-preview' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, managedIdentityPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    scope: cosmosAccount.id
    principalId: managedIdentityPrincipalId
  }
}

// Diagnostic settings
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: cosmosAccount
  name: '${accountName}-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'Requests'
        enabled: true
      }
    ]
  }
}

output accountName string = cosmosAccount.name
output accountEndpoint string = cosmosAccount.properties.documentEndpoint
output accountId string = cosmosAccount.id
output databaseName string = database.name
"""

    def _redis_module(self, spec: IntentSpec) -> str:
        """Generate Azure Cache for Redis Bicep module."""
        return """// ===================================================================
// Azure Cache for Redis Module
// In-memory cache with managed identity access and diagnostics.
// ===================================================================

@description('Azure region')
param location string

@description('Redis cache name')
param redisName string

@description('Managed Identity principal ID for data access')
param managedIdentityPrincipalId string

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Resource tags')
param tags object = {}

@description('Redis SKU name')
@allowed(['Basic', 'Standard', 'Premium'])
param skuName string = 'Standard'

@description('Redis SKU family')
@allowed(['C', 'P'])
param skuFamily string = 'C'

@description('Redis cache capacity')
param skuCapacity int = 1

resource redis 'Microsoft.Cache/redis@2024-03-01' = {
  name: redisName
  location: location
  tags: tags
  properties: {
    sku: {
      name: skuName
      family: skuFamily
      capacity: skuCapacity
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    redisConfiguration: {
      'aad-enabled': 'true'
    }
  }
}

// Grant Redis Cache Contributor role to Managed Identity
resource redisDataRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: redis
  name: guid(redis.id, managedIdentityPrincipalId, 'e0f68234-74aa-48ed-b826-c38b57376e17')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'e0f68234-74aa-48ed-b826-c38b57376e17')
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Diagnostic settings
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: redis
  name: '${redisName}-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'ConnectedClientList'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output redisName string = redis.name
output redisHostName string = redis.properties.hostName
output redisId string = redis.id
output redisSslPort int = redis.properties.sslPort
"""

    def _sql_module(self, spec: IntentSpec) -> str:
        """Generate Azure SQL Database Bicep module."""
        return """// ===================================================================
// Azure SQL Database Module
// Managed SQL database with managed identity access and diagnostics.
// ===================================================================

@description('Azure region')
param location string

@description('SQL Server name')
param serverName string

@description('Database name')
param databaseName string

@description('Managed Identity principal ID for admin access')
param managedIdentityPrincipalId string

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Resource tags')
param tags object = {}

@description('Database SKU name')
param skuName string = 'GP_S_Gen5_1'

@description('Database SKU tier')
param skuTier string = 'GeneralPurpose'

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: serverName
  location: location
  tags: tags
  properties: {
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      principalType: 'Application'
      sid: managedIdentityPrincipalId
      login: 'managed-identity-admin'
      tenantId: subscription().tenantId
    }
  }
}

resource database 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 34359738368  // 32 GB
    zoneRedundant: false
  }
}

// Diagnostic settings for SQL Server
resource serverDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: sqlServer
  name: '${serverName}-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'SQLSecurityAuditEvents'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Diagnostic settings for database
resource dbDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: database
  name: '${databaseName}-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'SQLInsights'
        enabled: true
      }
      {
        category: 'QueryStoreRuntimeStatistics'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'Basic'
        enabled: true
      }
    ]
  }
}

output serverName string = sqlServer.name
output serverFqdn string = sqlServer.properties.fullyQualifiedDomainName
output databaseName string = database.name
output serverId string = sqlServer.id
"""

    def _container_app_module(self, spec: IntentSpec) -> str:
        networking = getattr(spec.security, "networking", NetworkingModel.PRIVATE)
        external = "true" if networking == NetworkingModel.PUBLIC_RESTRICTED else "false"
        template = """// ===================================================================
// Azure Container Apps Module
// Managed container platform with auto-scaling, managed identity,
// and integrated logging.
// Naming: Azure CAF -- ca-{workload}-{env}-{region}
// ===================================================================

@description('Azure region')
param location string

@description('Container app name (CAF: ca-{workload}-{env}-{region})')
param appName string

@description('Container Apps Environment name (CAF: cae-{workload}-{env}-{region})')
param environmentName string

@description('Container image')
param containerImage string

@description('Container port')
param containerPort int = 8000

@description('User-assigned managed identity resource ID')
param managedIdentityId string

@description('Managed identity client ID')
param managedIdentityClientId string

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string

@description('Key Vault name for secret references')
param keyVaultName string

@description('Resource tags')
param tags object = {}

@description('Minimum replicas')
@minValue(0)
@maxValue(30)
param minReplicas int = 1

@description('Maximum replicas')
@minValue(1)
@maxValue(30)
param maxReplicas int = 3

// Container Apps Environment
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2023-09-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
    zoneRedundant: false
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        external: EXTERNAL_PLACEHOLDER
        targetPort: containerPort
        transport: 'http'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      secrets: []
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: managedIdentityClientId
            }
            {
              name: 'KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'PORT'
              value: string(containerPort)
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: containerPort
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: containerPort
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output appName string = containerApp.name
output appId string = containerApp.id
output environmentId string = environment.id
"""
        return template.replace("EXTERNAL_PLACEHOLDER", external)

    def _app_service_module(self, spec: IntentSpec) -> str:
        """Generate Azure App Service Bicep module."""
        lang = getattr(spec, "language", "python")
        if lang == "node":
            linux_fx = "NODE|20-lts"
        elif lang == "dotnet":
            linux_fx = "DOTNETCORE|8.0"
        else:
            linux_fx = "PYTHON|3.11"

        return f"""// ===================================================================
// Azure App Service Module
// Managed web application hosting with built-in scaling,
// managed identity, and integrated logging.
// ===================================================================

@description('Azure region')
param location string

@description('App Service name')
param appName string

@description('App Service Plan name')
param appServicePlanName string

@description('App Service Plan SKU')
param appServicePlanSku string = 'B1'

@description('User-assigned managed identity resource ID')
param managedIdentityId string

@description('Managed identity client ID')
param managedIdentityClientId string

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string

@description('Key Vault name for secret references')
param keyVaultName string

@description('Resource tags')
param tags object = {{}}

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {{
  name: appServicePlanName
  location: location
  tags: tags
  kind: 'linux'
  sku: {{
    name: appServicePlanSku
  }}
  properties: {{
    reserved: true
  }}
}}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {{
  name: appName
  location: location
  tags: tags
  identity: {{
    type: 'UserAssigned'
    userAssignedIdentities: {{
      '${{managedIdentityId}}': {{}}
    }}
  }}
  properties: {{
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {{
      linuxFxVersion: '{linux_fx}'
      alwaysOn: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      healthCheckPath: '/health'
      appSettings: [
        {{
          name: 'AZURE_CLIENT_ID'
          value: managedIdentityClientId
        }}
        {{
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }}
      ]
    }}
  }}
}}

// Diagnostic settings
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {{
  scope: webApp
  name: '${{appName}}-diagnostics'
  properties: {{
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {{
        category: 'AppServiceHTTPLogs'
        enabled: true
      }}
      {{
        category: 'AppServiceConsoleLogs'
        enabled: true
      }}
      {{
        category: 'AppServiceAppLogs'
        enabled: true
      }}
    ]
    metrics: [
      {{
        category: 'AllMetrics'
        enabled: true
      }}
    ]
  }}
}}

output defaultHostName string = webApp.properties.defaultHostName
output appName string = webApp.name
output appId string = webApp.id
"""

    def _function_app_module(self, spec: IntentSpec) -> str:
        """Generate Azure Functions Bicep module."""
        lang = getattr(spec, "language", "python")
        if lang == "node":
            runtime = "node"
        elif lang == "dotnet":
            runtime = "dotnet-isolated"
        else:
            runtime = "python"

        return f"""// ===================================================================
// Azure Function App Module
// Serverless compute with consumption-based scaling,
// managed identity, and integrated logging.
// ===================================================================

@description('Azure region')
param location string

@description('Function App name')
param functionAppName string

@description('App Service Plan name')
param appServicePlanName string

@description('Function runtime')
param functionRuntime string = '{runtime}'

@description('User-assigned managed identity resource ID')
param managedIdentityId string

@description('Managed identity client ID')
param managedIdentityClientId string

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string

@description('Key Vault name for secret references')
param keyVaultName string

@description('Resource tags')
param tags object = {{}}

// Storage account required by Azure Functions runtime
resource funcStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {{
  name: replace('${{functionAppName}}st', '-', '')
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {{
    name: 'Standard_LRS'
  }}
  properties: {{
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }}
}}

resource hostingPlan 'Microsoft.Web/serverfarms@2023-12-01' = {{
  name: appServicePlanName
  location: location
  tags: tags
  kind: 'functionapp'
  sku: {{
    name: 'Y1'
    tier: 'Dynamic'
  }}
  properties: {{
    reserved: true
  }}
}}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {{
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {{
    type: 'UserAssigned'
    userAssignedIdentities: {{
      '${{managedIdentityId}}': {{}}
    }}
  }}
  properties: {{
    serverFarmId: hostingPlan.id
    httpsOnly: true
    siteConfig: {{
      linuxFxVersion: ''
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {{
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${{funcStorage.name}};EndpointSuffix=${{az.environment().suffixes.storage}};AccountKey=${{funcStorage.listKeys().keys[0].value}}'
        }}
        {{
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }}
        {{
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: functionRuntime
        }}
        {{
          name: 'AZURE_CLIENT_ID'
          value: managedIdentityClientId
        }}
        {{
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }}
      ]
    }}
  }}
}}

// Diagnostic settings
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {{
  scope: functionApp
  name: '${{functionAppName}}-diagnostics'
  properties: {{
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {{
        category: 'FunctionAppLogs'
        enabled: true
      }}
    ]
    metrics: [
      {{
        category: 'AllMetrics'
        enabled: true
      }}
    ]
  }}
}}

output defaultHostName string = functionApp.properties.defaultHostName
output appName string = functionApp.name
output appId string = functionApp.id
"""

    def _parameters(self, spec: IntentSpec, env: str) -> str:
        return f"""{{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {{
    "projectName": {{
      "value": "{spec.project_name}"
    }},
    "environment": {{
      "value": "{env}"
    }},
    "containerPort": {{
      "value": 8000
    }},
    "ownerEmail": {{
      "value": "{self.tagging.owner}"
    }},
    "costCenter": {{
      "value": "{self.tagging.cost_center}"
    }}
  }}
}}
"""

    def _bicep_avm_config(self) -> str:
        """Generate bicepconfig.json with Azure Verified Modules registry alias."""
        return """{
  "$schema": "https://raw.githubusercontent.com/Azure/bicep/main/src/Bicep.Core/Configuration/bicepconfig.schema.json",
  "moduleAliases": {
    "br": {
      "public": {
        "registry": "mcr.microsoft.com",
        "modulePath": "bicep"
      }
    }
  },
  "analyzers": {
    "core": {
      "enabled": true,
      "rules": {
        "no-hardcoded-env-urls": { "level": "warning" },
        "no-unused-params": { "level": "warning" },
        "no-unused-vars": { "level": "warning" },
        "prefer-interpolation": { "level": "warning" },
        "secure-parameter-default": { "level": "error" },
        "simplify-interpolation": { "level": "warning" },
        "use-stable-resource-identifiers": { "level": "warning" }
      }
    }
  }
}
"""

    def _standards_doc(self, spec: IntentSpec) -> str:
        """Generate enterprise standards documentation."""
        names = self.naming.generate_all()
        name_rows = "\n".join(f"| {rt.value} | `{name}` |" for rt, name in names.items())

        tag_catalog = self.tagging.get_tag_catalog()
        required_rows = "\n".join(
            f"| `{t['name']}` | {t['description']} | `{t['example']}` |"
            for t in tag_catalog
            if t["requirement"] == "required"
        )
        optional_rows = "\n".join(
            f"| `{t['name']}` | {t['description']} | `{t['example']}` |"
            for t in tag_catalog
            if t["requirement"] == "optional"
        )

        return f"""# Enterprise Standards -- Naming & Tagging

> Auto-generated by Enterprise DevEx Orchestrator Agent

## Overview

This document defines the enterprise naming conventions and tagging standards
applied to all Azure resources in the **{spec.project_name}** project.

---

## Naming Convention

All resource names follow the **Azure Cloud Adoption Framework (CAF)** pattern:

```
{{resourcePrefix}}-{{workload}}-{{environment}}-{{region}}
```

### Resource Names for `{spec.project_name}` ({spec.environment} / {spec.azure_region})

| Resource Type | Generated Name |
|---|---|
{name_rows}

### Naming Rules

- **Resource Group:** `rg-{{workload}}-{{env}}-{{region}}`
- **Key Vault:** `kv-{{workload}}-{{env}}-{{region}}` (3-24 chars, alphanumeric + hyphens)
- **Storage Account:** `st{{workload}}{{env}}{{region}}` (3-24 chars, lowercase alphanumeric only)
- **Container Registry:** `cr{{workload}}{{env}}{{region}}` (5-50 chars, alphanumeric only)
- **Container App:** `ca-{{workload}}-{{env}}-{{region}}` (2-32 chars)
- **Log Analytics:** `law-{{workload}}-{{env}}-{{region}}`
- **Managed Identity:** `id-{{workload}}-{{env}}-{{region}}`

### Region Abbreviations

| Region | Abbreviation |
|---|---|
| eastus | eus |
| eastus2 | eus2 |
| westus2 | wus2 |
| northeurope | neu |
| westeurope | weu |
| uksouth | uks |

---

## Tagging Standard

All Azure resources **must** include enterprise-mandated tags for cost management,
governance, and operational accountability.

### Required Tags

| Tag | Description | Example |
|---|---|---|
{required_rows}

### Optional Tags (Recommended)

| Tag | Description | Example |
|---|---|---|
{optional_rows}

### Tag Enforcement

- The **Governance Reviewer Agent** validates all generated Bicep templates
  against the tagging standard before scaffolding.
- Missing required tags will result in a **FAIL** governance status.
- Invalid tag values (e.g., malformed email for `owner`) produce warnings.

### Customization

Edit `standards.yaml` in the project root to customize:
- Default cost center, owner, and data sensitivity
- Additional custom required tags
- Department and team defaults

---

## References

- [Azure CAF Naming Conventions](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming)
- [Azure CAF Tagging Strategy](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-tagging)
- [Azure Resource Naming Restrictions](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules)
"""
