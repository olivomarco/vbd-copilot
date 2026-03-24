## Demo 3 - RAG Pipeline and Architecture Walkthrough (15 min)

**Demo Access**: Jump box VM `CUSTOMER_NAME-bill-jumpbox-dev` via Azure Bastion (browser-based RDP, no public VM IP). From the jump box, private DNS resolves `CUSTOMER_NAME-bill-search-dev.search.windows.net` and `CUSTOMER_NAME-bill-cosmos-dev.documents.azure.com` - both services have `publicNetworkAccess: Disabled` in their Bicep definitions. Everything in this demo runs from the jump box browser or jump box terminal.

---

> **WOW Moment**
>
> Open AI Search "Search Explorer" and fire the same hybrid query the chatbot just ran against `CUSTOMER_NAME-knowledge`. Watch three scoring columns appear in the JSON response: `@search.score` (BM25 keyword match), the vector cosine similarity folded in by the hybrid ranker, and `@search.reranker_score` which is the semantic model's final verdict. The document that wins is not always the one with the highest keyword score. That re-ranking step is what separates relevant from merely matching. Then open Cosmos DB Data Explorer, find the `messages` container, and click the document from Demo 2. The field `modelUsed: "gpt-4o"` is sitting right there - the system recorded exactly which model answered, and why, on every single turn.

---

### Prerequisites

- Bastion browser session still active from Demo 2 (keep that tab open - the `SESSION_ID` from Demo 2 is needed in Step 3)
- `demo-3-rag-walkthrough.sh` staged on the jump box desktop and already marked executable
- Azure Portal already signed in on the jump box browser (Entra ID credentials with Reader + Search Index Data Reader + Cosmos DB Built-in Data Reader roles)
- `jq` installed on the jump box terminal (verify: `jq --version`)
- Note the `SESSION_ID` value from the Demo 2 API response or from the Container Apps log visible in Step 4

---

### Step 1 - Confirm Jump Box Access via Bastion (1 min)

Switch to the Azure Bastion tab in the presenter's browser. The jump box desktop should be live from the prior demo. Open a terminal (Windows Terminal or Git Bash) on the jump box.

> **Say this**: "Everything you saw in the last fifteen minutes - the streaming tokens, the session state, the billing lookup - none of that touched the public internet. The Container App, AI Search, Cosmos DB, Azure OpenAI: all private endpoints inside a 10.0.0.0/16 VNet. From your laptop right now, you cannot reach any of those service URLs. This jump box is the only thing with DNS resolution into that network. In production, this is your operations team's access path, or your CI/CD pipeline. Same story, tighter controls."

Open a new browser tab on the jump box. Go to `https://portal.azure.com`.

---

### Step 2 - Azure AI Search: Index Fields and Search Explorer (6 min)

#### 2a - Open the Index

From the jump box Azure Portal tab, go to **AI Search** -> **CUSTOMER_NAME-bill-search-dev** -> **Indexes** -> **CUSTOMER_NAME-knowledge**.

Click the **Fields** tab.

> **Say this**: "Here is the raw anatomy of the knowledge base. Every chunk of CUSTOMER_NAME documentation lands in one of these fields. `content` is the text - a paragraph-sized piece of a tariff guide or FAQ document. `sourceDocument` tells us which file it came from. `category` is a label we attach at indexing time: regulatory, tariff, FAQ. And then there is `contentVector` - that is a 1,536-dimensional floating-point array, one number per dimension, representing the semantic meaning of that chunk as understood by `text-embedding-3-small`. When a user asks a question, we embed the question into that same 1,536-dimension space and look for chunks that are geometrically close. That is the vector part of hybrid search."

Point to `contentVector` field. Mention it is 1,536 dimensions, matching the output of the `text-embedding-3-small` deployment visible in Step 5.

#### 2b - Run a Live Query in Search Explorer

Click the **Search Explorer** tab. Switch to **JSON view** and paste the following query body:

```json
{
  "search": "oneri di sistema",
  "queryType": "semantic",
  "semanticConfiguration": "default",
  "top": 3,
  "select": "content,sourceDocument,category,title",
  "vectorQueries": [
    {
      "kind": "text",
      "text": "oneri di sistema",
      "fields": "contentVector",
      "k": 3
    }
  ]
}
```

Click **Search**.

> **Say this**: "This is the exact same query shape that `search_service.py` fires when a user types a question in the chat. The `search` field is the BM25 keyword path. The `vectorQueries` array is the semantic embedding path. AI Search runs both in parallel, merges the ranked lists using Reciprocal Rank Fusion, and then passes the merged top results through the semantic re-ranker - that is a cross-encoder transformer model Microsoft runs on the S1 tier. The score you care about is `@search.reranker_score`. Range is 0 to 4. Anything above 2.5 is a confident match."

Scroll through the JSON response. Point to `@search.reranker_score` on the first result.

> **Say this**: "Look at that score. Now look at result two and three. The gap between first and second is what determines whether the answer sounds authoritative or hedging. This is not keyword matching - it is meaning matching. And the `sourceDocument` field tells your compliance team exactly which approved document that chunk came from."

**Expected output**: Three result objects, each with `content`, `sourceDocument`, `category`, `title`, and `@search.reranker_score` between 0 and 4. First result score is typically 2.8 or higher for this query.

---

### Step 3 - Cosmos DB Data Explorer: Sessions and Messages (4 min)

#### 3a - Open the Sessions Container

From the jump box Azure Portal tab, open a new tab. Go to **Cosmos DB** -> **CUSTOMER_NAME-bill-cosmos-dev** -> **Data Explorer**.

Expand **billexplainer** -> **sessions** -> **Items**.

> **Say this**: "The `billexplainer` database has three containers: `sessions`, `messages`, and `feedback`. Every partition key is `/sessionId` - which means all data for a given conversation lives in one physical partition, making reads fast and GDPR deletion clean. When a user requests erasure, one targeted delete clears the session document, all its messages, and all its feedback thumbs-up or thumbs-down in a single logical operation. No scatter-gather across multiple partitions."

#### 3b - Find the Demo 2 Session

In the query bar, run:

```sql
SELECT * FROM c WHERE c.id = "SESSION_ID_FROM_DEMO_2"
```

Replace `SESSION_ID_FROM_DEMO_2` with the session ID noted from Demo 2.

Click the session document to expand it.

> **Say this**: "There it is. `createdAt`, `lastActive`, `messageCount`, and `billRef: IT001-2024-DEMO`. Every field written by the `ConversationManager` class in the application. Notice there are no secrets here - no API keys, no bearer tokens. The application authenticates to Cosmos DB using `DefaultAzureCredential`, which resolves to the Container App's system-assigned managed identity. The Bicep sets `disableLocalAuth: true` on this account - so connection strings do not exist. Full stop."

#### 3c - Inspect the Messages Container

Switch to **billexplainer** -> **messages** -> **Items**. Query by session ID:

```sql
SELECT * FROM c WHERE c.sessionId = "SESSION_ID_FROM_DEMO_2" ORDER BY c.timestamp ASC
```

Click an assistant message document.

> **Say this**: "See `modelUsed: gpt-4o`. That field was written by the `save_message` call in the chat router, pulled directly from the `ModelClassification` object the RAG pipeline returns. Every assistant message carries the model name, `promptTokens`, and `completionTokens`. Your finance team can aggregate that by `modelUsed` and get a precise cost breakdown per conversation type - no guesswork."

Point to the TTL value.

> **Say this**: "The `messages` container has a default TTL of 2,592,000 seconds - that is exactly 30 days. After 30 days, Cosmos DB deletes these documents automatically at the storage layer. No cron job, no retention script. GDPR compliance built into the infrastructure definition. The `sessions` container TTL is 86,400 seconds - 24 hours. A session that goes cold is gone the next day."

**Expected output**: Message documents with fields `id`, `sessionId`, `role`, `content`, `timestamp`, `modelUsed`, `promptTokens`, `completionTokens`.

---

### Step 4 - Container Apps Log Stream (2 min)

The Container App running the RAG pipeline is `CUSTOMER_NAME-bill-ca-dev`. The script discovers the name via `az containerapp list`, but you can also open it directly in the Azure Portal from the jump box.

Open the jump box terminal. Run the companion script's log section, or run directly:

```bash
export RESOURCE_GROUP="rg-CUSTOMER_NAME-bill-dev"
export RESOURCE_PREFIX="CUSTOMER_NAME-bill"
export ENVIRONMENT="dev"

CA_NAME=$(az containerapp list \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?contains(name, '${RESOURCE_PREFIX}')].name | [0]" \
  -o tsv --only-show-errors)

az containerapp logs show \
  --name "$CA_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --tail 20 \
  --only-show-errors
```

> **Say this**: "This is the live log stream from the Container App, pulled straight from the Log Analytics workspace the Container Apps Environment writes to. Find the line that starts with `Pipeline:`. It reads `session=<id> model=gpt-4o-mini needs_billing=False` - or `gpt-4o` and `needs_billing=True` if it was the bill lookup. That log line comes from `rag_pipeline.py`, line 72, and it fires before a single token is sent to OpenAI. The routing decision is already made. Then look for `Hybrid search returned 5 results` - that is `search_service.py` confirming how many chunks went into the prompt context."

Point to both log lines in the terminal output.

> **Say this**: "Every one of these log lines flows into Application Insights as a trace. In Demo 4 you will see those same lines queryable in Kusto, correlated with token counts and end-to-end latency. This is not just logging - it is the full observability chain."

**Expected log lines** (approximate):
```
Pipeline: session=<uuid> model=gpt-4o-mini needs_billing=False
Hybrid search returned 5 results for query='oneri di sistema...'
```

---

### Step 5 - Azure OpenAI Model Deployments (2 min)

From the jump box Azure Portal tab, go to **Azure OpenAI** -> **CUSTOMER_NAME-bill-oai-dev** -> **Model Deployments**.

> **Say this**: "Three deployments. `gpt-4o` at 20k TPM, `gpt-4o-mini` at 50k TPM, `text-embedding-3-small` at 50k TPM. The capacity numbers are the demo overlay values - production is higher. Notice the SKU column says `DataZoneStandard` on all three. That is not the standard global deployment. Data Zone Standard means Microsoft commits to keeping your data within the EU data boundary. Prompts, completions, embeddings - none of that leaves the European Azure geography. This is the answer to your GDPR data residency question, and it is a property of the deployment SKU, not a policy document."

Point to the `DataZoneStandard` SKU label in the portal.

> **Say this**: "And the routing logic that decides which of these two generation models gets used is 30 lines of Python. Open `model_router.py` in your IDE and you will find four rules: bill reference present, message longer than 200 characters, Italian numerical-comparison keywords like `confronto` or `differenza`, or more than five turns in the conversation. Any one of those triggers GPT-4o. Everything else goes to GPT-4o-mini. That is roughly 80 percent of traffic on the cheaper model, with zero quality compromise for the common FAQ case."

---

### Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Search Explorer returns `403 Forbidden` | Jump box managed identity or user account missing `Search Index Data Reader` role on `CUSTOMER_NAME-bill-search-dev` | In Azure Portal, go to AI Search -> Access Control (IAM) -> add `Search Index Data Reader` to the signed-in account. Role propagation takes up to 2 minutes. |
| `@search.reranker_score` absent from results | Query sent to the wrong tier or semantic configuration name mismatch | Confirm `semanticConfiguration` is set to `"default"` - this matches the `semantic_configuration_name="default"` in `search_service.py`. Also confirm the service is S1 (Standard), not Free tier, which does not include semantic ranker. |
| Cosmos DB Data Explorer shows empty `sessions` container | Demo 2 was run before the seed script populated the containers, or session ID was not saved | Re-run Demo 2 end-to-end via the companion script to generate a fresh session. Or query `SELECT TOP 5 * FROM c ORDER BY c._ts DESC` to find the most recent item. |
| `az containerapp logs show` returns no output | Container App scaled to zero replicas between demos | Send a health check request first: `curl -sk https://<CA_FQDN>/health` from the jump box to wake the replica, then re-run the logs command after 15 seconds. |
| Log lines show `needs_billing=True` for a general FAQ | Bill reference lingered in the session from Demo 2 | This is correct behaviour - the session from Demo 2 carries `billRef`, so `model_router.py` Rule 1 fires. Start a fresh session for the FAQ query in the terminal, or explain to the audience that this is intentional session state. |
| Python inline Cosmos DB query fails with `ModuleNotFoundError` | `azure-cosmos` or `azure-identity` not installed on jump box | Run `pip install azure-cosmos azure-identity --quiet` on the jump box terminal before the demo. The companion script checks for this. |

---

### Transition to Demo 4

You have just seen the full data path: a query enters the RAG pipeline, hits AI Search for hybrid retrieval, passes through the model router, generates tokens via a GDPR-compliant Data Zone deployment, and writes every turn to Cosmos DB with a 30-day TTL. The next question is: how do you know when something goes wrong, how much it all costs per day, and what happens when someone tries to abuse the API? That is Demo 4 - Application Insights, APIM rate limits, and the WAF in action.

