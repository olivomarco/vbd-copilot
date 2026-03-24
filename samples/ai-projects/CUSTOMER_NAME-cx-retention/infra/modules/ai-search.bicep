// ---------------------------------------------------------------------------
// Module: Azure AI Search (S1 with Semantic Ranker)
// ---------------------------------------------------------------------------

@description('Azure region for AI Search.')
param location string

@description('Environment name (dev, prod).')
param environment string

@description('Resource naming prefix.')
param resourcePrefix string

@description('Number of replicas for the search service.')
param replicaCount int

@description('Resource tags applied to all resources in this module.')
param tags object

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------
var searchName = '${resourcePrefix}-search-${environment}'

// ---------------------------------------------------------------------------
// Azure AI Search
// ---------------------------------------------------------------------------
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchName
  location: location
  tags: tags
  sku: {
    name: 'standard'
  }
  properties: {
    replicaCount: replicaCount
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'disabled'
    semanticSearch: 'standard'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the AI Search service.')
output searchId string = search.id

@description('Name of the AI Search service.')
output searchName string = search.name

@description('Endpoint URL of the AI Search service.')
output searchEndpoint string = 'https://${search.name}.search.windows.net'
