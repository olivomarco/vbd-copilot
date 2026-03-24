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
