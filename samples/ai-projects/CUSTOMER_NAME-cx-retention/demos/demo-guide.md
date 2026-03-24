# CUSTOMER_NAME Intelligent Bill Explainer - Demo Guide

| Field | Value |
|---|---|
| **Customer** | CUSTOMER_NAME |
| **Project** | Intelligent Bill Explainer - AI Chatbot |
| **Demo Level** | L300 |
| **Target Audience** | Technical Decision Makers (CTOs, IT Directors) |
| **Total Duration** | ~60 minutes (4 x 15 min) |
| **Demo Count** | 4 |
| **Region** | Sweden Central |
| **Access Strategy** | Hybrid: Front Door (public chat widget) + Azure Bastion jump box (backend inspection) |

---

## Quick Reference

| Demo | Title | Duration | Entry Point | Companion Script |
|---|---|---|---|---|
| 1 | Live Chat - General FAQ | 15 min | Browser -> Front Door hostname | `demo-1-faq-chat.sh` |
| 2 | Live Chat - Personalised Bill Lookup | 15 min | Browser -> Front Door (same session) | `demo-2-bill-lookup.sh` |
| 3 | RAG Pipeline and Architecture Walkthrough | 15 min | Jump box via Azure Bastion | `demo-3-rag-walkthrough.sh` |
| 4 | Observability, Cost Controls, and Security Posture | 15 min | Azure portal + jump box terminal | `demo-4-rate-limit-and-observability.sh` |
| Setup | Billing API Stub Setup | 1-time | Jump box terminal | `billing-stub-setup.sh` |

---

## Prerequisites

- Azure subscription with the CUSTOMER_NAME Bill Explainer infrastructure deployed (`scripts/deploy.sh` completed for `dev` environment)
- Demo overlay deployed: `az deployment group create --resource-group <rg> --template-file demos/demo-access.bicep --parameters demos/demo.bicepparam`
- Demo data seeded: `RESOURCE_GROUP=<rg> SUBSCRIPTION_ID=<sub> bash demos/seed-demo-data.sh`
- AI Search indexer completed (seed script waits and confirms)
- Azure Bastion and jump box VM running (deployed by demo overlay)
- Presenter laptop: modern browser, Azure CLI logged in, `jq` installed
- Jump box: Edge/Chrome browser, Azure CLI, Python 3.11, `jq`, `curl` available (pre-installed on Windows Server 2022 image + seed script installs remaining tools)
- Billing API stub started on jump box (run `billing-stub-setup.sh start` from the Bastion session - see Step 5 below)

## Demo Infrastructure Setup

### Step 1 - Deploy demo access overlay
```bash
az deployment group create \
  --resource-group <your-resource-group> \
  --template-file outputs/ai-projects/CUSTOMER_NAME-cx-retention/demos/demo-access.bicep \
  --parameters outputs/ai-projects/CUSTOMER_NAME-cx-retention/demos/demo.bicepparam \
  --parameters adminPassword="<secure-password>"
```

### Step 2 - Seed demo data
```bash
export RESOURCE_GROUP="<your-resource-group>"
export SUBSCRIPTION_ID="<your-subscription-id>"
bash outputs/ai-projects/CUSTOMER_NAME-cx-retention/demos/seed-demo-data.sh
```

### Step 3 - Connect to jump box via Bastion
1. Open Azure portal on your laptop
2. Navigate to the resource group -> `CUSTOMER_NAME-bill-jumpbox-dev` VM
3. Click "Connect" -> "Bastion"
4. Username: `demoadmin`, Password: the password set in Step 1
5. A browser-based RDP session opens - no VPN or public IP needed

### Step 4 - Pre-open browser tabs (both laptop and jump box)
Laptop:
- Tab 1: `https://<frontdoor-hostname>/` (chat widget - load it now to verify)
- Tab 2: Azure portal -> `CUSTOMER_NAME-bill-appi-dev` Application Insights -> Live Metrics
- Tab 3: Azure portal -> `CUSTOMER_NAME-bill-apim-dev` API Management
- Tab 4: Azure portal -> Front Door -> WAF Policy

Jump box (in the Bastion RDP session):
- Tab 1: Azure portal -> `CUSTOMER_NAME-bill-search-dev` AI Search -> Indexes -> `CUSTOMER_NAME-knowledge`
- Tab 2: Azure portal -> `CUSTOMER_NAME-bill-cosmos-dev` Cosmos DB -> Data Explorer
- Tab 3: Azure portal -> `CUSTOMER_NAME-bill-ca-dev` Container Apps -> Log stream

### Step 5 - Start the billing API stub on the jump box

In the Bastion RDP session (jump box), open a terminal (PowerShell or Command Prompt) and run:

```bash
bash ~/billing-stub/billing-stub-setup.sh start
```

Wait for the confirmation message `Billing stub is running on port 8080`. Verify:

```bash
bash ~/billing-stub/billing-stub-setup.sh test
```

You should see the IT001-2024-DEMO bill JSON with total_amount: 187.43.

Note: The seed script (`seed-demo-data.sh`) uploads the stub script to the jump box automatically. If it is not present, copy `demos/billing-stub-setup.sh` to the jump box manually via Bastion file transfer.

---

## Demo 1 - Live Chat: General FAQ (15 min)

> **WOW Moment**: The AI streams an Italian-language explanation of "oneri di sistema" charges sourced directly from CUSTOMER_NAME's seeded tariff documentation - token by token, in real time - while GPT-4o-mini handles it for a fraction of what GPT-4o would cost.

---

### Demo Access

Everything in this demo runs from **your laptop browser**. No VPN, no Bastion, no jump box. Azure Front Door Premium is the public entry point. The chat widget is served at the Front Door hostname and calls back to the same origin for the API.

You will need two browser tabs open before you start:

- **Tab 1** - Chat widget: `https://${FRONT_DOOR_HOSTNAME}/`
- **Tab 2** - Azure portal, Application Insights resource, Logs blade (pre-opened and ready)

---

### Prerequisites

- `FRONT_DOOR_HOSTNAME` confirmed - run `az afd endpoint list --resource-group <rg> --profile-name <profile> --query "[0].hostName" -o tsv` from Azure Cloud Shell if you don't have it written down
- Chat widget loads without error at the Front Door URL (grey CUSTOMER_NAME header, white chat area, welcome message visible)
- AI Search indexer has completed - the knowledge base contains at least the five seed documents listed in the demo plan (`tariff-guide-2024.md`, `bill-structure-guide.md`, `faq-billing-2024.md`, `regulatory-charges-2024.md`, `payment-options.md`)
- Application Insights Logs blade is open in a second tab, query editor cleared
- APIM subscription key on hand in case you switch to the terminal path mid-demo

---

### Steps

---

**Step 1 - Confirm the system is live (1 min)**

From your laptop browser, open a new tab and go to:

```
https://${FRONT_DOOR_HOSTNAME}/api/v1/health
```

You should see:

```json
{"status": "ok", "services": {"search": true, "cosmos": true, "openai": true}}
```

> **Say this:**
>
> "Before we do anything else - let me show you the health endpoint. This is `GET /api/v1/health` defined in `health.py` inside the FastAPI app running on Azure Container Apps. It checks all three downstream dependencies in parallel: AI Search, Cosmos DB, and OpenAI. If any one of them is unreachable, the field flips to false. Right now everything is green, which means the private endpoints for all three services are up and the Managed Identity has the right role assignments. No keys anywhere in that check. Zero."

**Expected result:** All three service fields show `true`. If any show `false`, check the troubleshooting table before continuing.

---

**Step 2 - Open the chat widget (1 min)**

Switch to Tab 1 (`https://${FRONT_DOOR_HOSTNAME}/`).

The page loads `index.html` served by the Container Apps frontend path. You should see the CUSTOMER_NAME header, an empty chat area, and this welcome message already displayed:

> *"Ciao! Sono l'assistente virtuale di CUSTOMER_NAME. Posso aiutarti a capire la tua bolletta energetica. Puoi farmi domande generali sulle tariffe o inserire il numero della tua bolletta per una spiegazione personalizzata."*

> **Say this:**
>
> "This is the widget your customers would see embedded in My CUSTOMER_NAME or on the support portal. It is three static files - `index.html`, `chat.js`, and `styles.css` - served from the Container Apps instance through APIM and Front Door. There is no external CDN, no third-party dependencies, no npm bundle. The whole widget is plain JavaScript. What matters here is that the API call in `chat.js` goes back to the same origin, which means Front Door handles HTTPS termination, WAF inspection, and routing all in one hop. The customer's request never touches the APIM gateway URL directly."

**What to point out in the UI:** The absence of a bill reference badge in the top bar. That input is hidden. This is the general FAQ mode - no bill reference, no personalised data. That matters in a moment.

---

**Step 3 - Ask the main demo question: "oneri di sistema" (4 min)**

Click the chat input box and type exactly:

```
Cosa sono gli oneri di sistema sulla mia bolletta?
```

Press Enter. Do not click away.

**Watch for:** Three animated dots (the typing indicator) appear immediately while the backend is running. The typing indicator is rendered by `_showTypingIndicator()` in `chat.js` - it shows up before the first token arrives, so there is no blank-screen moment.

Within 1-2 seconds, tokens start appearing. Watch them fill in word by word.

> **Say this (while the response is streaming):**
>
> "Watch what is happening technically. The browser sent a single POST to `/api/v1/chat` - that is it. The request body is just: a message string, no session ID yet, no bill reference. On the server side, FastAPI's `chat.py` router called `EventSourceResponse` from `sse_starlette`. Every token the OpenAI deployment returns gets wrapped in a JSON event - `data: {\"token\": \"...\", \"done\": false}` - and written to the HTTP response stream immediately. The browser is reading that stream with the Fetch API and a `ReadableStream` reader. This is not the old EventSource API - it is POST-based streaming, which means APIM rate limiting and WAF inspection apply to every connection."

> **Say this (after the full response is visible):**
>
> "Look at the source citation at the bottom of that answer. The model said something like 'Secondo la guida tariffaria...' or 'Come indicato nel documento normativo...'. That is not invented politeness. The system prompt in `system_prompt.py` instructs the model to always name the document category when it cites a source - and the RAG pipeline in `rag_pipeline.py` injected up to five document chunks from AI Search into that system prompt before the model ever saw your question. The answer is grounded. If the knowledge base did not have it, the model would say so and point the customer to the call centre."

**What to point out in the UI:** Below the answer text, there is a small disclaimer: *"Risposta generata dall'AI - Per informazioni ufficiali contattare il servizio clienti CUSTOMER_NAME"*. And next to it, thumbs-up and thumbs-down buttons.

> **Say this:**
>
> "The disclaimer is hardcoded in `chat.js` - it appears on every assistant message. Not configurable, not optional. Legal reviewed that string and it goes out on every response. The thumbs-up/down buttons post to `POST /api/v1/chat/feedback`, which writes a record to the `feedback` container in Cosmos DB. You now have a training signal for every interaction, stored in your own tenancy, ready for future fine-tuning or RLHF."

**Note to presenter:** The session ID is now stored in browser `localStorage` under the key `CUSTOMER_NAME_session_id`. The `_saveSession()` method in `chat.js` does this on the first `done: true` event. Every subsequent message in this tab will carry that session ID, and the conversation history will be loaded from Cosmos DB.

---

**Step 4 - Show the SSE stream live in DevTools (2 min)**

Open browser DevTools (F12 on Chrome/Edge). Go to the **Network** tab. Filter by **Fetch/XHR**.

Type the second question in the chat input - do not press Enter yet:

```
Come si calcola la quota potenza?
```

Now press Enter, and immediately watch the Network tab.

You will see a POST request to `/api/v1/chat`. Click it. In the **Response** or **Preview** pane, select **EventStream** if the tab is available (Chrome shows this for SSE responses). You will see a list of individual SSE events scrolling in as they arrive.

> **Say this:**
>
> "Here is what the browser is actually receiving. Each line is `data: {\"token\": \"...\", \"done\": false}`. The response Content-Type is `text/event-stream`. The connection stays open until the server sends the final event with `done: true`, which also carries the `session_id` and `message_id` for this exchange. Notice the request headers - you can see `Content-Type: application/json` on the outgoing side and no API key. The key is handled upstream by APIM, which validated the subscription key before this request ever reached Container Apps."

> **Say this:**
>
> "Why does this matter? Because streaming cuts the perceived latency by a factor of three or four. The model takes 4-6 seconds to generate a full answer to a question like this. With streaming, the customer reads the first sentence in under a second. That is a direct impact on support call deflection rates - which is exactly what CUSTOMER_NAME is optimising for here."

**Expected result:** The answer explains quota potenza in plain Italian, likely with bullet points (the markdown renderer in `chat.js` converts `- item` lines to `<ul><li>` HTML in real time).

---

**Step 5 - Verify model routing in Application Insights (2 min)**

Switch to Tab 2 (Application Insights Logs blade).

Paste and run this Kusto query:

```kusto
traces
| where timestamp > ago(5m)
| where message contains "Query classified"
| project timestamp, message
| order by timestamp desc
| take 10
```

> **Say this:**
>
> "The `model_router.py` service logs every routing decision as a structured trace. You should see entries like: `Query classified: model=gpt-4o-mini needs_billing=False reasoning=Simple FAQ query -- using cost-effective model`. That reasoning string is computed in real time for each request based on four rules: message length, presence of a bill reference, specific Italian keywords like 'confronto' or 'calcolo', and conversation turn depth. Right now all three of our questions are short, have no bill reference, and contain no numerical-comparison keywords. So the router picked GPT-4o-mini for all of them. That is the 80% cost path - and you can verify it right here without touching any code."

**Expected result:** You see 2-3 trace entries with `model=gpt-4o-mini` and `reasoning=Simple FAQ query -- using cost-effective model`. If you see `model=gpt-4o`, check whether the question text accidentally contained a keyword from `model_router.py`'s `_COMPLEX_KEYWORDS` set (words like `calcolo`, `confronto`, `differenza`).

---

**Step 6 - Third question and feedback demonstration (2 min)**

Switch back to Tab 1. Type the third question:

```
Cosa significa il codice POD?
```

Press Enter. Let it stream. After it completes, click the **thumbs-up button** on the response.

You should see "Grazie per il feedback!" appear next to the buttons.

> **Say this:**
>
> "POD - Punto di Prelievo - is one of the most common questions CUSTOMER_NAME's contact centre receives. The answer just came from `bill-structure-guide.md` in the knowledge base, retrieved via a hybrid search combining BM25 keyword matching and vector similarity. The `SearchService` in `search_service.py` ran both in parallel, then sent the top five chunks through Azure AI Search's semantic ranker to re-order them by contextual relevance before they hit the model. That is why the answer reads coherently and doesn't just regurgitate raw document text."
>
> "And the thumbs-up I just clicked? That wrote a record to the `feedback` container in Cosmos DB with the `session_id`, `message_id`, rating `up`, and a timestamp. No personal data. The conversation is identified by a UUID, not a customer ID. CUSTOMER_NAME's data team can pull these feedback records and see which knowledge base documents are landing well and which are not."

---

### Expected Output Summary

| Step | What you see | Why it works |
|---|---|---|
| Health check | `{"status": "ok", "services": {"search": true, "cosmos": true, "openai": true}}` | Container Apps managed identity has Cognitive Services User (OpenAI), Search Index Data Reader, and Cosmos DB Built-in Data Contributor role assignments from `role-assignments.bicep` |
| Welcome message | Italian greeting rendered in chat area on page load | `_showWelcome()` in `chat.js` runs on DOM ready and calls `_addAssistantMessage()` - no API call, no cost |
| Streaming response | Tokens appear word by word within ~1 second of sending | `EventSourceResponse` in `chat.py` yields each token immediately; browser `ReadableStream` reader processes chunks as they arrive |
| Source citations in answer | Model prefixes with "Secondo la guida tariffaria..." | `get_system_prompt()` in `system_prompt.py` injects knowledge context with `[Fonte N - category (sourceDocument)]` labels that the model uses for attribution |
| App Insights trace | `model=gpt-4o-mini` for all three questions | `ModelRouter.classify()` in `model_router.py` returns `gpt-4o-mini` for messages with no bill_ref, length under 200 chars, no complex keywords |
| Feedback confirmation | "Grazie per il feedback!" appears | `_submitFeedback()` in `chat.js` posts to `/api/v1/chat/feedback`; `FeedbackService` writes to Cosmos DB `feedback` container |

---

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Chat widget page loads but shows blank white area, no welcome message | Container Apps is cold-starting (minimum replicas = 1 but the instance restarted) | Wait 20-30 seconds and hard-refresh. Container Apps cold start for the Python FastAPI app with `text-embedding-3-small` initialisation typically takes 15-25 seconds. |
| Health endpoint shows `"search": false` | AI Search private endpoint DNS not resolving correctly, or the Container Apps managed identity is missing the `Search Index Data Reader` role | From Azure Portal, open the AI Search resource > Access Control (IAM) and confirm the Container Apps identity has the role. Also check that the Container Apps environment is in the VNet with DNS resolution for `privatelink.search.windows.net`. |
| The answer is in English instead of Italian | The knowledge base index has documents that were uploaded in English, and the system prompt's `{knowledge_context}` block contains English text, which biases the model | Verify the seed documents in Blob Storage are the Italian-language versions from the demo data requirements. Re-trigger the AI Search indexer from Azure Portal > AI Search resource > Indexers. |
| Streaming stops mid-sentence and the response never completes | Azure OpenAI token-per-minute limit hit on the GPT-4o-mini deployment | Check the OpenAI resource in Azure Portal > Metrics > Token Usage. The demo uses a 50k TPM cap on GPT-4o-mini (from demo parameter overrides). Wait 60 seconds and retry, or temporarily increase the capacity in the OpenAI deployment blade. |
| App Insights Kusto query returns zero rows | The Application Insights connection string is not set on the Container Apps revision, so structured logs are not being forwarded | Open the Container Apps resource > Containers > Environment Variables and confirm `APP_INSIGHTS_CONNECTION_STRING` is set. If missing, add it from the Application Insights resource's Connection String blade and create a new revision. |
| Thumbs-up click shows no "Grazie" confirmation | The `/api/v1/chat/feedback` POST returned an error (5xx) | The feedback endpoint is non-critical - `_submitFeedback()` in `chat.js` catches errors silently and does not surface them. Open DevTools > Network and look at the feedback request's response code. Most likely the Cosmos DB connection string is misconfigured. |

---

### Transition to Demo 2

> **Say this:**
>
> "Everything you just saw was the general FAQ path. No bill reference, no customer data, pure knowledge base retrieval. That is the 80% case - a customer who wants to understand their bill but has not provided their account number yet.
>
> Now let me show you what happens when they do. In Demo 2, we set a bill reference in the widget, and the router flips to GPT-4o with the full billing data injected into the prompt. You will see a completely different response style - line by line, personalised, in the customer's specific context."

---

---

## Demo 2 - Live Chat: Personalised Bill Lookup (15 min)

---

### Demo Access

**Entry point**: The same browser tab from Demo 1, already showing the CUSTOMER_NAME chat widget at the Azure Front Door hostname. No new tabs needed. You are continuing the existing conversation session so history is live in Cosmos DB.

**Script alternative**: `demos/demo-2-bill-lookup.sh` can drive the API directly from your laptop terminal if the browser widget is unresponsive. It produces the same SSE stream in your terminal. Instructions below.

**Jump box access** (for Cosmos DB step): Azure Bastion -> jump box VM -> Azure Portal already signed in. Open the Cosmos DB Data Explorer tab you pre-loaded in the setup checklist.

---

> **WOW Moment**
>
> You type a single bill reference into the chat. The `ModelRouter` in the Container App reads `bill_ref` in the request, sets `needs_billing_data=True`, and routes straight to the GPT-4o deployment - not GPT-4o-mini. The `BillingAPIClient` fetches Mario Rossi's January bill from the billing API stub in under a second. GPT-4o then reasons over 420 kWh of consumption versus 280 kWh the previous month, explains every line item in the bill - Quota energia F1/F2/F3, Quota potenza, Oneri di sistema, Accise, IVA 22% - and attributes the EUR 187.43 total to the January cold snap. In plain Italian. From a customer's bill reference, not from a generic FAQ.

---

### Prerequisites for This Demo

- Demo 1 complete and the chat widget open in the browser (session ID is active in Cosmos DB)
- Billing API stub running on the jump box: `curl http://localhost:8080/health` returns HTTP 200
- AI Search indexer has finished (document count >= 5 chunks - verified in Demo 1)
- Cosmos DB Data Explorer tab open on the jump box browser: navigate to `billexplainer` database -> `sessions` container
- Environment variables set on your laptop for the script path:
  - `FRONT_DOOR_HOSTNAME` - the Azure Front Door hostname (e.g. `CUSTOMER_NAME-bill-dev-ENDPOINT.z01.azurefd.net`)
  - `SESSION_ID` - copy this from the final SSE event in Demo 1 (`"session_id": "..."`)

---

### Step-by-Step Walkthrough

---

**Step 1 - Set the scene: the problem with generic FAQ answers (1 min)**

Point at the chat widget where the Demo 1 answer is still visible.

> **Say this:**
>
> "That last answer was good. It explained Oneri di sistema accurately, pulled the right chunk from the regulatory charges document, cited its source. But there is a gap. Mario Rossi does not want a textbook definition - he wants to know why *his* bill this month is 67 euros higher than last month.
>
> Generic RAG cannot answer that. You need the customer's actual bill. So the next thing we are going to add is a bill reference. Watch what changes."

---

**Step 2 - Type the bill reference message (2 min)**

In the chat widget, type the following message and press send. Type it - do not paste. The audience needs to see the exact input.

```
Ho la mia bolletta di gennaio, il numero e IT001-2024-DEMO
```

Watch the response start streaming. Let it complete before speaking.

> **Say this (while response streams):**
>
> "The moment `bill_ref` appeared in that request body, the `ModelRouter` in the Container App made a routing decision. It did not run a classifier model - it applied a deterministic rule: bill reference present means `needs_billing_data=True`, which means GPT-4o, not GPT-4o-mini. We pay more per token, yes, but only when the query actually needs that reasoning depth. Around 80% of traffic never touches GPT-4o."

---

**Step 3 - Walk through the backend flow (3 min)**

Once the response finishes, walk the audience through the backend sequence. Use the architecture diagram if you have it on a second screen.

> **Say this:**
>
> "Here is the sequence that ran while those tokens were streaming.
>
> First: the chat router in `routers/chat.py` called `conversation_manager.get_or_create_session()`. That is a write to the `sessions` container in Cosmos DB - partition key `sessionId`.
>
> Second: `RAGPipeline.process_query()` started (the orchestrator in `services/rag_pipeline.py`). `ModelRouter.classify()` saw `bill_ref='IT001-2024-DEMO'` and set `needs_billing_data=True`. Reasoning logged as: 'Complex routing: bill reference provided'.
>
> Third: `BillingAPIClient.get_bill()` called the billing API stub on the jump box at `localhost:8080/api/v1/bills/IT001-2024-DEMO`. The client uses OAuth 2.0 client credentials - the client secret is fetched from Azure Key Vault on the first call, then cached in memory. One HTTP GET. Under a second.
>
> Fourth: `SearchService.hybrid_search()` ran against the AI Search index. BM25 keyword match plus vector similarity on the message text, then the semantic reranker on top. It pulled chunks from `bill-structure-guide.md` and `regulatory-charges-2024.md` - the exact documents that explain what Oneri di sistema are and how F1/F2/F3 time bands work.
>
> Fifth: `_build_messages()` assembled the OpenAI messages array. System prompt first. Then the knowledge context from AI Search. Then the bill data section injected by `get_bill_context_prompt()` in `prompts/system_prompt.py` - Mario Rossi, Via Roma 42, 420 kWh, EUR 187.43, every line item. Then conversation history. Then the user message. GPT-4o saw all of it.
>
> The response you are looking at is grounded in three sources at once: CUSTOMER_NAME documentation, live billing data, and the conversation so far."

Point at the line item breakdown in the AI response on screen.

> **Say this:**
>
> "Notice the structure of the answer. It names each line item, gives the EUR amount, and explains it. Quota energia broken into F1, F2, F3 time bands. Quota potenza as a fixed capacity charge. Oneri di sistema as ARERA-regulated levies. Accise as government excise duty. IVA at 22%. The amounts come directly from the `line_items` array the billing API returned. GPT-4o is doing the explanation layer. The numbers are from the source."

---

**Step 4 - Follow-up question: consumption spike (3 min)**

Type the follow-up question in the same session. Do not start a new chat.

```
Perche' la bolletta di gennaio e' cosi' alta rispetto al mese scorso?
```

Let the response stream.

> **Say this (while streaming):**
>
> "Same session. The conversation history is in Cosmos DB - the `messages` container, partitioned by `sessionId`, ordered by timestamp. When this request hit the chat endpoint, `get_conversation_history()` fetched the last 10 messages and passed them in the prompt. GPT-4o already knows we were talking about bill IT001-2024-DEMO. It can reference what it said before."

Once the response finishes:

> **Say this:**
>
> "The AI just reasoned over a 50% consumption increase - 420 kWh in January versus 280 kWh in December - and attributed it to the cold snap. That calculation came from GPT-4o working with the `consumption_kwh` field in the bill data. The cold snap context came from the tariff guide chunk in the AI Search index. Not invented. Cited.
>
> Think about what this means for your contact centre. A customer who gets this answer does not call. They got a clear, personalised explanation with their actual numbers, in Italian, in under three seconds. That is the deflection case."

---

**Step 5 - Submit positive feedback (1 min)**

While still in the chat widget, click the thumbs-up icon on the last AI response.

> **Say this:**
>
> "That thumbs-up writes a record to the `feedback` container in Cosmos DB - message ID, session ID, rating 'up', timestamp. The `FeedbackService` stores it linked to this session so it can be deleted in a single GDPR erasure call if Mario Rossi requests it. Feedback, messages, and session metadata all share the same `sessionId` partition key - that is not accidental. It makes bulk deletion deterministic."

---

**Step 6 - Show session persistence in Cosmos DB Data Explorer (4 min)**

Switch to the jump box browser via Azure Bastion. Open the Cosmos DB Data Explorer tab. You should be in the `billexplainer` database.

**6a. Sessions container**

Click the `sessions` container, then **Items**. Find the active session document and click it.

> **Say this:**
>
> "This is the session document. `sessionId` is the partition key - the same UUID that came back in the SSE final event. `billRef` is set to `IT001-2024-DEMO` because `ConversationManager.get_or_create_session()` stores the bill reference on the session when it first appears. `messageCount` will be 4 - two user messages, two assistant responses. `lastActive` updated on every turn. And this document has a 24-hour TTL set in the Bicep: `defaultTtl: 86400`. Cosmos DB purges it automatically."

**6b. Messages container**

Click the `messages` container, then **Items**. Find the two assistant messages.

> **Say this:**
>
> "Each message is its own document. Role, content, timestamp. The assistant messages also carry `modelUsed: 'gpt-4o'` - that field comes from `classification.model` in `ModelClassification`, persisted by the chat router after the stream completed. Full audit trail: which model answered which question, when, for which customer's bill. Messages have a 30-day TTL: `defaultTtl: 2592000`. They are not stored indefinitely."

**6c. Feedback container (optional if time allows)**

Click the `feedback` container, then **Items**.

> **Say this:**
>
> "And here is the thumbs-up record from Step 5. `messageId` links it to the exact assistant turn. `sessionId` is the partition key across all three containers - sessions, messages, feedback. One GDPR deletion call to `delete_session()` in `ConversationManager` wipes all three partitions. That is the compliance story."

---

**Step 7 - Optional: Container App log stream (1 min, only if time allows)**

From the jump box terminal, run:

```bash
RG="$(az group list --query '[0].name' -o tsv)"
APP_NAME="$(az containerapp list --resource-group "$RG" --query '[0].name' -o tsv)"
az containerapp logs show \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --tail 20
```

Point at the model router log line.

> **Say this:**
>
> "There it is: `Pipeline: session=<uuid> model=gpt-4o needs_billing=True`. Every request logs its routing decision. Query Log Analytics for that field and you know exactly what percentage of your live traffic hit GPT-4o versus GPT-4o-mini in the last hour. That query is in Demo 4."

---

### Using the Companion Script Instead of the Chat Widget

If the browser widget is unavailable or you want to show the raw SSE stream to the audience, run from your laptop terminal:

```bash
export FRONT_DOOR_HOSTNAME="your-fd-hostname.z01.azurefd.net"
export SESSION_ID="session-id-from-demo-1"   # optional - omit to start a new session
bash demos/demo-2-bill-lookup.sh
```

The script streams tokens to stdout token by token, then prints the final `session_id` and `message_id`. For the circuit breaker demo (advanced, adds ~60-75 seconds due to 5-second request timeouts):

```bash
bash demos/demo-2-bill-lookup.sh --test-circuit-breaker
```

Stop the billing API stub on the jump box before running this flag. Otherwise requests will succeed and the circuit will not trip.

---

### Expected Output at Key Steps

**Step 2 - Initial bill lookup response**

The AI response should open with Mario Rossi's name and bill reference confirmation, then list line items. Look for:
- "IT001-2024-DEMO" referenced in the response text
- Line items: Quota energia, Quota potenza, Oneri di sistema, Accise, IVA
- Total EUR 187.43 mentioned
- Source citation from `bill-structure-guide.md` or `guida tariffaria`

**Step 4 - Consumption delta response**

The response should include:
- 420 kWh (gennaio) and 280 kWh (mese precedente) - the 50% delta
- Attribution to cold snap ("ondata di freddo" or "freddo intenso" or similar)
- Advice on what the customer can do (tariff review, payment plan)

**Step 6 - Cosmos DB Data Explorer - sessions container**

```json
{
  "id": "<uuid>",
  "sessionId": "<uuid>",
  "billRef": "IT001-2024-DEMO",
  "messageCount": 4,
  "createdAt": "<iso-timestamp>",
  "lastActive": "<iso-timestamp>"
}
```

**Step 6 - Cosmos DB Data Explorer - messages container**

Assistant messages should include:

```json
{
  "role": "assistant",
  "modelUsed": "gpt-4o",
  "sessionId": "<uuid>",
  "content": "<full Italian response>"
}
```

---

### Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| AI response says it cannot find the bill data (no line items, no EUR 187.43) | Billing API stub not running on jump box | From jump box terminal: `curl http://localhost:8080/health`. If it fails, restart the stub with `nohup python3 ~/billing-stub/stub_server.py > ~/billing-stub/stub.log 2>&1 &` then retry the chat message. |
| SSE stream opens but no tokens arrive for more than 10 seconds | Container App cold start or APIM timeout | Wait up to 30 seconds. Container App `minReplicas` is 1 in the demo overlay so cold start should not occur after Demo 1 traffic. If it persists, check Container App status in the Azure Portal - look for a failed revision. |
| Cosmos DB Data Explorer shows no session document matching the conversation | 24-hour session TTL expired, or wrong database selected | Confirm you are in the `billexplainer` database. If the session is missing, use the session ID from the `SESSION_ID` env var and check the `messages` container directly. If nothing is there, the session likely started fresh - check the final SSE event in the script output for the new session ID. |
| `modelUsed` field absent on assistant message documents | Container App running default startup image, not the application | Verify the active revision image in the Azure Portal. It should not be `mcr.microsoft.com/azuredocs/containerapps-helloworld`. Redeploy with the correct image tag. |
| Follow-up question (Step 4) produces a generic answer with no mention of kWh values | Second request used a new session (no conversation history loaded) | Check the browser widget: the `session_id` in the second request body must match the first. In the script, verify `SESSION_ID` is exported and not empty. |
| `--test-circuit-breaker` flag: all 6 requests time out but no circuit-open error message appears | Billing stub is still running on the jump box | The circuit breaker in `billing_api.py` requires 5 consecutive failures (`_CB_FAILURE_THRESHOLD = 5`). Stop the stub first, wait for the first 5 requests to time out (5s timeout, 1 retry, so ~10s each), then the 6th request will return the circuit-open error instantly. |

---

### Transition to Demo 3

You have now seen the personalised bill flow from the outside: a customer message with a bill reference turns into a GPT-4o response that names every line item and reasons about the consumption delta. You have seen where the data lives in Cosmos DB.

What you have not seen is what happens inside that AI Search call. What does hybrid search actually produce? How does the semantic reranker change the ranking? Which document chunks scored highest for this query?

Demo 3 takes you onto the jump box and into the private network - querying AI Search directly via its REST API, reading the BM25 and vector scores, and watching the Container App log stream in real time.

---

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


---

## Demo 4 - Observability, Cost Controls, and Security Posture (15 min)

**Demo Access**: Azure portal from presenter laptop (Application Insights, APIM, Front Door, Azure Monitor). Jump box via Azure Bastion for terminal rate-limit trigger.

> **WOW Moment**: The Application Insights Live Metrics stream is already open when you fire the companion script. The audience watches the request rate spike and the dependency calls fan out - OpenAI, AI Search, Cosmos DB - all in real time. Then you flip to the jump box terminal and fire 12 rapid requests. Request 11 comes back HTTP 429 with a `Retry-After` header. Nobody wrote that rule today - it's been in the APIM policy since the infrastructure was deployed. That's AI running with guardrails, not without them.

---

### Why This Demo Matters

Every technical audience that sees an AI chatbot demo asks the same unspoken question: "What happens when this goes wrong? Who pays for runaway token usage? What stops a bad actor from hammering it?" This demo answers all three - with live evidence, not slides.

---

### Pre-Demo Setup (do this before the previous demo ends)

On your laptop, open four Azure portal browser tabs and pin them:

1. **Application Insights** - `CUSTOMER_NAME-bill-appi-dev` - open **Live Metrics** and leave it open and streaming
2. **APIM** - `CUSTOMER_NAME-bill-apim-dev` - go to **APIs**
3. **Front Door** - `CUSTOMER_NAME-bill-afd-dev` - go to **Security - WAF policy**
4. **Azure Monitor** - go to **Alerts - Alert rules**

On the jump box (connect now via Azure Bastion, leave the session open):
- Open a terminal and copy `demo-4-rate-limit-and-observability.sh` into the session
- Export `FRONT_DOOR_HOSTNAME` to the Front Door endpoint hostname (e.g. `CUSTOMER_NAME-bill-ep-dev.z01.azurefd.net`)
- Run `bash -n demo-4-rate-limit-and-observability.sh` to confirm the script is valid before the demo

---

### Step 1 - Application Insights Live Metrics

Switch to the **Live Metrics** tab. You should see the flat lines of a quiet system.

> **Say this**: "This is the heartbeat of the entire bill explainer. Incoming request rate, server response time, failed requests - all updated every second. But what makes it interesting for an AI system is what you see in the dependency section below. Every call the application makes - to Azure OpenAI, to AI Search, to Cosmos DB - is tracked as a named dependency with its own latency. When a user asks a question, you see four things happen in sequence: a Cosmos DB read for the session, an AI Search hybrid query, an OpenAI completion call, and another Cosmos DB write to save the response. That's your RAG pipeline, visible as it runs."

Now switch to the jump box and kick off the warm-up phase of the companion script:

```bash
# On the jump box terminal
export FRONT_DOOR_HOSTNAME="CUSTOMER_NAME-bill-ep-dev.z01.azurefd.net"
bash demo-4-rate-limit-and-observability.sh
```

The script fires three concurrent chat requests in the background before entering the rate-limit phase. Switch back immediately to the Live Metrics tab on your laptop.

**Expected output**: Within 5-10 seconds of the script firing, the request rate ticks up and the dependency graph shows three parallel spikes - AI Search latency (typically 80-150ms), OpenAI latency (600-2000ms depending on model), and Cosmos DB writes.

> **Say this**: "There's the traffic. Three simultaneous requests. You can see the AI Search queries resolve quickly - that's the hybrid index doing BM25 plus vector search. The OpenAI calls take longer - that's GPT-4o-mini generating the streamed response. And Cosmos DB at the bottom, writing the conversation turns. That dependency trace is what your on-call team uses at 2am when something slows down."

---

### Step 2 - Token Consumption by Model (Kusto)

Switch to `CUSTOMER_NAME-bill-appi-dev`. Go to **Logs** (not Live Metrics - the separate Logs tab). Open a new query window and run this query:

```kusto
customMetrics
| where name == "tokens_consumed"
| summarize total_tokens = sum(value), avg_tokens = avg(value) by bin(timestamp, 5m), tostring(customDimensions["model"])
| order by timestamp desc
| take 20
```

> **Say this**: "This is a custom metric that the application emits via the OpenTelemetry SDK - it's not something Azure OpenAI gives you for free. Each chat response records the prompt tokens plus completion tokens, tagged with the model name. What you're looking at now is token spend per five-minute window, broken down by GPT-4o-mini versus GPT-4o. This query is the foundation of any cost allocation conversation. CUSTOMER_NAME's finance team can pull this daily, pivot it by any dimension they add to that custom dimension map, and produce a cost breakdown before the Azure bill even arrives."

Point to the `avg_tokens` column. GPT-4o-mini responses should average 600-900 tokens. GPT-4o responses for complex bill lookups (like Demo 2) will run higher - typically 1,000-1,200 tokens based on the `MAX_TOKENS_BILL` ceiling set in `openai_service.py`.

> **Say this**: "See the difference in average token count between the two models? The bill-lookup queries going to GPT-4o run longer because the system prompt includes the actual bill data - energy components, time-band consumption, regulatory charges. That's expected. And it's controllable. Those `max_tokens` limits are hardcoded in the application: 800 tokens for FAQ, 1,200 for bill lookups. A runaway prompt cannot exceed those ceilings."

---

### Step 3 - Model Routing Distribution (Kusto)

Clear the query window and run this one:

```kusto
customMetrics
| where name == "model_routing_decision"
| summarize count() by tostring(customDimensions["model"])
```

> **Say this**: "This is the model routing split across all queries since deployment. The ModelRouter class in the application classifies every incoming message before it hits OpenAI. Simple FAQ questions - 'What is the POD code?' 'How is standing charge calculated?' - go to GPT-4o-mini. Complex queries - anything with a bill reference attached, anything over 200 characters, anything containing Italian numerical-comparison keywords like 'confronto' or 'percentuale', or any conversation that has gone past five turns - those go to GPT-4o."

The expected distribution is roughly 80% GPT-4o-mini, 20% GPT-4o.

> **Say this**: "That 80/20 split is not an accident - it's the routing logic working exactly as designed. GPT-4o-mini costs about one-fifteenth the price of GPT-4o per token. Routing 80% of traffic to the cheaper model while only escalating when the query genuinely needs stronger reasoning is how you build an AI product that scales without the cost line becoming a problem. And you can see it happening in real time, in your own environment, not in a marketing benchmark."

---

### Step 4 - APIM Rate Limiting Policy

Switch to the **APIM** portal tab (`CUSTOMER_NAME-bill-apim-dev`). Go to **APIs - Bill Explainer API - Design - Inbound processing**.

Click **</>** (the code editor icon) to view the raw policy XML.

Show the audience the rate-limit-by-key blocks. The policy enforces two independent limits:
- 10 requests per minute, keyed on the caller IP address
- 100 requests per hour, keyed on the `X-Session-ID` header (the session token)

> **Say this**: "Two separate controls. The IP-based limit stops a single machine - or a scraped credential - from flooding the service. The session-based limit means even if someone builds their own client and tries to have a very long conversation, they are capped at 100 turns per hour. That's not a soft suggestion - APIM enforces it at the gateway before the request ever reaches the Container App. Token throttling is also configured at the OpenAI layer for a second line of defence."

Now switch to the jump box terminal. The companion script has moved past the warm-up phase and into the rate-limit trigger phase, or will shortly. Watch the terminal output.

**Expected output**: Requests 1-10 should return HTTP 200 with response times printed. Request 11 (or around there, depending on timing from the warm-up) returns:

```
[11] HTTP 429  time=0.042s  Retry-After: 48s
--- RATE LIMIT TRIGGERED at request 11 ---
Retry-After: 48 seconds
```

> **Say this**: "There it is. HTTP 429, Retry-After 48 seconds. That's APIM counting the requests, enforcing the window, and telling the client exactly how long to wait before trying again. A well-behaved client respects that header. A misbehaving client gets the same 429 on every retry until the window expires. Zero cost incurred on the OpenAI side for those blocked requests - they never reach the model."

Point out the response time on the 429 - it should be under 100ms.

> **Say this**: "Notice the response time: 42 milliseconds. The Container App is not even involved. APIM rejected it at the edge. That is what a real guardrail looks like."

---

### Step 5 - Azure Front Door WAF

Switch to the **Front Door** portal tab (`CUSTOMER_NAME-bill-afd-dev`). Go to **Security - WAF Policy** - the associated policy is `CUSTOMER_NAMEbillwafdev`.

Point out three things in sequence:

**Managed rule sets**: `Microsoft_DefaultRuleSet 2.1` (formerly DRS) and `Microsoft_BotManagerRuleSet 1.1`, both in Prevention mode.

> **Say this**: "Prevention mode means threats are blocked, not just logged. OWASP-class attacks - SQL injection, cross-site scripting, malformed requests - are stopped before they reach APIM. The bot manager rule set handles credential stuffing, vulnerability scanners, and known bad automation. Both are managed by Microsoft and updated continuously - CUSTOMER_NAME's team does not need to maintain rule signatures."

**Custom rule - GeoFilterEUOnly**: Priority 100, action Block, matching on `RemoteAddr` NOT in the EU country code list.

> **Say this**: "This custom rule is specific to CUSTOMER_NAME's deployment. The bill explainer is a service for Italian and European customers. Traffic from outside the EU is blocked at the Front Door edge - it never touches APIM, never touches the Container App. The EU country list in the Bicep module covers all 27 EU member states. You can see Italy in there. Any request origin outside that list hits a 403 at the CDN layer."

Navigate to **Metrics** under the Front Door profile. Set the time range to the last hour and plot **Web Application Firewall Request Count**, split by `Action`.

> **Say this**: "The Blocked versus Allowed split here is your security posture at a glance. If you see a spike in blocked requests with no corresponding spike in allowed requests, that is a scan or an attack attempt that never got through. This is the data your SOC team would see in their Azure Monitor workbook."

---

### Step 6 - Network Security Topology (Closing Argument)

Go to the Azure portal home and open the resource group containing the CUSTOMER_NAME-bill resources. Switch to the **Map** view (top of the resource group blade, map icon).

Alternatively, open the **Virtual Network** - `CUSTOMER_NAME-bill-vnet-dev` - and open **Connected devices** to show the private endpoint NICs.

Point to the five private endpoint resources:
- `CUSTOMER_NAME-bill-pe-openai-dev`
- `CUSTOMER_NAME-bill-pe-search-dev`
- `CUSTOMER_NAME-bill-pe-cosmos-dev`
- `CUSTOMER_NAME-bill-pe-blob-dev`
- `CUSTOMER_NAME-bill-pe-kv-dev`

> **Say this**: "These five private endpoints are the reason none of the backend services have a public IP. Azure OpenAI, AI Search, Cosmos DB, Blob Storage, Key Vault - all five have 'Public network access: Disabled' in their network settings. Traffic from the Container App to any of those services travels over the Microsoft backbone, inside the virtual network, via private DNS. There is no path from the public internet to those resources. An attacker who bypasses Front Door and APIM still hits a wall."

Click on the Container Apps resource - `CUSTOMER_NAME-bill-ca-dev` - and go to **Identity**.

> **Say this**: "And this is the last piece. System-assigned managed identity, status Enabled. The Container App authenticates to Azure OpenAI, to AI Search, to Cosmos DB, to Key Vault - using this identity. No connection strings. No API keys. No secrets anywhere in the application code or environment variables. If you look at `openai_service.py` in the source, the client is initialised with `DefaultAzureCredential` and a bearer token provider pointed at `cognitiveservices.azure.com`. That is it. The credential is the managed identity. Which means zero secrets in code - ever."

---

### Closing Summary

> **Say this**: "So here is what you have seen in the last fifteen minutes. Three pillars. First, observe: Application Insights Live Metrics and custom Kusto queries give you token consumption by model, latency percentiles, and dependency traces down to the millisecond - all from the same workspace. Second, control: APIM rate limiting enforced in hardware at the gateway, token ceilings built into the application code, and model routing that keeps 80% of traffic on the cost-effective model. Third, protect: Front Door WAF blocking threats and non-EU traffic at the edge, five private endpoints with no public access on any backend service, and managed identity eliminating every credential rotation risk. That is not AI running unchecked. That is AI running in production."

---

### Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Live Metrics shows no data after script fires | Application Insights connection string not set in Container App environment | In Azure portal, open `CUSTOMER_NAME-bill-ca-dev` - Environment Variables - verify `APPLICATIONINSIGHTS_CONNECTION_STRING` is present; restart the revision if recently added |
| `customMetrics` Kusto query returns zero rows | Custom metrics not yet emitted; or time range too narrow | Confirm at least one chat request completed successfully after deployment; set Kusto time range to `last 24 hours` instead of `last 1 hour` |
| `model_routing_decision` shows only one model | All demo queries were simple FAQ questions; GPT-4o path not triggered | Run a request with `"bill_ref": "IT001-2024-DEMO"` in the body - that forces a complex classification and GPT-4o routing |
| Rate limit not triggering at request 11 | APIM session key header not consistent across requests; or warm-up requests consumed the window | Verify the script is sending `X-Session-ID: demo-rate-limit-session` on every request; if the window was consumed by warm-up traffic, wait 60 seconds and re-run |
| 429 arrives at request 2 or 3 | Warm-up concurrent requests in phase 1 counted against the same IP window | Add a 60-second sleep between warm-up and rate-limit phases in the script, or use `--skip-warmup` flag to go straight to rate-limit trigger |
| Front Door WAF metrics blade is empty | WAF metrics need at least one blocked request to populate; or time range too short | Confirm Prevention mode is enabled (not Detection); send a test request from outside EU with a VPN and wait 2-3 minutes for metric ingestion |
| Managed identity shows Disabled | Container App was redeployed without identity assignment | Re-run `scripts/deploy.sh` - the `role-assignments.bicep` module assigns the identity; or manually enable system-assigned identity in the portal and re-run the role assignment script |

---

*This is the final demo. The natural transition after the closing summary is to move to the commercial and delivery plan discussion - pointing the audience to `docs/delivery-plan.md` and `docs/cost-estimation.md` for the next conversation.*

---

## Post-Demo Cleanup

To remove demo overlay resources (jump box and Bastion only - core infra preserved):

```bash
export RESOURCE_GROUP="<your-resource-group>"
export RESOURCE_PREFIX="CUSTOMER_NAME-bill"
export ENVIRONMENT="dev"
bash outputs/ai-projects/CUSTOMER_NAME-cx-retention/demos/cleanup-demo.sh
```

This removes:
- Jump box VM (`CUSTOMER_NAME-bill-jumpbox-dev`) and its OS disk
- Azure Bastion (`CUSTOMER_NAME-bill-bastion-dev`) and its public IP

Core project infrastructure (Container Apps, OpenAI, AI Search, Cosmos DB, APIM, Front Door) is NOT affected.
