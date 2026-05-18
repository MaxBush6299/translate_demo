// Azure Document Translation demo infrastructure.
// Deploys an Azure AI Translator (S1) with system-assigned managed identity
// and an Azure Storage account with a single blob container. Grants the
// Translator MI Storage Blob Data Contributor on the storage account, and
// grants the deployer Cognitive Services User on the Translator account so
// the demo runs fully keyless via Entra ID.

targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Base name used to derive resource names. Lowercase letters and numbers.')
@minLength(3)
@maxLength(11)
param baseName string = 'xltdemo'

@description('Object ID (GUID) of the user/service principal that will run the Python scripts. Used to grant Cognitive Services User on the Translator account.')
param deployerObjectId string

@description('Principal type for the deployer role assignment.')
@allowed([
  'User'
  'ServicePrincipal'
  'Group'
])
param deployerPrincipalType string = 'User'

@description('Name of the blob container used by the demo.')
param containerName string = 'documents'

var suffix = uniqueString(resourceGroup().id, baseName)
var storageAccountName = toLower('st${baseName}${take(suffix, 6)}')
var translatorAccountName = 'cog-${baseName}-${take(suffix, 6)}'

// Built-in role definition IDs
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
    accessTier: 'Hot'
  }
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

resource translator 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: translatorAccountName
  location: location
  kind: 'TextTranslation'
  sku: {
    name: 'S1'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // Custom subdomain is required for Document Translation.
    customSubDomainName: translatorAccountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// Translator MI -> Storage Blob Data Contributor on the storage account.
resource translatorToStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, translator.id, storageBlobDataContributorRoleId)
  properties: {
    principalId: translator.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
  }
}

// Deployer -> Cognitive Services User on the Translator account.
resource deployerToTranslatorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: translator
  name: guid(translator.id, deployerObjectId, cognitiveServicesUserRoleId)
  properties: {
    principalId: deployerObjectId
    principalType: deployerPrincipalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
  }
}

// Deployer -> Storage Blob Data Contributor on the storage account so the
// local Python scripts can upload inputs and download translated outputs
// without using account keys.
resource deployerToStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, deployerObjectId, storageBlobDataContributorRoleId)
  properties: {
    principalId: deployerObjectId
    principalType: deployerPrincipalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
  }
}

output translatorEndpoint string = translator.properties.endpoint
output translatorAccountName string = translator.name
output storageAccountName string = storage.name
output containerName string = container.name
output containerUrl string = '${storage.properties.primaryEndpoints.blob}${container.name}'
