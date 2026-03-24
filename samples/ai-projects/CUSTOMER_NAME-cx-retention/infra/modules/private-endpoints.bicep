// ---------------------------------------------------------------------------
// Module: Private Endpoints and Private DNS Zones
// ---------------------------------------------------------------------------

@description('Azure region for private endpoints.')
param location string

@description('Environment name (dev, prod).')
param environment string

@description('Resource naming prefix.')
param resourcePrefix string

@description('Resource ID of the virtual network.')
param vnetId string

@description('Resource ID of the data subnet for private endpoints.')
param subnetDataId string

@description('Resource ID of the Azure OpenAI account.')
param openAiId string

@description('Resource ID of the AI Search service.')
param searchId string

@description('Resource ID of the Cosmos DB account.')
param cosmosId string

@description('Resource ID of the Storage account.')
param storageId string

@description('Resource ID of the Key Vault.')
param keyVaultId string

@description('Resource tags applied to all resources in this module.')
param tags object

// ---------------------------------------------------------------------------
// Private DNS Zone definitions
// ---------------------------------------------------------------------------
var dnsZones = [
  {
    name: 'privatelink.openai.azure.com'
    linkName: 'openai-vnet-link'
  }
  {
    name: 'privatelink.search.windows.net'
    linkName: 'search-vnet-link'
  }
  {
    name: 'privatelink.documents.azure.com'
    linkName: 'cosmos-vnet-link'
  }
  {
    name: 'privatelink.blob.core.windows.net'
    linkName: 'blob-vnet-link'
  }
  {
    name: 'privatelink.vaultcore.azure.net'
    linkName: 'keyvault-vnet-link'
  }
]

// ---------------------------------------------------------------------------
// Private endpoint definitions
// ---------------------------------------------------------------------------
var endpoints = [
  {
    name: '${resourcePrefix}-pe-openai-${environment}'
    targetId: openAiId
    groupId: 'account'
    dnsZoneIndex: 0
  }
  {
    name: '${resourcePrefix}-pe-search-${environment}'
    targetId: searchId
    groupId: 'searchService'
    dnsZoneIndex: 1
  }
  {
    name: '${resourcePrefix}-pe-cosmos-${environment}'
    targetId: cosmosId
    groupId: 'Sql'
    dnsZoneIndex: 2
  }
  {
    name: '${resourcePrefix}-pe-blob-${environment}'
    targetId: storageId
    groupId: 'blob'
    dnsZoneIndex: 3
  }
  {
    name: '${resourcePrefix}-pe-kv-${environment}'
    targetId: keyVaultId
    groupId: 'vault'
    dnsZoneIndex: 4
  }
]

// ---------------------------------------------------------------------------
// Private DNS Zones
// ---------------------------------------------------------------------------
resource privateDnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [
  for zone in dnsZones: {
    name: zone.name
    location: 'global'
    tags: tags
  }
]

// ---------------------------------------------------------------------------
// VNet Links for DNS Zones
// ---------------------------------------------------------------------------
resource vnetLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [
  for (zone, i) in dnsZones: {
    parent: privateDnsZones[i]
    name: zone.linkName
    location: 'global'
    tags: tags
    properties: {
      virtualNetwork: {
        id: vnetId
      }
      registrationEnabled: false
    }
  }
]

// ---------------------------------------------------------------------------
// Private Endpoints
// ---------------------------------------------------------------------------
resource privateEndpoints 'Microsoft.Network/privateEndpoints@2024-05-01' = [
  for ep in endpoints: {
    name: ep.name
    location: location
    tags: tags
    properties: {
      subnet: {
        id: subnetDataId
      }
      privateLinkServiceConnections: [
        {
          name: ep.name
          properties: {
            privateLinkServiceId: ep.targetId
            groupIds: [
              ep.groupId
            ]
          }
        }
      ]
    }
  }
]

// ---------------------------------------------------------------------------
// DNS Zone Groups (register A records in Private DNS)
// ---------------------------------------------------------------------------
resource dnsZoneGroups 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = [
  for (ep, i) in endpoints: {
    parent: privateEndpoints[i]
    name: 'default'
    properties: {
      privateDnsZoneConfigs: [
        {
          name: 'config'
          properties: {
            privateDnsZoneId: privateDnsZones[ep.dnsZoneIndex].id
          }
        }
      ]
    }
  }
]
