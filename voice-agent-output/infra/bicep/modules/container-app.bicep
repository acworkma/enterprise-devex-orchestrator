// ===================================================================
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
        external: false
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
