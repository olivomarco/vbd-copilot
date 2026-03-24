// ---------------------------------------------------------------------------
// CUSTOMER_NAME Intelligent Bill Explainer - Main Orchestrator
// ---------------------------------------------------------------------------
// Provisions the complete RAG chatbot infrastructure on Azure.
// Region: Sweden Central (EU data residency).
// ---------------------------------------------------------------------------

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------
@description('Azure region for all resources. Defaults to Sweden Central for EU data residency.')
param location string = 'swedencentral'

@description('Environment name used in resource naming (dev, prod).')
@allowed([
  'dev'
  'prod'
])
param environment string

@description('Resource naming prefix applied to all resources.')
param resourcePrefix string = 'CUSTOMER_NAME-bill'

@description('Minimum number of Container App replicas.')
@minValue(0)
param containerAppMinReplicas int = 2

@description('Maximum number of Container App replicas.')
@minValue(1)
param containerAppMaxReplicas int = 20

@description('AI Search replica count.')
@minValue(1)
param aiSearchReplicaCount int = 2

@description('Capacity (in thousands of TPM) for GPT-4o deployment.')
param openAiGpt4oCapacity int = 150

@description('Capacity (in thousands of TPM) for GPT-4o-mini deployment.')
param openAiGpt4oMiniCapacity int = 500

@description('Capacity (in thousands of TPM) for text-embedding-3-small deployment.')
param openAiEmbeddingCapacity int = 300

// ---------------------------------------------------------------------------
// Tags applied to all resources
// ---------------------------------------------------------------------------
var tags = {
  project: 'CUSTOMER_NAME-bill-explainer'
  environment: environment
  managedBy: 'bicep'
}

// ---------------------------------------------------------------------------
// Module: Virtual Network, Subnets, NSGs
// ---------------------------------------------------------------------------
module vnet 'modules/vnet.bicep' = {
  name: 'deploy-vnet'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Log Analytics + Application Insights
// ---------------------------------------------------------------------------
module monitoring 'modules/monitoring.bicep' = {
  name: 'deploy-monitoring'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Azure OpenAI with model deployments
// ---------------------------------------------------------------------------
module openai 'modules/openai.bicep' = {
  name: 'deploy-openai'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    gpt4oCapacity: openAiGpt4oCapacity
    gpt4oMiniCapacity: openAiGpt4oMiniCapacity
    embeddingCapacity: openAiEmbeddingCapacity
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Azure AI Search
// ---------------------------------------------------------------------------
module aiSearch 'modules/ai-search.bicep' = {
  name: 'deploy-ai-search'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    replicaCount: aiSearchReplicaCount
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Cosmos DB (Serverless)
// ---------------------------------------------------------------------------
module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'deploy-cosmos-db'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Blob Storage
// ---------------------------------------------------------------------------
module blobStorage 'modules/blob-storage.bicep' = {
  name: 'deploy-blob-storage'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Key Vault
// ---------------------------------------------------------------------------
module keyVault 'modules/key-vault.bicep' = {
  name: 'deploy-key-vault'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Container Apps (depends on VNet, Monitoring, and data services)
// ---------------------------------------------------------------------------
module containerApps 'modules/container-apps.bicep' = {
  name: 'deploy-container-apps'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    subnetAppsId: vnet.outputs.subnetAppsId
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    openAiEndpoint: openai.outputs.openAiEndpoint
    searchEndpoint: aiSearch.outputs.searchEndpoint
    cosmosEndpoint: cosmosDb.outputs.cosmosEndpoint
    storageBlobEndpoint: blobStorage.outputs.storageBlobEndpoint
    keyVaultUri: keyVault.outputs.keyVaultUri
    minReplicas: containerAppMinReplicas
    maxReplicas: containerAppMaxReplicas
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: API Management (Standard v2, public endpoint secured by Front Door)
// ---------------------------------------------------------------------------
module apim 'modules/apim.bicep' = {
  name: 'deploy-apim'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    tags: tags
    subnetApimId: vnet.outputs.subnetApimId
  }
}

// ---------------------------------------------------------------------------
// Module: Front Door + WAF (depends on APIM)
// ---------------------------------------------------------------------------
module frontDoor 'modules/front-door.bicep' = {
  name: 'deploy-front-door'
  params: {
    environment: environment
    resourcePrefix: resourcePrefix
    apimGatewayHostname: replace(replace(apim.outputs.apimGatewayUrl, 'https://', ''), '/', '')
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Private Endpoints + DNS Zones
// ---------------------------------------------------------------------------
module privateEndpoints 'modules/private-endpoints.bicep' = {
  name: 'deploy-private-endpoints'
  params: {
    location: location
    environment: environment
    resourcePrefix: resourcePrefix
    vnetId: vnet.outputs.vnetId
    subnetDataId: vnet.outputs.subnetDataId
    openAiId: openai.outputs.openAiId
    searchId: aiSearch.outputs.searchId
    cosmosId: cosmosDb.outputs.cosmosId
    storageId: blobStorage.outputs.storageId
    keyVaultId: keyVault.outputs.keyVaultId
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Module: Role Assignments (depends on Container Apps identity)
// ---------------------------------------------------------------------------
module roleAssignments 'modules/role-assignments.bicep' = {
  name: 'deploy-role-assignments'
  params: {
    containerAppPrincipalId: containerApps.outputs.containerAppPrincipalId
    openAiId: openai.outputs.openAiId
    searchId: aiSearch.outputs.searchId
    cosmosAccountName: cosmosDb.outputs.cosmosName
    storageId: blobStorage.outputs.storageId
    keyVaultId: keyVault.outputs.keyVaultId
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Front Door endpoint hostname (public entry point).')
output frontDoorHostname string = frontDoor.outputs.frontDoorEndpointHostname

@description('APIM gateway URL.')
output apimGatewayUrl string = apim.outputs.apimGatewayUrl

@description('Container App FQDN (internal).')
output containerAppFqdn string = containerApps.outputs.containerAppFqdn

@description('Azure OpenAI endpoint.')
output openAiEndpoint string = openai.outputs.openAiEndpoint

@description('AI Search endpoint.')
output searchEndpoint string = aiSearch.outputs.searchEndpoint

@description('Cosmos DB endpoint.')
output cosmosEndpoint string = cosmosDb.outputs.cosmosEndpoint

@description('Blob Storage endpoint.')
output storageBlobEndpoint string = blobStorage.outputs.storageBlobEndpoint

@description('Key Vault URI.')
output keyVaultUri string = keyVault.outputs.keyVaultUri

@description('Application Insights connection string.')
output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString

@description('Container App managed identity principal ID.')
output containerAppPrincipalId string = containerApps.outputs.containerAppPrincipalId
