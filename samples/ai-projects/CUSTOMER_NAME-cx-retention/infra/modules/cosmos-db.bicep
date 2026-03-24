// ---------------------------------------------------------------------------
// Module: Azure Cosmos DB (Serverless) with Containers
// ---------------------------------------------------------------------------

@description('Azure region for Cosmos DB.')
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
var cosmosName = '${resourcePrefix}-cosmos-${environment}'
var databaseName = 'billexplainer'

// ---------------------------------------------------------------------------
// Cosmos DB Account (Serverless, RBAC-only access)
// ---------------------------------------------------------------------------
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: cosmosName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    publicNetworkAccess: 'Disabled'
    disableLocalAuth: true
  }
}

// ---------------------------------------------------------------------------
// SQL Database
// ---------------------------------------------------------------------------
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// ---------------------------------------------------------------------------
// Container: sessions (TTL 24h = 86400s)
// ---------------------------------------------------------------------------
resource sessionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: 'sessions'
  properties: {
    resource: {
      id: 'sessions'
      partitionKey: {
        paths: [
          '/sessionId'
        ]
        kind: 'Hash'
        version: 2
      }
      defaultTtl: 86400
    }
  }
}

// ---------------------------------------------------------------------------
// Container: messages (TTL 30d = 2592000s)
// ---------------------------------------------------------------------------
resource messagesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: 'messages'
  properties: {
    resource: {
      id: 'messages'
      partitionKey: {
        paths: [
          '/sessionId'
        ]
        kind: 'Hash'
        version: 2
      }
      defaultTtl: 2592000
    }
  }
}

// ---------------------------------------------------------------------------
// Container: feedback (TTL 30d = 2592000s)
// ---------------------------------------------------------------------------
resource feedbackContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: 'feedback'
  properties: {
    resource: {
      id: 'feedback'
      partitionKey: {
        paths: [
          '/sessionId'
        ]
        kind: 'Hash'
        version: 2
      }
      defaultTtl: 2592000
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the Cosmos DB account.')
output cosmosId string = cosmosAccount.id

@description('Name of the Cosmos DB account.')
output cosmosName string = cosmosAccount.name

@description('Endpoint URL of the Cosmos DB account.')
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint

@description('Name of the SQL database.')
output cosmosDatabaseName string = database.name
