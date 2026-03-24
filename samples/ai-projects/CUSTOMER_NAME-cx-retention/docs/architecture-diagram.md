# CUSTOMER_NAME Intelligent Bill Explainer - Architecture Diagram

RAG-based Conversational AI on Microsoft Azure | Region: Sweden Central (EU)

---

## Solution Architecture

```text
+===================================================================+
|                          USER LAYER                               |
|                                                                   |
|                +---------------------------+                      |
|                |    Web Chat Widget         |                      |
|                |  (Static Web App / CDN)    |                      |
|                +-------------+-------------+                      |
|                              |                                    |
|                         HTTPS|                                    |
+=================================|=================================+
                                  |
                                  v
+===================================================================+
|                      EDGE / SECURITY                              |
|                                                                   |
|          +------------------------------------+                   |
|          |  Azure Front Door Premium          |                   |
|          |  WAF Policy + CDN + DDoS + Bot     |                   |
|          +----------------+-------------------+                   |
|                           |                                       |
+===========================|=======================================+
                            |
                       HTTPS|
                            v
+===================================================================+
|                       API GATEWAY                                 |
|                                                                   |
|          +------------------------------------+                   |
|          |  Azure API Management (Std v2)     |                   |
|          |  Rate Limit / Token Throttle / Log |                   |
|          +----------------+-------------------+                   |
|                           |                                       |
+===========================|=======================================+
                            |
                    REST API |
                            v
+===================================================================+
|                    APPLICATION TIER                                |
|                                                                   |
|          +------------------------------------+                   |
|          |  Azure Container Apps              |                   |
|          |  Python / FastAPI                  |                   |
|          |  RAG Orchestrator                  |                   |
|          +--+-------------+---------------+--+                   |
|             |             |               |                       |
+=============|=============|===============|=======================+
              |             |               |
      +-------+    +-------+-------+       +--------+
      |             |               |                |
      v             v               v                v
+===========+ +===========+ +============+ +=============+
| Azure     | | Azure AI  | | Azure      | | CUSTOMER_NAME   |
| OpenAI    | | Search    | | Cosmos DB  | | Billing API |
| Service   | | (S1)      | | (Svrless)  | | (External)  |
|           | |           | |            | |             |
| EU Data   | | Hybrid    | | Session    | | Customer    |
| Zone      | | Vector +  | | State +    | | Bill Data   |
|           | | Keyword   | | History    | | Lookup      |
| GPT-4o-   | | Semantic  | | 30-day TTL | |             |
| mini / 4o | | Ranker    | |            | |             |
+===========+ +-----+-----+ +============+ +=============+
                    |
                    | Indexer (every 6h)
                    |
              +-----+------+
              | Azure Blob |
              | Storage    |
              | (LRS Hot)  |
              |            |
              | Tariff     |
              | Docs, FAQs |
              | Bill Guides|
              +------------+

+===================================================================+
|                    CROSS-CUTTING SERVICES                         |
|                                                                   |
|  +---------------+ +----------------------+ +----------------+   |
|  | Azure         | | Azure Monitor +      | | Microsoft      |   |
|  | Key Vault     | | App Insights         | | Entra ID       |   |
|  | (Standard)    | |                      | |                |   |
|  |               | | Token usage,         | | Managed        |   |
|  | API keys,     | | latency, content     | | Identity for   |   |
|  | certs,        | | filter events,       | | service-to-    |   |
|  | conn strings  | | dashboards, alerts   | | service auth   |   |
|  +---------------+ +----------------------+ +----------------+   |
|                                                                   |
+===================================================================+
```

### Reading the Diagram

- **Top-to-bottom flow** represents the primary request path from
  user to backend services and back.
- **Vertical lines** (`|`) represent synchronous HTTPS/REST calls.
- **Branching lines** from the Application Tier show the orchestrator
  calling multiple backend services in parallel or sequence depending
  on query type.
- **Cross-cutting services** at the bottom apply to every layer above
  them (secrets management, observability, identity).

---

## Component Legend

| Component | Azure Service | SKU / Tier | Purpose |
|---|---|---|---|
| Chat Widget | Static Web App / CDN | Free | Chat interface for customers |
| Edge Security | Azure Front Door | Premium | WAF, CDN, DDoS, bot filter |
| API Gateway | API Management | Standard v2 | Rate limit, throttle, logging |
| Orchestrator | Container Apps | Consumption | FastAPI RAG orchestration |
| LLM | Azure OpenAI | Data Zone EU | GPT-4o-mini / GPT-4o |
| Search | AI Search | S1 (2 replicas) | Hybrid vector+keyword, ranker |
| Session Store | Cosmos DB | Serverless | History (30d TTL), sessions |
| Doc Store | Blob Storage | LRS Hot | Tariffs, FAQs, bill guides |
| External API | CUSTOMER_NAME Billing | N/A | Bill data by reference/ID |
| Secrets | Key Vault | Standard | API creds, certs, conn strings |
| Observability | Monitor + App Insights | Pay-as-you-go | Tokens, latency, alerts |
| Identity | Entra ID | Included | Managed Identity auth |

---

## Data Flow Summary

### Flow 1 - General FAQ Query

A customer asks a general question such as "How is my gas tariff
calculated?"

```text
User
 --> Front Door (WAF inspection)
 --> APIM (rate limit check, request logged)
 --> Container Apps (query classification: FAQ)
 --> AI Search (hybrid vector + keyword over tariff docs)
 --> Azure OpenAI GPT-4o-mini (grounded answer generation)
 --> Container Apps (format response, save to Cosmos DB)
 --> APIM --> Front Door --> User
```

**Latency target:** under 4 seconds end-to-end (P95).

### Flow 2 - Personalized Bill Lookup

A customer provides a bill reference and asks "Why is my bill higher
this month?"

```text
User
 --> Front Door --> APIM
 --> Container Apps (query classification: bill-specific)
 --> CUSTOMER_NAME Billing API (fetch bill line items)
 --> AI Search (retrieve relevant tariff/FAQ context)
 --> Azure OpenAI GPT-4o (complex reasoning over data)
 --> Container Apps (compose explanation, save to Cosmos DB)
 --> APIM --> Front Door --> User
```

**Latency target:** under 8 seconds end-to-end (P95), accounting
for the external API call.

### Flow 3 - Knowledge Ingestion Pipeline

Background process that keeps the search index current with the
latest documents.

```text
Blob Storage (new/updated tariff docs, FAQs, bill guides)
 --> AI Search Indexer (scheduled every 6 hours)
 --> Document cracking + chunking (512 tokens, 128 overlap)
 --> Azure OpenAI text-embedding-3-small (vectorization)
 --> AI Search Index (updated vectors + metadata)
```

**Trigger:** Automatic on schedule. Manual re-index available via
admin endpoint.

### Flow 4 - Conversation Lifecycle

Session management for multi-turn conversations.

```text
Container Apps <--> Cosmos DB (Serverless, NoSQL API)
 - On first message: create session doc (ID, timestamp)
 - On each turn: append user + assistant messages
 - On read: retrieve last N turns for context window
 - TTL policy: auto-expire documents after 30 days
 - Partition key: /sessionId for efficient reads
```

**Storage estimate:** approximately 2 KB per turn, 10 turns average
per session.

---

## Network and Security Boundaries

```text
+--[ Public Internet ]------------------------------------------+
|                                                                |
|   Users (CUSTOMER_NAME customers via web browser)                  |
|                                                                |
+--------------------------+-------------------------------------+
                           |
                      HTTPS only
                           |
+--------------------------v-------------------------------------+
|  Azure Front Door Premium (Global Edge)                        |
|  - WAF managed ruleset (OWASP 3.2)                            |
|  - Custom rules: geo-filter (EU only), rate limit              |
|  - Bot protection enabled                                      |
+---------------------------+------------------------------------+
                            |
                     Private Link
                            |
+---------------------------v------------------------------------+
|  Virtual Network (10.0.0.0/16) - Sweden Central                |
|                                                                 |
|  +--[Subnet: apim (10.0.1.0/24)]--------------------------+   |
|  |  API Management (Standard v2, VNet-integrated)          |   |
|  +------------------------------+--------------------------+   |
|                                 |                               |
|  +--[Subnet: apps (10.0.2.0/24)]|-------------------------+   |
|  |  Container Apps Environment  v                          |   |
|  |  (internal ingress only)                                |   |
|  +--+---------------+-----------------+--------------------+   |
|     |               |                 |                         |
|  +--v----------+ +--v------------+ +--v-----------------+      |
|  | Private     | | Private       | | Private            |      |
|  | Endpoint:   | | Endpoint:     | | Endpoint:          |      |
|  | OpenAI      | | AI Search     | | Cosmos DB          |      |
|  +-------------+ +---------------+ +--------------------+      |
|                                                                 |
|  +--[Subnet: data (10.0.3.0/24)]--------------------------+   |
|  |  Private Endpoint: Blob Storage                         |   |
|  |  Private Endpoint: Key Vault                            |   |
|  +---------------------------------------------------------+   |
|                                                                 |
+-----------------------------------------------------------------+
```

All service-to-service communication uses Managed Identity via
Microsoft Entra ID. No secrets are stored in application code or
environment variables. Key Vault holds only external API credentials
and certificates required for the CUSTOMER_NAME Billing API integration.
