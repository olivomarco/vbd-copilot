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
  - `FRONT_DOOR_HOSTNAME` - the Azure Front Door hostname (e.g. `CUSTOMER_NAME-bill-dev-xxxx.z01.azurefd.net`)
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
| `modelUsed` field absent on assistant message documents | Container App running placeholder image, not the application | Verify the active revision image in the Azure Portal. It should not be `mcr.microsoft.com/azuredocs/containerapps-helloworld`. Redeploy with the correct image tag. |
| Follow-up question (Step 4) produces a generic answer with no mention of kWh values | Second request used a new session (no conversation history loaded) | Check the browser widget: the `session_id` in the second request body must match the first. In the script, verify `SESSION_ID` is exported and not empty. |
| `--test-circuit-breaker` flag: all 6 requests time out but no circuit-open error message appears | Billing stub is still running on the jump box | The circuit breaker in `billing_api.py` requires 5 consecutive failures (`_CB_FAILURE_THRESHOLD = 5`). Stop the stub first, wait for the first 5 requests to time out (5s timeout, 1 retry, so ~10s each), then the 6th request will return the circuit-open error instantly. |

---

### Transition to Demo 3

You have now seen the personalised bill flow from the outside: a customer message with a bill reference turns into a GPT-4o response that names every line item and reasons about the consumption delta. You have seen where the data lives in Cosmos DB.

What you have not seen is what happens inside that AI Search call. What does hybrid search actually produce? How does the semantic reranker change the ranking? Which document chunks scored highest for this query?

Demo 3 takes you onto the jump box and into the private network - querying AI Search directly via its REST API, reading the BM25 and vector scores, and watching the Container App log stream in real time.
