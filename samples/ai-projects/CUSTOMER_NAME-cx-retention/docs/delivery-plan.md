# Delivery Plan - CUSTOMER_NAME Intelligent Bill Explainer

## Project Overview

CUSTOMER_NAME serves approximately 10 million energy retail customers in the Italian market. A significant share of inbound contact center volume stems from billing inquiries - customers seeking explanations of line items, tariff changes, consumption breakdowns, and payment terms. This project delivers an AI-powered chatbot that explains energy bills in natural Italian, using a Retrieval-Augmented Generation (RAG) pattern on Microsoft Azure.

The chatbot ingests CUSTOMER_NAME tariff documentation, billing FAQs, terms and conditions, and bill structure guides into an Azure AI Search knowledge base. At query time it retrieves relevant context and generates accurate, conversational explanations via Azure OpenAI. When the customer provides a bill reference, the system calls the CUSTOMER_NAME billing API to deliver personalized, line-by-line explanations.

**Timeline:** 7 weeks to production launch (plus optional post-launch optimization from Week 8).

**Objective:** Reduce call center billing inquiry volume by at least 15% within three months of launch while maintaining customer satisfaction above 75%.

**Core team:** 8 people (Solution Architect, 2 Backend Developers, Frontend Developer, AI/ML Engineer, DevOps Engineer, QA Engineer, Project Manager).

---

## Phased Delivery Plan

### Phase 0: Foundation (Week 1)

The first week establishes all Azure infrastructure so that development teams can begin coding against real services from Day 5 onward.

| Task | Owner | Details |
|------|-------|---------|
| Azure subscription setup and resource group creation | DevOps Engineer | Dedicated resource group `rg-CUSTOMER_NAME-billexplainer-prod` in Sweden Central; tagging policy applied |
| Azure OpenAI resource deployment | DevOps Engineer | Data Zone EU deployment (Sweden Central); models: GPT-4o (complex chat completion), GPT-4o-mini (simple FAQ chat completion), text-embedding-3-small (embeddings) |
| Azure AI Search deployment | DevOps Engineer | Standard S1 tier; 1 replica, 1 partition; enable semantic ranker |
| Cosmos DB account creation | DevOps Engineer | Serverless capacity mode; database `billexplainer`, containers for conversation history and feedback |
| Container Apps environment setup | DevOps Engineer | Managed environment in Sweden Central VNet; workload profile: Consumption |
| Azure Key Vault setup with Managed Identity | DevOps Engineer | Store API keys, connection strings; system-assigned managed identities for Container Apps and AI Search |
| VNet and private endpoint configuration | Solution Architect, DevOps Engineer | Private endpoints for OpenAI, AI Search, Cosmos DB, Key Vault; NSG rules restricting public access |
| Azure Front Door and APIM stub deployment | DevOps Engineer | Front Door Premium tier with WAF policy; APIM Standard v2 for initial deployment (Developer tier may be used for local development only; Standard v2 is required from initial deployment for VNet integration) |
| CI/CD pipeline setup (GitHub Actions) | DevOps Engineer | Bicep IaC pipeline (validate, what-if, deploy); application build-and-deploy pipeline with staging slot |
| Entra ID app registrations | Solution Architect | App registrations for APIM, Container Apps; service principal for CI/CD |
| Engage CUSTOMER_NAME DPO for GDPR review | Project Manager | Document planned data flows; confirm no PII stored in knowledge base; agree conversation data retention policy |
| Request Azure OpenAI quota increase | Solution Architect | Request 150K TPM for GPT-4o, 100K TPM for GPT-4o-mini, 300K TPM for text-embedding-3-small to support load testing in Phase 3 |

**Milestone (end of Week 1):** All Azure infrastructure provisioned, accessible, and validated. CI/CD pipeline deploys a "hello world" Container App successfully. GDPR data flow documentation drafted and sent to CUSTOMER_NAME DPO.

---

### Phase 1: Core RAG Pipeline (Weeks 2-3)

This phase builds the end-to-end retrieval-augmented generation pipeline and proves it can answer general Italian energy billing questions accurately.

| Task | Owner | Week | Details |
|------|-------|------|---------|
| Knowledge base content gathering | AI/ML Engineer, Project Manager | Week 2 | Collect from CUSTOMER_NAME: tariff rate cards, billing FAQ documents, terms and conditions, bill layout/structure guides, regulatory notices (all Italian language) |
| Document preprocessing and chunking | AI/ML Engineer | Week 2 | Parse PDFs and HTML; chunk at ~512 tokens with 128-token overlap; preserve section headers as metadata; output JSON lines format |
| Embedding pipeline | AI/ML Engineer, Backend Developer | Week 2 | Batch embed chunks using text-embedding-3-small (1536 dimensions); store vectors in Azure AI Search index |
| Azure AI Search index creation | AI/ML Engineer | Week 2 | Hybrid search index: vector field (HNSW, cosine), keyword fields (Italian analyzer), semantic ranker configuration; filterable metadata fields (doc_type, tariff_name, effective_date) |
| FastAPI orchestrator - basic RAG flow | Backend Developer (x2) | Weeks 2-3 | Python/FastAPI application: receive user query, generate embedding, hybrid search (top 5 chunks), construct prompt with retrieved context, classify query complexity, route simple FAQ queries to GPT-4o-mini and complex personalized queries to GPT-4o, return response |
| System prompt engineering | AI/ML Engineer | Week 2-3 | Italian-language system prompt for energy billing domain; persona definition (helpful CUSTOMER_NAME assistant); grounding instructions (cite source documents, do not fabricate tariff numbers); refusal behavior for out-of-scope questions |
| Cosmos DB conversation history | Backend Developer | Week 3 | Container `messages` partitioned by session_id; create session, append messages, read history for multi-turn context; TTL of 30 days on conversation documents |
| Content filtering configuration | AI/ML Engineer | Week 2 | Configure Azure OpenAI content filters: medium threshold for hate/violence/sexual/self-harm; test that valid Italian energy terms (e.g., "gas naturale", "potenza impegnata") pass filters |
| Unit and integration tests | QA Engineer, Backend Developers | Week 3 | Unit tests for chunking, embedding, search, prompt construction; integration tests for full RAG flow against live Azure services; target 80% code coverage |
| RAG quality evaluation | AI/ML Engineer | Week 3 | Create evaluation dataset of 50 Italian billing questions with expected answers; measure answer relevance, groundedness, and completeness; iterate on prompt and retrieval parameters |

**Milestone (end of Week 3):** Working RAG chatbot accessible via API endpoint. Demonstrates accurate answers to general Italian energy billing questions (tariff explanations, bill component breakdowns, payment terms). Evaluation dataset scores: relevance > 4.0/5.0, groundedness > 4.0/5.0.

---

### Phase 2: Integration and UX (Weeks 4-5)

This phase adds the customer-facing chat interface, connects to CUSTOMER_NAME billing systems for personalized answers, and hardens the API layer.

| Task | Owner | Week | Details |
|------|-------|------|---------|
| Web chat widget development | Frontend Developer | Weeks 4-5 | Standalone, embeddable JavaScript widget (TypeScript, bundled as single JS + CSS); responsive design for mobile and desktop; Italian UI text; message bubbles, typing indicator, session persistence via localStorage |
| Streaming response support | Backend Developer, Frontend Developer | Week 4 | Server-Sent Events (SSE) from FastAPI orchestrator; frontend renders tokens as they arrive; reduces perceived latency |
| APIM configuration | DevOps Engineer | Week 4 | Import FastAPI OpenAPI spec; configure rate limiting (100 requests/minute per IP), token-based throttling (50K tokens/minute per subscription), CORS policy for CUSTOMER_NAME domains |
| Azure Front Door finalization | DevOps Engineer | Week 4 | WAF managed rule sets (OWASP 3.2, bot protection); custom rules blocking requests without valid origin header; CDN caching for static chat widget assets; SSL/TLS with CUSTOMER_NAME custom domain |
| CUSTOMER_NAME billing API integration | Backend Developer (x2) | Weeks 4-5 | REST integration with CUSTOMER_NAME billing API; lookup bill by reference number; retrieve line items, consumption data, tariff applied; circuit breaker pattern (Polly-equivalent in Python: tenacity with exponential backoff, 3 retries, 30s timeout) |
| Personalized bill explanation flow | Backend Developer, AI/ML Engineer | Week 5 | When user provides bill reference: fetch bill data, inject bill line items into prompt context alongside knowledge base results, generate personalized explanation of each charge |
| Conversation session management | Backend Developer | Week 4 | Session creation on first message; session ID in response headers; multi-turn context window (last 10 messages from Cosmos DB); session expiry after 30 minutes of inactivity |
| User feedback capture | Backend Developer, Frontend Developer | Week 5 | Thumbs up/down buttons on each assistant message; store feedback in Cosmos DB container `feedback` (session_id, message_id, rating, timestamp); simple feedback analytics query |
| Integration testing | QA Engineer | Week 5 | End-to-end tests: widget loads, user sends question, receives streaming response, provides bill reference, gets personalized explanation, submits feedback; cross-browser testing (Chrome, Safari, Edge on mobile and desktop) |

**Milestone (end of Week 5):** Full chatbot experience working end-to-end. Customer can open chat widget, ask general billing questions, provide a bill reference for personalized explanation, and submit feedback. All traffic routed through Front Door and APIM with WAF protection.

---

### Phase 3: Hardening and Launch (Weeks 6-7)

This phase focuses on production readiness: performance validation, security review, observability, and controlled rollout.

| Task | Owner | Week | Details |
|------|-------|------|---------|
| Load testing | QA Engineer, DevOps Engineer | Week 6 | Simulate 50,000 queries/day (peak 100 concurrent users) using Azure Load Testing; validate P95 latency < 5 seconds; identify bottlenecks in search, OpenAI calls, or Cosmos DB |
| Autoscaling validation | DevOps Engineer | Week 6 | Confirm Container Apps scales 2-20 replicas based on concurrent HTTP requests; verify scale-to-zero disabled (min replicas = 2 for availability) |
| Security review | Solution Architect, QA Engineer | Week 6 | Penetration testing against APIM and chat widget endpoints; WAF rule validation; verify private endpoints block direct access to backend services; validate no PII leakage in logs |
| Prompt injection testing | AI/ML Engineer, QA Engineer | Week 6 | Test 50+ prompt injection patterns (jailbreak, instruction override, data exfiltration attempts); verify system prompt cannot be extracted; validate content filters catch adversarial inputs |
| Responsible AI review | AI/ML Engineer, Solution Architect | Week 6 | Review content filter configuration; test edge cases (customer complaints about pricing fairness, regulatory questions, competitor comparisons); verify chatbot gracefully declines out-of-scope requests; document responsible AI assessment |
| Observability dashboards | DevOps Engineer | Week 6 | Application Insights dashboards: request volume, P50/P95/P99 latency, error rates, token usage per conversation, search relevance scores, feedback sentiment ratio |
| Alerting configuration | DevOps Engineer | Week 6 | Azure Monitor alerts: P95 latency > 5 seconds, error rate > 1%, OpenAI token consumption > 80% of budget, Container Apps replica count at max, Cosmos DB 429 throttling events |
| User acceptance testing | Project Manager, QA Engineer | Week 7 | UAT sessions with 5-8 CUSTOMER_NAME stakeholders (customer service leads, billing team, digital team); structured test scenarios; feedback collection and issue triage |
| Documentation | Solution Architect, Backend Developers | Week 7 | Operations runbook (incident response, scaling procedures, knowledge base update process); API documentation (OpenAPI spec published on APIM developer portal); knowledge base maintenance guide for CUSTOMER_NAME content team |
| Soft launch | Project Manager, DevOps Engineer | Week 7 | Limited release to 5% of web traffic via Front Door traffic splitting; monitor error rates, latency, and user feedback for 48 hours |
| Full production launch | Project Manager, DevOps Engineer | Week 7 | Ramp to 100% traffic; war room for first 24 hours; communication to CUSTOMER_NAME customer service team |

**Milestone (end of Week 7):** Production-ready chatbot live for Italian customers. All monitoring and alerting active. Operations runbook handed over to CUSTOMER_NAME operations team. Soft launch validated and full rollout complete.

---

### Phase 4 (Optional): Post-Launch Optimization (Week 8+)

Post-launch activities driven by real usage data. These are planned but prioritized based on observed customer behavior and business metrics.

| Task | Owner | Details |
|------|-------|---------|
| Conversation pattern analysis | AI/ML Engineer | Analyze top 100 most frequent questions; identify unanswered or poorly answered topics; prioritize knowledge base gaps |
| System prompt optimization | AI/ML Engineer | Refine prompt based on real conversation data; improve handling of edge cases identified during live usage |
| Knowledge base expansion | AI/ML Engineer, Project Manager | Add documents for newly identified topics; re-index and validate search quality; establish monthly knowledge base review cadence with CUSTOMER_NAME |
| Response caching for frequent queries | Backend Developer | Implement Azure Cache for Redis; cache responses for top 20 most common questions (TTL 24 hours); reduce OpenAI token consumption and latency for repeat queries |
| GPT-4o vs GPT-4o-mini routing ratio optimization | AI/ML Engineer, Backend Developer | Analyze production query classification accuracy; fine-tune complexity threshold for GPT-4o vs GPT-4o-mini split based on real usage data; A/B test adjusted routing ratios for quality, latency, and cost improvements |
| Multilingual expansion planning | Solution Architect, AI/ML Engineer | Assess requirements for next markets (if applicable); evaluate multilingual embedding models; plan knowledge base structure for multi-language support |
| CUSTOMER_NAME app/portal integration planning | Solution Architect, Frontend Developer | Design integration with existing CUSTOMER_NAME customer app; evaluate deep linking from bill view to chatbot; plan authenticated sessions for automatic bill context |

---

## Team Structure

| Role | Count | Responsibilities |
|------|-------|-----------------|
| Solution Architect | 1 | Architecture design, Azure service configuration, security review, responsible AI assessment, stakeholder alignment |
| Backend Developer | 2 | RAG pipeline implementation, FastAPI orchestrator, Cosmos DB integration, CUSTOMER_NAME billing API integration, streaming support |
| Frontend Developer | 1 | Chat widget development (TypeScript), UX design, responsive layout, feedback UI, accessibility |
| AI/ML Engineer | 1 | Prompt engineering, knowledge base preparation, document chunking and embedding, content filtering, RAG quality evaluation and optimization |
| DevOps Engineer | 1 | Infrastructure as Code (Bicep), CI/CD pipelines (GitHub Actions), monitoring dashboards, alerting, load testing infrastructure, autoscaling configuration |
| QA Engineer | 1 | Functional testing, integration testing, load testing execution, security testing, prompt injection testing, UAT coordination |
| Project Manager | 1 | Sprint planning, CUSTOMER_NAME stakeholder coordination, risk management, UAT scheduling, launch coordination, status reporting |
| **Total** | **8** | |

**Working model:** Two-week sprints aligned to delivery phases. Daily standups (15 minutes). Sprint demos with CUSTOMER_NAME stakeholders at the end of each phase. All team members co-located or available in CET timezone for overlap with CUSTOMER_NAME teams in Italy.

---

## Dependencies and Risks

### External Dependencies

| Dependency | Owner | Required By | Status Action |
|------------|-------|-------------|---------------|
| Azure subscription with sufficient OpenAI quota | CUSTOMER_NAME IT / Microsoft | Week 1 | Confirm subscription access and submit quota increase request on Day 1 |
| CUSTOMER_NAME tariff documentation and billing FAQs (Italian) | CUSTOMER_NAME Content Team | Week 2 | Project Manager to request documents in Phase 0; start with publicly available tariff information if delayed |
| CUSTOMER_NAME billing API access (test environment) | CUSTOMER_NAME IT | Week 4 | Request API credentials and test environment access in Week 1; develop against mock data until available |
| CUSTOMER_NAME billing API access (production) | CUSTOMER_NAME IT | Week 7 | Request production credentials in Week 5; validate connectivity from Container Apps VNet |
| CUSTOMER_NAME custom domain and SSL certificate | CUSTOMER_NAME IT | Week 4 | Needed for Front Door configuration; request in Week 1 |
| CUSTOMER_NAME DPO sign-off on data processing | CUSTOMER_NAME Legal/DPO | Week 6 | Engage in Phase 0; provide data flow documentation and DPIA draft by Week 3 |
| CUSTOMER_NAME stakeholders for UAT | CUSTOMER_NAME Business | Week 7 | Schedule UAT sessions by Week 5; provide async feedback form as fallback |

### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CUSTOMER_NAME billing API access delayed | High | High | Start with mock billing data built from sample bill structures; full API integration is Phase 2, allowing 4 weeks of buffer from project start; mock service contract defined in Week 1 |
| Knowledge base content not ready (Italian tariff docs, FAQs) | Medium | High | Work with CUSTOMER_NAME content team from Day 1; AI/ML Engineer starts with publicly available CUSTOMER_NAME tariff information from their website; content gathering runs parallel to infrastructure setup |
| Azure OpenAI quota insufficient for load testing | Low | Medium | Submit quota increase request on Day 1 of Phase 0; use GPT-4o-mini for development and initial testing to conserve GPT-4o quota; load test with realistic but reduced volume if quota is constrained |
| Content filtering too aggressive (blocks valid Italian energy terms) | Medium | Low | Test content filters early in Phase 1 with a corpus of 200+ real billing questions; apply for modified content filter configuration through Microsoft if standard filters block legitimate energy terminology |
| CUSTOMER_NAME stakeholder availability for UAT | Medium | Medium | Schedule UAT sessions two weeks in advance (Week 5 for Week 7 UAT); provide asynchronous feedback mechanism (recorded demo + structured feedback form) as alternative; identify backup stakeholders |
| GDPR compliance review delays launch | Low | High | Engage CUSTOMER_NAME DPO in Phase 0; document all data flows by Week 2; confirm no customer PII is stored in the knowledge base index; conversation history TTL set to 30 days; prepare DPIA draft by Week 3 |
| Italian language quality insufficient | Low | Medium | AI/ML Engineer creates evaluation dataset of 50 Italian billing questions in Week 2; native Italian speaker reviews chatbot responses during Phase 1; GPT-4o has strong Italian language capability |
| Azure service outage in primary region | Low | High | Container Apps and Cosmos DB support multi-region; for MVP launch, accept single-region with documented RTO of 4 hours; plan multi-region failover as post-launch enhancement |

---

## Key Milestones

| Week | Milestone | Deliverable | Gate Criteria |
|------|-----------|-------------|---------------|
| Week 1 | Infrastructure Ready | All Azure resources provisioned; CI/CD pipeline operational | Bicep deployment succeeds; Container App serves health check endpoint; all private endpoints validated |
| Week 3 | Core RAG Working | Chatbot answers general Italian billing questions via API | Evaluation dataset: relevance > 4.0/5.0, groundedness > 4.0/5.0; API responds in < 5 seconds P95; 50+ test questions answered correctly |
| Week 5 | Full Integration | End-to-end chatbot with billing data and embedded chat widget | Personalized bill explanation works for 10 test bills; chat widget loads in < 2 seconds; streaming responses functional; feedback capture operational |
| Week 7 | Production Launch | Live chatbot for Italian energy customers | Load test passes (50K queries/day); security review complete with no critical findings; UAT sign-off from CUSTOMER_NAME stakeholders; monitoring and alerting active |
| Week 8+ | Optimization | Performance tuning and expansion planning | Conversation pattern report delivered; top 10 knowledge gaps identified and addressed; caching strategy defined |

---

## Success Criteria

The following metrics define project success, measured over the first three months post-launch:

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| P95 response latency | < 5 seconds | Application Insights request duration percentile |
| Conversation completion rate | > 70% | Ratio of conversations with 2+ user messages to total conversations (Cosmos DB analytics) |
| User satisfaction (thumbs up rate) | > 75% | Thumbs up / (thumbs up + thumbs down) from feedback container in Cosmos DB |
| Call center billing inquiry volume reduction | > 15% within 3 months | CUSTOMER_NAME call center reporting; compare billing inquiry volume month-over-month against pre-launch baseline |
| Critical security incidents | Zero | Azure Security Center alerts; incident tracking |
| System availability | > 99.5% | Azure Front Door health probe success rate; calculated monthly |

---

## Communication Plan

| Cadence | Meeting | Attendees | Purpose |
|---------|---------|-----------|---------|
| Daily | Standup | Delivery team (8 people) | Blockers, progress, coordination |
| Weekly | Status Report | CUSTOMER_NAME stakeholders, delivery team leads | Progress against milestones, risk updates, decisions needed |
| Bi-weekly | Sprint Demo | CUSTOMER_NAME stakeholders, full delivery team | Demonstrate working software; gather feedback |
| Ad hoc | Technical Design Review | Solution Architect, Backend Developers, AI/ML Engineer | Resolve architectural decisions (prompt design, API contracts, search configuration) |
| Week 7 | UAT Sessions | CUSTOMER_NAME business stakeholders, QA Engineer | Structured acceptance testing with real billing scenarios |
| Week 7 | Launch Readiness Review | All stakeholders | Go/no-go decision based on gate criteria |

---

## Definition of Done

A feature or task is considered done when:

- Code is peer-reviewed and merged to the main branch
- Unit tests pass with minimum 80% coverage for new code
- Integration tests pass against Azure staging environment
- No critical or high-severity security findings from static analysis
- Documentation updated (API docs, runbook, or knowledge base guide as applicable)
- Deployed to staging environment and verified by QA Engineer
- Product Owner (CUSTOMER_NAME stakeholder or Project Manager) accepts the feature in sprint demo
