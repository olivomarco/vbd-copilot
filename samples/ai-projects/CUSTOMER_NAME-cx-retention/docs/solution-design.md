# CUSTOMER_NAME Intelligent Bill Explainer - Solution Design

| Field | Value |
|---|---|
| **Customer** | CUSTOMER_NAME |
| **Project** | Intelligent Bill Explainer - AI Chatbot |
| **Version** | 1.0 |
| **Status** | Draft |
| **Classification** | Confidential |

---

## 1. Executive Summary

CUSTOMER_NAME serves approximately 10 million retail energy customers across six EU countries. A significant share of inbound call center volume - estimated at 35-40% - relates to billing inquiries: customers struggling to understand line items, tariff changes, consumption patterns, and regulatory charges on their energy bills. These calls are repetitive, high-volume, and costly to handle through human agents. CUSTOMER_NAME has identified an opportunity to deploy an AI-powered conversational chatbot that explains energy bills in plain, accessible Italian, reducing call center load while improving customer satisfaction.

The proposed solution is a web-based chatbot widget that uses Microsoft Azure OpenAI Service and a Retrieval Augmented Generation (RAG) architecture to answer billing questions in two modes. In the first mode, customers ask general questions about tariffs, bill structure, regulatory charges, and payment options, and receive answers grounded in CUSTOMER_NAME's published documentation. In the second mode, customers provide a bill reference number or customer code, and the chatbot retrieves their actual billing data through CUSTOMER_NAME's backend APIs, then explains specific charges, consumption figures, and cost breakdowns in conversational language. No customer login is required - the bill reference acts as a lightweight identifier, keeping friction low.

The expected business impact is a 20-30% reduction in billing-related call center inquiries within the first six months of full deployment, translating to estimated annual savings of EUR 3-5 million in contact center operational costs. Beyond cost savings, the solution provides 24/7 availability, consistent answer quality, and a modern self-service experience that aligns with CUSTOMER_NAME's digital transformation strategy. The chatbot also generates structured feedback data (thumbs up/down, conversation completion rates) that CUSTOMER_NAME can use to continuously improve billing communications and identify systemic pain points.

The delivery timeline is 6-8 weeks from kickoff to production launch, divided into three phases: foundation and RAG pipeline (weeks 1-3), personalized bill integration and conversational UX (weeks 4-5), and hardening, testing, and go-live (weeks 6-8). The architecture is designed for multilingual expansion - while version 1 supports Italian only, the system can be extended to serve CUSTOMER_NAME's other markets (Spain, France, Greece, Portugal, Slovenia) through additional knowledge base indexes and locale-parameterized prompts with no architectural changes.

---

## 2. Architecture Overview

> **Visual diagram:** See [architecture-diagram.drawio](architecture-diagram.drawio) for the full visual architecture diagram, or [architecture-diagram.md](architecture-diagram.md) for an ASCII text version.

The solution follows a Retrieval Augmented Generation (RAG) pattern, organized into six architectural layers. Each layer uses Azure-native services, deployed exclusively in EU regions to meet GDPR data residency requirements.

### 2.1 Layer Breakdown

| Layer | Purpose | Primary Azure Services |
|---|---|---|
| **User Layer** | Serve the chatbot widget with global edge performance and web application firewall protection | Azure Front Door (Premium) |
| **API Gateway** | Rate limiting, token-based throttling, session management, API versioning | Azure API Management (Standard v2) |
| **Application Layer** | Orchestrate RAG pipeline: conversation management, retrieval, prompt composition, LLM invocation, response streaming | Azure Container Apps (Consumption) |
| **AI Layer** | Large language model inference and text embedding | Azure OpenAI Service (Data Zone EU) |
| **Knowledge Layer** | Hybrid search over CUSTOMER_NAME's billing documentation, tariff guides, FAQs, and terms and conditions | Azure AI Search (S1), Azure Blob Storage |
| **Data Layer** | Conversation history, session state, user feedback | Azure Cosmos DB (Serverless) |
| **Observability** | End-to-end monitoring, token usage tracking, alerting | Azure Monitor, Application Insights |

### 2.2 Component Description

**User Layer - Azure Front Door (Premium with WAF)**
Azure Front Door serves as the entry point for all customer traffic. It provides a Web Application Firewall (WAF) with OWASP 3.2 Core Rule Set for protection against injection attacks, bot detection and mitigation, and geo-filtering to restrict traffic to EU origins. Front Door also acts as a CDN for the static chatbot widget assets (HTML, CSS, JavaScript), ensuring sub-100ms load times across CUSTOMER_NAME's EU markets. TLS termination occurs at the edge with managed certificates.

**API Gateway - Azure API Management (Standard v2)**
APIM sits between Front Door and the application backend. It enforces rate limiting per client IP (to prevent abuse from anonymous access), manages API versioning for future iterations, applies request/response transformation policies, and provides a developer portal for CUSTOMER_NAME's internal teams. Token-based throttling policies cap per-session usage to prevent runaway LLM costs from individual sessions.

**Application Layer - Azure Container Apps (Consumption Plan)**
The core orchestrator runs as a Python/FastAPI application on Azure Container Apps. For each incoming user question, the orchestrator: (1) loads or creates a conversation session from Cosmos DB, (2) retrieves the last N messages as conversation history, (3) classifies the query as general FAQ or personalized bill inquiry, (4) for personalized queries, calls CUSTOMER_NAME's billing API to retrieve bill data, (5) executes a hybrid search query against Azure AI Search to retrieve relevant documentation context, (6) composes a prompt combining the system instructions, RAG context, billing data (if applicable), conversation history, and the user question, (7) calls Azure OpenAI with the composed prompt, and (8) streams the response back to the user via Server-Sent Events (SSE). Container Apps auto-scales from 2 to 20 replicas based on concurrent HTTP request count.

**AI Layer - Azure OpenAI Service (Data Zone EU)**
Two model deployments handle different query complexities. GPT-4o-mini handles approximately 80% of queries - straightforward billing FAQ questions where a concise, grounded answer suffices. GPT-4o handles the remaining 20% - complex multi-part questions, personalized bill explanations requiring numerical reasoning over actual billing data, and cases where GPT-4o-mini produces low-confidence or incomplete answers. The orchestrator uses a lightweight classifier (based on query length, presence of bill reference, and conversation turn count) to route to the appropriate model. Text-embedding-3-small generates 1536-dimensional vectors for document indexing and query embedding during the search phase.

**Knowledge Layer - Azure AI Search (S1, 2 Replicas)**
AI Search maintains a hybrid index combining BM25 keyword search, vector search (using embeddings from text-embedding-3-small), and semantic ranker for re-ranking results. The index contains chunked and embedded versions of CUSTOMER_NAME's tariff documentation, billing FAQs, terms and conditions, bill structure guides, and regulatory charge explanations. Source documents are stored in Azure Blob Storage (Hot tier, LRS) and ingested via AI Search's built-in indexer on a 6-hour schedule. Two replicas provide both high availability and the throughput needed for peak query volumes.

**Data Layer - Azure Cosmos DB (Serverless)**
Cosmos DB stores three types of data: (1) conversation history (messages, timestamps, model used, token counts) with a 30-day TTL for automatic cleanup, (2) session state (current session context, bill reference if provided, session metadata) with a 24-hour TTL, and (3) user feedback (thumbs up/down ratings, optional free-text comments linked to specific assistant messages). The serverless tier is cost-optimal for the bursty, variable traffic pattern of a chatbot workload - CUSTOMER_NAME pays only for consumed RU/s rather than provisioned capacity.

**Observability - Azure Monitor and Application Insights**
Application Insights is integrated into the FastAPI orchestrator via the OpenTelemetry SDK, capturing request traces, dependency calls (to OpenAI, AI Search, Cosmos DB, CUSTOMER_NAME billing API), and custom metrics. Key metrics tracked include: tokens consumed per query (prompt + completion), P95 response latency, AI Search query latency, content filter trigger events, conversation completion rate (sessions with feedback vs. abandoned), model routing distribution (GPT-4o-mini vs. GPT-4o), and error rates by dependency. Azure Monitor alert rules notify the operations team of latency spikes, error rate increases, or token consumption anomalies.

---

## 3. Azure Service Choices and Justification

| Service | SKU / Tier | Region | Justification |
|---|---|---|---|
| **Azure OpenAI Service** | Data Zone EU deployment; GPT-4o (2024-11-20), GPT-4o-mini (2024-07-18), text-embedding-3-small | Sweden Central (Data Zone EU) | Data Zone EU ensures all inference data stays within EU boundaries. GPT-4o-mini provides cost-effective handling of simple queries (80% of volume) at roughly 1/30th the cost of GPT-4o. GPT-4o handles complex bill explanations requiring numerical reasoning. Data Zone deployment chosen over regional deployment for broader EU capacity and higher rate limits. |
| **Azure AI Search** | Standard S1, 2 replicas, 1 partition | Sweden Central | S1 supports semantic ranker (required for hybrid search quality), up to 25 indexes (sufficient for single-language v1 with room for multilingual expansion), and 15M documents per partition. Two replicas provide 99.99% read SLA and handle 200+ QPS peak load. Chosen over Basic tier which lacks semantic ranker; S2 unnecessary given document volume. |
| **Azure Container Apps** | Consumption plan, workload profile: Consumption | Sweden Central | Consumption plan provides serverless scaling (0-20 replicas) with per-second billing, ideal for variable chatbot traffic patterns. Built-in support for KEDA-based autoscaling on HTTP concurrent requests. Chosen over Azure App Service (less granular scaling), AKS (operational overhead disproportionate to workload complexity), and Azure Functions (poor fit for long-running SSE streaming connections). |
| **Azure Cosmos DB** | Serverless, NoSQL API | Sweden Central | Serverless pricing aligns with bursty chatbot traffic - no cost during off-peak hours. NoSQL API provides flexible schema for varying document types (sessions, messages, feedback). Automatic TTL eliminates need for cleanup jobs. Chosen over provisioned throughput (cost-inefficient for variable load) and Azure SQL (schema rigidity unnecessary for session/conversation data). |
| **Azure API Management** | Standard v2 | Sweden Central | Standard v2 provides VNet integration, custom domains, built-in rate limiting, and developer portal at a competitive price point. v2 platform offers faster deployment and better performance than classic tiers. Chosen over Basic v2 (lacks VNet integration) and Premium (unnecessary scale; multi-region not required for v1). |
| **Azure Front Door** | Premium | Global (edge POPs) | Premium tier includes WAF with Microsoft-managed rule sets (OWASP 3.2 CRS), bot protection, and geo-filtering. Provides global anycast for low-latency widget delivery across EU. Chosen over Standard tier (lacks bot protection rules) and Application Gateway (single-region only, no CDN capability). |
| **Azure Blob Storage** | General Purpose v2, LRS, Hot tier | Sweden Central | Stores source documents (tariff PDFs, FAQ markdown, T&Cs) for AI Search indexer ingestion. Hot tier appropriate since indexer reads documents every 6 hours. LRS sufficient - documents are authored by CUSTOMER_NAME and can be re-uploaded if storage fails. Soft delete enabled for accidental deletion protection. |
| **Azure Monitor + Application Insights** | Pay-as-you-go (workspace-based) | Sweden Central | Workspace-based Application Insights provides full distributed tracing, custom metrics, and log analytics. OpenTelemetry SDK integration with Python/FastAPI. Chosen as the native Azure observability stack with no viable alternative in the Azure ecosystem. 90-day default retention, extended to 180 days for operational analytics. |
| **Azure Key Vault** | Standard | Sweden Central | Stores external secrets: CUSTOMER_NAME billing API credentials, any configuration values that must not be in application configuration. Standard tier sufficient (no HSM-backed keys required). All access via Managed Identity - no Key Vault access keys distributed. |
| **Microsoft Entra ID** | Managed Identity (system-assigned) | N/A (global service) | System-assigned Managed Identities on Container Apps eliminate all service-to-service API keys. Container Apps authenticates to Azure OpenAI, AI Search, Cosmos DB, Blob Storage, and Key Vault using Entra ID tokens. Chosen as the Azure-native zero-trust authentication model; no alternative considered. |

---

## 4. Data Flows and Integrations

### 4.1 Flow 1: General FAQ Query

This flow handles general billing questions that do not require customer-specific data. It represents approximately 80% of expected query volume.

**Trigger:** User types a general billing question (e.g., "What is the system charges component on my bill?" or "How do I read my meter?")

| Step | Component | Action | Details |
|---|---|---|---|
| 1 | Chatbot Widget | User submits question | HTTPS POST to `/api/v1/chat` with `session_id` (or null for new session) and `message` body |
| 2 | Azure Front Door | Edge processing | WAF rule evaluation, TLS termination, route to APIM backend |
| 3 | Azure API Management | Gateway policies | Rate limit check (100 requests/session/hour, 10 requests/IP/minute), request validation, add correlation ID header, forward to Container Apps backend |
| 4 | Container Apps (Orchestrator) | Session management | Load or create session in Cosmos DB. Retrieve last 10 messages as conversation history |
| 5 | Container Apps (Orchestrator) | Query classification | Lightweight classifier determines this is a general FAQ query (no bill reference detected). Route to GPT-4o-mini path |
| 6 | Container Apps (Orchestrator) | Hybrid search | Generate query embedding via text-embedding-3-small. Execute hybrid query against AI Search: vector similarity + BM25 keyword match + semantic re-ranking. Retrieve top 5 document chunks |
| 7 | Container Apps (Orchestrator) | Prompt composition | Assemble prompt: system message (Italian language, energy billing scope, CUSTOMER_NAME tone of voice, responsible AI guardrails) + retrieved document chunks as context + conversation history + user question |
| 8 | Azure OpenAI (GPT-4o-mini) | Inference | Generate response with `temperature=0.3`, `max_tokens=800`, streaming enabled. Content filters active (Medium threshold, all categories) |
| 9 | Container Apps (Orchestrator) | Response streaming | Stream response tokens to client via SSE. On completion, persist assistant message to Cosmos DB with token usage metadata |
| 10 | Chatbot Widget | Display | Render streamed response with markdown formatting. Show "AI-generated" disclaimer. Display feedback buttons (thumbs up/down) |

**Latency budget:**

| Segment | Target |
|---|---|
| Front Door + APIM | < 50 ms |
| Session load (Cosmos DB) | < 30 ms |
| Embedding generation | < 100 ms |
| AI Search hybrid query | < 200 ms |
| Azure OpenAI first token | < 1,000 ms |
| Total first token (P95) | < 1,500 ms |
| Total complete response (P95) | < 5,000 ms |

### 4.2 Flow 2: Personalized Bill Lookup

This flow handles requests tied to a specific bill, requiring retrieval of actual billing data from CUSTOMER_NAME's backend systems.

**Trigger:** User provides a bill reference number (e.g., "Explain bill number FT-2025-0012345") or customer code for lookup.

| Step | Component | Action | Details |
|---|---|---|---|
| 1 | Chatbot Widget | User submits bill reference | HTTPS POST to `/api/v1/chat` with `session_id`, `message` containing bill reference, optionally `bill_ref` field if structured input provided |
| 2 | Azure Front Door + APIM | Gateway processing | Same as Flow 1 (WAF, rate limiting, routing) |
| 3 | Container Apps (Orchestrator) | Reference extraction and validation | Extract bill reference from message using regex pattern matching. Validate format against known CUSTOMER_NAME reference patterns (alphanumeric, expected length). Reject malformed references with user-friendly error |
| 4 | Container Apps (Orchestrator) | Billing API call | Call CUSTOMER_NAME's internal billing API (REST, authenticated via client credentials stored in Key Vault) with bill reference. API returns structured bill summary: total amount, billing period, consumption (kWh/Smc), tariff code, line item breakdown, payment status, due date |
| 5 | Container Apps (Orchestrator) | Error handling | If bill not found: respond with "Bill reference not found" message and suggest verifying the number. If API timeout: respond with fallback message and suggest trying again. If API returns partial data: proceed with available fields |
| 6 | Container Apps (Orchestrator) | Context enrichment | Query AI Search with tariff code and bill charge categories to retrieve relevant tariff documentation, regulatory explanations, and FAQ content. Top 5 chunks retrieved |
| 7 | Container Apps (Orchestrator) | Prompt composition | Assemble prompt: system message (include numerical accuracy instructions, unit formatting rules) + structured bill data as JSON context + retrieved documentation chunks + conversation history + user question. Route to GPT-4o for numerical reasoning |
| 8 | Azure OpenAI (GPT-4o) | Inference | Generate response with `temperature=0.2` (lower temperature for numerical accuracy), `max_tokens=1200`, streaming enabled. Content filters active. Prompt Shields active to prevent bill reference injection attacks |
| 9 | Container Apps (Orchestrator) | Response post-processing | Stream response to client. Persist message with bill reference association. Apply Groundedness Detection to flag any claims not supported by the bill data or retrieved documents |
| 10 | Chatbot Widget | Display | Render explanation with structured formatting (tables for line items where appropriate). Show "AI-generated" disclaimer. Show feedback buttons and option to "Talk to an agent" for disputes |

**CUSTOMER_NAME Billing API Integration:**

| Parameter | Value |
|---|---|
| Protocol | REST over HTTPS (TLS 1.2+) |
| Authentication | OAuth 2.0 client credentials flow |
| Credentials storage | Azure Key Vault (secret: `CUSTOMER_NAME-billing-api-client-secret`) |
| Timeout | 5 seconds (hard timeout) |
| Retry policy | 1 retry with 500ms backoff |
| Circuit breaker | Open after 5 consecutive failures, half-open after 30 seconds |
| Response format | JSON |
| Data returned | Bill summary (no raw PDF, no payment instrument details, no full customer PII) |

### 4.3 Flow 3: Knowledge Base Ingestion

This flow populates and maintains the AI Search index with CUSTOMER_NAME's billing documentation.

| Step | Component | Action | Details |
|---|---|---|---|
| 1 | CUSTOMER_NAME content team | Upload documents | Upload tariff PDFs, FAQ markdown files, T&C documents, bill structure guides to designated Blob Storage container (`knowledge-base/`) via Azure Storage Explorer or automated pipeline |
| 2 | Azure Blob Storage | Store documents | Documents stored in Hot tier container with versioning enabled. Folder structure: `knowledge-base/{category}/{document-name}` where category is one of: `tariffs`, `faqs`, `terms`, `bill-guides`, `regulatory` |
| 3 | Azure AI Search (Indexer) | Scheduled indexing | Built-in indexer runs every 6 hours (configurable). Detects new/modified/deleted blobs via change tracking. Processes documents through skillset pipeline |
| 4 | Azure AI Search (Skillset) | Document processing | Skillset pipeline: (a) Document cracking - extract text from PDF, markdown, DOCX. (b) Text splitting - chunk documents into 512-token segments with 128-token overlap. (c) Embedding - call text-embedding-3-small to generate 1536-dim vector for each chunk. (d) Language detection - confirm Italian language tag |
| 5 | Azure AI Search (Index) | Index population | Each chunk stored as index document with fields: `chunk_id`, `content` (text), `content_vector` (1536-dim float array), `source_document` (blob path), `category`, `language`, `last_updated`, `title` |
| 6 | Validation | Index health check | Application Insights custom metric tracks document count, indexer success/failure, and last successful run timestamp. Alert on indexer failure or document count drop > 10% |

**Index Schema:**

| Field | Type | Searchable | Filterable | Retrievable | Notes |
|---|---|---|---|---|---|
| `chunk_id` | `Edm.String` | No | Yes | Yes | Primary key, format: `{blob_name}_{chunk_number}` |
| `content` | `Edm.String` | Yes (analyzer: `it.lucene`) | No | Yes | Chunk text, Italian Lucene analyzer for keyword search |
| `content_vector` | `Collection(Edm.Single)` | Yes (HNSW) | No | No | 1536-dimensional embedding vector |
| `source_document` | `Edm.String` | No | Yes | Yes | Blob storage path |
| `category` | `Edm.String` | No | Yes | Yes | Document category for filtering |
| `language` | `Edm.String` | No | Yes | Yes | Language code (v1: `it`) |
| `title` | `Edm.String` | Yes | No | Yes | Document title for citation |
| `last_updated` | `Edm.DateTimeOffset` | No | Yes | Yes | Blob last modified timestamp |

### 4.4 Flow 4: Conversation Lifecycle

This flow describes how conversation state is managed across the user's interaction.

| Step | Event | Action | Data |
|---|---|---|---|
| 1 | First message from user | Create session document in Cosmos DB | `{ session_id, created_at, last_active, language: "it", bill_ref: null, message_count: 0, ttl: 86400 }` |
| 2 | Each user message | Append user message to conversation container | `{ message_id, session_id, role: "user", content, timestamp, ttl: 2592000 }` (30-day TTL) |
| 3 | Each assistant response | Append assistant message with metadata | `{ message_id, session_id, role: "assistant", content, timestamp, model_used, prompt_tokens, completion_tokens, search_results_count, bill_ref_used, ttl: 2592000 }` |
| 4 | Bill reference provided | Update session document | Set `bill_ref` field on session document. Subsequent queries in same session can reuse billing context without re-fetch |
| 5 | User feedback | Create feedback document | `{ feedback_id, session_id, message_id, rating: "up"/"down", comment: null, timestamp, ttl: 2592000 }` |
| 6 | Session inactivity (24h) | Cosmos DB TTL auto-delete | Session document removed. Conversation messages retained for 30 days for analytics |
| 7 | Message expiry (30 days) | Cosmos DB TTL auto-delete | All conversation messages and feedback older than 30 days automatically purged. No manual cleanup required. GDPR-compliant data minimization |
| 8 | Right-to-erasure request | GDPR deletion API | DELETE `/api/v1/sessions/{session_id}` - removes all messages, feedback, and session data for specified session. CUSTOMER_NAME support team can invoke via internal tooling |

**Cosmos DB Container Design:**

| Container | Partition Key | TTL | Purpose |
|---|---|---|---|
| `sessions` | `/session_id` | 86,400 seconds (24 hours) | Active session state, bill reference cache |
| `messages` | `/session_id` | 2,592,000 seconds (30 days) | Conversation history for context window and analytics |
| `feedback` | `/session_id` | 2,592,000 seconds (30 days) | User ratings and comments for quality monitoring |

---

## 5. Security and Governance

### 5.1 Network Security

The solution implements defense-in-depth networking with no public-internet-exposed backend services.

| Layer | Control | Configuration |
|---|---|---|
| **Edge** | Azure Front Door WAF | OWASP 3.2 Core Rule Set (prevention mode), bot protection rule set (Microsoft-managed), geo-filter allowing only EU country codes (AT, BE, BG, HR, CY, CZ, DK, EE, FI, FR, DE, GR, HU, IE, IT, LV, LT, LU, MT, NL, PL, PT, RO, SK, SI, ES, SE), rate limit rule: 1000 requests per IP per 5 minutes |
| **API Gateway** | APIM network isolation | APIM Standard v2 deployed with VNet integration. Public endpoint accepts traffic only from Front Door (validated via `X-Azure-FDID` header check policy). Backend calls routed through VNet |
| **Application** | Container Apps VNet | Container Apps Environment deployed in dedicated subnet. Ingress restricted to APIM subnet via network security group (NSG) rules |
| **Data services** | Private endpoints | Private endpoints for: Cosmos DB, Azure AI Search, Azure OpenAI, Blob Storage, Key Vault. All deployed in the same VNet with dedicated subnets. Public network access disabled on all data services |
| **DNS** | Azure Private DNS Zones | Private DNS zones for each service (`privatelink.documents.azure.com`, `privatelink.search.windows.net`, `privatelink.openai.azure.com`, `privatelink.blob.core.windows.net`, `privatelink.vaultcore.azure.net`) linked to the application VNet |

### 5.2 Identity and Access Management

All service-to-service authentication uses Microsoft Entra ID Managed Identity. No API keys, connection strings, or credentials are stored in application code or configuration.

| Source | Target | Authentication Method | Entra ID Role Assignment |
|---|---|---|---|
| Container Apps | Azure OpenAI | System-assigned Managed Identity | `Cognitive Services OpenAI User` |
| Container Apps | Azure AI Search | System-assigned Managed Identity | `Search Index Data Reader` |
| Container Apps | Cosmos DB | System-assigned Managed Identity | `Cosmos DB Built-in Data Contributor` |
| Container Apps | Blob Storage | System-assigned Managed Identity | `Storage Blob Data Reader` |
| Container Apps | Key Vault | System-assigned Managed Identity | `Key Vault Secrets User` |
| AI Search Indexer | Blob Storage | System-assigned Managed Identity | `Storage Blob Data Reader` |
| AI Search Indexer | Azure OpenAI | System-assigned Managed Identity | `Cognitive Services OpenAI User` |
| APIM | Container Apps | Managed Identity (not required - VNet routing with ingress FQDN) | N/A |

**External API Authentication:**

| Integration | Method | Secret Storage |
|---|---|---|
| CUSTOMER_NAME Billing API | OAuth 2.0 client credentials | Client ID in Container Apps environment variable; Client Secret in Key Vault (`CUSTOMER_NAME-billing-api-client-secret`). Token cached in memory with 5-minute refresh |

### 5.3 Data Protection

| Control | Implementation |
|---|---|
| **EU data residency** | All Azure services deployed in Sweden Central (primary). Azure OpenAI Data Zone EU ensures model inference stays within EU boundaries. No data crosses EU borders at any point in the processing pipeline |
| **Encryption at rest** | Cosmos DB: Microsoft-managed encryption keys (AES-256). Blob Storage: Microsoft-managed encryption keys (AES-256). AI Search: Microsoft-managed encryption keys. Key Vault: FIPS 140-2 Level 2 validated HSM backing |
| **Encryption in transit** | TLS 1.2+ enforced on all connections. Front Door terminates TLS at edge and re-encrypts to backend. All inter-service communication within VNet uses TLS |
| **Data minimization** | 30-day TTL on conversation data (automatic deletion). 24-hour TTL on session state. Billing API returns summary data only - no raw PDFs, no payment instrument details, no full address. No customer PII stored beyond session scope |
| **Right to erasure (GDPR Art. 17)** | DELETE endpoint (`/api/v1/sessions/{session_id}`) removes all conversation messages, session state, and feedback for a given session. CUSTOMER_NAME support team can invoke this via internal tooling when a customer requests data deletion. Bulk deletion supported for session ranges |
| **Azure OpenAI data handling** | Data Zone EU deployment: customer prompts and completions are not stored by Microsoft, not used for model training, and processed exclusively within EU data centers. Abuse monitoring may process data but retains it for no more than 30 days within the same geography |

### 5.4 Responsible AI

| Control | Implementation | Purpose |
|---|---|---|
| **Content Filtering** | Azure OpenAI content filters enabled at Medium severity threshold for all categories (hate, sexual, violence, self-harm) on both input and output | Prevent harmful content in responses |
| **Prompt Shields** | Enabled on all requests to detect and block jailbreak attempts and indirect prompt injection via retrieved documents | Prevent adversarial manipulation of the chatbot |
| **Groundedness Detection** | Post-processing step on assistant responses; responses flagged as ungrounded trigger a disclaimer or fallback to "I cannot verify this information" response | Prevent hallucinated billing information that could mislead customers |
| **PII Detection** | Output filter configured to detect and redact PII (fiscal codes, IBAN numbers, full addresses) that may appear in generated responses | Prevent accidental PII exposure in chat responses |
| **Topic restriction** | System prompt explicitly restricts the assistant to energy billing, tariff explanation, bill reading guidance, and payment information topics. Off-topic queries receive a polite redirect: "I can only help with CUSTOMER_NAME energy billing questions" | Prevent misuse for unrelated queries |
| **Human escalation** | Chatbot offers "Talk to an agent" option when: (a) user expresses dissatisfaction, (b) query involves billing disputes or complaints, (c) user explicitly requests human assistance, (d) confidence is low after 2 attempts | Ensure complex or sensitive issues reach human agents |
| **AI disclosure** | Every response includes a visible "This response was generated by AI and may contain errors. For official information, contact CUSTOMER_NAME customer service" disclaimer | Transparency about AI-generated content |
| **Feedback loop** | Thumbs up/down on every response. Monthly review of low-rated responses by CUSTOMER_NAME content team to identify knowledge gaps, prompt improvements, and documentation updates | Continuous quality improvement |
| **Usage analytics** | Weekly dashboard showing: content filter trigger rate, topic restriction trigger rate, human escalation rate, average feedback score, abandoned conversation rate | Monitor responsible AI control effectiveness |

### 5.5 RBAC for Operations Team

| Role | Azure RBAC Assignment | Scope | Purpose |
|---|---|---|---|
| **Platform Engineer** | Contributor | Resource Group | Deploy and configure all Azure resources via IaC |
| **Application Developer** | Container Apps Contributor, Reader on all other services | Resource Group | Deploy application code, view logs and metrics |
| **AI Engineer** | Cognitive Services OpenAI Contributor, Search Service Contributor | OpenAI + AI Search resources | Manage model deployments, update search indexes and skillsets |
| **Operations/SRE** | Monitoring Contributor, Reader | Resource Group + Log Analytics Workspace | View dashboards, configure alerts, investigate incidents |
| **CUSTOMER_NAME Content Manager** | Storage Blob Data Contributor | Blob Storage (knowledge-base container) | Upload and manage knowledge base documents |
| **CUSTOMER_NAME Support Agent** | Cosmos DB Built-in Data Reader | Cosmos DB | Read conversation history for support escalation scenarios |
| **Security Auditor** | Security Reader | Subscription | Review security posture, access logs, compliance status |

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Metric | Target | Measurement Method |
|---|---|---|
| P95 end-to-end response latency (complete) | < 5,000 ms | Application Insights request duration (end-to-end trace) |
| P95 first token latency (streaming) | < 1,500 ms | Custom metric: time from request receipt to first SSE token emitted |
| P50 end-to-end response latency | < 3,000 ms | Application Insights request duration |
| AI Search query latency (P95) | < 200 ms | Application Insights dependency tracking |
| Cosmos DB read latency (P95) | < 30 ms | Application Insights dependency tracking |
| CUSTOMER_NAME billing API latency (P95) | < 2,000 ms | Application Insights dependency tracking (external dependency) |
| Widget initial load time | < 1,500 ms | Front Door analytics, synthetic monitoring |

**Performance optimization strategies:**
- Streaming responses via SSE to provide perceived responsiveness while the full response generates
- Conversation history limited to last 10 messages in prompt context to control token count and latency
- AI Search configured with semantic ranker in query-time mode (not indexing-time) for optimal latency
- Cosmos DB point reads by session_id (partition key) for single-digit millisecond reads
- Billing API token cached in memory to avoid per-request OAuth token exchange

### 6.2 Scalability

| Dimension | Specification | Configuration |
|---|---|---|
| Daily query volume | 50,000 - 100,000 queries/day | Baseline design target |
| Average throughput | 35 - 70 queries per second | Based on 16-hour active window (06:00-22:00 CET) |
| Peak throughput | 200 queries per second | Monday mornings, bill delivery days (monthly spike) |
| Container Apps replicas | Min: 2, Max: 20 | KEDA HTTP scaler, scale at 50 concurrent requests per replica |
| AI Search replicas | 2 | Provides read throughput for peak load and high availability |
| AI Search partitions | 1 | Sufficient for expected document volume (< 100K chunks) |
| Azure OpenAI throughput (GPT-4o-mini) | 500K tokens per minute (Data Zone EU) | Data Zone provides higher limits than regional deployment |
| Azure OpenAI throughput (GPT-4o) | 150K tokens per minute (Data Zone EU) | Reserved for 20% of queries (complex/personalized) |
| Cosmos DB (serverless) | Auto-scales to 5,000 RU/s burst | Serverless automatically handles traffic spikes |

**Scaling triggers and thresholds:**

| Component | Metric | Scale-out Threshold | Scale-in Threshold | Cooldown |
|---|---|---|---|---|
| Container Apps | HTTP concurrent requests | 50 per replica | 20 per replica | 300 seconds |
| AI Search | Query latency P95 | Manual scaling (add replica if > 500ms sustained) | Manual scaling | N/A |

### 6.3 Availability

| Component | SLA | Configuration for HA |
|---|---|---|
| Azure Front Door (Premium) | 99.99% | Global anycast, automatic failover across edge POPs |
| Azure API Management (Standard v2) | 99.95% | Single-region deployment (sufficient for v1; multi-region if needed in v2) |
| Azure Container Apps | 99.95% | Minimum 2 replicas ensures no downtime during single-instance failure or deployment. Zone redundancy enabled |
| Azure OpenAI Service | 99.9% | Data Zone deployment with automatic load balancing across EU data centers |
| Azure AI Search (S1, 2 replicas) | 99.99% (read) | Two replicas provide read high availability SLA. Write SLA 99.9% with 2 replicas |
| Azure Cosmos DB (Serverless) | 99.99% | Single-region serverless with automatic replication within region |
| **Composite SLA (estimated)** | **99.8%** | Calculated from critical path: Front Door x APIM x Container Apps x OpenAI x AI Search x Cosmos DB |

**Availability design decisions:**
- No multi-region deployment for v1 (single EU region sufficient for Italian market; cost-prohibitive for initial launch)
- Container Apps minimum 2 replicas with zone redundancy eliminates single-point-of-failure for application tier
- AI Search 2 replicas ensures read availability during index updates
- Graceful degradation: if AI Search is temporarily unavailable, chatbot can still answer using conversation history context only (reduced quality, not outage). If billing API is unavailable, chatbot responds with "billing data temporarily unavailable" and continues FAQ mode

### 6.4 Disaster Recovery

| Parameter | Target | Implementation |
|---|---|---|
| **RPO (Recovery Point Objective)** | < 1 hour | Cosmos DB continuous backup (point-in-time restore with 1-second granularity, 30-day retention). Blob Storage soft delete (14-day retention). AI Search index can be rebuilt from Blob Storage source documents |
| **RTO (Recovery Time Objective)** | < 4 hours | Full infrastructure redeployable via Bicep IaC templates. Container Apps image stored in Azure Container Registry (geo-replicated). AI Search index rebuild from Blob Storage takes approximately 1-2 hours for full corpus |
| **Backup strategy** | Automated, no manual intervention | Cosmos DB: continuous backup (included in serverless). Blob Storage: soft delete + versioning. AI Search: no backup needed (rebuild from source). Application code: Azure Container Registry + Git repository |
| **DR procedure** | Documented runbook | (1) Deploy infrastructure via Bicep to secondary region (West Europe). (2) Restore Cosmos DB to point-in-time. (3) Repoint AI Search indexer to Blob Storage. (4) Trigger full index rebuild. (5) Update Front Door backend to new Container Apps endpoint. (6) Validate end-to-end flow. Estimated execution: 2-3 hours |

**Recovery priority order:**

| Priority | Component | Recovery Action | Estimated Time |
|---|---|---|---|
| 1 | Container Apps + APIM | Deploy via Bicep, pull image from Container Registry | 30 minutes |
| 2 | Cosmos DB | Point-in-time restore to new account | 30-60 minutes |
| 3 | Azure OpenAI | Deploy model to secondary region (West Europe) | 15 minutes |
| 4 | AI Search | Deploy index schema, trigger full rebuild from Blob Storage | 60-120 minutes |
| 5 | Front Door | Update backend pool to new region endpoints | 5 minutes |

### 6.5 Multilingual Readiness

While version 1 supports Italian only, the architecture is designed for low-friction multilingual expansion to CUSTOMER_NAME's other markets.

| Aspect | v1 (Italian) | Multilingual Expansion Path |
|---|---|---|
| **AI Search index** | Single index with `it.lucene` analyzer | Add per-language indexes (e.g., `knowledge-es`, `knowledge-fr`) with language-specific Lucene analyzers. Alternatively, single index with language field filter |
| **Document ingestion** | Single Blob Storage container | Per-language folder structure: `knowledge-base/{language}/{category}/` |
| **Azure OpenAI** | System prompt in Italian | System prompt parameterized by locale. GPT-4o and GPT-4o-mini handle multilingual natively - no model changes needed |
| **Embedding model** | text-embedding-3-small (multilingual) | Same model supports all target languages natively |
| **Widget** | Italian UI strings | Locale detection from browser/URL parameter. UI string externalization via i18n framework |
| **APIM routing** | Single backend | Language detection in APIM policy (Accept-Language header or query parameter) routes to language-specific orchestration config |

### 6.6 Compliance

| Regulation | Requirement | Implementation |
|---|---|---|
| **GDPR (EU 2016/679)** | Data minimization | 30-day TTL on conversation data, 24-hour TTL on session state. No persistent customer profiles created |
| **GDPR** | Right to erasure (Art. 17) | DELETE API endpoint for session-level data removal. Cosmos DB TTL provides automatic baseline deletion |
| **GDPR** | Data residency | All services deployed in Sweden Central (EU). Azure OpenAI Data Zone EU. No data transferred outside EU |
| **GDPR** | Lawful basis | Legitimate interest (customer self-service for their own billing data). No special category data processed |
| **GDPR** | Transparency | AI-generated disclaimer on all responses. Privacy notice in chatbot widget footer linking to CUSTOMER_NAME's privacy policy |
| **GDPR** | Data processing agreement | Microsoft Azure DPA covers all Azure services. CUSTOMER_NAME billing API integration covered under existing internal data governance |
| **ARERA** | Customer service response quality | Chatbot complements (does not replace) regulated customer service channels. Human escalation path always available. Response accuracy monitored via feedback loop and periodic manual review |
| **AI Act (EU 2024/1689)** | Transparency for AI systems | AI disclosure on all responses. System classified as limited risk (customer service chatbot) - transparency obligations apply. Documentation of system purpose, capabilities, and limitations maintained |

---

## Appendix A: Azure Region and Service Availability

All services are confirmed available in Sweden Central as of the design date.

| Service | Sweden Central Availability | Fallback Region |
|---|---|---|
| Azure OpenAI (Data Zone EU) | Available (GPT-4o, GPT-4o-mini, text-embedding-3-small) | West Europe |
| Azure AI Search (S1) | Available | West Europe |
| Azure Container Apps | Available | West Europe |
| Azure Cosmos DB (Serverless) | Available | West Europe |
| Azure API Management (Standard v2) | Available | West Europe |
| Azure Front Door (Premium) | Global service | N/A |
| Azure Blob Storage | Available | West Europe |
| Azure Key Vault | Available | West Europe |
| Application Insights | Available (workspace-based) | West Europe |

## Appendix B: System Prompt Design Principles

The system prompt for the CUSTOMER_NAME Bill Explainer chatbot follows these design principles:

| Principle | Implementation |
|---|---|
| **Role definition** | "You are CUSTOMER_NAME's billing assistant, helping customers understand their energy bills in clear, simple Italian." |
| **Scope restriction** | Explicitly limited to: energy bill explanation, tariff information, consumption data interpretation, payment information, meter reading guidance. Rejects: complaints handling, contract changes, technical support, non-CUSTOMER_NAME topics |
| **Grounding instruction** | "Answer only based on the provided context documents and billing data. If the information is not in the provided context, say you don't have that information and suggest contacting CUSTOMER_NAME customer service." |
| **Tone** | Professional, friendly, patient. Avoid technical jargon. Explain regulatory terms (e.g., "oneri di sistema") in plain language |
| **Numerical accuracy** | "When presenting numbers from billing data, always include the unit (EUR, kWh, Smc) and the billing period. Do not perform calculations unless the source data is explicitly provided." |
| **Language** | Italian only (v1). Respond in Italian regardless of input language. Politely redirect non-Italian queries |
| **Safety** | "Never provide financial advice. Never confirm or deny payment status as definitive. Always recommend contacting customer service for disputes or payment issues." |
| **Citations** | "When referencing tariff documentation or regulatory information, indicate the source document category (e.g., 'According to the current tariff conditions...')" |

---

*End of Solution Design Document*
