# KEDA + Azure Service Bus on AKS — L300 Demo Research
> Compiled by Demo Research Subagent | Mode: DEEP | Duration target: ~15 minutes

---

## 📁 Verified GitHub URLs

| Resource | URL | Stars / Status |
|---|---|---|
| Primary sample repo | https://github.com/kedacore/sample-dotnet-worker-servicebus-queue | ✅ Official kedacore org |
| App deployment YAML (workload identity) | https://github.com/kedacore/sample-dotnet-worker-servicebus-queue/blob/main/deploy/workload-identity/deploy-app-with-workload-identity.yaml | ✅ Verified |
| ScaledObject + TriggerAuth YAML | https://github.com/kedacore/sample-dotnet-worker-servicebus-queue/blob/main/deploy/workload-identity/deploy-app-autoscaling.yaml | ✅ Verified |
| Workload Identity walkthrough | https://github.com/kedacore/sample-dotnet-worker-servicebus-queue/blob/main/workload-identity.md | ✅ Verified |
| AKS KEDA add-on overview | https://learn.microsoft.com/en-us/azure/aks/keda-about | ✅ Official MS docs |
| AKS KEDA CLI deploy | https://learn.microsoft.com/en-us/azure/aks/keda-deploy-add-on-cli | ✅ Official MS docs |
| KEDA Workload Identity tutorial | https://learn.microsoft.com/en-us/azure/aks/keda-workload-identity | ✅ Official MS docs |
| KEDA Service Bus scaler spec | https://keda.sh/docs/2.14/scalers/azure-service-bus/ | ✅ Official KEDA docs |
| Consumer/producer container image | ghcr.io/azure-samples/aks-app-samples/servicebusdemo:latest | ✅ Used in MS docs |
| Order processor container image | ghcr.io/kedacore/sample-dotnet-worker-servicebus-queue:latest | ✅ Official kedacore |

---

## 🧱 Prerequisites — Azure Resources Required

```bash
# Variables — set these before running any commands
export RG_NAME="rg-keda-demo"
export LOCATION="eastus"
export AKS_NAME="aks-keda-demo"
export SB_NAME="sb-keda-demo-$RANDOM"          # must be globally unique
export SB_QUEUE_NAME="orders"
export SB_HOSTNAME="${SB_NAME}.servicebus.windows.net"
export MI_NAME="mi-keda-demo"
export NAMESPACE="keda-dotnet-sample"
```

### Required Azure Resources Checklist
- [ ] Azure Subscription with Contributor rights
- [ ] Resource Group
- [ ] AKS cluster (1.27+) with flags: `--enable-keda --enable-workload-identity --enable-oidc-issuer`
- [ ] Azure Service Bus namespace (Standard SKU minimum for queue metrics; Premium for production)
- [ ] Service Bus Queue named `orders`
- [ ] User-Assigned Managed Identity
- [ ] Two Federated Credentials (one for app SA, one for keda-operator SA)
- [ ] RBAC: `Azure Service Bus Data Owner` on the namespace scope
- [ ] Tools: `az CLI`, `kubectl`, `Python 3.x` or `azure-servicebus` pip package

---

## ⚙️ EXACT CLI COMMANDS — Full Setup Sequence

### Phase 1: Infrastructure (pre-demo, ~10 min)

```bash
# 1. Create resource group
az group create --name $RG_NAME --location $LOCATION

# 2. Create AKS cluster with KEDA + Workload Identity + OIDC in ONE command
az aks create \
  --name $AKS_NAME \
  --resource-group $RG_NAME \
  --enable-workload-identity \
  --enable-oidc-issuer \
  --enable-keda \
  --node-count 3 \
  --generate-ssh-keys

# 3. Get kubeconfig
az aks get-credentials --name $AKS_NAME --resource-group $RG_NAME --overwrite-existing

# 4. Verify KEDA is running (should see keda-operator, keda-admission-webhooks, keda-operator-metrics-apiserver)
kubectl get pods -n kube-system | grep keda

# 5. Create Service Bus namespace (--disable-local-auth enforces AAD-only = security best practice)
az servicebus namespace create \
  --name $SB_NAME \
  --resource-group $RG_NAME \
  --sku Standard \
  --disable-local-auth

# 6. Create the orders queue
az servicebus queue create \
  --name $SB_QUEUE_NAME \
  --namespace $SB_NAME \
  --resource-group $RG_NAME

# 7. Create Managed Identity
MI_CLIENT_ID=$(az identity create \
  --name $MI_NAME \
  --resource-group $RG_NAME \
  --query "clientId" --output tsv)

# 8. Get OIDC issuer URL from the cluster
AKS_OIDC_ISSUER=$(az aks show \
  --name $AKS_NAME \
  --resource-group $RG_NAME \
  --query oidcIssuerProfile.issuerUrl --output tsv)

# 9. Federated credential for the APP's service account (namespace: keda-dotnet-sample)
az identity federated-credential create \
  --name "fed-app" \
  --identity-name $MI_NAME \
  --resource-group $RG_NAME \
  --issuer $AKS_OIDC_ISSUER \
  --subject "system:serviceaccount:${NAMESPACE}:order-processor-sa" \
  --audience api://AzureADTokenExchange

# 10. Federated credential for the KEDA OPERATOR's service account
az identity federated-credential create \
  --name "fed-keda" \
  --identity-name $MI_NAME \
  --resource-group $RG_NAME \
  --issuer $AKS_OIDC_ISSUER \
  --subject "system:serviceaccount:kube-system:keda-operator" \
  --audience api://AzureADTokenExchange

# 11. Assign Azure Service Bus Data Owner to managed identity
MI_OBJECT_ID=$(az identity show \
  --name $MI_NAME \
  --resource-group $RG_NAME \
  --query "principalId" --output tsv)

SB_ID=$(az servicebus namespace show \
  --name $SB_NAME \
  --resource-group $RG_NAME \
  --query "id" --output tsv)

az role assignment create \
  --role "Azure Service Bus Data Owner" \
  --assignee-object-id $MI_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --scope $SB_ID

# 12. Restart KEDA operator so Workload Identity env vars are injected
kubectl rollout restart deployment keda-operator -n kube-system
kubectl rollout status deployment keda-operator -n kube-system

# 13. Verify WI env vars injected into KEDA operator pod
KEDA_POD=$(kubectl get po -n kube-system -l app=keda-operator -o jsonpath='{.items[0].metadata.name}')
kubectl describe pod $KEDA_POD -n kube-system | grep -A5 "Environment:"
# ✅ WOW MOMENT: Show AZURE_TENANT_ID, AZURE_FEDERATED_TOKEN_FILE, AZURE_AUTHORITY_HOST injected automatically
```

---

## 📄 EXACT YAML SNIPPETS

### 1. ServiceAccount (Workload Identity annotated)

```yaml
# serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: order-processor-sa
  namespace: keda-dotnet-sample
  labels:
    azure.workload.identity/use: "true"
  annotations:
    azure.workload.identity/client-id: "<MI_CLIENT_ID>"   # ← substitute $MI_CLIENT_ID
```

### 2. Deployment (order processor consumer)

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-processor
  namespace: keda-dotnet-sample
  labels:
    app: order-processor
    azure.workload.identity/use: "true"
spec:
  selector:
    matchLabels:
      app: order-processor
  template:
    metadata:
      labels:
        app: order-processor
    spec:
      serviceAccountName: order-processor-sa   # ← binds WI token
      containers:
      - name: order-processor
        image: ghcr.io/kedacore/sample-dotnet-worker-servicebus-queue:latest
        env:
        - name: KEDA_SERVICEBUS_AUTH_MODE
          value: WorkloadIdentity
        - name: KEDA_SERVICEBUS_HOST_NAME
          value: "<SB_NAME>.servicebus.windows.net"   # ← substitute
        - name: KEDA_SERVICEBUS_QUEUE_NAME
          value: orders
```

### 3. TriggerAuthentication (Workload Identity, no secrets!)

```yaml
# triggerauthentication.yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: trigger-auth-service-bus-orders
  namespace: keda-dotnet-sample
spec:
  podIdentity:
    provider: azure-workload          # ← tells KEDA: use WI, no conn string!
    identityId: "<MI_CLIENT_ID>"      # ← substitute $MI_CLIENT_ID
```

### 4. ScaledObject — the STAR of the demo

```yaml
# scaledobject.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-processor-scaler
  namespace: keda-dotnet-sample
  labels:
    app: order-processor
spec:
  scaleTargetRef:
    name: order-processor             # ← must match Deployment name
  minReplicaCount: 0                  # ← SCALE TO ZERO! Cost saving WOW moment
  maxReplicaCount: 10
  pollingInterval: 10                 # seconds between metrics checks
  cooldownPeriod: 30                  # seconds before scaling back down
  triggers:
  - type: azure-servicebus
    metadata:
      namespace: "<SB_NAME>"          # ← Service Bus namespace name
      queueName: orders
      messageCount: "5"               # 1 pod per every 5 messages
      activationMessageCount: "1"     # start scaling from 0 when ≥1 message
    authenticationRef:
      name: trigger-auth-service-bus-orders
```

### 5. Combined apply manifest (all-in-one for demo)

```bash
kubectl create namespace keda-dotnet-sample

# Apply everything in order
kubectl apply -f serviceaccount.yaml
kubectl apply -f deployment.yaml
kubectl apply -f triggerauthentication.yaml
kubectl apply -f scaledobject.yaml
```

---

## 🔥 MESSAGE BLAST — Python Script (the "Wow" trigger)

```python
#!/usr/bin/env python3
# blast_queue.py — Send N messages to Azure Service Bus queue
# pip install azure-servicebus azure-identity
import asyncio
import argparse
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential

async def blast(hostname: str, queue_name: str, count: int):
    credential = DefaultAzureCredential()
    async with ServiceBusClient(
        fully_qualified_namespace=hostname,
        credential=credential
    ) as client:
        async with client.get_queue_sender(queue_name=queue_name) as sender:
            batch = await sender.create_message_batch()
            for i in range(count):
                msg_body = f'{{"orderId": "order-{i:04d}", "product": "Widget {i}", "quantity": {i % 10 + 1}}}'
                try:
                    batch.add_message(ServiceBusMessage(msg_body))
                except ValueError:
                    # Batch full — send and start a new one
                    await sender.send_messages(batch)
                    batch = await sender.create_message_batch()
                    batch.add_message(ServiceBusMessage(msg_body))
            if len(batch) > 0:
                await sender.send_messages(batch)
    await credential.close()
    print(f"✅ Blasted {count} messages to {hostname}/{queue_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Blast messages to Azure Service Bus")
    parser.add_argument("--hostname", required=True, help="e.g. myns.servicebus.windows.net")
    parser.add_argument("--queue", default="orders", help="Queue name")
    parser.add_argument("--count", type=int, default=100, help="Number of messages")
    args = parser.parse_args()
    asyncio.run(blast(args.hostname, args.queue, args.count))
```

**Usage:**
```bash
pip install azure-servicebus azure-identity
# Authenticate with az login (uses DefaultAzureCredential)
az login
python blast_queue.py --hostname ${SB_HOSTNAME} --queue orders --count 100
```

### Alternative: Azure CLI one-liner blast (no Python needed)
```bash
# Send a single test message via CLI
az servicebus queue message send \
  --resource-group $RG_NAME \
  --namespace-name $SB_NAME \
  --queue-name orders \
  --body '{"orderId":"test-001","product":"Demo Widget"}'
```

---

## 👁️ KUBECTL WATCH COMMANDS — Live Scaling Observatory

```bash
# Terminal 1 — Watch pods scale up/down in real time (THE MONEY SHOT)
watch -n 2 "kubectl get pods -n keda-dotnet-sample"

# Terminal 2 — Watch HPA that KEDA manages behind the scenes
kubectl get hpa -n keda-dotnet-sample -w

# Terminal 3 — Watch the ScaledObject status and current metric value
watch -n 3 "kubectl describe scaledobject order-processor-scaler -n keda-dotnet-sample | grep -A 10 'Conditions:\|Active Triggers:\|External Metric'"

# Terminal 4 — Tail logs from one worker pod (shows messages being processed)
kubectl logs -f $(kubectl get pods -n keda-dotnet-sample -l app=order-processor -o jsonpath='{.items[0].metadata.name}') -n keda-dotnet-sample

# Check ScaledObject health at any time
kubectl get scaledobject -n keda-dotnet-sample
kubectl describe scaledobject order-processor-scaler -n keda-dotnet-sample

# Verify KEDA sees the correct metric (queue depth)
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1/namespaces/keda-dotnet-sample/s0-azure-servicebus-orders"

# Show Events — watch KEDA scaling decisions
kubectl get events -n keda-dotnet-sample --sort-by='.lastTimestamp' -w

# Scale-to-zero proof (after queue drains, ~30s cooldown)
kubectl get pods -n keda-dotnet-sample
# Expected: No resources found in keda-dotnet-sample namespace. ← WOW
```

---

## 🎬 STEP-BY-STEP DEMO FLOW (15 minutes)

### PRE-DEMO CHECKLIST (done before audience arrives, ~15 min setup)
- [ ] AKS cluster running, kubeconfig loaded
- [ ] Service Bus namespace + queue created
- [ ] Managed identity + federated credentials created
- [ ] RBAC role assignment applied
- [ ] KEDA operator restarted, WI env vars verified
- [ ] Namespace `keda-dotnet-sample` created
- [ ] All 4 YAML files ready to `kubectl apply`
- [ ] blast_queue.py staged and tested
- [ ] 4 terminal windows open (pods watch / HPA watch / ScaledObject describe / logs)

---

### STEP 1 — Set the Stage [0:00–1:30] 🗣️ Talking Points
> **"Traditional HPA scales on CPU/memory. But what if your app idles at 0.1% CPU while 10,000 messages pile up? KEDA scales on the thing that actually matters — the queue depth."**

```bash
# Show the empty deployment — ZERO pods (prove scale-to-zero)
kubectl get pods -n keda-dotnet-sample
# Output: No resources found    ← THIS IS THE POINT. Zero cost at idle.

# Show KEDA components are fully managed by AKS add-on
kubectl get pods -n kube-system | grep keda
```
**🎯 WOW #1:** "Zero pods running, zero compute cost. The deployment exists but consumes nothing."

---

### STEP 2 — Explain Architecture [1:30–3:00] 🗣️ Talking Points
Show the diagram: `Queue depth → KEDA metrics server → HPA → Deployment replicas`

```bash
# Show the ScaledObject (already deployed)
kubectl describe scaledobject order-processor-scaler -n keda-dotnet-sample
```
> **"Notice: no connection strings, no secrets in YAML. The TriggerAuthentication uses azure-workload provider — KEDA gets a short-lived federated token from the OIDC issuer. Zero secret sprawl."**

**🎯 WOW #2:** "The KEDA operator itself has a federated credential. It authenticates to Service Bus with its own workload identity to READ metrics — completely separate from the app identity."

---

### STEP 3 — Deploy the Consumer [3:00–5:00]
```bash
kubectl apply -f serviceaccount.yaml
kubectl apply -f deployment.yaml
kubectl apply -f triggerauthentication.yaml
kubectl apply -f scaledobject.yaml

# Verify — still 0 pods (queue is empty)
kubectl get pods -n keda-dotnet-sample
kubectl get scaledobject -n keda-dotnet-sample
```
> **"Applied 4 YAML files. ScaledObject is active, pollingInterval is 10 seconds. Queue is empty → 0 pods. KEDA is watching."**

---

### STEP 4 — THE BLAST [5:00–6:00] 🔥 High drama moment
```bash
# Open watch in separate terminal FIRST so audience sees pods appear in real time
watch -n 2 "kubectl get pods -n keda-dotnet-sample"

# NOW fire the messages
python blast_queue.py --hostname ${SB_HOSTNAME} --queue orders --count 100
# ✅ Blasted 100 messages to <namespace>.servicebus.windows.net/orders
```
**🎯 WOW #3:** Watch pod count go from 0 → 2 → 5 → 10 in ~30 seconds while the audience watches live.

---

### STEP 5 — Observe Live Scaling [6:00–9:00]
```bash
# Show queue depth metric being read by KEDA
kubectl describe scaledobject order-processor-scaler -n keda-dotnet-sample

# Show HPA KEDA created automatically
kubectl get hpa -n keda-dotnet-sample

# Show worker logs — messages being processed
kubectl logs -f <pod-name> -n keda-dotnet-sample
```
> **"With messageCount: 5, KEDA targets 1 replica per 5 messages. 100 messages = 20 replicas desired, but maxReplicaCount caps it at 10. As workers drain the queue, KEDA recalculates every 10 seconds."**

**Key metric formula to explain:**
```
desiredReplicas = ceil(currentMessages / messageCount)
= ceil(100 / 5) = 20  → capped at maxReplicaCount: 10
```

---

### STEP 6 — Scale-to-Zero [9:00–11:00]
```bash
# Watch the queue drain and pods disappear
watch -n 2 "kubectl get pods -n keda-dotnet-sample"
# After cooldownPeriod (30s), pods go: 10 → 5 → 2 → 1 → 0
```
> **"After the cooldown period, KEDA scales back to minReplicaCount: 0. Complete scale-to-zero. In a real workload — nights, weekends, low-traffic windows — you pay for nothing."**

**🎯 WOW #4:** "Terminal shows 'No resources found'. All 10 pods gone. Cost: $0.00/hour for this workload right now."

---

### STEP 7 — Security Deep-Dive [11:00–13:00] (L300 differentiator)
```bash
# Show NO secrets anywhere in the cluster
kubectl get secrets -n keda-dotnet-sample
# Output: Only default service account token — NO Service Bus connection strings!

# Show the OIDC token file path inside a running pod (during blast phase)
kubectl exec -it <pod-name> -n keda-dotnet-sample -- ls /var/run/secrets/azure/tokens/
# Output: azure-identity-token  ← short-lived JWT, auto-rotated

# Show the federated credentials
az identity federated-credential list --identity-name $MI_NAME --resource-group $RG_NAME -o table
```
> **"This token is a Kubernetes-signed JWT exchanged for an Azure AD access token via OIDC federation. No long-lived secrets. No rotation scripts. The token file is valid for 24 hours and automatically refreshed by the webhook."**

---

### STEP 8 — Wrap Up & Cleanup [13:00–15:00]
```bash
# Show KEDA version installed
kubectl get crd/scaledobjects.keda.sh -o jsonpath='{.metadata.labels.app\.kubernetes\.io/version}'

# Show it's fully managed (no Helm chart to maintain)
az aks show --name $AKS_NAME --resource-group $RG_NAME \
  --query "workloadAutoScalerProfile.keda.enabled"
# Output: true   ← managed add-on, AKS handles upgrades

# Optional: Live cleanup
kubectl delete scaledobject order-processor-scaler -n keda-dotnet-sample
kubectl delete namespace keda-dotnet-sample
# az group delete --name $RG_NAME --yes --no-wait
```

---

## 💡 WOW MOMENTS SUMMARY

| # | Moment | What to Show | Talking Point |
|---|---|---|---|
| 🎯1 | **Scale-to-Zero** | `kubectl get pods` → "No resources found" | "Zero pods = Zero compute cost at idle" |
| 🎯2 | **No Secrets** | `kubectl get secrets` — only default token | "Workload Identity eliminates secret sprawl entirely" |
| 🎯3 | **Pods Surge Live** | Watch terminal as blast runs | "0 → 10 pods in 30 seconds, driven by queue depth" |
| 🎯4 | **KEDA's Own Identity** | Two federated credentials — app + keda-operator | "KEDA authenticates separately from the app for least privilege" |
| 🎯5 | **Managed Add-On** | `az aks show --query workloadAutoScalerProfile` | "No Helm chart, no YAML, AKS manages KEDA upgrades" |
| 🎯6 | **External Metrics API** | `kubectl get --raw /apis/external.metrics.k8s.io/...` | "KEDA exposes custom metrics as first-class K8s API objects" |

---

## 📊 DEMO EVALUATION SCORES

| Criterion | Score | Notes |
|---|---|---|
| **Runnability** | 9/10 | All official images, no build required, ~15 min infra setup |
| **Visual Impact** | 10/10 | Live pod surge is viscerally satisfying in watch terminal |
| **L300 Calibration** | 9/10 | YAML mods + CLI + security concepts, no live coding needed |
| **Customer Relevance** | 10/10 | Cost optimization + security (no secrets) resonates universally |
| **Repeatability** | 9/10 | Idempotent YAML; re-blast anytime for multiple runs |

---

## 🧩 COMPANION FILES TO CREATE

| File | Purpose |
|---|---|
| `00-env-vars.sh` | Export all variables — source this first |
| `01-infra-setup.sh` | Full infra provisioning script (AKS + SB + MI + RBAC) |
| `02-keda-setup.sh` | Federated creds + restart keda-operator |
| `serviceaccount.yaml` | Annotated ServiceAccount |
| `deployment.yaml` | Order processor Deployment |
| `triggerauthentication.yaml` | KEDA TriggerAuthentication |
| `scaledobject.yaml` | ScaledObject with minReplicaCount: 0 |
| `blast_queue.py` | Python message sender |
| `watch-commands.sh` | Multi-terminal watch setup using tmux |
| `cleanup.sh` | Full teardown |

---

## ⚠️ KNOWN GOTCHAS FOR DEMO

1. **KEDA must be restarted AFTER Workload Identity is enabled** — if you enable WI after KEDA, env vars won't be injected. Always run `kubectl rollout restart deployment keda-operator -n kube-system`.

2. **Service Bus SKU**: Basic SKU does NOT support queue depth metrics via the management API. Use **Standard or Premium** for KEDA to work.

3. **`--disable-local-auth`** on Service Bus namespace prevents connection string fallback — this is intentional for security demo but means Python blast script MUST use `DefaultAzureCredential` (not conn string).

4. **Two federated credentials required**: One for `kube-system:keda-operator` (so KEDA can read metrics) and one for `keda-dotnet-sample:order-processor-sa` (so the app can consume messages). Demo both — it's an L300 talking point.

5. **KEDA as sole external metrics adapter**: Only one external metrics server allowed per cluster. Conflicts with other HPA-based autoscalers.

6. **pollingInterval**: Default is 30s. Set to `10` for demo snappiness. In production, use longer intervals to avoid Service Bus throttling.

7. **Scale-to-zero timing**: With `cooldownPeriod: 30` and last pod draining final messages, expect ~60-90 seconds from "queue empty" to "0 pods". Warn audience so demo doesn't feel broken.

