# Azure AI Best Practices Research Skill

This skill enforces mandatory research of Microsoft's official documentation before making any technology choice in AI solution architectures. AI models, hosting platforms, frameworks, and patterns evolve rapidly - your training data is stale by the time you use it. You MUST fetch live documentation to ensure recommendations match Microsoft's current guidance.

## When to Use

- Designing any AI solution architecture on Azure
- Selecting AI models (LLM, embedding, speech, vision, image generation)
- Choosing between hosting options (Microsoft Foundry vs standalone Azure OpenAI)
- Designing agent-based architectures
- Building RAG solutions
- Selecting SDKs and frameworks for AI development
- Writing solution-design.md, executive-brief.md, or cost-estimation.md

## MANDATORY Research Protocol

Before writing ANY architecture document, you MUST complete the following research steps. Do NOT rely on your training data for model names, versions, service names, or architectural patterns. Fetch the live documentation.

### Step 1: Current AI Model Landscape

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure`

Extract and record:

- Latest GPT model families available (as of early 2026: GPT-5.4, GPT-5.3, GPT-5.2, GPT-5.1, GPT-5, GPT-4.1 series, o-series reasoning models)
- Latest embedding models (text-embedding-3-large, text-embedding-3-small)
- Latest image generation models (gpt-image-1 series)
- Latest audio/speech models (gpt-audio, gpt-realtime series)
- Deployment types available (Global Standard, Global Provisioned, Data Zone Standard, Data Zone Provisioned, Standard, Batch)
- Region availability for the models you plan to recommend
- Which models are GA vs Preview (NEVER recommend preview models for production)
- Model retirement dates - do NOT recommend models approaching retirement

**Decision rules from this research:**

- Always recommend the latest GA model appropriate for the workload complexity
- For cost-sensitive workloads, recommend smaller models (mini, nano variants) when they meet quality requirements
- For reasoning-heavy tasks, consider o-series models (o4-mini, o3, codex-mini)
- For code generation, consider codex-optimized variants
- Include the specific model version string (e.g., `gpt-5.2 (2025-12-11)`) in architecture docs

### Step 2: Microsoft Foundry Platform (CRITICAL - Architecture Shift)

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-foundry`

**KEY ARCHITECTURAL DECISION:** Microsoft has consolidated AI services under **Microsoft Foundry**. The previous pattern of deploying standalone Azure OpenAI resources is being superseded. Your architecture MUST reflect this shift:

- **USE:** Microsoft Foundry as the central platform for AI model access, agent hosting, and AI application development
- **USE:** Foundry projects to organize AI workloads, models, and connections
- **USE:** Foundry Agent Service for hosting and managing AI agents (both prompt-based and code-based/hosted agents)
- **USE:** Foundry Models catalog for model discovery, deployment, and management
- **USE:** Foundry IQ for turnkey RAG with knowledge bases
- **AVOID:** Deploying standalone Azure Cognitive Services / Azure OpenAI resources unless there is a specific legacy integration requirement. Route through Foundry instead.

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/ai-foundry/agents/overview`

Extract:

- Foundry Agent Service capabilities (prompt-based agents, hosted agents, connected agents)
- Standard agent setup vs basic setup (standard = bring your own network, storage, search)
- Agent tools available (code interpreter, file search, Bing grounding, Azure AI Search, custom APIs)
- Supported models for agents

### Step 3: Reference Architecture Patterns

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-chat`

This is Microsoft's official baseline reference architecture for enterprise AI chat solutions. Extract and apply:

- Network topology (App Gateway + WAF, private endpoints, Azure Firewall for egress)
- Identity model (managed identities, Entra ID, RBAC per project)
- Data layer (Cosmos DB for agent state, AI Search for grounding, Storage for files)
- Deployment model (standard agent setup with customer-managed dependencies)
- Reliability patterns (zone redundancy, multi-region considerations)
- Security patterns (private link, NSGs, subnet segmentation, egress control)
- Cost optimization strategies

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-landing-zone`

For enterprise deployments in Azure Landing Zones - shared firewall, DDoS, hub-spoke networking.

### Step 4: Agent Orchestration Patterns

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns`

When the solution involves AI agents, research and apply the correct orchestration pattern:

- **Sequential** - linear pipeline, each agent processes previous output
- **Concurrent** - parallel fan-out/fan-in for independent analysis
- **Group chat** - conversational collaboration, maker-checker loops
- **Handoff** - dynamic delegation between specialists
- **Magentic** - open-ended planning with task ledger

**Decision rules:**

- Start simple: if a single agent with tools can solve it, don't over-engineer with multi-agent
- Use the pattern matching table in the doc to select the right orchestration
- Always design for human-in-the-loop at critical decision points

### Step 5: AI Development Frameworks

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview`

Microsoft Agent Framework is the current recommended SDK for building AI agents. It replaces both Semantic Kernel agent patterns and AutoGen. Extract:

- Agent vs Workflow decision criteria
- Supported model providers
- Integration with Foundry Agent Service
- Workflow orchestration types available

**Additional framework references to check based on use case:**

| Use Case | URL to Fetch |
|----------|-------------|
| RAG design guide | `https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-solution-design-and-evaluation-guide` |
| Vector search options | `https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/vector-search` |
| AI workload Well-Architected guidance | `https://learn.microsoft.com/en-us/azure/well-architected/ai/get-started` |
| Foundry SDKs overview | `https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/sdk-overview` |
| Model retirement schedule | `https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirements` |
| Azure OpenAI gateway patterns | `https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/azure-openai-gateway-multi-backend` |
| Content Safety | `https://learn.microsoft.com/en-us/azure/ai-services/content-safety/overview` |
| Responsible AI overview | `https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-use-of-ai-overview` |

### Step 6: Pricing and Deployment Types

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types`

Extract current deployment types and their trade-offs:

- **Global Standard** - best throughput, traffic routed globally
- **Global Provisioned** - reserved capacity, global routing
- **Data Zone Standard** - data residency within a geographic zone
- **Data Zone Provisioned** - reserved capacity with data residency
- **Standard (regional)** - single region, data stays in region
- **Provisioned Managed** - reserved capacity, single region

**Decision rules:**

- Use Global Standard for most workloads unless data residency is required
- Use Data Zone for EU/GDPR customers who need data to stay in-geography
- Use Provisioned for production workloads with predictable throughput needs
- Use Standard regional only when strict single-region data processing is mandated

**FETCH THIS URL:** `https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/`

For current pricing when building cost estimations.

### Step 7: Compute and Hosting Decisions (OPINIONATED)

This section provides an opinionated decision framework for where to host each component of an AI solution. These are not just options - they are ranked preferences. Follow them unless the customer has a specific constraint that forces a different choice, and document the justification when deviating.

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/compute-decision-tree`

**FETCH THIS URL:** `https://learn.microsoft.com/en-us/azure/container-apps/compare-options`

#### AI Agent Hosting - Decision Ladder

Use this ladder top-to-bottom. Stop at the first option that fits.

| Priority | Platform | When to Use | When to Skip |
|----------|----------|------------|--------------|
| 1st | **Foundry Agent Service (prompt-based)** | Agent behavior is defined by system prompt + tools + knowledge stores. No custom code in the agent loop. Single or connected agents with nondeterministic orchestration. | You need deterministic control over execution, custom models not supported by the service, or code-level agent logic. |
| 2nd | **Foundry Agent Service (hosted agents)** | You need code-driven agent logic (Microsoft Agent Framework, LangGraph, custom code) but want Foundry to manage infrastructure, scaling, state, and lifecycle. Your agent is containerized. | You need advanced networking (custom ingress, service mesh), GPU workloads on the agent tier, or fine-grained autoscaling. |
| 3rd | **Azure Container Apps** | You need full control over agent runtime, custom scaling rules (KEDA), sidecar containers, service mesh, or you run multiple microservices alongside agents. Kubernetes-style but without cluster management. | You need direct Kubernetes API access, custom operators, or node-level control. |
| 4th | **Azure Kubernetes Service (AKS)** | You need full Kubernetes control plane, custom operators, GPU node pools for local model inference, advanced networking (Cilium, Calico), or the customer has existing AKS investment. | The team lacks Kubernetes expertise and the requirements can be met by Container Apps or Foundry. |
| 5th | **Azure App Service** | You are hosting a simple agent API with no containerization needs, and it is essentially a web API that calls Foundry endpoints. | The agent needs scaling to zero, event-driven triggers, or container-native features. |

**Key principle:** Do NOT default to AKS. AKS is the right choice only when the team has Kubernetes expertise AND needs capabilities that Container Apps or Foundry Agent Service cannot provide. Recommending AKS to a team without K8s skills is an anti-pattern that creates operational burden.

#### Web Frontend / Chat UI - Decision Ladder

| Priority | Platform | When to Use |
|----------|----------|------------|
| 1st | **Azure App Service** | Default for web frontends. Microsoft's baseline reference architecture uses App Service for the chat UI. Managed TLS, deployment slots, autoscaling, VNet integration. Simplest operational model. |
| 2nd | **Azure Container Apps** | Frontend is containerized and deployed alongside other containerized microservices. You want a single environment for both frontend and backend. |
| 3rd | **Azure Static Web Apps** | SPA frontends (React, Vue, Angular) with API backends. No server-side rendering needed. |
| 4th | **AKS** | Only if the customer already runs their entire estate on AKS and wants consistency. |

#### Backend APIs and Middleware - Decision Ladder

| Priority | Platform | When to Use |
|----------|----------|------------|
| 1st | **Azure Container Apps** | Default for containerized APIs and microservices. Serverless scaling, Dapr integration, revision management, scale-to-zero. Low operational overhead. |
| 2nd | **Azure App Service** | Simple web APIs, non-containerized workloads, or teams comfortable with App Service. |
| 3rd | **AKS** | Complex microservice estates requiring service mesh, custom networking, or GPU workloads. |

#### Event-Driven / Background Processing - Decision Ladder

| Priority | Platform | When to Use |
|----------|----------|------------|
| 1st | **Azure Functions** | Event-driven processing, triggers (queue, HTTP, timer, Cosmos DB change feed), short-lived executions. Flex Consumption plan for VNet integration and scale. |
| 2nd | **Azure Container Apps Jobs** | Longer-running background jobs, scheduled tasks, cron-style processing that exceeds function timeout limits. |
| 3rd | **Azure Container Apps** | Always-on background workers, message processors with custom scaling rules. |

#### Data Ingestion and Processing Pipelines - Decision Ladder

| Priority | Platform | When to Use |
|----------|----------|------------|
| 1st | **Azure Functions** | Lightweight ETL, document processing triggers, change feed processing. |
| 2nd | **Azure Container Apps Jobs** | Batch processing, document chunking pipelines, embedding generation at scale. |
| 3rd | **Azure Batch** | Large-scale parallel compute for massive document ingestion or model training data preparation. |

#### API Gateway / Model Access Layer

| Priority | Platform | When to Use |
|----------|----------|------------|
| 1st | **Azure API Management** | Rate limiting, authentication, multi-model routing, circuit breaking, caching, developer portal. Use in front of Foundry endpoints for production workloads. |
| 2nd | **Direct Foundry endpoint** | Simple architectures, single model, internal-only access where APIM overhead is not justified. |

**FETCH THIS URL (if API gateway pattern is relevant):** `https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/azure-openai-gateway-multi-backend`

#### Decision Summary Table

The following table provides a quick lookup for common AI solution components:

| Component | Default Choice | Requires Justification to Override |
|-----------|---------------|-----------------------------------|
| AI agents (no custom code) | Foundry Agent Service (prompt-based) | Yes |
| AI agents (custom code) | Foundry Agent Service (hosted) | Yes |
| Chat UI / web frontend | Azure App Service | No |
| Backend APIs | Azure Container Apps | No |
| Event processing | Azure Functions (Flex Consumption) | No |
| Background jobs | Azure Container Apps Jobs | No |
| Model access gateway | Azure API Management | No |
| Vector search / grounding | Azure AI Search | Yes |
| Agent state / memory | Azure Cosmos DB | Yes |
| File storage | Azure Storage (Blob) | Yes |
| Identity | Microsoft Entra ID + managed identities | Yes - never use API keys |
| Secrets | Azure Key Vault | Yes |
| Monitoring | Azure Monitor + Application Insights | Yes |
| CI/CD | GitHub Actions or Azure DevOps | No |

#### Compute Anti-Patterns

| Anti-Pattern | Why it is Wrong | Correct Choice |
|-------------|----------------|----------------|
| Defaulting to AKS for everything | Operational overhead, requires K8s expertise the customer may not have | Container Apps or Foundry Agent Service |
| Running agents on Azure Functions | Functions are for short-lived event processing, not long-running agent conversations | Foundry Agent Service or Container Apps |
| Deploying a standalone VM to host an agent | No auto-scaling, manual patching, no managed identity integration | Any PaaS option above |
| Using App Service for background workers | App Service is for request/response web workloads, not background processing | Container Apps Jobs or Azure Functions |
| Hosting AI agents on Azure Bot Service | Bot Service is for channel integration (Teams, Slack), not AI agent orchestration | Foundry Agent Service |
| Skipping API Management for multi-model setups | No rate limiting, no circuit breaking, no observability at the gateway level | Azure API Management |
| Using ACI for production workloads | No orchestration, no auto-scaling, no revision management | Container Apps |

## Research Output Format

After completing research, document your findings in a concise research summary block at the top of your working context (not in the output files). Format:

```text
## Research Summary (fetched [date])

### Models Selected
- Primary LLM: [model] ([version]) - [why]
- Embedding: [model] - [why]
- Other: [models if needed]

### Platform
- Hosting: Microsoft Foundry (project: [region])
- Agent hosting: Foundry Agent Service [standard/basic] setup
- Deployment type: [type] - [why]

### Compute Decisions
- Agent tier: [Foundry Agent Service / Container Apps / AKS] - [why]
- Web frontend: [App Service / Container Apps / Static Web Apps] - [why]
- Backend APIs: [Container Apps / App Service] - [why]
- Event processing: [Azure Functions / Container Apps Jobs] - [why]
- API gateway: [APIM / direct] - [why]

### Architecture Pattern
- [Reference architecture used]
- [Agent orchestration pattern if applicable]

### Framework
- [SDK/framework selected] - [why]

### Key Findings
- [Any surprises or changes from expected patterns]
- [Deprecated services or models to avoid]
- [Region constraints or availability issues]
```

## Anti-Patterns to Catch and Fix

If you find yourself writing any of these, STOP and re-research:

| Anti-Pattern | Correct Pattern |
|-------------|----------------|
| "Deploy an Azure OpenAI resource" as standalone | Use Microsoft Foundry project with model deployments |
| Recommending GPT-4o or GPT-4 Turbo as primary model | Check latest models - GPT-5.x series is current |
| Using `text-embedding-ada-002` | Use `text-embedding-3-large` or `text-embedding-3-small` |
| Recommending Azure Cognitive Services (old branding) | Use "Foundry Tools" or specific service names |
| Using Semantic Kernel or AutoGen for new projects | Use Microsoft Agent Framework |
| "Azure AI Studio" (old name) | Use "Microsoft Foundry" / "Foundry portal" |
| "Azure OpenAI Studio" (old name) | Use "Microsoft Foundry portal" |
| Recommending DALL-E 3 for image generation | Check latest: gpt-image-1 series is current |
| Using Azure Bot Service for AI agents | Use Foundry Agent Service |
| Hardcoding model names without version strings | Always include version (e.g., `gpt-5.2 (2025-12-11)`) |
| Recommending preview models for production | Only recommend GA models for production workloads |
| Defaulting to AKS without K8s expertise on the team | Use Container Apps or Foundry Agent Service |
| Running AI agents on Azure Functions | Use Foundry Agent Service or Container Apps |
| Using Azure Bot Service for AI agents | Use Foundry Agent Service |
| Skipping APIM for multi-model production setups | Use Azure API Management as gateway |

## Minimum Research Checklist

Before declaring architecture research complete, verify ALL boxes:

- [ ] Fetched current model catalog and selected specific model versions
- [ ] Confirmed models are GA (not preview) for production recommendations
- [ ] Confirmed model availability in target deployment region(s)
- [ ] Architecture uses Microsoft Foundry as the AI platform (not standalone AOAI)
- [ ] Checked reference architecture patterns and applied relevant ones
- [ ] Selected appropriate agent orchestration pattern (if agents are involved)
- [ ] Verified framework recommendation is current (Agent Framework, not SK/AutoGen for new builds)
- [ ] Checked deployment type matches data residency and throughput requirements
- [ ] Fetched current pricing for cost estimation accuracy
- [ ] Checked model retirement dates - no models approaching end-of-life
- [ ] Verified Responsible AI requirements are addressed
- [ ] Selected compute platform for each component using the decision ladders (Step 7)
- [ ] Justified any deviation from default compute choices (e.g., AKS instead of Container Apps)
- [ ] Verified the customer team has skills for the selected compute platform (do not recommend AKS to teams without K8s expertise)
