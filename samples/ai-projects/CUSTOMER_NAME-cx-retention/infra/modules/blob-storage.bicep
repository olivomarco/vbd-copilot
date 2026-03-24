// ---------------------------------------------------------------------------
// Module: Azure Blob Storage with knowledge-base container
// ---------------------------------------------------------------------------

@description('Azure region for Storage Account.')
param location string

@description('Environment name (dev, prod).')
param environment string

@description('Resource naming prefix.')
param resourcePrefix string

@description('Resource tags applied to all resources in this module.')
param tags object

// ---------------------------------------------------------------------------
// Variables
// Storage account names must be 3-24 chars, lowercase alphanumeric only.
// ---------------------------------------------------------------------------
var storageNameRaw = replace('${resourcePrefix}st${environment}', '-', '')
var storageName = length(storageNameRaw) > 24 ? substring(storageNameRaw, 0, 24) : storageNameRaw

// ---------------------------------------------------------------------------
// Storage Account
// ---------------------------------------------------------------------------
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

// ---------------------------------------------------------------------------
// Blob Services - soft delete and versioning
// ---------------------------------------------------------------------------
resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    isVersioningEnabled: true
  }
}

// ---------------------------------------------------------------------------
// Container: knowledge-base
// ---------------------------------------------------------------------------
resource knowledgeBaseContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: 'knowledge-base'
  properties: {
    publicAccess: 'None'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the storage account.')
output storageId string = storageAccount.id

@description('Name of the storage account.')
output storageName string = storageAccount.name

@description('Blob endpoint of the storage account.')
output storageBlobEndpoint string = storageAccount.properties.primaryEndpoints.blob
