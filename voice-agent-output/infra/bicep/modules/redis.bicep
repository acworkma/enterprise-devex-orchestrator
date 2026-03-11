// ===================================================================
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
