// ---------------------------------------------------------------------------
// Module: Azure Container Apps Environment and Application
// ---------------------------------------------------------------------------

@description('Azure region for Container Apps.')
param location string

@description('Environment name (dev, prod).')
param environment string

@description('Resource naming prefix.')
param resourcePrefix string

@description('Resource ID of the apps subnet for Container Apps environment.')
param subnetAppsId string

@description('Resource ID of the Log Analytics workspace.')
param logAnalyticsWorkspaceId string

@description('Application Insights connection string.')
param appInsightsConnectionString string

@description('Azure OpenAI endpoint URL.')
param openAiEndpoint string

@description('Azure AI Search endpoint URL.')
param searchEndpoint string

@description('Azure Cosmos DB endpoint URL.')
param cosmosEndpoint string

@description('Azure Blob Storage endpoint URL.')
param storageBlobEndpoint string

@description('Azure Key Vault URI.')
param keyVaultUri string

@description('Minimum number of container replicas.')
param minReplicas int

@description('Maximum number of container replicas.')
param maxReplicas int

@description('Resource tags applied to all resources in this module.')
param tags object

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------
var envName = '${resourcePrefix}-cae-${environment}'
var appName = '${resourcePrefix}-ca-${environment}'

// ---------------------------------------------------------------------------
// Container Apps Environment
// ---------------------------------------------------------------------------
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  tags: tags
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: subnetAppsId
      internal: true
    }
    zoneRedundant: true
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2023-09-01').customerId
        #disable-next-line use-resource-symbol-reference
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Container App
// ---------------------------------------------------------------------------
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: false
        targetPort: 80
        transport: 'auto'
        allowInsecure: false
      }
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'bill-explainer'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: openAiEndpoint
            }
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: searchEndpoint
            }
            {
              name: 'AZURE_COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'AZURE_STORAGE_BLOB_ENDPOINT'
              value: storageBlobEndpoint
            }
            {
              name: 'AZURE_KEY_VAULT_URI'
              value: keyVaultUri
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
            {
              name: 'ENVIRONMENT'
              value: environment
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

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the Container App.')
output containerAppId string = containerApp.id

@description('Name of the Container App.')
output containerAppName string = containerApp.name

@description('FQDN of the Container App.')
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn

@description('Principal ID of the Container App system-assigned managed identity.')
output containerAppPrincipalId string = containerApp.identity.principalId

@description('Resource ID of the Container Apps Environment.')
output containerAppEnvId string = containerAppEnv.id
