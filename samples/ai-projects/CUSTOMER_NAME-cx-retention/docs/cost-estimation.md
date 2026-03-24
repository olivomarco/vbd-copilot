# Cost Estimation - CUSTOMER_NAME Intelligent Bill Explainer

> **Disclaimer:** All prices in this document are estimates based on publicly available Azure pricing as of mid-2025. Actual costs may vary depending on negotiated Enterprise Agreement rates, regional pricing adjustments, currency fluctuations, and real-world usage patterns. Prices are stated in EUR using an approximate conversion rate of 1 USD = 0.92 EUR where Azure lists prices in USD. Azure OpenAI prices reflect EU Data Zone deployment, which carries a slight premium over Global deployment. This document should be used for planning purposes and validated against the Azure Pricing Calculator before budget commitment.

---

## 1. Assumptions

The following assumptions underpin all cost calculations in this document:

- **Query volume:** 50,000 to 100,000 individual user messages per day. A "query" is a single user message sent to the system, not a full conversation.
- **Conversation profile:** Average conversation consists of 3 turns (3 user messages and 3 assistant responses). At 50,000 queries/day this equates to roughly 16,700 conversations/day; at 100,000 queries/day roughly 33,300 conversations/day.
- **Token budget per API call (per turn):**
  - Total input tokens: ~1,200 average, broken down as:
    - System prompt: ~400 tokens (cached via Azure OpenAI prompt caching at 50% input price discount)
    - RAG context (retrieved document chunks): ~500 tokens
    - Conversation history (prior turns): ~200 tokens average
    - Current user message: ~100 tokens
  - Cached input portion: ~400 tokens (system prompt, eligible for 50% discount)
  - Non-cached input portion: ~800 tokens (RAG context + history + user message)
  - Output tokens: ~350 tokens average (assistant response)
- **Model split:** 80% of queries are handled by GPT-4o-mini (simple bill explanations, FAQ-style questions, straightforward tariff lookups). 20% of queries are routed to GPT-4o (complex tariff comparisons, multi-variable calculations, nuanced regulatory questions).
- **Prompt caching:** Azure OpenAI prompt caching is enabled. The system prompt prefix (~400 tokens) is identical across all requests and qualifies for the 50% cached input token discount after the first call in each session.
- **Knowledge base:** Approximately 500 documents (tariff PDFs, FAQs, terms and conditions, regulatory guides) totaling roughly 200 MB of indexed content in Azure AI Search.
- **Conversation history:** Retained for 30 days in Cosmos DB to support multi-session continuity and analytics. Session state retained for 24 hours.
- **Availability:** 24/7 service availability. Peak traffic hours are 8:00-22:00 CET, with roughly 85% of daily volume concentrated in this window.
- **Region:** All services deployed in Sweden Central (EU data residency). Azure OpenAI models use EU Data Zone deployment.
- **Currency:** All costs stated in EUR.

### 1.1 Azure OpenAI Pricing Reference (EU Data Zone, Pay-as-you-go)

| Model | Cached Input (EUR/1M tokens) | Standard Input (EUR/1M tokens) | Output (EUR/1M tokens) |
|---|---|---|---|
| GPT-4o-mini | 0.075 | 0.15 | 0.60 |
| GPT-4o | 1.25 | 2.50 | 10.00 |
| text-embedding-3-small | N/A | 0.02 | N/A |

---

## 2. Monthly Cost Breakdown

### 2.1 Azure OpenAI Inference Cost - Detailed Calculation

The inference cost calculation is shown step by step to ensure transparency and auditability.

#### Low Scenario: 50,000 queries/day

Monthly queries: 50,000 x 30 = 1,500,000 queries/month

**GPT-4o-mini (80% of queries = 1,200,000 queries/month):**

| Token Category | Tokens per Query | Monthly Tokens | Price (EUR/1M tokens) | Monthly Cost (EUR) |
|---|---|---|---|---|
| Cached input (system prompt) | 400 | 480,000,000 (480M) | 0.075 | 36 |
| Non-cached input (RAG + history + user) | 800 | 960,000,000 (960M) | 0.15 | 144 |
| Output (assistant response) | 350 | 420,000,000 (420M) | 0.60 | 252 |
| **GPT-4o-mini subtotal** | | | | **432** |

**GPT-4o (20% of queries = 300,000 queries/month):**

| Token Category | Tokens per Query | Monthly Tokens | Price (EUR/1M tokens) | Monthly Cost (EUR) |
|---|---|---|---|---|
| Cached input (system prompt) | 400 | 120,000,000 (120M) | 1.25 | 150 |
| Non-cached input (RAG + history + user) | 800 | 240,000,000 (240M) | 2.50 | 600 |
| Output (assistant response) | 350 | 105,000,000 (105M) | 10.00 | 1,050 |
| **GPT-4o subtotal** | | | | **1,800** |

**Total OpenAI inference (low): EUR 432 + EUR 1,800 = EUR 2,232/month**

#### High Scenario: 100,000 queries/day

All token volumes double. Monthly queries: 100,000 x 30 = 3,000,000 queries/month.

| Model | Queries/Month | Cached Input Cost | Non-cached Input Cost | Output Cost | Subtotal (EUR) |
|---|---|---|---|---|---|
| GPT-4o-mini (80%) | 2,400,000 | 72 | 288 | 504 | 864 |
| GPT-4o (20%) | 600,000 | 300 | 1,200 | 2,100 | 3,600 |
| **Total** | **3,000,000** | **372** | **1,488** | **2,604** | **4,464** |

**Total OpenAI inference (high): EUR 4,464/month**

### 2.2 Full Monthly Cost Summary

| Service | SKU / Tier | Configuration | Unit Price (EUR) | Monthly Usage (Low - High) | Monthly Cost (EUR) |
|---|---|---|---|---|---|
| Azure OpenAI - GPT-4o-mini | Data Zone EU, PAYG | 80% of queries; cached + non-cached input; see calculation above | See Section 2.1 | 1.2M - 2.4M queries | 432 - 864 |
| Azure OpenAI - GPT-4o | Data Zone EU, PAYG | 20% of queries; cached + non-cached input; see calculation above | See Section 2.1 | 300K - 600K queries | 1,800 - 3,600 |
| Azure OpenAI - Embeddings | text-embedding-3-small | Index maintenance on document updates (re-embedding changed/new documents) | 0.02 per 1M tokens | ~5M tokens/month (incremental) | 1 |
| Azure AI Search | Standard S1 | 2 replicas for high availability, 1 partition | ~230 per search unit/month | 2 search units (2 replicas x 1 partition) | 460 |
| Azure Container Apps | Consumption plan | Chatbot API backend; 2-4 replicas during peak, 0.5 vCPU and 1 GB RAM per replica | 0.000024 per vCPU-second | ~2.6M - 5.2M vCPU-seconds/month | 50 - 100 |
| Azure Cosmos DB | Serverless | Session state (24h TTL) and conversation history (30-day TTL); reads and writes | 0.25 per 1M RU + 0.25 per GB storage | ~50M - 100M RU/month; ~5 GB | 15 - 30 |
| Azure API Management | Standard v2 | API gateway, rate limiting, auth token validation; 1 unit | 160 per unit/month | 1 unit | 160 |
| Azure Front Door | Premium | Global entry point with WAF policies, SSL termination, CDN for static assets | ~310 base/month + data transfer | Base + ~50-100 GB outbound/month | 340 - 370 |
| Azure Blob Storage | LRS Hot | Source document storage for tariff PDFs, FAQs, T&Cs | 0.02 per GB/month | ~1 GB | 1 |
| Azure Key Vault | Standard | API keys, connection strings, TLS certificates | 0.03 per 10K operations | ~100K operations/month | 1 |
| Azure Monitor + App Insights | Pay-as-you-go | Distributed tracing, custom metrics, log analytics | 2.10 per GB ingested | 10 - 20 GB telemetry/month | 25 - 45 |
| **TOTAL (Monthly)** | | | | | **3,285 - 5,632** |

### 2.3 Cost Distribution by Category

| Category | Services Included | Monthly Range (EUR) | Share of Total |
|---|---|---|---|
| AI/ML (Models + Search) | Azure OpenAI (GPT-4o, GPT-4o-mini, Embeddings), AI Search | 2,693 - 4,925 | 82% - 88% |
| Compute + Networking | Container Apps, API Management, Front Door | 550 - 630 | 11% - 17% |
| Data + Storage | Cosmos DB, Blob Storage | 16 - 31 | <1% - 1% |
| Operations + Security | Key Vault, Monitor, App Insights | 26 - 46 | <1% - 1% |

**Key insight:** Azure OpenAI inference dominates the cost profile at 68% - 79% of total spend (EUR 2,232 - 4,464 of the total). GPT-4o alone accounts for 55% - 64% of total cost despite handling only 20% of queries. This makes the model routing split the single most important cost lever.

---

## 3. Cost Scenarios

Three scenarios model the expected cost trajectory from pilot through scale.

### 3.1 Pilot Phase (10,000 queries/day)

| Parameter | Value |
|---|---|
| Daily query volume | 10,000 user messages |
| Monthly queries | 300,000 |
| Monthly conversations (~3 turns each) | ~100,000 |
| GPT-4o-mini queries (80%) | 240,000/month |
| GPT-4o queries (20%) | 60,000/month |

**Pilot OpenAI inference calculation:**

| Model | Queries/Month | Cached Input | Non-cached Input | Output | Subtotal (EUR) |
|---|---|---|---|---|---|
| GPT-4o-mini | 240,000 | 96M tokens = 7 | 192M tokens = 29 | 84M tokens = 50 | 86 |
| GPT-4o | 60,000 | 24M tokens = 30 | 48M tokens = 120 | 21M tokens = 210 | 360 |
| **Total inference** | | | | | **446** |

| Service | Pilot Monthly Cost (EUR) |
|---|---|
| Azure OpenAI - GPT-4o-mini | 86 |
| Azure OpenAI - GPT-4o | 360 |
| Azure OpenAI - Embeddings | 1 |
| Azure AI Search (S1, 1 replica for pilot) | 230 |
| Azure Container Apps (1-2 replicas) | 20 |
| Azure Cosmos DB (serverless, low RU) | 5 |
| Azure API Management (Standard v2) | 160 |
| Azure Front Door (Premium) | 320 |
| Azure Blob Storage | 1 |
| Azure Key Vault | 1 |
| Azure Monitor + App Insights | 10 |
| **Pilot Total** | **~1,194** |

**Pilot range estimate: EUR 1,100 - 1,400/month** depending on actual usage ramp-up and whether AI Search runs 1 or 2 replicas.

### 3.2 Production Phase (50,000 queries/day)

This is the low-end baseline scenario from the detailed breakdown in Section 2.

**Production estimate: ~EUR 3,285/month**

### 3.3 Scale Phase (100,000 queries/day)

This is the high-end scenario from the detailed breakdown in Section 2, with all services at peak utilization.

**Scale estimate: ~EUR 5,632/month**

### 3.4 Scenario Comparison Summary

| Scenario | Queries/Day | Conversations/Day | Monthly Cost (EUR) | Cost per Query (EUR) | Cost per Conversation (EUR) |
|---|---|---|---|---|---|
| Pilot | 10,000 | ~3,300 | ~1,194 | 0.0040 | 0.0119 |
| Production | 50,000 | ~16,700 | ~3,285 | 0.0022 | 0.0066 |
| Scale | 100,000 | ~33,300 | ~5,632 | 0.0019 | 0.0056 |

The decreasing cost per query at higher volumes reflects the fixed-cost components (AI Search, APIM, Front Door) being amortized across more interactions. At production scale, the cost per conversation (EUR 0.0066) is roughly 450x-1,200x cheaper than a human-assisted call center interaction (typically EUR 3-8 per call in the Italian energy market).

---

## 4. Cost Optimization Recommendations

### 4.1 Model Selection and Prompt Engineering

- **Maximize GPT-4o-mini usage (target 85%+):** Route simple bill explanations, FAQ-type questions, and straightforward tariff lookups to GPT-4o-mini. GPT-4o costs roughly 17x more per input token and 17x more per output token than GPT-4o-mini. Increasing the mini share from 80% to 90% saves approximately EUR 846/month at 50K queries/day. Implement an intent classifier or complexity scorer to route only genuinely complex queries to GPT-4o.
- **Leverage prompt caching aggressively:** Azure OpenAI prompt caching is already factored into the estimates above, providing a 50% discount on the ~400-token system prompt. To maximize caching benefits, keep the system prompt stable and place variable content (RAG results, user message) after the cached prefix. If the system prompt can be extended to include frequently used instructions (~600+ tokens), caching savings increase proportionally.
- **Optimize prompt length:** Regularly review and trim system prompts, reduce redundant instructions, and compress RAG context by extracting only the most relevant passages. A 20% reduction in average input tokens translates directly to a 20% reduction in input token costs.
- **Monitor model evolution:** As newer cost-efficient models become available in EU Data Zones (such as GPT-4.1-mini or successors), evaluate migration. Newer models often deliver equivalent or better quality at lower per-token costs.

### 4.2 Data and Storage

- **Cosmos DB TTL policies:** Set aggressive Time-to-Live values: 24 hours for ephemeral session state, 30 days for conversation history. This automatically purges stale data and prevents unbounded storage growth.
- **Conversation summarization:** Instead of retaining full conversation transcripts for 30 days, consider summarizing older conversations (older than 7 days) into compact summaries. This reduces both storage costs and RU consumption on reads.
- **AI Search index optimization:** Keep the index lean by removing outdated documents promptly. Use field-level indexing (only index searchable fields) to reduce index size.

### 4.3 Compute and Networking

- **Scale Container Apps to zero during off-peak:** Between midnight and 6:00 CET, traffic is typically negligible. Configure minimum replicas to 0 during this window, letting Container Apps scale down completely. This can save 15-20% on compute costs.
- **APIM response caching:** Implement response caching in API Management for frequently asked general questions (e.g., "What are the components of my bill?", "How is my tariff calculated?"). Cache responses for 1-4 hours to avoid redundant LLM calls. Even caching 5-10% of queries yields meaningful savings on OpenAI token costs - at 5% cache hit rate, this saves roughly EUR 110/month at production scale.
- **Front Door caching:** Cache static assets (chatbot UI, JavaScript bundles, CSS) aggressively at the CDN edge to minimize origin traffic.

### 4.4 Monitoring and Governance

- **Set Azure Monitor sampling rates:** Use adaptive sampling in Application Insights to reduce telemetry volume during high-traffic periods. Target 10-20 GB/month ingestion by sampling routine successful requests at 10-20% while capturing 100% of errors and slow requests.
- **Create cost alerts:** Configure Azure Cost Management alerts at 80% and 100% of monthly budget thresholds for each resource group. Set up anomaly detection to catch unexpected cost spikes (e.g., a prompt injection causing excessive token generation, or a retry loop inflating query counts).
- **Weekly cost reviews:** Establish a practice of reviewing the Azure Cost Management dashboard weekly during the first 3 months to identify optimization opportunities based on actual usage patterns.

---

## 5. Reserved vs Pay-as-you-go Analysis

| Service | Pay-as-you-go (EUR/month) | 1-Year Reserved (EUR/month) | Savings | Recommendation |
|---|---|---|---|---|
| Azure AI Search (S1, 2 SU) | 460 | ~300 | ~35% | Reserve after 3 months if usage is stable |
| Azure API Management (Std v2) | 160 | N/A (no reservation option) | N/A | Continue pay-as-you-go |
| Azure Front Door (Premium) | 340-370 | N/A (no reservation option) | N/A | Continue pay-as-you-go |
| Azure OpenAI (PTU) | 2,232-4,464 (token-based) | Evaluate per-model PTU | 20-40% at sustained high utilization | Evaluate at scale (100K queries/day) |
| Azure Cosmos DB | 15-30 (serverless) | N/A (serverless has no reservation) | N/A | Remain on serverless unless RU usage exceeds 1M RU/day consistently |

### Reservation Strategy

**Phase 1 - Months 1-3 (Pilot and Early Production):** Start entirely on pay-as-you-go pricing. Use this period to collect real usage telemetry, validate traffic assumptions, and understand actual token consumption patterns. Do not commit to reservations until usage is understood.

**Phase 2 - Months 4-6 (Optimization):** Review 3 months of actual cost data. If Azure AI Search usage is stable at 2 search units, purchase a 1-year reservation to save approximately EUR 1,920/year. Analyze the actual GPT-4o-mini vs GPT-4o query distribution - if GPT-4o usage can be reduced below 20%, the monthly savings are significant (each 5% shift from GPT-4o to GPT-4o-mini saves roughly EUR 423/month at production scale).

**Phase 3 - Months 7-12 (Scale Optimization):** If daily query volume reaches and sustains 75K+ queries/day, evaluate Azure OpenAI Provisioned Throughput Units (PTU). PTU pricing offers a fixed monthly cost for a guaranteed throughput level, which becomes cost-effective when utilization is consistently high. At sustained 100K queries/day, PTU can save 20-40% compared to token-based pay-as-you-go, depending on the model and usage pattern.

**Recommendation:** Start with pay-as-you-go for the first 3 months, then evaluate reserved capacity based on actual usage patterns. The only service where early reservation is clearly beneficial is Azure AI Search, given its high fixed cost relative to total spend.

---

## 6. Annual Cost Projection

### 6.1 Year 1 Total by Scenario

| Scenario | Monthly Estimate (EUR) | Annual Estimate (EUR) | Notes |
|---|---|---|---|
| Pilot (10K queries/day) | ~1,194 | ~14,328 | Assumes pilot runs full year at low volume; unlikely in practice |
| Production (50K queries/day) | ~3,285 | ~39,420 | Baseline annual run-rate |
| Scale (100K queries/day) | ~5,632 | ~67,584 | Full-scale annual run-rate |

### 6.2 Realistic Year 1 Projection (Blended)

A more realistic Year 1 projection accounts for the ramp-up from pilot to production:

| Period | Duration | Scenario | Monthly Cost (EUR) | Period Total (EUR) |
|---|---|---|---|---|
| Months 1-2 | 2 months | Pilot (10K queries/day) | ~1,194 | 2,388 |
| Months 3-4 | 2 months | Ramp-up (25K queries/day) | ~2,170 | 4,340 |
| Months 5-8 | 4 months | Production (50K queries/day) | ~3,285 | 13,140 |
| Months 9-12 | 4 months | Scale (75K-100K queries/day) | ~4,450 | 17,800 |
| **Year 1 Total** | **12 months** | **Blended** | | **~37,668** |

Ramp-up estimate (25K queries/day) breakdown: 750K queries/month; GPT-4o-mini inference EUR 216 + GPT-4o inference EUR 900 = EUR 1,116 inference + ~EUR 1,053 infrastructure = ~EUR 2,170/month.

### 6.3 Year 1 with Reservations and Optimizations Applied

If Azure AI Search 1-year reservation is purchased at Month 4:

| Adjustment | Annual Savings (EUR) |
|---|---|
| AI Search 1-year reservation (9 months of savings) | ~1,440 |
| APIM response caching (5% query reduction, Months 3-12) | ~500 - 1,000 |
| Off-peak scaling (Container Apps zero-scale 6h/day) | ~100 - 200 |
| **Optimized Year 1 Total** | **~35,028 - 35,628** |

### 6.4 Executive Cost Context

Even at the full-scale annual run-rate of ~EUR 67,584/year, this represents a fraction of the cost of traditional customer support channels. For context:

- A human-assisted call center interaction in the Italian energy market costs EUR 3-8 per call.
- At 100,000 queries/day (33,300 conversations/day, roughly 1M conversations/month), handling these through a call center would cost EUR 3M-8M per month, or EUR 36M-96M per year.
- The AI solution at EUR 67,584/year represents a cost reduction of 99.8% compared to equivalent call center capacity.
- Even deflecting just 10% of call center volume to the AI chatbot (100K calls/month) would save EUR 300K-800K/month against a marginal AI cost increase of under EUR 6K/month.

---

## 7. Cost Sensitivity Analysis

The model routing split (GPT-4o-mini vs GPT-4o) is the single most impactful cost variable. The table below shows how different routing strategies affect total monthly cost at the production baseline of 50,000 queries/day.

### 7.1 Impact of Model Routing Split (50,000 queries/day)

| Routing Split | Mini Inference (EUR) | 4o Inference (EUR) | Total Inference (EUR) | Infrastructure (EUR) | Total Monthly (EUR) |
|---|---|---|---|---|---|
| 100% GPT-4o-mini | 540 | 0 | 540 | 1,053 | 1,593 |
| 90% mini / 10% 4o | 486 | 900 | 1,386 | 1,053 | 2,439 |
| **80% mini / 20% 4o (recommended)** | **432** | **1,800** | **2,232** | **1,053** | **3,285** |
| 70% mini / 30% 4o | 378 | 2,700 | 3,078 | 1,053 | 4,131 |
| 50% mini / 50% 4o | 270 | 4,500 | 4,770 | 1,053 | 5,823 |
| 100% GPT-4o | 0 | 9,000 | 9,000 | 1,053 | 10,053 |

**Calculation basis for 100% mini row:** 1,500,000 queries x (400 cached tokens x EUR 0.075/1M + 800 non-cached tokens x EUR 0.15/1M + 350 output tokens x EUR 0.60/1M) = EUR 45 + EUR 180 + EUR 315 = EUR 540.

**Calculation basis for 100% 4o row:** 1,500,000 queries x (400 cached tokens x EUR 1.25/1M + 800 non-cached tokens x EUR 2.50/1M + 350 output tokens x EUR 10.00/1M) = EUR 750 + EUR 3,000 + EUR 5,250 = EUR 9,000.

### 7.2 Key Takeaways

- **The 80/20 split is recommended** as the starting point. It provides high-quality responses for complex billing queries (via GPT-4o) while keeping the majority of simple interactions on the cost-efficient GPT-4o-mini model.
- **Each 10% shift from GPT-4o to GPT-4o-mini saves approximately EUR 846/month** at 50,000 queries/day. This makes the intent classifier / complexity router a high-value optimization target.
- **100% GPT-4o-mini is viable for pilot** to validate the architecture and user experience at minimal cost, with GPT-4o routing introduced once query complexity patterns are understood.
- **100% GPT-4o is not cost-justified.** At EUR 10,053/month (3.1x the recommended split), the quality improvement on simple queries does not warrant the additional spend. The routing approach delivers better cost-to-quality economics.
- **Infrastructure costs are largely fixed** at EUR 1,053/month regardless of the model split, representing 32% of total cost at the recommended split but only 10% at the 100% GPT-4o extreme. This means optimization efforts should focus primarily on inference costs.

### 7.3 Impact of Query Volume on Total Cost

For the recommended 80/20 split, total monthly cost scales as follows:

| Daily Queries | Monthly Queries | Inference Cost (EUR) | Infrastructure Cost (EUR) | Total (EUR) |
|---|---|---|---|---|
| 10,000 | 300,000 | 446 | 748 | 1,194 |
| 25,000 | 750,000 | 1,116 | 1,053 | 2,169 |
| 50,000 | 1,500,000 | 2,232 | 1,053 | 3,285 |
| 75,000 | 2,250,000 | 3,348 | 1,100 | 4,448 |
| 100,000 | 3,000,000 | 4,464 | 1,168 | 5,632 |

Infrastructure increases modestly at higher volumes due to additional Container Apps replicas, higher Cosmos DB RU consumption, increased data transfer through Front Door, and greater telemetry volume. The relationship between query volume and total cost is nearly linear because inference (the variable component) dominates the cost structure.

---

*This cost estimation was prepared for planning purposes. All figures are approximate and should be validated against current Azure pricing and CUSTOMER_NAME's Enterprise Agreement terms before budget approval. Prices reflect publicly available Azure rates as of mid-2025 and are subject to change. The token consumption estimates (1,200 input / 350 output per turn) should be validated against actual production telemetry within the first month of deployment and this document updated accordingly.*
