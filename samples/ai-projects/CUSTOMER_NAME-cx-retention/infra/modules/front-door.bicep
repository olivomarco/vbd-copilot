// ---------------------------------------------------------------------------
// Module: Azure Front Door Premium with WAF Policy
// ---------------------------------------------------------------------------

@description('Environment name (dev, prod).')
param environment string

@description('Resource naming prefix.')
param resourcePrefix string

@description('Backend APIM gateway hostname.')
param apimGatewayHostname string

@description('Resource tags applied to all resources in this module.')
param tags object

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------
var frontDoorName = '${resourcePrefix}-afd-${environment}'
var wafPolicyName = replace('${resourcePrefix}-waf-${environment}', '-', '')
var endpointName = '${resourcePrefix}-ep-${environment}'

// EU country codes for geo-filter
var euCountryCodes = [
  'AT' // Austria
  'BE' // Belgium
  'BG' // Bulgaria
  'HR' // Croatia
  'CY' // Cyprus
  'CZ' // Czechia
  'DK' // Denmark
  'EE' // Estonia
  'FI' // Finland
  'FR' // France
  'DE' // Germany
  'GR' // Greece
  'HU' // Hungary
  'IE' // Ireland
  'IT' // Italy
  'LV' // Latvia
  'LT' // Lithuania
  'LU' // Luxembourg
  'MT' // Malta
  'NL' // Netherlands
  'PL' // Poland
  'PT' // Portugal
  'RO' // Romania
  'SK' // Slovakia
  'SI' // Slovenia
  'ES' // Spain
  'SE' // Sweden
]

// ---------------------------------------------------------------------------
// WAF Policy
// ---------------------------------------------------------------------------
resource wafPolicy 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: wafPolicyName
  location: 'Global'
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
      requestBodyCheck: 'Enabled'
    }
    customRules: {
      rules: [
        {
          name: 'GeoFilterEUOnly'
          priority: 100
          ruleType: 'MatchRule'
          action: 'Block'
          enabledState: 'Enabled'
          matchConditions: [
            {
              matchVariable: 'RemoteAddr'
              operator: 'GeoMatch'
              negateCondition: true
              matchValue: euCountryCodes
            }
          ]
        }
      ]
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
          ruleSetAction: 'Block'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.1'
          ruleSetAction: 'Block'
        }
      ]
    }
  }
}

// ---------------------------------------------------------------------------
// Front Door Profile (Premium)
// ---------------------------------------------------------------------------
resource frontDoor 'Microsoft.Cdn/profiles@2024-09-01' = {
  name: frontDoorName
  location: 'Global'
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    originResponseTimeoutSeconds: 60
  }
}

// ---------------------------------------------------------------------------
// Endpoint
// ---------------------------------------------------------------------------
resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2024-09-01' = {
  parent: frontDoor
  name: endpointName
  location: 'Global'
  tags: tags
  properties: {
    enabledState: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Origin Group
// ---------------------------------------------------------------------------
resource originGroup 'Microsoft.Cdn/profiles/originGroups@2024-09-01' = {
  parent: frontDoor
  name: 'apim-origin-group'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/status-0123456789abcdef'
      probeRequestType: 'HEAD'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 30
    }
    sessionAffinityState: 'Disabled'
  }
}

// ---------------------------------------------------------------------------
// Origin (APIM backend)
// ---------------------------------------------------------------------------
resource origin 'Microsoft.Cdn/profiles/originGroups/origins@2024-09-01' = {
  parent: originGroup
  name: 'apim-origin'
  properties: {
    hostName: apimGatewayHostname
    httpPort: 80
    httpsPort: 443
    originHostHeader: apimGatewayHostname
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Route
// ---------------------------------------------------------------------------
resource route 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-09-01' = {
  parent: endpoint
  name: 'default-route'
  properties: {
    originGroup: {
      id: originGroup.id
    }
    supportedProtocols: [
      'Https'
    ]
    patternsToMatch: [
      '/*'
    ]
    forwardingProtocol: 'HttpsOnly'
    linkToDefaultDomain: 'Enabled'
    httpsRedirect: 'Enabled'
  }
  dependsOn: [
    origin
  ]
}

// ---------------------------------------------------------------------------
// Security Policy (link WAF to endpoint)
// ---------------------------------------------------------------------------
resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2024-09-01' = {
  parent: frontDoor
  name: 'waf-security-policy'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: {
        id: wafPolicy.id
      }
      associations: [
        {
          domains: [
            {
              id: endpoint.id
            }
          ]
          patternsToMatch: [
            '/*'
          ]
        }
      ]
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
@description('Resource ID of the Front Door profile.')
output frontDoorId string = frontDoor.id

@description('Name of the Front Door profile.')
output frontDoorName string = frontDoor.name

@description('Hostname of the Front Door endpoint.')
output frontDoorEndpointHostname string = endpoint.properties.hostName
