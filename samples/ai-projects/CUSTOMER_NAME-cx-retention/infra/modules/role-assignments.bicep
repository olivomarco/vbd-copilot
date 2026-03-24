// ---------------------------------------------------------------------------
// Module: Managed Identity Role Assignments
// ---------------------------------------------------------------------------

@description('Principal ID of the Container App system-assigned managed identity.')
param containerAppPrincipalId string

@description('Resource ID of the Azure OpenAI account.')
param openAiId string

@description('Resource ID of the AI Search service.')
param searchId string

@description('Name of the Cosmos DB account (used for data-plane SQL role assignment).')
param cosmosAccountName string

@description('Resource ID of the Storage account.')
param storageId string

@description('Resource ID of the Key Vault.')
param keyVaultId string

// ---------------------------------------------------------------------------
// Well-known Azure RBAC Role Definition IDs
// ---------------------------------------------------------------------------

// Cognitive Services OpenAI User
var cognitiveServicesOpenAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// Search Index Data Reader
var searchIndexDataReaderRoleId = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

// Storage Blob Data Reader
var storageBlobDataReaderRoleId = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

// Key Vault Secrets User
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

// Cosmos DB built-in data-plane role: Data Contributor
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

// ---------------------------------------------------------------------------
// Container Apps -> Azure OpenAI: Cognitive Services OpenAI User
// ---------------------------------------------------------------------------
resource openAiResource 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(openAiId, '/'))
}

resource openAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiId, containerAppPrincipalId, cognitiveServicesOpenAiUserRoleId)
  scope: openAiResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Container Apps -> AI Search: Search Index Data Reader
// ---------------------------------------------------------------------------
resource searchResource 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: last(split(searchId, '/'))
}

resource searchRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchId, containerAppPrincipalId, searchIndexDataReaderRoleId)
  scope: searchResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReaderRoleId)
    principalId: containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Container Apps -> Cosmos DB: SQL Data Contributor (data-plane role)
// ---------------------------------------------------------------------------
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
}

resource cosmosSqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, containerAppPrincipalId, cosmosDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    principalId: containerAppPrincipalId
    scope: cosmosAccount.id
  }
}

// ---------------------------------------------------------------------------
// Container Apps -> Blob Storage: Storage Blob Data Reader
// ---------------------------------------------------------------------------
resource storageResource 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: last(split(storageId, '/'))
}

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageId, containerAppPrincipalId, storageBlobDataReaderRoleId)
  scope: storageResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataReaderRoleId)
    principalId: containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Container Apps -> Key Vault: Key Vault Secrets User
// ---------------------------------------------------------------------------
resource keyVaultResource 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: last(split(keyVaultId, '/'))
}

resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultId, containerAppPrincipalId, keyVaultSecretsUserRoleId)
  scope: keyVaultResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}
