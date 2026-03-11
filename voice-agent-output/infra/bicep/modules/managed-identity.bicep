// ===================================================================
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
