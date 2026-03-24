// ---------------------------------------------------------------------------
// Module: Log Analytics Workspace and Application Insights
// ---------------------------------------------------------------------------

@description('Azure region for monitoring resources.')
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
var logAnalyticsName = '${resourcePrefix}-law-${environment}'
var appInsightsName = '${resourcePrefix}-appi-${environment}'

// ---------------------------------------------------------------------------
// Log Analytics Workspace
// ---------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 180
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Application Insights (workspace-based)
// ---------------------------------------------------------------------------
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the Log Analytics workspace.')
output logAnalyticsWorkspaceId string = logAnalytics.id

@description('Name of the Log Analytics workspace.')
output logAnalyticsWorkspaceName string = logAnalytics.name

@description('Resource ID of Application Insights.')
output appInsightsId string = appInsights.id

@description('Name of Application Insights.')
output appInsightsName string = appInsights.name

@description('Application Insights instrumentation key.')
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey

@description('Application Insights connection string.')
output appInsightsConnectionString string = appInsights.properties.ConnectionString
