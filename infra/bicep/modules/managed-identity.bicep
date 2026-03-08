// User-Assigned Managed Identity Module
// Provides passwordless authentication for all Azure services

@description('Name of the managed identity')
param identityName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object = {}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

output identityId string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId
output identityName string = identity.name
