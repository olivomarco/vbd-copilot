// =============================================================================
// demo-access.bicep
// Purpose  : Demo overlay for CUSTOMER_NAME Intelligent Bill Explainer
//            Deploys Azure Bastion + Windows jump box into the existing VNet.
//            Strategy C - Hybrid: Front Door / APIM remain public; this module
//            adds Bastion + jump box for backend access (AI Search, Cosmos DB,
//            APIM developer portal).
// Scope    : resourceGroup
// IMPORTANT: This module is ADDITIVE. It does NOT modify any existing infra
//            module or overwrite any existing resource.
// =============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Azure region for all resources in this module.')
param location string = 'swedencentral'

@description('Environment tag value. Must match the dev deployment this overlays.')
@allowed(['dev', 'demo'])
param environment string = 'dev'

@description('Shared resource-name prefix used across the project.')
param resourcePrefix string = 'CUSTOMER_NAME-bill'

@description('Name of the existing project VNet to attach the new subnets to.')
param vnetName string

@description('Local administrator password for the jump box VM.')
@secure()
param adminPassword string

@description('Resource tags applied to all resources created by this module.')
param tags object = {
  project: 'CUSTOMER_NAME-bill-explainer'
  environment: environment
  purpose: 'demo-access'
  managedBy: 'bicep'
}

// ---------------------------------------------------------------------------
// Variables - derived resource names follow ${resourcePrefix}-{svc}-${environment}
// ---------------------------------------------------------------------------

var bastionName        = '${resourcePrefix}-bastion-${environment}'
var bastionPipName     = '${resourcePrefix}-bastion-pip-${environment}'
var jumpboxNsgName     = '${resourcePrefix}-jumpbox-nsg-${environment}'
var jumpboxNicName     = '${resourcePrefix}-jumpbox-nic-${environment}'
var jumpboxVmName      = '${resourcePrefix}-jumpbox-${environment}'
var searchAccountName  = '${resourcePrefix}-search-${environment}'
var cosmosAccountName  = '${resourcePrefix}-cosmos-${environment}'

// Built-in role definition IDs (subscription-scoped)
var readerRoleId                = 'acdd72a7-3385-48ef-bd42-f606fba81ae7'
var searchIndexDataReaderRoleId = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

// Cosmos DB built-in data-plane role: "Cosmos DB Built-in Data Reader"
var cosmosBuiltInDataReaderRoleId = '00000000-0000-0000-0000-000000000001'

// ---------------------------------------------------------------------------
// Reference existing VNet (read-only - no properties are changed on the VNet)
// ---------------------------------------------------------------------------

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' existing = {
  name: vnetName
}

// ---------------------------------------------------------------------------
// NSG for jumpbox subnet
// Inbound: allow Bastion ports 3389/22 from AzureBastionSubnet; deny all else.
// Outbound: allow all (default).
// ---------------------------------------------------------------------------

resource jumpboxNsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: jumpboxNsgName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowBastionRDP'
        properties: {
          priority: 100
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourceAddressPrefix: '10.0.4.0/26'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '3389'
          description: 'Allow RDP from AzureBastionSubnet'
        }
      }
      {
        name: 'AllowBastionSSH'
        properties: {
          priority: 110
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourceAddressPrefix: '10.0.4.0/26'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '22'
          description: 'Allow SSH from AzureBastionSubnet'
        }
      }
      {
        name: 'DenyAllOtherInbound'
        properties: {
          priority: 4000
          protocol: '*'
          access: 'Deny'
          direction: 'Inbound'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
          description: 'Deny all other inbound traffic to the jump box'
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// AzureBastionSubnet - must use this exact name; minimum /26
// Declared as a child resource of the existing VNet; does not affect other subnets.
// ---------------------------------------------------------------------------

resource bastionSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' = {
  parent: vnet
  name: 'AzureBastionSubnet'
  properties: {
    addressPrefix: '10.0.4.0/26'
    // No NSG on AzureBastionSubnet - Azure Bastion manages its own traffic rules
  }
}

// ---------------------------------------------------------------------------
// jumpbox subnet - /28 gives 16 addresses, sufficient for one VM + overhead
// Depends on bastionSubnet to avoid concurrent subnet-update conflicts on VNet
// ---------------------------------------------------------------------------

resource jumpboxSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' = {
  parent: vnet
  name: 'jumpbox'
  properties: {
    addressPrefix: '10.0.5.0/28'
    networkSecurityGroup: {
      id: jumpboxNsg.id
    }
  }
  dependsOn: [
    bastionSubnet
  ]
}

// ---------------------------------------------------------------------------
// Public IP for Azure Bastion - Standard SKU, Static allocation (required)
// ---------------------------------------------------------------------------

resource bastionPip 'Microsoft.Network/publicIPAddresses@2024-01-01' = {
  name: bastionPipName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Regional'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    publicIPAddressVersion: 'IPv4'
  }
}

// ---------------------------------------------------------------------------
// Azure Bastion - Standard SKU enables copy/paste, file transfer, native RDP
// ---------------------------------------------------------------------------

resource bastion 'Microsoft.Network/bastionHosts@2024-01-01' = {
  name: bastionName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    scaleUnits: 2
    enableTunneling: true
    enableIpConnect: false
    enableShareableLink: false
    ipConfigurations: [
      {
        name: 'bastionIpConfig'
        properties: {
          subnet: {
            id: bastionSubnet.id
          }
          publicIPAddress: {
            id: bastionPip.id
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// NIC for jump box VM - no public IP; access only via Bastion
// ---------------------------------------------------------------------------

resource jumpboxNic 'Microsoft.Network/networkInterfaces@2024-01-01' = {
  name: jumpboxNicName
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: jumpboxSubnet.id
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
    enableAcceleratedNetworking: false
  }
}

// ---------------------------------------------------------------------------
// Jump box VM - Windows Server 2022, Standard_B2s, system-assigned identity
// No public IP; presenter connects exclusively through Azure Bastion.
// ---------------------------------------------------------------------------

resource jumpboxVm 'Microsoft.Compute/virtualMachines@2024-03-01' = {
  name: jumpboxVmName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_B2s'
    }
    osProfile: {
      computerName: 'jumpbox'
      adminUsername: 'demoadmin'
      adminPassword: adminPassword
      windowsConfiguration: {
        enableAutomaticUpdates: true
        patchSettings: {
          patchMode: 'AutomaticByOS'
          assessmentMode: 'ImageDefault'
        }
        provisionVMAgent: true
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'MicrosoftWindowsServer'
        offer: 'WindowsServer'
        sku: '2022-datacenter-azure-edition'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: 128
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
        deleteOption: 'Delete'
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: jumpboxNic.id
          properties: {
            deleteOption: 'Delete'
          }
        }
      ]
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: true
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Role assignments for the jump box managed identity
// ---------------------------------------------------------------------------

// 1. Reader on the resource group - allows portal navigation and resource discovery
resource readerRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, jumpboxVm.id, readerRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', readerRoleId)
    principalId: jumpboxVm.identity.principalId
    principalType: 'ServicePrincipal'
    description: 'Jump box demo identity - Reader on resource group'
  }
}

// 2. Azure AI Search Index Data Reader - allows querying the search index
resource searchAccount 'Microsoft.Search/searchServices@2023-11-01' existing = {
  name: searchAccountName
}

resource searchRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchAccount.id, jumpboxVm.id, searchIndexDataReaderRoleId)
  scope: searchAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReaderRoleId)
    principalId: jumpboxVm.identity.principalId
    principalType: 'ServicePrincipal'
    description: 'Jump box demo identity - Search Index Data Reader'
  }
}

// 3. Cosmos DB Built-in Data Reader (data-plane SQL role assignment)
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource cosmosSqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, jumpboxVm.id, cosmosBuiltInDataReaderRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataReaderRoleId}'
    principalId: jumpboxVm.identity.principalId
    scope: cosmosAccount.id
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the Azure Bastion host.')
output bastionId string = bastion.id

@description('Public IP address of the Azure Bastion host.')
output bastionPublicIp string = bastionPip.properties.ipAddress

@description('Resource ID of the jump box VM.')
output jumpboxVmId string = jumpboxVm.id

@description('Private IP address of the jump box VM NIC.')
output jumpboxPrivateIp string = jumpboxNic.properties.ipConfigurations[0].properties.privateIPAddress

@description('System-assigned managed identity principal ID of the jump box VM.')
output jumpboxPrincipalId string = jumpboxVm.identity.principalId
