// ---------------------------------------------------------------------------
// Module: Virtual Network, Subnets, and Network Security Groups
// ---------------------------------------------------------------------------

@description('Azure region for all networking resources.')
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
var vnetName = '${resourcePrefix}-vnet-${environment}'
var nsgApimName = '${resourcePrefix}-nsg-apim-${environment}'
var nsgAppsName = '${resourcePrefix}-nsg-apps-${environment}'
var nsgDataName = '${resourcePrefix}-nsg-data-${environment}'

var vnetAddressPrefix = '10.0.0.0/16'
var subnetApimPrefix = '10.0.1.0/24'
var subnetAppsPrefix = '10.0.2.0/24'
var subnetDataPrefix = '10.0.3.0/24'

// ---------------------------------------------------------------------------
// NSG - APIM Subnet
// ---------------------------------------------------------------------------
resource nsgApim 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: nsgApimName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowFrontDoorInbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'AzureFrontDoor.Backend'
          sourcePortRange: '*'
          destinationAddressPrefix: subnetApimPrefix
          destinationPortRanges: [
            '443'
            '80'
          ]
        }
      }
      {
        name: 'AllowAPIMManagement'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'ApiManagement'
          sourcePortRange: '*'
          destinationAddressPrefix: subnetApimPrefix
          destinationPortRange: '3443'
        }
      }
      {
        name: 'AllowAzureLoadBalancer'
        properties: {
          priority: 120
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// NSG - Apps Subnet (allow inbound from APIM subnet only)
// ---------------------------------------------------------------------------
resource nsgApps 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: nsgAppsName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowApimSubnetInbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: subnetApimPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: subnetAppsPrefix
          destinationPortRanges: [
            '443'
            '80'
          ]
        }
      }
      {
        name: 'AllowAzureLoadBalancer'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// NSG - Data Subnet (allow inbound from apps subnet only)
// ---------------------------------------------------------------------------
resource nsgData 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: nsgDataName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowAppsSubnetInbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: subnetAppsPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: subnetDataPrefix
          destinationPortRange: '*'
        }
      }
      {
        name: 'AllowAzureLoadBalancer'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Virtual Network
// ---------------------------------------------------------------------------
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'apim'
        properties: {
          addressPrefix: subnetApimPrefix
          networkSecurityGroup: {
            id: nsgApim.id
          }
        }
      }
      {
        name: 'apps'
        properties: {
          addressPrefix: subnetAppsPrefix
          networkSecurityGroup: {
            id: nsgApps.id
          }
          delegations: [
            {
              name: 'container-apps-delegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'data'
        properties: {
          addressPrefix: subnetDataPrefix
          networkSecurityGroup: {
            id: nsgData.id
          }
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the virtual network.')
output vnetId string = vnet.id

@description('Name of the virtual network.')
output vnetName string = vnet.name

@description('Resource ID of the APIM subnet.')
output subnetApimId string = vnet.properties.subnets[0].id

@description('Resource ID of the apps subnet.')
output subnetAppsId string = vnet.properties.subnets[1].id

@description('Resource ID of the data subnet.')
output subnetDataId string = vnet.properties.subnets[2].id
