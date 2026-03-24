# CUSTOMER_NAME Intelligent Bill Explainer

An AI-powered chatbot that explains Italian energy bills to CUSTOMER_NAME customers using Retrieval-Augmented Generation (RAG) on Azure. The system operates in two modes: **general FAQ** (answering common questions about Italian energy tariffs, regulations, and bill components) and **personalised bill lookup** (retrieving a specific customer bill and explaining line items in plain language). It is designed to serve 10 million CUSTOMER_NAME customers at a sustained throughput of 50,000 to 100,000 queries per day.

The backend is a Python FastAPI application that streams responses via Server-Sent Events, backed by Azure OpenAI, Azure AI Search, Azure Cosmos DB, and the CUSTOMER_NAME Billing API. A lightweight HTML/CSS/JS chat widget is included for demonstration purposes. Infrastructure is defined entirely in Bicep and deployed to Azure Container Apps behind Azure Front Door and API Management.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Repository Structure](#repository-structure)
4. [Environment Setup](#environment-setup)
5. [Infrastructure Deployment](#infrastructure-deployment)
6. [Application Deployment](#application-deployment)
7. [Quick Deploy (deploy.sh)](#quick-deploy-deploysh)
8. [Validation (validate.sh)](#validation-validatesh)
9. [Local Development](#local-development)
10. [CI/CD Pipeline](#cicd-pipeline)
11. [API Reference](#api-reference)
12. [Demo Guide with Sample I/O](#demo-guide-with-sample-io)
13. [Troubleshooting](#troubleshooting)
14. [Project Documentation Links](#project-documentation-links)

---

## Architecture Overview

```
Customer Browser
       |
       v
+-----------------+
| Azure Front Door|   (Premium SKU, WAF, EU geo-filter)
+-----------------+
       |
       v
+---------------------+
| Azure API Management|   (Standard v2)
+---------------------+
       |  (VNet-integrated)
       v
+----------------------------+
| Azure Container Apps       |   (Consumption plan, 2-20 replicas)
|  uvicorn + FastAPI         |
|  +-----------------------+ |
|  | Model Router          | |   classify query -> GPT-4o-mini (simple) or GPT-4o (complex)
|  | RAG Pipeline          | |   orchestrate search, billing, prompt, stream
|  | Conversation Manager  | |   session + message persistence
|  | Feedback Service      | |   thumbs-up / thumbs-down ratings
|  +-----------------------+ |
+----------------------------+
       |           |            |             |
       v           v            v             v
+----------+ +------------+ +----------+ +-----------+
|Azure     | |Azure AI    | |Azure     | |CUSTOMER_NAME  |
|OpenAI    | |Search      | |Cosmos DB | |Billing API|
|S0        | |Standard S1 | |Serverless| |(external) |
|GPT-4o    | |Semantic    | |sessions, | |bill data  |
|GPT-4o-   | |Ranker      | |messages, | |lookup     |
|mini      | |Hybrid      | |feedback  | |           |
|Embedding | |search      | |          | |           |
+----------+ +------------+ +----------+ +-----------+
       |
       v
+---------------------+   +-------------------+
| Azure Blob Storage  |   | Azure Key Vault   |
| (Standard LRS)      |   | (Standard)        |
| knowledge base docs |   | secrets + certs   |
+---------------------+   +-------------------+
       |
       v
+---------------------------+
| Azure Monitor             |
| Log Analytics + App       |
| Insights (OpenTelemetry)  |
+---------------------------+
```

### Azure Services

| Service | SKU / Tier | Purpose |
|---------|-----------|---------|
| Azure OpenAI | S0 (Data Zone Standard) | GPT-4o, GPT-4o-mini, text-embedding-3-small |
| Azure AI Search | Standard (S1) | Hybrid search with semantic ranker over knowledge base |
| Azure Cosmos DB | Serverless | Conversation sessions, messages, and feedback storage |
| Azure Container Apps | Consumption | Application hosting with auto-scale (2-20 replicas prod) |
| Azure API Management | Standard v2 | Rate limiting, API policies, analytics |
| Azure Front Door | Premium | Global CDN, WAF, EU geo-filtering |
| Azure Blob Storage | Standard LRS | Knowledge base documents, bill PDFs |
| Azure Key Vault | Standard | Secrets, certificates, and configuration |
| Azure Monitor | Log Analytics (PerGB2018) | Logging, tracing, Application Insights |
| Virtual Network | -- | Network isolation with subnets and private endpoints |

For a detailed architecture diagram, see [docs/architecture-diagram.md](docs/architecture-diagram.md).

---

## Prerequisites

Before you begin, ensure the following are installed and configured:

| Requirement | Minimum Version | Verification Command |
|------------|----------------|---------------------|
| Azure subscription with OpenAI access | -- | `az account show` |
| Azure CLI | 2.60+ | `az version` |
| Docker Desktop | latest | `docker --version` |
| Python | 3.11+ | `python3 --version` |
| Git | latest | `git --version` |
| GitHub CLI (optional, for CI/CD) | latest | `gh --version` |

Your Azure subscription must have Azure OpenAI access approved. Request access at [https://aka.ms/oai/access](https://aka.ms/oai/access) if you have not done so already.

---

## Repository Structure

```
CUSTOMER_NAME-cx-retention/
|-- .github/
|   +-- workflows/
|       +-- ci-cd.yml               # GitHub Actions CI/CD pipeline
|-- docs/
|   |-- ai-brainstorming.md         # Initial AI approach exploration
|   |-- architecture-diagram.md     # Architecture description and diagram
|   |-- architecture-diagram.drawio # Editable diagram (draw.io format)
|   |-- cost-estimation.md          # Monthly cost estimates (dev and prod)
|   |-- delivery-plan.md            # Sprint-based delivery plan
|   +-- solution-design.md          # Full solution design document
|-- infra/
|   |-- main.bicep                  # Orchestrator template (all modules)
|   |-- modules/
|   |   |-- ai-search.bicep         # Azure AI Search (Standard S1)
|   |   |-- apim.bicep              # API Management (Standard v2)
|   |   |-- blob-storage.bicep      # Blob Storage (Standard LRS)
|   |   |-- container-apps.bicep    # Container Apps environment + app
|   |   |-- cosmos-db.bicep         # Cosmos DB (Serverless)
|   |   |-- front-door.bicep        # Front Door Premium + WAF
|   |   |-- key-vault.bicep         # Key Vault (Standard)
|   |   |-- monitoring.bicep        # Log Analytics + App Insights
|   |   |-- openai.bicep            # Azure OpenAI + model deployments
|   |   |-- private-endpoints.bicep # Private endpoints + DNS zones
|   |   |-- role-assignments.bicep  # RBAC for managed identity
|   |   +-- vnet.bicep              # VNet, subnets, NSGs
|   +-- parameters/
|       |-- dev.bicepparam          # Dev environment parameters
|       +-- prod.bicepparam         # Prod environment parameters
|-- scripts/
|   +-- deploy.sh                   # Idempotent deployment script
|-- src/
|   |-- Dockerfile                  # Multi-stage Docker build
|   |-- requirements.txt            # Python dependencies
|   |-- pyproject.toml              # Project metadata and tool config
|   |-- app/
|   |   |-- __init__.py
|   |   |-- main.py                 # FastAPI application factory
|   |   |-- config.py               # Settings from environment variables
|   |   |-- models/
|   |   |   +-- schemas.py          # Pydantic request/response models
|   |   |-- prompts/
|   |   |   +-- system_prompt.py    # System prompt templates (Italian)
|   |   |-- routers/
|   |   |   |-- chat.py             # POST /api/v1/chat (SSE streaming)
|   |   |   |-- health.py           # GET /health, GET /health/ready
|   |   |   +-- sessions.py         # GET/DELETE /api/v1/sessions/{id}
|   |   +-- services/
|   |       |-- billing_api.py      # CUSTOMER_NAME Billing API client
|   |       |-- conversation_manager.py  # Cosmos DB session/message persistence
|   |       |-- feedback_service.py # Feedback storage
|   |       |-- model_router.py     # Query classifier (GPT-4o vs GPT-4o-mini)
|   |       |-- openai_service.py   # Azure OpenAI streaming client
|   |       |-- rag_pipeline.py     # End-to-end RAG orchestrator
|   |       +-- search_service.py   # Azure AI Search hybrid search
|   +-- frontend/
|       |-- index.html              # Chat widget HTML
|       |-- chat.js                 # Chat widget JavaScript
|       +-- styles.css              # Chat widget styles
|-- tests/
|   |-- conftest.py                 # Shared fixtures (Settings mock, etc.)
|   |-- pytest.ini                  # Pytest configuration
|   |-- validate.sh                 # Validation harness entry point
|   |-- unit/
|   |   |-- test_billing_api.py
|   |   |-- test_chat_router.py
|   |   |-- test_conversation_manager.py
|   |   |-- test_feedback_service.py
|   |   |-- test_health_router.py
|   |   |-- test_model_router.py
|   |   |-- test_openai_service.py
|   |   |-- test_rag_pipeline.py
|   |   |-- test_schemas.py
|   |   |-- test_search_service.py
|   |   |-- test_sessions_router.py
|   |   +-- test_system_prompt.py
|   +-- smoke/
|       |-- conftest.py             # Smoke test fixtures (base URL)
|       +-- test_endpoints.py       # Live endpoint health and API tests
+-- README.md                       # This file
```

---

## Environment Setup

### 1. Navigate to the project directory

```bash
cd outputs/ai-projects/CUSTOMER_NAME-cx-retention
```

### 2. Create a Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r src/requirements.txt
pip install pytest pytest-asyncio pytest-cov httpx respx ruff
```

### 4. Configure environment variables

The application reads configuration from environment variables (or a `.env` file in the working directory). Create a `.env` file in the `src/` directory:

```bash
cat > src/.env << 'EOF'
# -- Azure OpenAI --
AZURE_OPENAI_ENDPOINT=https://<your-openai-resource>.openai.azure.com/
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o
AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# -- Azure AI Search --
AZURE_SEARCH_ENDPOINT=https://<your-search-resource>.search.windows.net
AZURE_SEARCH_INDEX_NAME=knowledge-base

# -- Azure Cosmos DB --
COSMOS_DB_ENDPOINT=https://<your-cosmos-resource>.documents.azure.com:443/
COSMOS_DB_DATABASE_NAME=billexplainer

# -- CUSTOMER_NAME Billing API --
BILLING_API_BASE_URL=https://api.CUSTOMER_NAME.example.com/billing/v1
BILLING_API_CLIENT_ID=<your-entra-client-id>
BILLING_API_SCOPE=api://<your-billing-api-scope>/.default

# -- Azure Key Vault --
KEY_VAULT_URL=https://<your-keyvault>.vault.azure.net/

# -- Observability (optional) --
APP_INSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...

# -- Application --
LOG_LEVEL=DEBUG
CORS_ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000
EOF
```

#### Complete environment variable reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | -- | Azure OpenAI resource endpoint URL |
| `AZURE_OPENAI_GPT4O_DEPLOYMENT` | No | `gpt-4o` | GPT-4o deployment name |
| `AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT` | No | `gpt-4o-mini` | GPT-4o-mini deployment name |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | No | `text-embedding-3-small` | Embedding model deployment name |
| `AZURE_SEARCH_ENDPOINT` | Yes | -- | Azure AI Search service endpoint |
| `AZURE_SEARCH_INDEX_NAME` | No | `knowledge-base` | Name of the search index |
| `COSMOS_DB_ENDPOINT` | Yes | -- | Cosmos DB account endpoint |
| `COSMOS_DB_DATABASE_NAME` | No | `billexplainer` | Cosmos DB database name |
| `BILLING_API_BASE_URL` | Yes | -- | CUSTOMER_NAME Billing API base URL |
| `BILLING_API_CLIENT_ID` | Yes | -- | Entra ID client ID for billing API auth |
| `BILLING_API_SCOPE` | Yes | -- | OAuth scope for billing API |
| `KEY_VAULT_URL` | Yes | -- | Azure Key Vault URI |
| `APP_INSIGHTS_CONNECTION_STRING` | No | `None` | Application Insights connection string |
| `LOG_LEVEL` | No | `INFO` | Python logging level |
| `CORS_ALLOWED_ORIGINS` | No | `*` | Comma-separated list of allowed CORS origins |

Authentication uses `DefaultAzureCredential`. For local development, run `az login` so the Azure SDK can pick up your credentials.

---

## Infrastructure Deployment

### Deploy with Bicep

All infrastructure is defined in `infra/main.bicep` with modular files in `infra/modules/`. Parameter files for dev and prod environments are in `infra/parameters/`.

#### 1. Create the resource group

```bash
az group create \
  --name rg-CUSTOMER_NAME-dev \
  --location swedencentral \
  --tags project=CUSTOMER_NAME-bill-explainer environment=dev
```

#### 2. Validate the template

```bash
az deployment group validate \
  --resource-group rg-CUSTOMER_NAME-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam
```

#### 3. Deploy

```bash
az deployment group create \
  --resource-group rg-CUSTOMER_NAME-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam \
  --mode Incremental \
  --name "manual-dev-$(date +%Y%m%d-%H%M%S)"
```

#### 4. View deployment outputs

```bash
az deployment group show \
  --resource-group rg-CUSTOMER_NAME-dev \
  --name "<deployment-name>" \
  --query "properties.outputs"
```

### Parameter differences: dev vs prod

| Parameter | Dev | Prod |
|-----------|-----|------|
| `containerAppMinReplicas` | 1 | 2 |
| `containerAppMaxReplicas` | 5 | 20 |
| `aiSearchReplicaCount` | 1 | 2 |
| `openAiGpt4oCapacity` (K TPM) | 30 | 150 |
| `openAiGpt4oMiniCapacity` (K TPM) | 100 | 500 |
| `openAiEmbeddingCapacity` (K TPM) | 100 | 300 |

### Resources created

The deployment creates the following Azure resources (prefixed with `CUSTOMER_NAME-bill-<env>`):

- Virtual Network with 3 subnets (apps, data, APIM) and NSGs
- Azure OpenAI account with 3 model deployments (GPT-4o, GPT-4o-mini, text-embedding-3-small)
- Azure AI Search service (Standard S1) with semantic ranker
- Azure Cosmos DB account (Serverless) with database and containers
- Azure Blob Storage account (Standard LRS)
- Azure Key Vault (Standard)
- Azure Container Apps environment and application
- Azure API Management instance (Standard v2)
- Azure Front Door profile (Premium) with WAF policy and EU geo-filter
- Private endpoints and DNS zones for all data services
- Managed identity RBAC role assignments
- Log Analytics workspace and Application Insights

### Verify deployment

```bash
# Check all resources in the group
az resource list --resource-group rg-CUSTOMER_NAME-dev --output table

# Check Container App status
az containerapp show \
  --name CUSTOMER_NAME-bill-ca-dev \
  --resource-group rg-CUSTOMER_NAME-dev \
  --query "{status:properties.runningStatus, fqdn:properties.configuration.ingress.fqdn}"
```

---

## Application Deployment

### 1. Build the Docker image

```bash
cd src/
docker build -t CUSTOMER_NAME-bill-explainer:latest -f Dockerfile .
cd ..
```

### 2. Push to Azure Container Registry

```bash
# Login to your ACR
az acr login --name <your-acr-name>

# Tag and push
ACR_SERVER="<your-acr-name>.azurecr.io"
docker tag CUSTOMER_NAME-bill-explainer:latest ${ACR_SERVER}/CUSTOMER_NAME-bill-explainer:latest
docker push ${ACR_SERVER}/CUSTOMER_NAME-bill-explainer:latest
```

### 3. Update the Container App

```bash
az containerapp update \
  --name CUSTOMER_NAME-bill-ca-dev \
  --resource-group rg-CUSTOMER_NAME-dev \
  --image "${ACR_SERVER}/CUSTOMER_NAME-bill-explainer:latest"
```

### 4. Verify the app is running

```bash
FQDN=$(az containerapp show \
  --name CUSTOMER_NAME-bill-ca-dev \
  --resource-group rg-CUSTOMER_NAME-dev \
  --query "properties.configuration.ingress.fqdn" -o tsv)

curl -s "https://${FQDN}/health" | python3 -m json.tool
```

Expected output:

```json
{
    "status": "healthy",
    "services": {}
}
```

---

## Quick Deploy (deploy.sh)

The `scripts/deploy.sh` script automates the full deployment lifecycle: infrastructure provisioning via Bicep and application build/push/deploy via Docker and Azure Container Apps. It is idempotent and safe to re-run.

### Usage

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh --help
```

### Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--resource-group` | `-g` | Azure resource group name (required) |
| `--location` | `-l` | Azure region (default: `swedencentral`) |
| `--environment` | `-e` | Target environment: `dev` or `prod` (default: `dev`) |
| `--infra-only` | -- | Deploy infrastructure only, skip app build/push |
| `--app-only` | -- | Deploy application only, skip Bicep deployment |
| `--help` | `-h` | Show help and exit |

### Environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_SUBSCRIPTION_ID` | Override the active Azure subscription |
| `ACR_NAME` | Override auto-detected ACR name |
| `IMAGE_TAG` | Override Docker image tag (default: git short SHA or `latest`) |

### Examples

```bash
# Full deployment to dev
./scripts/deploy.sh -g rg-CUSTOMER_NAME-dev -e dev

# Infrastructure only to production
./scripts/deploy.sh -g rg-CUSTOMER_NAME-prod -e prod --infra-only

# Redeploy application only (after a code change)
./scripts/deploy.sh -g rg-CUSTOMER_NAME-dev -e dev --app-only

# Deploy with a specific image tag
IMAGE_TAG=v1.2.3 ./scripts/deploy.sh -g rg-CUSTOMER_NAME-dev -e dev --app-only
```

---

## Validation (validate.sh)

The `tests/validate.sh` script is the single entry point for verifying the solution. It checks infrastructure templates, runs unit tests, and optionally runs smoke tests against a live deployment.

### Usage

```bash
chmod +x tests/validate.sh
./tests/validate.sh --help
```

### Flags

| Flag | Description |
|------|-------------|
| `--live` | Also run smoke tests against a deployed environment |
| `--help` | Show help and exit |

### What it checks

1. **Prerequisites** -- verifies Python 3, pytest, and (optionally) Azure CLI are available.
2. **Infrastructure (Bicep)** -- runs `az bicep build` on `main.bicep` and all module files. Skipped gracefully if Azure CLI is not installed.
3. **Unit tests** -- runs `pytest tests/unit/` with a coverage threshold of 80%.
4. **Smoke tests** (only with `--live`) -- runs `pytest tests/smoke/` against the deployed API, or falls back to curl-based health checks.

### Environment variables for smoke tests

| Variable | Description |
|----------|-------------|
| `API_BASE_URL` | Full base URL of the deployed API (e.g., `https://myapp.azurecontainerapps.io`) |
| `CONTAINER_APP_FQDN` | Alternative: just the FQDN, and the script prepends `https://` |

### Examples

```bash
# Run infra validation and unit tests only
./tests/validate.sh

# Run everything including smoke tests against dev
API_BASE_URL=https://CUSTOMER_NAME-bill-ca-dev.azurecontainerapps.io \
  ./tests/validate.sh --live
```

### Expected output

```
CUSTOMER_NAME Intelligent Bill Explainer - Validation
==================================================

--- Checking prerequisites ---
[INFO]  python3 found: Python 3.11.x
[INFO]  pytest found: pytest 8.x.x
[INFO]  Azure CLI found: 2.6x.x

--- Validating infrastructure (Bicep) ---
[INFO]  Building: main.bicep
[INFO]    main.bicep - OK
[INFO]  Building: modules/ai-search.bicep
...
[INFO]  All Bicep files validated successfully

--- Running unit tests ---
[INFO]  Found 12 test file(s) in tests/unit
...
[INFO]  Unit tests passed

==========================================
         VALIDATION SUMMARY
==========================================

  PASS  Prerequisites
  PASS  Infrastructure (Bicep)
  PASS  Unit Tests
  SKIP  Smoke Tests

  -----------------------------------------
  Passed: 3  Failed: 0  Skipped: 1

  RESULT: PASS
```

---

## Local Development

### Run the application locally

```bash
# From the project root, with the virtual environment activated
cd src/
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The application starts on [http://localhost:8000](http://localhost:8000). The chat widget is served from the root path, and the auto-generated OpenAPI documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

You must have the environment variables set (via `src/.env` or exported in your shell) and be logged in to Azure (`az login`) for `DefaultAzureCredential` to work.

### Run tests locally

```bash
# Unit tests with coverage report
python3 -m pytest tests/unit/ -v --cov=src/app --cov-report=term-missing

# A single test file
python3 -m pytest tests/unit/test_model_router.py -v

# Smoke tests against a local server
API_BASE_URL=http://localhost:8000 python3 -m pytest tests/smoke/ -v
```

### Lint code

```bash
pip install ruff

# Check for lint errors
ruff check src/app/

# Auto-fix lint errors
ruff check src/app/ --fix

# Check formatting
ruff format src/app/ --check --diff

# Apply formatting
ruff format src/app/
```

---

## CI/CD Pipeline

The GitHub Actions workflow at `.github/workflows/ci-cd.yml` runs on every push and pull request to `main` that touches files under `outputs/ai-projects/CUSTOMER_NAME-cx-retention/`.

### Pipeline jobs

| Job | Trigger | Description |
|-----|---------|-------------|
| **lint** | PR and push | Runs `ruff check` and `ruff format --check` on application code |
| **test** | PR and push | Runs `pytest tests/unit/` with 80% coverage threshold; uploads coverage and test result artifacts |
| **validate-infra** | PR and push | Installs Bicep CLI; builds `main.bicep` and all modules; runs `az deployment group validate` on PRs |
| **build** | Push to main only | Builds Docker image and pushes to ACR with git-SHA tag and `latest` tag |
| **deploy-dev** | Push to main only | Deploys infra (Bicep incremental) + app (Container App image update) to the dev environment; verifies health |
| **deploy-prod** | Push to main only | Same as dev, but targets prod; requires manual approval via GitHub environment protection rules |

### Required GitHub secrets

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | Service principal credentials JSON for `azure/login` |
| `ACR_NAME` | Azure Container Registry name (without `.azurecr.io`) |
| `RESOURCE_GROUP_DEV` | Resource group for the dev environment |
| `RESOURCE_GROUP_PROD` | Resource group for the prod environment |

### Production approval

The `deploy-prod` job uses a GitHub `environment: prod` configuration. Configure environment protection rules in your repository settings under **Settings > Environments > prod** to require manual approval before production deployments execute.

---

## API Reference

### Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/health` | Liveness probe. Always returns 200 if the process is running. | None |
| `GET` | `/health/ready` | Readiness probe. Checks Cosmos DB, AI Search, and OpenAI connectivity. Returns 503 if degraded. | None |
| `POST` | `/api/v1/chat` | Send a chat message and receive a streamed response via SSE. | API key (via APIM) |
| `POST` | `/api/v1/chat/feedback` | Submit thumbs-up/down feedback for an assistant message. | API key (via APIM) |
| `GET` | `/api/v1/sessions/{session_id}` | Retrieve session metadata and full message history. | API key (via APIM) |
| `DELETE` | `/api/v1/sessions/{session_id}` | GDPR erasure: permanently delete a session and all associated data. | API key (via APIM) |
| `GET` | `/docs` | Auto-generated OpenAPI (Swagger) documentation. | None |
| `GET` | `/` | Chat widget frontend (static HTML). | None |

### POST /api/v1/chat

**Request body:**

```json
{
  "message": "Cosa sono gli oneri di sistema nella mia bolletta?",
  "session_id": null,
  "bill_ref": null
}
```

**Response:** `text/event-stream` (Server-Sent Events)

Each event carries a JSON payload on the `data:` line:

```
data: {"token": "Gli ", "done": false, "session_id": null, "message_id": null}

data: {"token": "oneri ", "done": false, "session_id": null, "message_id": null}

data: {"token": "di sistema...", "done": false, "session_id": null, "message_id": null}

data: {"token": "", "done": true, "session_id": "a1b2c3d4-...", "message_id": "msg-5678-..."}
```

The final event has `"done": true` and includes the `session_id` (for continuing the conversation) and `message_id` (for submitting feedback).

### POST /api/v1/chat/feedback

**Request body:**

```json
{
  "session_id": "a1b2c3d4-...",
  "message_id": "msg-5678-...",
  "rating": "up",
  "comment": "Spiegazione molto chiara, grazie!"
}
```

**Response:**

```json
{
  "feedback_id": "fb-9012-...",
  "status": "recorded"
}
```

### GET /api/v1/sessions/{session_id}

**Response:**

```json
{
  "session_id": "a1b2c3d4-...",
  "created_at": "2025-01-15T10:30:00Z",
  "last_active": "2025-01-15T10:35:00Z",
  "bill_ref": "BILL-2024-123456",
  "message_count": 4,
  "messages": [
    {
      "message_id": "msg-1234-...",
      "role": "user",
      "content": "Perche' la mia bolletta e' piu' alta questo mese?",
      "timestamp": "2025-01-15T10:30:00Z",
      "model_used": null
    },
    {
      "message_id": "msg-5678-...",
      "role": "assistant",
      "content": "Buongiorno! Ho analizzato la sua bolletta...",
      "timestamp": "2025-01-15T10:30:05Z",
      "model_used": "gpt-4o"
    }
  ]
}
```

### GET /health/ready

**Response (all healthy):**

```json
{
  "status": "healthy",
  "services": {
    "cosmos_db": "healthy",
    "ai_search": "healthy",
    "openai": "healthy"
  }
}
```

**Response (degraded, HTTP 503):**

```json
{
  "status": "degraded",
  "services": {
    "cosmos_db": "healthy",
    "ai_search": "unhealthy",
    "openai": "healthy"
  }
}
```

---

## Demo Guide with Sample I/O

This section walks through a customer demonstration of the Bill Explainer chatbot.

### Step 1: Open the chat widget

Navigate to the application URL in a browser. For local development, open [http://localhost:8000](http://localhost:8000). For a deployed environment, use the Front Door endpoint hostname.

### Step 2: Ask a general FAQ question

Type a general question about Italian energy bills. The system routes this to GPT-4o-mini (cost-effective model) and uses the knowledge base for context.

**User input:**

```
Cosa sono gli oneri di sistema nella bolletta elettrica?
```

**Expected response (streamed):**

```
Gli oneri di sistema sono una componente della bolletta elettrica che copre
i costi generali del sistema elettrico nazionale italiano. Includono:

- Incentivi per le fonti rinnovabili (componente ASOS)
- Costi per il decommissioning nucleare
- Agevolazioni tariffarie per il settore ferroviario
- Promozione dell'efficienza energetica

Questi oneri sono stabiliti dall'ARERA (Autorita' di Regolazione per Energia
Reti e Ambiente) e vengono aggiornati trimestralmente. Nella sua bolletta,
li trova nella sezione "Oneri di sistema" espressi in euro per kilowattora
(EUR/kWh) consumato.

Ha altre domande sulla sua bolletta?
```

### Step 3: Ask a personalised bill question

Provide a bill reference to trigger personalised mode. The system routes this to GPT-4o (complex reasoning) and calls the Billing API.

**curl command:**

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Perche la mia bolletta e piu alta rispetto al mese scorso?",
    "bill_ref": "BILL-2024-123456"
  }'
```

**Expected streamed response:**

```
Buongiorno! Ho analizzato la sua bolletta BILL-2024-123456 relativa al
periodo 01/12/2024 - 31/12/2024.

Il totale di questa bolletta e' di EUR 187,45, rispetto alla bolletta
precedente. Ecco i fattori principali dell'aumento:

1. **Consumo maggiore**: Il suo consumo nel periodo e' stato di 320 kWh,
   superiore alla media dei mesi precedenti.

2. **Oneri di sistema**: La componente ASOS e' stata aggiornata
   dall'ARERA nel quarto trimestre 2024.

3. **Spesa per il trasporto e la gestione del contatore**: Questa voce
   e' rimasta stabile a EUR 23,10.

Se desidera un dettaglio su una voce specifica della bolletta, me lo
indichi pure.
```

### Step 4: Submit feedback

After receiving a response, submit feedback using the `session_id` and `message_id` from the final SSE event.

```bash
curl -X POST "http://localhost:8000/api/v1/chat/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "a1b2c3d4-...",
    "message_id": "msg-5678-...",
    "rating": "up",
    "comment": "Spiegazione chiara e dettagliata"
  }'
```

**Response:**

```json
{
  "feedback_id": "fb-9012-...",
  "status": "recorded"
}
```

### Step 5: Test health endpoints

```bash
# Liveness
curl -s http://localhost:8000/health | python3 -m json.tool

# Readiness (checks backend services)
curl -s http://localhost:8000/health/ready | python3 -m json.tool
```

### Step 6: Retrieve session history

```bash
curl -s "http://localhost:8000/api/v1/sessions/a1b2c3d4-..." | python3 -m json.tool
```

### Step 7: GDPR erasure

```bash
curl -X DELETE "http://localhost:8000/api/v1/sessions/a1b2c3d4-..."
# Returns HTTP 204 No Content
```

---

## Troubleshooting

### Azure OpenAI quota errors

**Symptom:** HTTP 429 responses from the chat endpoint, or `RateLimitError` in logs.

**Solution:** Check your OpenAI deployment TPM (tokens per minute) quota in the Azure portal under **Azure OpenAI > Deployments**. Increase capacity in the Bicep parameter file (`openAiGpt4oCapacity`, `openAiGpt4oMiniCapacity`) and redeploy infrastructure. For dev, 30K TPM for GPT-4o is the minimum; for production, 150K+ is recommended.

```bash
# Check current quota usage
az cognitiveservices account deployment list \
  --name CUSTOMER_NAME-bill-oai-dev \
  --resource-group rg-CUSTOMER_NAME-dev \
  --output table
```

### Cosmos DB connection issues

**Symptom:** `/health/ready` returns `"cosmos_db": "unhealthy"`, or `ServiceRequestError` in logs.

**Solution:**
1. Verify the `COSMOS_DB_ENDPOINT` environment variable is correct.
2. Confirm the managed identity has the `Cosmos DB Built-in Data Contributor` role. The `role-assignments.bicep` module assigns this automatically.
3. Check that the private endpoint and DNS zone are configured correctly by testing from within the VNet.

```bash
az cosmosdb show --name CUSTOMER_NAME-bill-cosmos-dev \
  --resource-group rg-CUSTOMER_NAME-dev \
  --query "{status:provisioningState, endpoint:documentEndpoint}"
```

### AI Search index not found

**Symptom:** Chat responses lack context, or `ResourceNotFoundError` with index name in logs.

**Solution:** The search index (`knowledge-base` by default) must be created and populated separately after provisioning the AI Search service. Upload your knowledge base documents to Blob Storage and configure an indexer, or create the index manually via the Azure portal or REST API. Verify the index name matches `AZURE_SEARCH_INDEX_NAME`.

```bash
# List available indexes
curl -s "https://CUSTOMER_NAME-bill-search-dev.search.windows.net/indexes?api-version=2024-07-01" \
  -H "api-key: $(az search admin-key show --service-name CUSTOMER_NAME-bill-search-dev \
       --resource-group rg-CUSTOMER_NAME-dev --query primaryKey -o tsv)"
```

### Container Apps scaling issues

**Symptom:** High latency during traffic spikes, or pods stuck in `Pending` state.

**Solution:** Check the min/max replica settings. Dev defaults to 1-5, prod to 2-20. Increase `containerAppMaxReplicas` in the Bicep parameters if sustained throughput exceeds capacity. Monitor replica count and CPU/memory usage in Azure Monitor.

```bash
az containerapp show \
  --name CUSTOMER_NAME-bill-ca-dev \
  --resource-group rg-CUSTOMER_NAME-dev \
  --query "properties.template.scale"
```

### SSE streaming not working

**Symptom:** The browser or client receives the entire response at once instead of streaming tokens, or the connection drops mid-stream.

**Solution:**
1. Ensure no intermediary proxy is buffering the response. Azure Front Door and APIM should pass through `text/event-stream` without buffering.
2. In local development, confirm you are using `uvicorn` (not a WSGI server).
3. If using a reverse proxy (nginx), add `proxy_buffering off;` to the location block.
4. Check that the client sets `Accept: text/event-stream` and does not set a short timeout.

### CORS errors in development

**Symptom:** Browser console shows `Access-Control-Allow-Origin` errors.

**Solution:** Set `CORS_ALLOWED_ORIGINS` to include your frontend origin. For local development:

```bash
export CORS_ALLOWED_ORIGINS="http://localhost:8000,http://localhost:3000"
```

The default value is `*` (allow all), which is acceptable for development but should be restricted in production.

### Billing API timeout

**Symptom:** Personalised bill queries take excessively long or return a generic error.

**Solution:**
1. Verify `BILLING_API_BASE_URL`, `BILLING_API_CLIENT_ID`, and `BILLING_API_SCOPE` are correct.
2. Check that the managed identity (or service principal) has the required permissions on the billing API.
3. The billing API client uses a 30-second timeout by default. If the API is slow, the chatbot gracefully degrades and responds without bill data. Check application logs for `BillingAPIError` entries.

```bash
# View recent Container App logs
az containerapp logs show \
  --name CUSTOMER_NAME-bill-ca-dev \
  --resource-group rg-CUSTOMER_NAME-dev \
  --follow
```

---

## Project Documentation Links

| Document | Description |
|----------|-------------|
| [docs/solution-design.md](docs/solution-design.md) | Full solution design: requirements, architecture decisions, data flow, security |
| [docs/cost-estimation.md](docs/cost-estimation.md) | Monthly cost estimates for dev and prod environments |
| [docs/delivery-plan.md](docs/delivery-plan.md) | Sprint-based delivery plan with milestones and timelines |
| [docs/architecture-diagram.md](docs/architecture-diagram.md) | Detailed architecture description with component interactions |
| [docs/ai-brainstorming.md](docs/ai-brainstorming.md) | Initial AI approach exploration and technology choices |
