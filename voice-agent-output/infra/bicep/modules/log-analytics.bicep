// ===================================================================
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
