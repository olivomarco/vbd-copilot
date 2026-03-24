using '../main.bicep'

param environment = 'dev'
param location = 'swedencentral'
param resourcePrefix = 'CUSTOMER_NAME-bill'
param containerAppMinReplicas = 1
param containerAppMaxReplicas = 5
param aiSearchReplicaCount = 1
param openAiGpt4oCapacity = 30
param openAiGpt4oMiniCapacity = 100
param openAiEmbeddingCapacity = 100
