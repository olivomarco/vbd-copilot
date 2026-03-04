# KEDA - L300 Demo Guide

**Topic:** Kubernetes Event-Driven Autoscaling (KEDA) on Azure Kubernetes Service
**Level:** L300
**Demos:** 3 x ~15 minutes (~45 minutes total)

---

## Demo Overview

| # | Title | Trigger | WOW Moment |
|---|-------|---------|------------|
| 1 | KEDA + Azure Service Bus: Event-Driven Scale-to-Zero | azure-servicebus | 0 to 10 pods in ~30s as messages arrive; back to 0 when queue drains |
| 2 | KEDA + Prometheus: Scale on Any Custom Metric | prometheus | PromQL query drives pod count - any business metric, not just CPU |
| 3 | KEDA HTTP Add-on: Scale-to-Zero HTTP Workloads | http | Cold-start request queued by interceptor - no 503, no client retry logic |

---

## Common Environment Setup

All three demos share an AKS cluster with KEDA enabled as a managed add-on.

```bash
export RG_NAME="rg-keda-demo"
export LOCATION="eastus"
export AKS_NAME="aks-keda-demo"

az group create --name $RG_NAME --location $LOCATION

az aks create \
  --name $AKS_NAME \
  --resource-group $RG_NAME \
  --enable-workload-identity \
  --enable-oidc-issuer \
  --enable-keda \
  --node-count 3 \
  --generate-ssh-keys

az aks get-credentials --name $AKS_NAME --resource-group $RG_NAME --overwrite-existing

kubectl get pods -n kube-system | grep keda
az aks show --name $AKS_NAME --resource-group $RG_NAME \
  --query "workloadAutoScalerProfile.keda.enabled"
```

**Additional prerequisites by demo:**
- Demo 1: Azure Service Bus Standard SKU + User-Assigned Managed Identity
- Demo 2: Helm + prometheus-community/kube-prometheus-stack
- Demo 3: Helm + kedacore/keda-add-ons-http

---

## Demo 1: KEDA + Azure Service Bus: Event-Driven Scale-to-Zero

This demo shows how KEDA's Azure Service Bus scaler drives a .NET order-processor
worker from zero replicas to a burst of ten - and back to zero - without a single
secret or connection string stored in the cluster. The audience sees the full
event-driven loop: idle cluster costs nothing, a message burst triggers an
automatic scale-out, and Workload Identity keeps credentials entirely out of
Kubernetes. Expected run time is approximately 15 minutes.

---

> **[WOW MOMENT - SCALE-TO-ZERO]**
> Before any messages arrive the namespace contains *zero running pods*.
> Zero pods = $0/hour idle compute cost. KEDA does not keep a warm standby;
> it eliminates the standby entirely. This is the economic argument for
> event-driven autoscaling in one terminal window.

---

### Prerequisites

**Azure resources (created during setup - see companion script comments)**
- Azure subscription with Owner or Contributor + User Access Administrator rights
- Resource group: `rg-keda-demo` in `eastus`
- AKS cluster created with `--enable-workload-identity`, `--enable-oidc-issuer`,
  and `--enable-keda` (all three flags are required; see Step 1)
- Azure Service Bus namespace, Standard SKU, local auth disabled
  (Basic SKU does NOT expose queue-depth metrics - KEDA cannot scale from it)
- Service Bus queue named `orders`
- User-assigned Managed Identity with two federated credentials:
  one for `keda-operator` in `kube-system`, one for `order-processor-sa`
  in `keda-dotnet-sample`
- Role assignment: `Azure Service Bus Data Owner` on the namespace for the
  Managed Identity

**Tooling on the presenter workstation**
- `az` CLI 2.48+ with `aks-preview` extension
- `kubectl` 1.27+
- Python 3.10+ with packages: `azure-servicebus`, `azure-identity`
  (`pip install azure-servicebus azure-identity`)
- `watch` (Linux/macOS native; Windows: use `while ($true)` loop in PowerShell)
- Active `az login` session and `kubectl` context pointing to `aks-keda-demo`

**Environment variables - set these before any step**

```bash
export RG_NAME="rg-keda-demo"
export LOCATION="eastus"
export AKS_NAME="aks-keda-demo"
export SB_NAME="<YOUR_SB_NAMESPACE_NAME>"       # e.g. sb-keda-demo-31337
export SB_QUEUE_NAME="orders"
export SB_HOSTNAME="${SB_NAME}.servicebus.windows.net"
export MI_NAME="mi-keda-demo"
export NAMESPACE="keda-dotnet-sample"
export MI_CLIENT_ID="<YOUR_MI_CLIENT_ID>"       # from: az identity show ...
```

> **Before running companion YAMLs:** substitute `<MI_CLIENT_ID>` and
> `<SB_NAME>` / `<SB_HOSTNAME>` with your actual values. Search for angle-bracket
> placeholders with `grep -r '<' outputs/demos/internal-keda/`.

---

### Infrastructure Setup (pre-demo, ~20 minutes before session)

Run these commands ahead of time. They take 8-12 minutes and must be complete
before the demo begins.

**Step P-1 - Create resource group and AKS cluster**

```bash
az group create --name $RG_NAME --location $LOCATION

az aks create \
  --name $AKS_NAME \
  --resource-group $RG_NAME \
  --enable-workload-identity \
  --enable-oidc-issuer \
  --enable-keda \
  --node-count 3 \
  --generate-ssh-keys

az aks get-credentials \
  --name $AKS_NAME \
  --resource-group $RG_NAME \
  --overwrite-existing
```

Verify KEDA is running in the cluster:

```bash
kubectl get pods -n kube-system | grep keda
```

Expected output - two pods: `keda-operator-*` and `keda-operator-metrics-apiserver-*`,
both in `Running` state.

**Step P-2 - Create Service Bus namespace and queue**

```bash
az servicebus namespace create \
  --name $SB_NAME \
  --resource-group $RG_NAME \
  --sku Standard \
  --disable-local-auth

az servicebus queue create \
  --name $SB_QUEUE_NAME \
  --namespace $SB_NAME \
  --resource-group $RG_NAME
```

> Standard SKU is required. Basic SKU does not surface queue depth to the
> Azure Monitor metrics API that KEDA queries. This is a common support
> escalation - save the customer a call by setting Standard from the start.

**Step P-3 - Wire Workload Identity**

```bash
MI_CLIENT_ID=$(az identity create \
  --name $MI_NAME \
  --resource-group $RG_NAME \
  --query "clientId" --output tsv)

AKS_OIDC_ISSUER=$(az aks show \
  --name $AKS_NAME \
  --resource-group $RG_NAME \
  --query oidcIssuerProfile.issuerUrl --output tsv)

# Federated credential for the application's ServiceAccount
az identity federated-credential create \
  --name "fed-app" \
  --identity-name $MI_NAME \
  --resource-group $RG_NAME \
  --issuer $AKS_OIDC_ISSUER \
  --subject "system:serviceaccount:${NAMESPACE}:order-processor-sa" \
  --audience api://AzureADTokenExchange

# Federated credential for the KEDA operator itself
az identity federated-credential create \
  --name "fed-keda" \
  --identity-name $MI_NAME \
  --resource-group $RG_NAME \
  --issuer $AKS_OIDC_ISSUER \
  --subject "system:serviceaccount:kube-system:keda-operator" \
  --audience api://AzureADTokenExchange
```

> **[WOW MOMENT - DUAL FEDERATED CREDENTIALS]**
> Two credentials, two separate identities: the KEDA operator gets permission
> to *read* queue depth, and the application pod gets permission to *consume*
> messages. Neither can exceed its own scope. This is least-privilege by
> architecture, not by policy document.

```bash
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
```

Restart the KEDA operator so it picks up the new federated credential binding.
This step is frequently missed and causes the ScaledObject to stay in an
`AuthNotFound` condition:

```bash
kubectl rollout restart deployment keda-operator -n kube-system
kubectl rollout status deployment keda-operator -n kube-system
```

---

### Live Demo Steps

#### Step 1 - Show the cluster with KEDA already enabled

```bash
kubectl get pods -n kube-system | grep keda
```

> **Say this:**
> "We created this AKS cluster with three flags that are all first-party,
> fully supported add-ons today: `--enable-workload-identity`,
> `--enable-oidc-issuer`, and `--enable-keda`. One CLI command, no Helm chart
> to manage, no custom controller image to version-pin. Microsoft operates
> the KEDA control plane as part of the node pool SLA. You can also enable
> it on an existing cluster with a single `az aks update --enable-keda`."

---

#### Step 2 - Create the namespace and apply the ServiceAccount

```bash
kubectl create namespace keda-dotnet-sample --dry-run=client -o yaml | kubectl apply -f -
```

Open `demo-1-serviceaccount.yaml`. Point out the annotation and the label:

```bash
cat outputs/demos/internal-keda/demo-1-serviceaccount.yaml
kubectl apply -f outputs/demos/internal-keda/demo-1-serviceaccount.yaml
```

> **Say this:**
> "The ServiceAccount carries two things: an annotation that says 'my identity
> is this specific Managed Identity client ID', and the label
> `azure.workload.identity/use: true`. The Azure Workload Identity mutating
> webhook intercepts every pod that references this ServiceAccount and injects
> a projected token volume automatically. The developer writes no credential
> code at all - they just reference this ServiceAccount."

---

#### Step 3 - Deploy the order processor (starts at zero)

Open `demo-1-deployment.yaml` and highlight the three environment variables:

```bash
cat outputs/demos/internal-keda/demo-1-deployment.yaml
kubectl apply -f outputs/demos/internal-keda/demo-1-deployment.yaml
```

```bash
kubectl get pods -n keda-dotnet-sample
```

> **Say this:**
> "Notice: `replicas` is not set in this Deployment. KEDA will own the replica
> count. The app authenticates to Service Bus via `KEDA_SERVICEBUS_AUTH_MODE:
> WorkloadIdentity` - it reads the injected token from the filesystem. The only
> things hard-coded here are the hostname and the queue name, both of which are
> non-sensitive configuration."

After a few seconds:

```bash
kubectl get pods -n keda-dotnet-sample
# Expected: No resources found in keda-dotnet-sample namespace.
```

> **[WOW MOMENT - ZERO PODS]**
>
> **Say this:**
> "No resources found. Zero pods. This is the idle state. Every enterprise I
> talk to has weekend and overnight batch windows where processing queues are
> empty. With traditional HPA you keep a minimum of one pod running 24/7 to
> satisfy liveness probes. With KEDA scale-to-zero, that cost goes to zero.
> For a fleet of 50 microservices that is a meaningful line item."

---

#### Step 4 - Apply TriggerAuthentication

Open `demo-1-triggerauth.yaml`:

```bash
cat outputs/demos/internal-keda/demo-1-triggerauth.yaml
kubectl apply -f outputs/demos/internal-keda/demo-1-triggerauth.yaml
```

> **[WOW MOMENT - NO SECRETS]**
>
> **Say this:**
> "There is no `secretTargetRef` here. Traditional KEDA deployments store a
> Service Bus connection string in a Kubernetes Secret, which lands in etcd,
> which appears in backups, audit logs, and any `kubectl get secret` that a
> cluster-admin runs. This TriggerAuthentication references `azure-workload`
> as the provider and delegates entirely to the OIDC token exchange we wired
> up earlier. Let me prove no secrets exist:"

```bash
kubectl get secrets -n keda-dotnet-sample
```

Expected: only `default-token-*` or nothing beyond the default service account
token - no Service Bus credentials of any kind.

---

#### Step 5 - Apply the ScaledObject and open the watch window

```bash
cat outputs/demos/internal-keda/demo-1-scaledobject.yaml
kubectl apply -f outputs/demos/internal-keda/demo-1-scaledobject.yaml
```

In a second terminal pane, start the pod watcher:

```bash
watch -n 2 "kubectl get pods -n keda-dotnet-sample"
```

In a third terminal pane, watch the ScaledObject conditions:

```bash
watch -n 3 "kubectl describe scaledobject order-processor-scaler \
  -n keda-dotnet-sample | grep -A10 'Conditions:\|Metric\|Active'"
```

> **Say this:**
> "The ScaledObject is the bridge between the external metric source - in this
> case the Service Bus queue depth - and the Kubernetes HPA. `minReplicaCount: 0`
> enables scale-to-zero. `maxReplicaCount: 10` caps the burst. `messageCount: 5`
> is the target messages-per-pod ratio: KEDA will calculate desired replicas as
> `ceil(queueDepth / 5)`. `activationMessageCount: 1` means the very first
> message kicks the system from zero to one - that initial cold-start message
> is the activation threshold. `pollingInterval: 10` is tuned down from the
> 30-second default so we see action quickly in the demo."

Wait for the ScaledObject to show `Active: False` and `Ready: True`:

```bash
kubectl get scaledobject -n keda-dotnet-sample
```

---

#### Step 6 - Blast messages and watch the surge

Substitute your Service Bus hostname before running:

```bash
python3 outputs/demos/internal-keda/demo-1-blast_queue.py \
  --hostname "${SB_HOSTNAME}" \
  --queue orders \
  --count 100
```

Switch focus to the pod watcher terminal.

> **[WOW MOMENT - LIVE POD SURGE]**
>
> **Say this:**
> "Watch the pod watcher. KEDA polled the queue, saw 100 messages, divided by
> the target of 5, and asked the HPA for 20 replicas - capped at our maximum
> of 10. From zero to ten pods in roughly 30 seconds. The Kubernetes scheduler
> is binding them in parallel. Each pod authenticates to Service Bus with its
> own workload identity token - no shared credential, no rotation event, no
> secret expiry to manage."

While pods are processing, show the external metrics API directly:

```bash
kubectl get --raw \
  "/apis/external.metrics.k8s.io/v1beta1/namespaces/keda-dotnet-sample/s0-azure-servicebus-orders" \
  | python3 -m json.tool
```

> **Say this:**
> "This is the external metrics endpoint that KEDA publishes to the HPA. The
> HPA sees this exactly the same way it sees CPU or memory - it has no idea
> the metric came from a message broker. KEDA is a metrics adapter as much as
> it is a controller. That is why it composes cleanly with everything already
> in your cluster."

---

#### Step 7 - Watch scale-back-to-zero

Once the queue drains (roughly 1-3 minutes depending on consumer throughput),
point at the pod watcher:

> **Say this:**
> "The queue is empty. The cooldown period is 30 seconds - deliberately short
> for this demo, a production cluster would use 60-300 seconds to avoid
> thrashing. Watch the replica count drop. And... zero. We are back to the
> idle state we started in. The cycle is complete: empty queue, zero pods,
> zero cost."

Follow pod termination in the logs before they disappear:

```bash
kubectl logs -l app=order-processor -n keda-dotnet-sample --tail=20
```

---

#### Step 8 - Confirm no secrets anywhere (recap)

```bash
kubectl get secrets -n keda-dotnet-sample
kubectl get secrets -n kube-system | grep -i servicebus
```

> **Say this:**
> "Both of those come back clean. No connection strings, no SAS keys, no
> rotating credentials anywhere in cluster state. The audit trail for 'who
> accessed the Service Bus namespace' lives entirely in Azure AD sign-in logs,
> tied to the Managed Identity. That is the story your security team needs to
> hear."

---

### Talking Points Summary

| Moment | Core message |
|--------|-------------|
| Zero pods at idle | Eliminate warm-standby cost across all event-driven workloads |
| Workload Identity - no secrets | Credentials never touch etcd, backups, or kubectl output |
| Dual federated credentials | Least-privilege by architecture - KEDA and app scoped separately |
| 0 to 10 in ~30 seconds | Kubernetes scheduler handles burst without pre-provisioned headroom |
| External metrics API | KEDA is a first-class metrics provider - composes with native HPA |
| One AKS flag to enable | No Helm, no custom operators - Microsoft-managed control plane |

---

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| ScaledObject condition: `AuthNotFound` or metrics calls fail with 401 | KEDA operator was not restarted after federated credential creation | `kubectl rollout restart deployment keda-operator -n kube-system` then wait 60 seconds |
| Pods stuck in `ContainerCreating` with `FailedMount` for projected volume | Workload Identity webhook not installed or label missing on ServiceAccount | Verify `azure.workload.identity/use: "true"` label exists on the ServiceAccount; check webhook pods in `azure-workload-identity-system` namespace |
| `blast_queue.py` fails with `DefaultAzureCredential` error | Local `az login` session expired or wrong subscription context | Run `az login` and `az account set --subscription <id>`; ensure the logged-in identity has Service Bus Data Sender on the namespace |
| ScaledObject shows `Active: False` but queue has messages | Basic SKU Service Bus - queue depth metrics not exposed | Re-create the namespace with `--sku Standard`; Basic SKU is not supported by the KEDA Azure Service Bus scaler |
| Pods scale to 1 but not further | `activationMessageCount` threshold met but `messageCount` ratio not triggering HPA | Confirm `messageCount` in the ScaledObject is lower than your total message count; 5 messages per pod with 6 messages should yield 2 replicas |
| Scale-to-zero never happens | `cooldownPeriod` is too long or minReplicaCount not 0 | Verify `minReplicaCount: 0` in `demo-1-scaledobject.yaml`; reduce `cooldownPeriod` to 30 for demo |
| `kubectl get --raw` metrics endpoint returns 404 | ScaledObject not yet `Ready` or metrics server pod not healthy | `kubectl get pods -n kube-system | grep metrics-apiserver`; describe the ScaledObject for condition detail |

---

### Cleanup

Run these after the demo to avoid ongoing charges:

```bash
# Remove Kubernetes resources only (keep Azure infra for Demo 2)
kubectl delete scaledobject order-processor-scaler -n keda-dotnet-sample
kubectl delete triggerauthentication trigger-auth-service-bus-orders -n keda-dotnet-sample
kubectl delete deployment order-processor -n keda-dotnet-sample
kubectl delete serviceaccount order-processor-sa -n keda-dotnet-sample

# Full teardown (only after all three demos are complete)
# az group delete --name $RG_NAME --yes --no-wait
```

---

> **Transition:** Demo 1 covered the core autoscaling loop for a single queue
> with one consumer type. Demo 2 builds on the same cluster and introduces
> PromQL-driven autoscaling with KEDA's Prometheus scaler - replacing the fixed CPU/memory model
> with any business metric you can express in a query.

---

## Demo 2: KEDA + Prometheus: Scale on Any Custom Metric

**Level:** L300 | **Duration:** ~15 minutes | **Type:** Live deployment + live load test

### Overview

This demo replaces the fixed mental model of "CPU scales pods" with something far more powerful: any PromQL expression can become a scaling policy. You deploy a real HTTP workload with zero replicas, wire it to Prometheus via a ServiceMonitor, and then let KEDA evaluate a rate-based query to drive every scaling decision. The audience watches the math happen in real time - request rate divided by a threshold equals the exact replica count Kubernetes is told to create. The same YAML, with one field changed, scales against Azure Monitor Managed Prometheus in production.

---

### * WOW Moment

When load generation starts, the replica count goes from **0 to 8+ pods in under 60 seconds** - something native HPA cannot do because HPA enforces `minReplicas >= 1`. Ask the audience to focus on the HPA output: the `EXTERNAL` metric column shows the live Prometheus query result as a first-class Kubernetes metric. The number they see divided by 5 (the threshold) equals the pod count they see. No black box.

---

### Prerequisites

```bash
# Navigate to the companion files directory for this demo
cd outputs/demos/internal-keda/
```

Confirm the following are complete before beginning this demo. These steps are shared setup from Demo 1.

| Requirement | Verify command |
|---|---|
| AKS cluster running, KEDA add-on enabled | `kubectl get po -n kube-system -l app=keda-operator` |
| kubectl context set | `kubectl config current-context` |
| kube-prometheus-stack installed in `monitoring` ns | `kubectl get po -n monitoring -l app.kubernetes.io/name=prometheus` |
| Helm repo `prometheus-community` added | `helm repo list` |

**Install kube-prometheus-stack** (if not already done from Demo 1 setup):

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kube-prom-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
  --wait
```

> Note: The flag `serviceMonitorSelectorNilUsesHelmValues=false` tells Prometheus to discover ALL ServiceMonitors in the cluster, not just those created by the Helm release. This is required for the demo namespace's ServiceMonitor to be picked up.

Open two extra terminal windows before starting. One for a `watch` loop on pods, one for `watch` on the HPA.

```bash
# Terminal 2
watch -n 3 kubectl get pods -n demo

# Terminal 3
watch -n 5 kubectl get hpa -n demo
```

---

### Step 1: Deploy the Application at Zero Replicas

Apply `demo-2-demo-app.yaml`. This creates the `demo` namespace, a Deployment intentionally set to `replicas: 0`, and a Service with two ports - one for application traffic (80) and one for Prometheus scraping (8080).

```bash
kubectl apply -f demo-2-demo-app.yaml
```

Expected output:
```
namespace/demo created
deployment.apps/demo-app created
service/demo-app created
```

Verify the Deployment is registered but dormant:
```bash
kubectl get deployment demo-app -n demo
```

```
NAME       READY   UP-TO-DATE   AVAILABLE   AGE
demo-app   0/0     0            0           12s
```

> **Say this:** "Notice `replicas: 0` in the manifest. I want to call this out explicitly because it is not a typo - it is the point. Native Kubernetes HPA has a hard minimum of 1 replica. It cannot represent 'this service should not exist when no one is using it.' KEDA removes that constraint. We have a real production workload right now consuming zero node capacity, zero memory, zero CPU. The moment it is needed, KEDA will bring it to life."

---

### Step 2: Register the Prometheus Scrape Target

Apply `demo-2-servicemonitor.yaml`. This ServiceMonitor tells Prometheus to scrape the `http-metrics` port of any Service labelled `app: demo-app` in the `demo` namespace every 15 seconds.

```bash
kubectl apply -f demo-2-servicemonitor.yaml
```

Expected output:
```
servicemonitor.monitoring.coreos.com/demo-app created
```

> **Say this:** "The ServiceMonitor is a Prometheus Operator CRD - a Kubernetes-native way to declare scrape configuration. We are telling Prometheus: watch this service, hit `/metrics` every 15 seconds, and store whatever it exposes. Right now there are no pods, so Prometheus will discover the target but collect nothing. That is intentional - the metric will start flowing the moment KEDA scales pods up."

**Critical label check** - confirm the label matches your Prometheus release name:

```bash
kubectl get servicemonitor demo-app -n demo -o jsonpath='{.metadata.labels}'
```

You should see `{"release":"kube-prom-stack"}`. If your Helm release was named differently, this label must match or Prometheus will silently ignore the ServiceMonitor.

---

### Step 3: Verify Prometheus Sees the Target

Port-forward to the Prometheus UI to confirm the scrape target is registered before wiring KEDA.

```bash
kubectl port-forward -n monitoring \
  svc/kube-prom-stack-kube-prome-prometheus 9090:9090 &
```

Open `http://localhost:9090/targets` in a browser. Look for a row with `namespace="demo"` and `job="demo-app"`. The state will show "0/0 up" because there are no pods yet - this is correct. The target definition itself must be present.

Then navigate to the **Graph** tab and run the scaling PromQL manually:

```
sum(rate(http_requests_total{namespace="demo",job="demo-app"}[2m]))
```

The result will be `0` or `no data`. This is the baseline you will compare to once load is running.

> **Say this:** "I want everyone to see this query before KEDA ever touches it. This is the entire scaling policy - one PromQL expression. There is no YAML field called `scaleOnRequestRate`. There is no built-in HTTP metric type you have to configure. KEDA hands Prometheus an arbitrary query and treats the numeric result as a workload signal. This means anything you can express in PromQL - latency percentiles, queue depth, error rates, business metrics like orders-per-second - can drive autoscaling."

---

### Step 4: Create the ScaledObject

Apply `demo-2-scaledobject.yaml`. This is the object that connects KEDA, Prometheus, and the Deployment.

```bash
kubectl apply -f demo-2-scaledobject.yaml
```

Expected output:
```
scaledobject.keda.sh/demo-app-scaler created
```

Inspect what KEDA created automatically:

```bash
kubectl get scaledobject demo-app-scaler -n demo
kubectl get hpa -n demo
```

Expected ScaledObject output:
```
NAME               SCALETARGETKIND      SCALETARGETNAME   MIN   MAX   TRIGGERS     READY   ACTIVE   FALLBACK   AGE
demo-app-scaler    apps/Deployment      demo-app          0     10    prometheus   True    False    False      20s
```

Expected HPA output:
```
NAME                       REFERENCE             TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
keda-hpa-demo-app-scaler   Deployment/demo-app   0/5 (avg)      1         10        0          20s
```

> **Say this:** "Two things to point out here. First - KEDA created that HPA. We did not write an HPA manifest. KEDA owns it entirely and will keep it reconciled. Second - look at the TARGETS column: `0/5`. The left number is the current Prometheus query result, normalized per replica. The right number is our threshold. When the left number crosses 5, pods appear. Right now it is zero, and Kubernetes is holding zero pods. The HPA is active, and the deployment is dormant - this is the scale-to-zero state."

---

### Step 5: Generate Load and Watch the Scaling Event

Open Terminal 2 and Terminal 3 so the audience can see pod count and HPA metrics side by side. Then start the load generator.

**Option A - using `hey` (simple, no install required in-cluster):**

```bash
kubectl run load-gen \
  --image=alpine/hey \
  --restart=Never \
  --namespace=demo \
  -- hey -z 5m -c 50 http://demo-app.demo.svc.cluster.local/
```

**Option B - using k6 with staged ramp (use `demo-2-k6-script.js`):**

```bash
# If running k6 from outside the cluster, expose the service first
kubectl expose deployment demo-app --type=LoadBalancer --name=demo-app-lb \
  --port=80 --target-port=http --namespace=demo

export SERVICE_URL="http://$(kubectl get svc demo-app-lb -n demo \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"

k6 run -e TARGET_URL=$SERVICE_URL demo-2-k6-script.js
```

> **Say this:** "Load is starting now. Watch Terminal 2. In a moment you will see pods transition from `0/0` to `0/1` - that first pod is KEDA crossing the `activationThreshold` of 1 request per second. Once pods are Running and passing readiness checks, Prometheus begins receiving real metric data, the rate climbs, and KEDA starts adding pods aggressively. We set `scaleUp.policies` to allow 3 pods per 15-second window so the ramp is visible and not instantaneous."

Watch the scaling progression in Terminal 2:

```
# ~15s after load starts
NAME                        READY   STATUS              RESTARTS   AGE
demo-app-6d9f7b8c4-abc12    0/1     ContainerCreating   0          3s

# ~45s - load is fully measured, rate drives replica calculation
NAME                        READY   STATUS    RESTARTS   AGE
demo-app-6d9f7b8c4-abc12    1/1     Running   0          32s
demo-app-6d9f7b8c4-def34    1/1     Running   0          17s
demo-app-6d9f7b8c4-ghi56    1/1     Running   0          17s
...
```

Watch the HPA in Terminal 3 to see the live metric value:

```bash
kubectl get hpa keda-hpa-demo-app-scaler -n demo --watch
```

```
NAME                        REFERENCE             TARGETS          MINPODS   MAXPODS   REPLICAS
keda-hpa-demo-app-scaler    Deployment/demo-app   47300m/5 (avg)   1         10        10
```

> **Say this:** "Look at that TARGETS value - `47300m/5`. The `m` suffix means milli-units, so 47300m is 47.3. That is the PromQL query result right now: 47.3 requests per second total. Divide 47.3 by 5 and take the ceiling - you get 10. Kubernetes is running exactly 10 pods. You can do that arithmetic in your head and it matches what the cluster is doing. The scaling formula is not hidden in an algorithm. It is right there in the YAML."

Return to the Prometheus browser tab and refresh the graph query to show the rate climbing.

---

### Step 6: Confirm the External Metric Registration

While load is running, show how KEDA exposes the Prometheus value as a native Kubernetes external metric.

```bash
kubectl get --raw \
  "/apis/external.metrics.k8s.io/v1beta1/namespaces/demo/s0-prometheus-http_requests_total" \
  | jq .
```

Expected output (abbreviated):
```json
{
  "kind": "ExternalMetricValueList",
  "apiVersion": "external.metrics.k8s.io/v1beta1",
  "items": [
    {
      "metricName": "s0-prometheus-http_requests_total",
      "value": "47300m",
      "timestamp": "2024-01-15T10:23:41Z"
    }
  ]
}
```

> **Say this:** "This endpoint is the Kubernetes External Metrics API. KEDA registers itself as a metrics provider - the same extension point that custom metrics adapters use. The HPA does not speak Prometheus. It speaks this API. KEDA is the translator. By registering the Prometheus query result here, the standard Kubernetes HPA control loop drives the scaling - KEDA is not bypassing any Kubernetes primitives. It is extending them."

---

### Step 7: Watch Scale-Down and Return to Zero

Delete the load generator pod and observe the cooldown behavior.

```bash
kubectl delete pod load-gen -n demo
```

> **Say this:** "The load is gone. Now watch what happens over the next two minutes. The rate query will decay - `rate()` uses a 2-minute window, so the value will slide toward zero over 120 seconds. KEDA's `scaleDown` policy removes at most 50% of pods per 30-second step, so the scale-down is gradual. After the rate drops below the `activationThreshold` of 1, KEDA will begin the `cooldownPeriod` countdown - 60 seconds in this config. Once that expires, the deployment returns to zero replicas. No pods, no cost."

Watch the drain in Terminal 2. The pods will step down roughly every 30 seconds rather than terminating all at once:

```
# After ~90s
demo-app-6d9f7b8c4-abc12    1/1     Running   0          6m
demo-app-6d9f7b8c4-def34    1/1     Running   0          5m45s
demo-app-6d9f7b8c4-ghi56    Terminating   0          5m45s
...

# After ~3m - back to zero
No resources found in demo namespace.
```

```bash
kubectl get deployment demo-app -n demo
```

```
NAME       READY   UP-TO-DATE   AVAILABLE   AGE
demo-app   0/0     0            0           12m
```

---

### Optional: Azure Monitor Managed Prometheus Upgrade Path

This section is relevant when the audience is discussing production architecture or multi-cluster observability. Show `demo-2-scaledobject-azure-monitor.yaml` to illustrate that the migration from in-cluster Prometheus to Azure Monitor requires changing exactly two fields.

```bash
# Side-by-side diff to show minimal change
diff demo-2-scaledobject.yaml demo-2-scaledobject-azure-monitor.yaml
```

The key changes are:

| Field | In-cluster Prometheus | Azure Monitor Managed Prometheus |
|---|---|---|
| `serverAddress` | `http://kube-prom-stack...svc.cluster.local:9090` | `https://<WORKSPACE_NAME>.eastus.prometheus.monitor.azure.com` |
| `authenticationRef` | (not present) | `azure-managed-prometheus-trigger-auth` |
| `pollingInterval` | 15 | 30 |
| PromQL query | unchanged | unchanged |

```bash
# Substitute placeholders before applying
# Replace <YOUR_UAMI_CLIENT_ID> with output of:
az identity show --name <UAMI_NAME> --resource-group $RG --query clientId -o tsv

# Replace <WORKSPACE_NAME> with output of:
az monitor account list --query "[].name" -o tsv

# Remove the in-cluster ScaledObject first (only one ScaledObject per Deployment)
kubectl delete scaledobject demo-app-scaler -n demo

# Apply the Azure Monitor variant
kubectl apply -f demo-2-scaledobject-azure-monitor.yaml
```

> **Say this:** "In production you would not run Prometheus inside the cluster just for scaling. Azure Monitor Managed Prometheus gives you a fully managed, multi-cluster, highly available metrics store with 18 months of retention. The ScaledObject swap is literally a URL change and an authentication reference. The PromQL query is identical. You can use the same scaling logic across dev clusters with in-cluster Prometheus and production clusters with Managed Prometheus without rewriting anything."

Reference: [Azure Monitor Managed Prometheus overview](https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/prometheus-metrics-overview)

---

### Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| ScaledObject `READY: False`, condition `FailedGetScale` | KEDA cannot reach Prometheus at the serverAddress | Confirm the FQDN includes `.svc.cluster.local`. Run `kubectl run curl-test --image=curlimages/curl --restart=Never --rm -it -- curl -s http://kube-prom-stack-kube-prome-prometheus.monitoring.svc.cluster.local:9090/-/healthy` |
| ServiceMonitor exists but target absent from `http://localhost:9090/targets` | Label mismatch between ServiceMonitor and Prometheus serviceMonitorSelector | Check `kubectl get servicemonitor demo-app -n demo -o yaml` - label `release` must match Helm release name, or set `serviceMonitorSelectorNilUsesHelmValues=false` |
| HPA shows `<unknown>/5` in TARGETS column | KEDA has not yet registered as external metrics provider, or no metric value exists | Wait 30s after ScaledObject creation. If persists: `kubectl describe scaledobject demo-app-scaler -n demo` to see conditions |
| Pods created but immediately `OOMKilled` | Resource limits too low for the node pool or workload burst | Increase `resources.limits.memory` in demo-2-demo-app.yaml. Check with `kubectl top pods -n demo` |
| Load generator pod stays `Pending` | Insufficient cluster capacity while demo-app pods are consuming nodes | Check `kubectl get events -n demo --sort-by=.lastTimestamp`. Add a node or reduce replica max |
| `replicas: 0` stuck - pods never appear | `activationThreshold: 1` not crossed - load not reaching the service | Verify Service endpoints with `kubectl get endpoints demo-app -n demo`. If empty, the Service selector may not match pod labels |
| Azure Monitor variant: `Forbidden` on metrics query | UAMI missing "Monitoring Data Reader" role on the workspace | `az role assignment create --assignee <CLIENT_ID> --role "Monitoring Data Reader" --scope <WORKSPACE_RESOURCE_ID>` |

---

### Cleanup

```bash
# Remove load generator if still running
kubectl delete pod load-gen -n demo --ignore-not-found

# Remove KEDA resources (HPA will be auto-deleted with ScaledObject)
kubectl delete scaledobject demo-app-scaler -n demo
kubectl delete scaledobject demo-app-scaler-amp -n demo --ignore-not-found
kubectl delete triggerauthentication azure-managed-prometheus-trigger-auth -n demo --ignore-not-found

# Remove application and monitoring config
kubectl delete -f demo-2-servicemonitor.yaml
kubectl delete -f demo-2-demo-app.yaml

# Verify namespace is clean
kubectl get all -n demo
```

> Note: Do NOT remove the `monitoring` namespace or kube-prometheus-stack if Demo 3 also requires Prometheus.

---

*This demo demonstrates scale-to-zero and PromQL-driven autoscaling using the KEDA Prometheus scaler documented at https://keda.sh/docs/2.14/scalers/prometheus/ . Demo 3 extends this pattern to event-driven workloads - showing how KEDA handles pull-based queue sources like Azure Service Bus, where the scaling signal is not a rate but a message backlog count.*

---

## Demo 3: KEDA HTTP Add-on: Scale-to-Zero HTTP Workloads

> **Level:** L300  |  **Duration:** ~15 minutes  |  **Companion files:** `demo-3-demo-app.yaml`, `demo-3-httpscaledobject.yaml`, `demo-3-httpscaledobject-concurrency.yaml`, `demo-3-load-test.sh`

---

### Overview

This demo shows the **KEDA HTTP Add-on** - a separate, community-maintained Helm chart that extends KEDA with a dedicated HTTP scaling pipeline. Unlike the previous two demos that scaled on queue depth or Prometheus metrics, this demo scales on **live HTTP traffic** and drives replicas all the way to zero when no traffic is flowing.

**Honest beta caveats - say these upfront, they build trust:**

| Caveat | Customer impact |
|---|---|
| Beta status - no production SLA | PoC and dev/staging workloads only without a supported wrapper |
| Interceptor sits in the critical HTTP path | Adds single-digit millisecond latency overhead |
| Cold start latency 10-30 seconds | First request after zero pods is held, not dropped |
| AKS managed KEDA add-on does NOT bundle the HTTP add-on | Separate Helm install required regardless of cluster type |
| Incompatible with pre-existing HPA on the same Deployment | Remove any existing HPA before applying HTTPScaledObject |
| Default scaledownPeriod is 300 seconds | Tune to 60 seconds for demo visibility; tune back for production |
| Production recommendation: Kedify or Knative | See Production Guidance section at the end of this demo |

References:
- HTTP add-on repo and docs: https://github.com/kedacore/http-add-on
- Install guide: https://github.com/kedacore/http-add-on/blob/main/docs/install.md
- Walkthrough: https://github.com/kedacore/http-add-on/blob/main/docs/walkthrough.md
- HTTPScaledObject reference: https://github.com/kedacore/http-add-on/blob/main/docs/ref/v0.12.2/http_scaled_object.md

---

### Architecture

The HTTP add-on introduces three components alongside core KEDA:

```
  Internet / Client
        |
        v
+-------------------------+
|   Interceptor Proxy      |  <-- smart HTTP proxy; counts in-flight requests
|   (ClusterIP service)    |      HOLDS requests in queue when pods = 0
+-------------------------+
        |  routes by Host header
        v
+-------------------------+
|   Your Deployment        |  <-- nginx:alpine (demo-app)
|   (0 .. 10 replicas)     |
+-------------------------+

+-------------------------+
|   Operator               |  <-- watches HTTPScaledObject CRDs
|   (controller-manager)   |      auto-creates ScaledObject + routing services
+-------------------------+

+-------------------------+
|   External Scaler        |  <-- sidecar speaking KEDA external-push protocol
|   (metrics sidecar)      |      feeds requestRate / concurrency to KEDA
+-------------------------+
        |
        v
   KEDA core ScaledObject -> HPA -> Deployment replicas
```

**Key insight:** The interceptor is what makes scale-to-zero safe for HTTP. A standard Kubernetes HPA cannot scale below 1 replica without dropping the first request after a cold start. The interceptor buffers that first request in memory while KEDA brings a pod up - the caller sees a slow response, not a 503.

---

### Prerequisites

```bash
# Navigate to the companion files directory for this demo
cd outputs/demos/internal-keda/
```

```bash
# Environment variables used throughout this demo
export NAMESPACE=keda-http-demo
export DEMO_HOST=myapp.demo.com

# Reuse the AKS cluster from Demo 1 or 2, or create a new one:
az aks create \
  --resource-group rg-keda-demo \
  --name aks-keda-demo \
  --node-count 2 \
  --enable-keda \
  --generate-ssh-keys

az aks get-credentials --resource-group rg-keda-demo --name aks-keda-demo

# Create a dedicated namespace for the HTTP add-on and demo app
kubectl create namespace ${NAMESPACE}

# Add the kedacore Helm repo (may already be present from Demo 1/2)
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# Install the HTTP add-on into the SAME namespace as the demo app
helm install http-add-on kedacore/keda-add-ons-http \
  --namespace ${NAMESPACE} \
  --wait

# Verify all three add-on components are Running
kubectl get pods -n ${NAMESPACE}
# Expected output (names will vary):
#   keda-add-ons-http-controller-manager-xxx   1/1   Running
#   keda-add-ons-http-external-scaler-xxx      1/1   Running
#   keda-add-ons-http-interceptor-xxx          1/1   Running
```

> **Say this:** "Notice we have three new pods - operator, interceptor, and scaler. The interceptor is the key piece. It is a smart proxy that holds requests in a local queue when there are no pods ready, then forwards them the moment KEDA brings a replica up. Your calling application does not need to implement any retry logic."

---

### Step-by-Step

#### Step 1 - Deploy the application

```bash
kubectl apply -f demo-3-demo-app.yaml
kubectl get deployment demo-app -n ${NAMESPACE}
```

> **Say this:** "We are deploying a plain nginx container. Notice there is no `replicas:` field in the spec. We intentionally leave that unset because the HTTPScaledObject is about to own replica management completely. Once KEDA takes over, any manual replica count you set will be overwritten."

Expected output:
```
NAME       READY   UP-TO-DATE   AVAILABLE   AGE
demo-app   0/0     0            0           5s
```

The deployment starts at zero replicas - there is no traffic yet, so there is no reason to pay for a running pod.

---

#### Step 2 - Apply the HTTPScaledObject

```bash
kubectl apply -f demo-3-httpscaledobject.yaml
```

```bash
# Verify the HTTPScaledObject was accepted
kubectl get httpscaledobject -n ${NAMESPACE}

# The operator auto-creates a backing ScaledObject - confirm it is here too
kubectl get scaledobject -n ${NAMESPACE}

# And an HPA behind that
kubectl get hpa -n ${NAMESPACE}
```

> **[*] WOW MOMENT - Say this:** "One YAML file just wired together three Kubernetes objects: an HTTPScaledObject, a backing ScaledObject, and an HPA. No boilerplate, no cross-referencing object names manually. The operator handled all of that. From an operator's perspective this is a single unit of intent - 'scale this deployment based on HTTP traffic, down to zero.'"

Expected output:
```
NAME       HOSTS             MINREPLICAS   MAXREPLICAS   AGE
demo-app   myapp.demo.com    0             10            10s
```

Review the key fields in `demo-3-httpscaledobject.yaml`:

```yaml
replicas:
  min: 0          # true scale-to-zero
  max: 10
scaledownPeriod: 60   # 60s idle before pods removed (300s default in production)
scalingMetric:
  requestRate:
    granularity: 1s
    targetValue: 10   # req/s per pod
    window: 1m
```

> **Say this:** "The scaling math is transparent and auditable. A targetValue of 10 requests per second per pod means: at 50 requests per second you will see 5 pods. At 100 requests per second you will see 10 pods - the maximum. Your capacity planning team can reason about this directly from the YAML. There is no black box."

---

#### Step 3 - Port-forward the interceptor and test the cold start

Open a second terminal to watch pods live:

```bash
# Terminal 2 - pod watcher
watch -n 1 kubectl get pods -n keda-http-demo
```

Back in Terminal 1, set up the port-forward:

```bash
# Port-forward the interceptor proxy to localhost
kubectl port-forward svc/keda-add-ons-http-interceptor-proxy \
  -n ${NAMESPACE} 8080:8080 &

# Capture the process ID - you will need this to stop the port-forward cleanly later
PORTFWD_PID=$!
echo "Port-forward PID: ${PORTFWD_PID}"
```

Now trigger the cold start:

```bash
# Send ONE request - this will block until KEDA scales up from zero
time curl -v -H "Host: myapp.demo.com" http://localhost:8080/
```

> **[*] WOW MOMENT - Say this:** "Watch Terminal 2. We are at zero pods right now. I am sending one HTTP request - watch what happens. The request does NOT fail. The interceptor is holding it in an in-memory queue while it signals to KEDA that there is pending demand. KEDA tells the HPA to create a pod. The pod starts, passes its readiness probe, and then - and only then - the interceptor forwards our queued request. The curl command will return after 10 to 30 seconds depending on node provisioning time. Your application, your load balancer, your monitoring - none of them see a 503."

Expected output from `time curl`:
```
< HTTP/1.1 200 OK
...
real    0m14.302s   # cold start wait - expected; duration depends on node warmup
```

Watch the interceptor logs to see the queuing in action:

```bash
kubectl logs -n ${NAMESPACE} \
  -l app.kubernetes.io/component=interceptor \
  --follow --tail=50
```

---

#### Step 4 - Run the load test and watch scale-out

Install `hey` for the best throughput measurement experience:

```bash
go install github.com/rakyll/hey@latest
# OR on macOS: brew install hey
```

Run the load test (the script falls back to curl if hey is absent):

```bash
./demo-3-load-test.sh 2000 50 myapp.demo.com
```

The script accepts four positional arguments - all optional with sensible defaults:

| Argument | Default | Description |
|---|---|---|
| 1 - requests | 2000 | Total requests to send |
| 2 - concurrency | 50 | Parallel workers |
| 3 - host | myapp.demo.com | Host header value |
| 4 - interceptor_url | http://localhost:8080 | Interceptor base URL |

In Terminal 2 you will see pods scaling up within 15-30 seconds.

> **[*] WOW MOMENT - Say this:** "Look at the pod count climbing. KEDA is adding pods proportionally as our request rate climbs. The scaling math is doing exactly what the YAML promised - for every 10 requests per second of sustained rate, you get one pod. This is not a heuristic. It is a deterministic formula the team can put in a runbook and hand to their capacity planning team."

```bash
# Check the HPA to see current and desired replicas in real time
kubectl get hpa -n ${NAMESPACE} -w
```

---

#### Step 5 - Watch scale-to-zero

Stop the load test and wait. With `scaledownPeriod: 60` in the HTTPScaledObject, pods will be removed within 60-90 seconds of traffic stopping.

```bash
watch -n 1 kubectl get pods -n keda-http-demo
```

> **[*] WOW MOMENT - Say this:** "This is the cost conversation. In a dev or staging environment with overnight idle periods - say 16 hours out of 24 - you eliminate roughly two thirds of your compute spend for that workload. On a cluster shared across 20 microservices, that adds up fast. And because the interceptor queues the first morning request rather than dropping it, developers do not notice the cold start unless they are specifically looking for it."

---

#### Step 6 - Compare: concurrency-based scaling (optional, +5 min)

Switch to the concurrency variant to illustrate the metric choice decision:

```bash
# Remove the requestRate HTTPScaledObject first
kubectl delete -f demo-3-httpscaledobject.yaml

# Apply the concurrency variant
kubectl apply -f demo-3-httpscaledobject-concurrency.yaml
kubectl get httpscaledobject -n ${NAMESPACE}
```

> **Say this:** "The concurrency metric counts simultaneous in-flight requests rather than a per-second rate. Choose requestRate when your backend is fast - under 100 milliseconds - and you want to cap throughput per pod. Choose concurrency when requests are slow or variable in duration and you want to cap how many each pod is working on at once. Long-running uploads, synchronous database operations, ML inference endpoints - those are concurrency candidates. The scale-to-zero behaviour is identical either way."

```bash
./demo-3-load-test.sh 2000 50 myapp.demo.com
```

---

### Advanced Patterns

#### Wildcard host routing for multi-tenant scenarios

The `hosts` field accepts wildcard entries. This means a single HTTPScaledObject can cover all subdomains for a tenant namespace without enumerating individual hostnames:

```yaml
spec:
  hosts:
    - myapp.demo.com       # exact match
    - "*.demo.com"         # all subdomains - tenant A, tenant B, etc.
```

> **Say this:** "If your platform team provisions one namespace per tenant, each with its own subdomain, you can deploy one HTTPScaledObject template per namespace and cover every tenant with a wildcard. Onboarding a new tenant is a namespace creation, not a YAML edit."

#### Hybrid triggers with skip-scaledobject-creation

The annotation `httpscaledobject.keda.sh/skip-scaledobject-creation: "true"` prevents the operator from auto-creating the backing ScaledObject. This lets you write your own ScaledObject manually and combine the HTTP external scaler with other KEDA triggers - for example, scaling on both HTTP traffic and a Service Bus queue depth at the same time:

```yaml
metadata:
  annotations:
    httpscaledobject.keda.sh/skip-scaledobject-creation: "true"
```

Then create your own ScaledObject referencing the HTTP add-on external scaler endpoint alongside any other trigger you need. This is an advanced pattern - reach for it when a workload has both HTTP traffic and a background job queue that should both influence replica count.

Reference: https://github.com/kedacore/http-add-on/blob/main/docs/walkthrough.md

---

### Production Guidance

| Scenario | Recommendation |
|---|---|
| PoC, dev, staging | KEDA HTTP add-on (this demo) - free, open source, community maintained |
| Production HTTP scale-to-zero on AKS | **Kedify HTTP Scaler** (https://kedify.io) - commercial wrapper with SLA and support |
| Production on any Kubernetes, event-driven HTTP | **Knative Serving** (https://knative.dev) - CNCF graduated, production-ready, broader ecosystem |
| Existing Knative users adding more KEDA triggers | KEDA and Knative integration (community supported) |

> **Say this:** "I want to be direct with you: the KEDA HTTP add-on is beta software. It is excellent for proving out the concept and for dev and staging environments where a cold start edge case or a rough release is acceptable. If you are building a production service with an SLA attached, the two paths I recommend are Kedify - which is a commercially supported wrapper around exactly what you just saw - or Knative, which is the CNCF graduated option and has a broader production track record. We can map either of those to your team's roadmap in a follow-up conversation."

---

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `curl: (7) Failed to connect to localhost port 8080` | Port-forward not running or died | Re-run: `kubectl port-forward svc/keda-add-ons-http-interceptor-proxy -n keda-http-demo 8080:8080 &` |
| `curl` hangs indefinitely and never returns | Pod failed readiness probe; KEDA cannot bring a healthy pod up | Check: `kubectl describe pod -n keda-http-demo -l app=demo-app`; verify image pull and resource limits |
| HTTPScaledObject stuck in `Pending` | HTTP add-on controller not running, or CRD not installed | Check: `kubectl get pods -n keda-http-demo`; re-run Helm install with `--wait` |
| `error: no kind "HTTPScaledObject" is registered` | HTTP add-on Helm chart not installed in this namespace | `helm install http-add-on kedacore/keda-add-ons-http --namespace keda-http-demo` |
| Pods scale up but `hey` reports high error rate | Host header not matching any `hosts:` entry in HTTPScaledObject | Confirm `-H "Host: myapp.demo.com"` matches the hosts list; check interceptor logs |
| ScaledObject not auto-created after applying HTTPScaledObject | Annotation `skip-scaledobject-creation` is `"true"` | Set annotation to `"false"` or remove it; re-apply the HTTPScaledObject |
| Pods do not scale to zero after load stops | `scaledownPeriod` still at default 300s | Verify `scaledownPeriod: 60` in applied manifest: `kubectl get httpscaledobject demo-app -n keda-http-demo -o yaml` |
| `hey` binary not found | hey not installed | `go install github.com/rakyll/hey@latest` or `brew install hey`; load test script falls back to curl automatically |
| Conflict: existing HPA on demo-app | HPA was deployed before the HTTPScaledObject | `kubectl delete hpa demo-app -n keda-http-demo` then re-apply the HTTPScaledObject |

---

### Cleanup

```bash
# Remove the HTTPScaledObject first (also removes the auto-created ScaledObject and HPA)
kubectl delete -f demo-3-httpscaledobject.yaml
# OR if you applied the concurrency variant:
# kubectl delete -f demo-3-httpscaledobject-concurrency.yaml

# Remove the application
kubectl delete -f demo-3-demo-app.yaml

# Uninstall the HTTP add-on
helm uninstall http-add-on -n keda-http-demo

# Stop the port-forward - bring it to the foreground and press Ctrl-C,
# or terminate the process using PORTFWD_PID saved earlier:
#   fg   (if still in same shell session)
#   -- or --
#   send SIGTERM to ${PORTFWD_PID}
kill "$PORTFWD_PID"

# Optionally remove the namespace entirely
# kubectl delete namespace keda-http-demo
```

---

This demo completes the three-part KEDA package. The narrative arc for the customer debrief is: Demo 1 showed event-driven scaling on Azure-native queues with the managed AKS add-on; Demo 2 showed custom business metric scaling via Prometheus; Demo 3 showed true HTTP scale-to-zero with request buffering - the workload exists only when someone is talking to it. Together they cover the full range of KEDA trigger types a platform team is likely to encounter when consolidating their Kubernetes autoscaling strategy.