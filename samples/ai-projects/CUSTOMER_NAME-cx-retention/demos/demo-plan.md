# CUSTOMER_NAME Intelligent Bill Explainer - Demo Plan

| Field | Value |
|---|---|
| **Customer** | CUSTOMER_NAME |
| **Project** | Intelligent Bill Explainer - AI Chatbot |
| **Demo Level** | L300 |
| **Target Audience** | Technical Decision Makers (CTOs, IT Directors) |
| **Total Duration** | ~60 minutes (4 x 15 min) |
| **Access Strategy** | Strategy C - Hybrid |
| **Demo Environment** | Azure (Sweden Central) |

---

## Demo Overview

| # | Title | Duration | WOW Moment |
|---|---|---|---|
| 1 | Live Chat - General FAQ | 15 min | AI explains Italian energy tariff components in real-time with streaming, grounded in CUSTOMER_NAME docs |
| 2 | Live Chat - Personalised Bill Lookup | 15 min | Customer provides bill reference; AI fetches billing data and narrates each line item in plain Italian |
| 3 | RAG Pipeline and Architecture Walkthrough | 15 min | Trace a query live through AI Search hybrid index, show document chunks, model routing decision, Cosmos DB session |
| 4 | Observability, Cost Controls, and Security Posture | 15 min | Live Application Insights dashboard showing token consumption, model routing split, WAF in action, private endpoint topology |

---

## Per-Demo Details

### Demo 1 - Live Chat: General FAQ (15 min)
- **Goal**: Show the end-user chat experience for a general billing question; highlight streaming and RAG grounding.
- **Key Azure services shown**: Azure Front Door, Azure API Management, Azure Container Apps, Azure OpenAI (GPT-4o-mini), Azure AI Search.
- **WOW moment**: The AI streams an accurate explanation of "Sistema di Protezione dei Consumatori Vulnerabili" charges directly from CUSTOMER_NAME's tariff documentation, with source citations.
- **Entry point**: Chat widget via Front Door public hostname (browser on presenter laptop).
- **Companion file**: `demo-1-faq-chat.sh` (curl script to drive the API directly as an alternative path).
- **Sample questions**:
  - "Cosa sono gli oneri di sistema sulla mia bolletta?"
  - "Come si calcola la quota potenza?"
  - "Cosa significa il codice POD sulla bolletta?"

### Demo 2 - Live Chat: Personalised Bill Lookup (15 min)
- **Goal**: Show the personalised bill mode; customer provides a bill reference, AI retrieves and explains specific charges.
- **Key Azure services shown**: Azure Container Apps (model router + billing API integration), Azure OpenAI (GPT-4o for complex reasoning), Azure Cosmos DB (session persistence).
- **WOW moment**: Presenter enters bill reference "IT001-2024-DEMO"; AI fetches seeded bill data (EUR 187.43, high consumption month) and explains each line item, why consumption is higher, and offers a payment plan option.
- **Entry point**: Chat widget via Front Door (same browser session continues from Demo 1).
- **Companion file**: `demo-2-bill-lookup.sh` (drive API with bill reference, show SSE stream).
- **Sample flow**:
  - User: "Ho la mia bolletta di gennaio, il numero e IT001-2024-DEMO"
  - AI: retrieves bill data, explains F1/F2/F3 time bands, consumption spike, regulatory charges.

### Demo 3 - RAG Pipeline and Architecture Walkthrough (15 min)
- **Goal**: Walk through the technical stack from the inside; show AI Search index, document chunks, model routing logic, Cosmos DB data.
- **Key Azure services shown**: Azure AI Search (index explorer), Azure Cosmos DB (data explorer), Azure Container Apps (log stream), Azure OpenAI (model deployments).
- **WOW moment**: Open AI Search "Search Explorer" and run the same hybrid query the chatbot just ran - show BM25 + vector scores and semantic reranking in action. Then open Cosmos DB Data Explorer and show the conversation just persisted.
- **Entry point**: Jump box VM (via Azure Bastion) - all backend services accessible via private DNS.
- **Companion file**: `demo-3-rag-walkthrough.sh` (query AI Search REST API directly, dump Cosmos DB session).
- **Steps**:
  - Show AI Search index fields (content, contentVector, sourceName, chunkId).
  - Run a hybrid query with `$select` and `@search.score`.
  - Open Cosmos DB and browse the `sessions` and `messages` containers.
  - Show Container Apps log stream for the last request.

### Demo 4 - Observability, Cost Controls, and Security Posture (15 min)
- **Goal**: Show the operational and security story; demonstrate that CUSTOMER_NAME has full visibility and cost control over AI consumption.
- **Key Azure services shown**: Application Insights (Live Metrics, custom dashboards), Azure Monitor (alert rules), Azure API Management (rate limiting policy), Azure Front Door (WAF metrics), Private Endpoints (network topology).
- **WOW moment**: Live Metrics stream shows real-time token consumption as presenter fires API calls. Then trigger APIM rate limit (11 requests in 60 seconds from same IP) and show the 429 response with `Retry-After` header.
- **Entry point**: Azure portal (presenter laptop browser) + jump box for APIM developer portal.
- **Companion file**: `demo-4-rate-limit-and-observability.sh` (loop curl to trigger rate limit, show App Insights query).
- **Steps**:
  - Open Application Insights Live Metrics - show real-time request rate, P95 latency, dependency calls.
  - Run a Kusto query for token consumption by model over last hour.
  - Run companion script to trigger rate limiting; show 429 in terminal.
  - Show Front Door WAF metrics (blocked requests, bot protection).
  - Show network topology: private endpoints for OpenAI, Search, Cosmos, Storage, Key Vault.

---

## Demo Infrastructure Requirements

### Additional Azure Resources (Demo Overlay - additive, never modifies core infra)

| Resource | SKU | Purpose |
|---|---|---|
| Azure Bastion | Standard | Secure browser-based RDP/SSH to jump box, no public VM IP needed |
| Jump Box VM | Standard_B2s (Windows Server 2022) | Browser + curl + Azure CLI on the private network; accesses all private endpoints |
| AzureBastionSubnet | 10.0.4.0/26 | Required subnet name and minimum /26 for Bastion |
| Jump Box Subnet | 10.0.5.0/28 | Isolated subnet for the jump box VM |
| Public IP (Bastion) | Standard Static | Required for Bastion host |
| NSG (Jump Box Subnet) | - | Allow Bastion inbound only; deny all else |

### Demo Parameter Overrides (lower cost for demo environment)

| Parameter | Dev Value | Demo Value | Reason |
|---|---|---|---|
| containerAppMinReplicas | 1 | 1 | No change needed |
| containerAppMaxReplicas | 5 | 3 | Reduce max for demo cost |
| aiSearchReplicaCount | 1 | 1 | No change needed |
| openAiGpt4oCapacity | 30 | 20 | Sufficient for live demo |
| openAiGpt4oMiniCapacity | 100 | 50 | Sufficient for live demo |
| openAiEmbeddingCapacity | 100 | 50 | Sufficient for live demo |

---

## Demo Data Requirements

### AI Search Knowledge Base (seed into Blob Storage, then trigger indexer)

| Document | Type | Purpose |
|---|---|---|
| `tariff-guide-2024.md` | Tariff documentation | Explains Italian energy tariff components (F1/F2/F3, potenza, energia, oneri) |
| `bill-structure-guide.md` | Bill anatomy guide | Explains each section of an Italian CUSTOMER_NAME bill |
| `faq-billing-2024.md` | FAQ | 30 common billing questions and answers in Italian |
| `regulatory-charges-2024.md` | Regulatory reference | Explains ARERA regulatory charges: oneri di sistema, accise, IVA |
| `payment-options.md` | Service documentation | Direct debit, online payment, installment plans |

### Cosmos DB Seed Data

| Container | Item | Purpose |
|---|---|---|
| sessions | demo-session-001 | Pre-seeded session for Demo 2 quick start |
| billing-stub | IT001-2024-DEMO | Synthetic bill (EUR 187.43, January 2024, residential) for personalised lookup |

### Billing API Stub

The CUSTOMER_NAME Billing API is an external dependency not deployed in Azure. The seed script configures a local HTTP stub on the jump box that returns the IT001-2024-DEMO bill data on request, allowing Demo 2 to run without a real API connection.

---

## Environment Setup Checklist

- [ ] Deploy core infrastructure (`scripts/deploy.sh` with `dev.bicepparam`)
- [ ] Deploy demo overlay (`demos/demo-access.bicep` with `demos/demo.bicepparam`)
- [ ] Run `demos/seed-demo-data.sh` to upload knowledge base docs and trigger AI Search indexer
- [ ] Verify AI Search indexer completed (check index document count >= 5 chunks)
- [ ] Verify chat widget loads at Front Door hostname
- [ ] Connect to jump box via Azure Bastion; verify private DNS resolution for all services
- [ ] Start billing API stub on jump box
- [ ] Test Demo 1 query end-to-end from presenter laptop browser
- [ ] Test Demo 2 bill lookup end-to-end
- [ ] Verify Application Insights Live Metrics stream is active
- [ ] Pre-open Azure portal tabs: App Insights, Cosmos DB Data Explorer, AI Search Explorer, Front Door WAF
