using './main.bicep'

// Max's demo defaults. Customers should override these.
param location = 'eastus'
param baseName = 'xltdemo'

// Required: object ID of the user/SP running the Python scripts.
// Pass at deploy time:
//   -p deployerObjectId=$(az ad signed-in-user show --query id -o tsv)
param deployerObjectId = ''
param deployerPrincipalType = 'User'
param containerName = 'documents'
