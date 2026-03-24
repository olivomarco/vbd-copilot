// =============================================================================
// demo.bicepparam
// Purpose  : Parameter file for the CUSTOMER_NAME Bill Explainer demo overlay.
//            Targets the existing dev deployment in Sweden Central.
//            Run with:
//              az deployment group create \
//                --resource-group <rg-name> \
//                --bicep-file demo-access.bicep \
//                --parameters demo.bicepparam \
//                --parameters adminPassword=<secure-value>
// Note     : adminPassword is intentionally omitted here. Pass it at deploy
//            time via --parameters adminPassword=<value> or a Key Vault
//            reference to avoid storing secrets in source control.
// =============================================================================

using 'demo-access.bicep'

param environment = 'dev'

param location = 'swedencentral'

param resourcePrefix = 'CUSTOMER_NAME-bill'

param vnetName = 'CUSTOMER_NAME-bill-vnet-dev'

// adminPassword must be supplied at deployment time - do not store here.
// Example: az deployment group create ... --parameters adminPassword='...'
// adminPassword: pass at deploy time via --parameters adminPassword="<your-password>" - do not store here

param tags = {
  project: 'CUSTOMER_NAME-bill-explainer'
  environment: 'dev'
  purpose: 'demo-access'
  managedBy: 'bicep'
}
