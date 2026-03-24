// ---------------------------------------------------------------------------
// Module: Azure OpenAI Service with Model Deployments
// ---------------------------------------------------------------------------

@description('Azure region for Azure OpenAI.')
param location string

@description('Environment name (dev, prod).')
param environment string

@description('Resource naming prefix.')
param resourcePrefix string

@description('Capacity in thousands of tokens per minute for GPT-4o deployment.')
param gpt4oCapacity int

@description('Capacity in thousands of tokens per minute for GPT-4o-mini deployment.')
param gpt4oMiniCapacity int

@description('Capacity in thousands of tokens per minute for text-embedding-3-small deployment.')
param embeddingCapacity int

@description('Resource tags applied to all resources in this module.')
param tags object

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------
var openAiName = '${resourcePrefix}-oai-${environment}'

// ---------------------------------------------------------------------------
// Azure OpenAI Account
// ---------------------------------------------------------------------------
resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: openAiName
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAiName
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
    }
  }
}

// ---------------------------------------------------------------------------
// Model Deployments
// ---------------------------------------------------------------------------
resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'gpt-4o'
  sku: {
    name: 'DataZoneStandard'
    capacity: gpt4oCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
  }
}

resource gpt4oMiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'gpt-4o-mini'
  sku: {
    name: 'DataZoneStandard'
    capacity: gpt4oMiniCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
    }
  }
  dependsOn: [
    gpt4oDeployment
  ]
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'text-embedding-3-small'
  sku: {
    name: 'DataZoneStandard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
  dependsOn: [
    gpt4oMiniDeployment
  ]
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the Azure OpenAI account.')
output openAiId string = openAi.id

@description('Name of the Azure OpenAI account.')
output openAiName string = openAi.name

@description('Endpoint URL of the Azure OpenAI account.')
output openAiEndpoint string = openAi.properties.endpoint
