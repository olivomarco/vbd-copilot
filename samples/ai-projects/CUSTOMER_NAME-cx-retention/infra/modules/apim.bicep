// ---------------------------------------------------------------------------
// Module: Azure API Management (Standard v2)
// ---------------------------------------------------------------------------
// Standard v2 uses outbound VNet integration (not classic VNet injection)
// to reach internal Container Apps. The public endpoint is secured by
// Azure Front Door origin validation.
// ---------------------------------------------------------------------------

@description('Azure region for API Management.')
param location string

@description('Environment name (dev, prod).')
param environment string

@description('Resource naming prefix.')
param resourcePrefix string

@description('Resource tags applied to all resources in this module.')
param tags object

@description('Resource ID of the subnet for APIM outbound VNet integration.')
param subnetApimId string

@description('Publisher email address for APIM.')
param publisherEmail string = 'admin@CUSTOMER_NAME.com'

@description('Publisher name for APIM.')
param publisherName string = 'CUSTOMER_NAME Bill Explainer'

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------
var apimName = '${resourcePrefix}-apim-${environment}'

// ---------------------------------------------------------------------------
// API Management
// ---------------------------------------------------------------------------
resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' = {
  name: apimName
  location: location
  tags: tags
  sku: {
    name: 'StandardV2'
    capacity: 1
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    virtualNetworkConfiguration: {
      subnetResourceId: subnetApimId
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of API Management.')
output apimId string = apim.id

@description('Name of API Management.')
output apimName string = apim.name

@description('Gateway URL of API Management.')
output apimGatewayUrl string = apim.properties.gatewayUrl
