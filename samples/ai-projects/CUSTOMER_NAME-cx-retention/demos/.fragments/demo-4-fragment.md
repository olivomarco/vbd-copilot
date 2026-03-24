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
