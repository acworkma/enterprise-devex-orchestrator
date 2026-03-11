// ===================================================================
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
