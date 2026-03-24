// ---------------------------------------------------------------------------
// Module: Azure Key Vault
// ---------------------------------------------------------------------------

@description('Azure region for Key Vault.')
param location string

@description('Environment name (dev, prod).')
param environment string

@description('Resource naming prefix.')
param resourcePrefix string

@description('Resource tags applied to all resources in this module.')
param tags object

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------
var keyVaultName = '${resourcePrefix}-kv-${environment}'

// ---------------------------------------------------------------------------
// Key Vault
// ---------------------------------------------------------------------------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenant().tenantId
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

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the Key Vault.')
output keyVaultId string = keyVault.id

@description('Name of the Key Vault.')
output keyVaultName string = keyVault.name

@description('URI of the Key Vault.')
output keyVaultUri string = keyVault.properties.vaultUri
