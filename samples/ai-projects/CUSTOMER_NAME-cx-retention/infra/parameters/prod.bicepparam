using '../main.bicep'

param environment = 'prod'
param location = 'swedencentral'
param resourcePrefix = 'CUSTOMER_NAME-bill'
param containerAppMinReplicas = 2
param containerAppMaxReplicas = 20
param aiSearchReplicaCount = 2
param openAiGpt4oCapacity = 150
param openAiGpt4oMiniCapacity = 500
param openAiEmbeddingCapacity = 300
