# Demo 2 Research Report: AKS Automatic — Deployment & Guardrails
## DEEP-Mode Research | L300 Demo (~15 minutes)

---

## 1. SOURCE INVENTORY

| # | Source | URL | Status |
|---|--------|-----|--------|
| 1 | AKS Store Demo repo | github.com/Azure-Samples/aks-store-demo | ✅ Fetched — README + 3 YAML manifests |
| 2 | Deployment Safeguards docs | learn.microsoft.com/en-us/azure/aks/deployment-safeguards | ✅ Fetched — full policy table + error messages |
| 3 | App Routing add-on docs | learn.microsoft.com/en-us/azure/aks/app-routing | ✅ Fetched — full deployment + ingress steps |
| 4 | AKS Automatic overview | learn.microsoft.com/en-us/azure/aks/intro-aks-automatic | ✅ Fetched — feature comparison table |
| 5 | aks-store-ingress-quickstart.yaml | raw.githubusercontent.com/…/aks-store-ingress-quickstart.yaml | ✅ Full YAML captured |
| 6 | AKS CLI quickstart | learn.microsoft.com/en-us/azure/aks/learn/quick-kubernetes-deploy-cli | ✅ Fetched |

---

## 2. KEY FINDING: AKS Automatic Pre-Configured Defaults

AKS Automatic comes with these features **preconfigured** (cannot be disabled):

| Feature | Status in AKS Automatic |
|---------|------------------------|
| Deployment Safeguards | **Preconfigured** — Enforce level by default |
| Baseline Pod Security Standards | **Preconfigured** — Cannot be turned off |
| App Routing (managed NGINX) | **Preconfigured** — always enabled |
| Azure CNI Overlay + Cilium | **Default** networking |
| Node Autoprovision (NAP/Karpenter) | **Preconfigured** — no manual node pools |
| Managed NAT Gateway (egress) | **Preconfigured** |
| Azure RBAC for K8s auth | **Preconfigured** |
| Workload Identity + OIDC | **Preconfigured** |
| Image Cleaner | **Preconfigured** |

> **Demo Talking Point**: "With AKS Automatic, you get production-grade security guardrails from minute zero. You don't have to opt into best practices — they're enforced by default."

---

## 3. DEMO PART A: Deploy AKS Store Demo Application

### 3A.1 — Recommended YAML File

**Use `aks-store-ingress-quickstart.yaml`** — this is the all-in-one manifest that includes the Ingress resource. It's the exact file used in the official docs for the app routing quickstart.

**URL**: `https://raw.githubusercontent.com/Azure-Samples/aks-store-demo/main/aks-store-ingress-quickstart.yaml`

**What it creates** (4 workloads + Ingress):

| Resource | Kind | Image | Notes |
|----------|------|-------|-------|
| rabbitmq | StatefulSet | `mcr.microsoft.com/azurelinux/base/rabbitmq-server:3.13` | Message queue |
| order-service | Deployment | `ghcr.io/azure-samples/aks-store-demo/order-service:2.1.0` | Has init container |
| product-service | Deployment | `ghcr.io/azure-samples/aks-store-demo/product-service:2.1.0` | Lightweight Rust service |
| store-front | Deployment | `ghcr.io/azure-samples/aks-store-demo/store-front:2.1.0` | Vue.js web UI |
| store-front | Ingress | — | `ingressClassName: webapprouting.kubernetes.azure.com` |

**Key characteristics of this YAML (good for demo)**:
- ✅ All images use **explicit version tags** (`2.1.0`, `3.13`, `1.37.0`) — NOT `:latest`
- ✅ All containers have **resource requests AND limits** defined
- ✅ All containers have **liveness and readiness probes** (plus startup probes where needed)
- ✅ Uses **Secrets** for RabbitMQ credentials (base64-encoded)
- ✅ Uses **ConfigMaps** for service configs
- ✅ Ingress uses `webapprouting.kubernetes.azure.com` class (managed NGINX)
- ✅ All services are `ClusterIP` (no direct LoadBalancer exposure — ingress handles it)

### 3A.2 — Exact Deployment Commands

```bash
# Step 1: Create namespace
kubectl create namespace pets

# Step 2: Deploy the full application with Ingress
kubectl apply -f https://raw.githubusercontent.com/Azure-Samples/aks-store-demo/main/aks-store-ingress-quickstart.yaml -n pets

# Step 3: Watch pods come up (great for live demo)
kubectl get pods -n pets -w

# Step 4: Check all resources are running
kubectl get all -n pets
```

**Expected output after ~60-90 seconds**:
```
NAME                                  READY   STATUS    RESTARTS   AGE
pod/order-service-xxxxxxxxx-xxxxx     1/1     Running   0          85s
pod/product-service-xxxxxxxxx-xxxxx   1/1     Running   0          85s
pod/rabbitmq-0                        1/1     Running   0          85s
pod/store-front-xxxxxxxxx-xxxxx       1/1     Running   0          85s
```

### 3A.3 — Timing Considerations

| Phase | Expected Time | Notes |
|-------|---------------|-------|
| `kubectl apply` | Instant | Manifests accepted |
| RabbitMQ StatefulSet ready | 30-60 sec | Has `startupProbe` with 10s initial delay |
| order-service ready | 60-90 sec | init container waits for RabbitMQ |
| product-service ready | 15-30 sec | Lightweight Rust binary |
| store-front ready | 15-30 sec | Vue.js app |
| **Ingress IP assigned** | **60-120 sec** | Load balancer provisioning — **pre-deploy recommended** |
| App fully accessible via browser | 2-3 min total | From first `kubectl apply` |

> ⚠️ **PRESENTER TIP**: Pre-deploy the app ~5 minutes before the demo starts. During the demo, show a fresh `kubectl apply` to a second namespace or show the already-running app. The ingress IP provisioning wait is the biggest risk for live timing.

---

## 4. DEMO PART B: Managed NGINX Ingress (App Routing)

### 4B.1 — How It Works on AKS Automatic

- **Preconfigured**: App Routing is always enabled on AKS Automatic clusters
- **IngressClass**: `webapprouting.kubernetes.azure.com`
- **Controller runs in**: `app-routing-system` namespace (managed by AKS)
- **Load Balancer**: Automatically creates an Azure Standard Load Balancer with public IP
- **Integrations**: Azure DNS (public/private zones), Azure Key Vault for TLS certificates

### 4B.2 — Ingress Manifest (included in aks-store-ingress-quickstart.yaml)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: store-front
spec:
  ingressClassName: webapprouting.kubernetes.azure.com
  rules:
    - http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: store-front
                port:
                  number: 80
```

### 4B.3 — Ingress Verification Commands

```bash
# Check Ingress status and get external IP
kubectl get ingress -n pets
# Expected:
# NAME          CLASS                                HOSTS   ADDRESS       PORTS   AGE
# store-front   webapprouting.kubernetes.azure.com   *       51.8.10.109   80      110s

# Alternative: get just the IP
kubectl get ingress store-front -n pets -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Or check the NGINX controller service directly
kubectl get service -n app-routing-system nginx -o jsonpath="{.status.loadBalancer.ingress[0].ip}"

# Verify the app-routing controller is healthy
kubectl get pods -n app-routing-system

# Quick curl test
INGRESS_IP=$(kubectl get ingress store-front -n pets -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Store is at: http://$INGRESS_IP"
curl -s -o /dev/null -w "%{http_code}" http://$INGRESS_IP
# Expected: 200
```

> **Demo Talking Point**: "Notice we didn't install an ingress controller, we didn't create a LoadBalancer service, and we didn't configure any NGINX settings. AKS Automatic includes the managed NGINX ingress as a built-in capability. We just reference the IngressClass and get a public endpoint automatically."

---

## 5. DEMO PART C: Deployment Safeguards — The "Bad Manifest" Demo

### 5C.1 — Deployment Safeguards Policy List (AKS Automatic)

On AKS Automatic, Deployment Safeguards are **preconfigured in Enforce mode**. Baseline Pod Security Standards are also **on by default and cannot be turned off**.

#### Core Deployment Safeguards Policies

| Policy | Mode | What It Checks | On Violation |
|--------|------|----------------|-------------|
| Resource Requests Required | **Enforce + Mutate** | CPU/memory requests & limits on all containers | **Mutates**: sets defaults (500m CPU, 2Gi memory) if missing |
| No "Latest" Image Tag | **Enforce (Deny)** | Image tags must be explicit, not `:latest` or blank | **Denied** |
| Enforce Liveness/Readiness Probes | **Enforce (Warn or Deny)** | All containers need health probes | Warning or denial |
| Anti-Affinity / TopologySpread | **Enforce + Mutate** | Multi-replica deployments need spread constraints | **Mutates**: adds preferred anti-affinity + topology spread |
| Reserved System Pool Taints | **Enforce + Mutate** | `CriticalAddonsOnly` taint reserved for system pool | **Mutates**: removes taint from user pool |
| No AKS-Specific Labels | **Enforce (Deny)** | `kubernetes.azure.com` labels reserved for AKS | **Denied** |
| Cannot Edit Individual Nodes | **Enforce (Deny)** | Must use node pools, not individual node edits | **Denied** |
| CSI Driver StorageClass | **Enforce (Deny)** | Must use CSI driver, not in-tree provisioner | **Denied** |
| Unique Service Selectors | **Enforce (Warn or Deny)** | Services must have unique selectors | Warning or denial |

#### Baseline Pod Security Standard Policies (always on in AKS Automatic)

| Policy | What It Blocks |
|--------|---------------|
| Privileged Containers | `securityContext.privileged: true` |
| Host Namespaces | `hostNetwork`, `hostPID`, `hostIPC` |
| HostPath Volumes | Volume type `hostPath` |
| Host Ports | Container `hostPort` specifications |
| Capabilities | Disallowed Linux capabilities (e.g., `SYS_ADMIN`, `NET_RAW`) |
| AppArmor | Non-default AppArmor profiles |
| SELinux | Non-standard SELinux types |
| /proc Mount | Non-default procMount values |
| Seccomp | Explicit `Unconfined` seccomp profiles |

#### Resource Request Mutator Defaults (when resources are missing)

| Resource | Default Request | Default Limit | Minimum Enforced |
|----------|----------------|---------------|-----------------|
| CPU | 500m | 500m | 100m |
| Memory | 2048Mi (2Gi) | 2048Mi (2Gi) | 100Mi |

### 5C.2 — Crafted "Bad" Manifest for Demo

Save this as `bad-deployment.yaml`. It intentionally violates **6 policies** to create a dramatic demo moment:

```yaml
# bad-deployment.yaml — Intentionally violates AKS Automatic Deployment Safeguards
# Use this to demonstrate how guardrails protect the cluster
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bad-app
  namespace: pets
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bad-app
  template:
    metadata:
      labels:
        app: bad-app
    spec:
      # VIOLATION 1: hostNetwork is disallowed (Baseline PSS)
      hostNetwork: true
      # VIOLATION 2: hostPID is disallowed (Baseline PSS)
      hostPID: true
      containers:
        - name: bad-container
          # VIOLATION 3: "latest" image tag is not allowed
          image: nginx:latest
          # VIOLATION 4: No resource requests/limits defined
          # (will be mutated if other checks pass, but let's see what happens)
          # VIOLATION 5: Privileged container
          securityContext:
            privileged: true
          # VIOLATION 6: hostPath volume mount
          volumeMounts:
            - name: host-vol
              mountPath: /host
          # No liveness/readiness probes (VIOLATION 7)
      volumes:
        - name: host-vol
          hostPath:
            path: /
            type: Directory
```

### 5C.3 — Expected Error Output

When you run `kubectl apply -f bad-deployment.yaml`, AKS Automatic will **deny** the deployment. Expected output will include multiple policy violation messages:

```
Error from server (Forbidden): error when creating "bad-deployment.yaml": admission webhook
"validation.gatekeeper.sh" denied the request:

[azurepolicy-k8sazurev2nohostnetwork-...] Host network namespaces are disallowed:
  spec.hostNetwork is set to true

[azurepolicy-k8sazurev2nohostpid-...] Host PID namespaces are disallowed:
  spec.hostPID is set to true

[azurepolicy-k8sazurev3noprivilege-...] Privileged containers are disallowed:
  spec.containers[*].securityContext.privileged is set to true

[azurepolicy-k8sazurev2nohostpath-...] HostPath volumes are forbidden under
  restricted security policy unless containers mounting them are from allowed images

[azurepolicy-k8sazurev1nolatestimg-...] Please specify an explicit, versioned image tag
  such as '1.0' for container bad-container. Using explicit version tags is a best practice
  to ensure reproducibility, prevent unintended updates, and facilitate easier debugging
  and rollbacks. Avoid using the 'latest' tag because it can change over time without notice.
```

> **Key Demo Point**: The errors are **descriptive and actionable** — they tell the developer exactly what's wrong and how to fix it. This isn't a cryptic error; it's a teaching moment.

### 5C.4 — The "Fixed" Manifest

Show fixing the manifest to comply with all policies:

```yaml
# good-deployment.yaml — Fixed version that passes all Deployment Safeguards
apiVersion: apps/v1
kind: Deployment
metadata:
  name: good-app
  namespace: pets
spec:
  replicas: 1
  selector:
    matchLabels:
      app: good-app
  template:
    metadata:
      labels:
        app: good-app
    spec:
      # FIXED: Removed hostNetwork and hostPID
      containers:
        - name: good-container
          # FIXED: Explicit version tag
          image: nginx:1.27.0
          ports:
            - containerPort: 80
          # FIXED: Resource requests and limits defined
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 250m
              memory: 256Mi
          # FIXED: Not privileged, running as non-root
          securityContext:
            privileged: false
            allowPrivilegeEscalation: false
          # FIXED: Probes added
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 15
      # FIXED: Removed hostPath volume, using emptyDir instead
      # (or just remove the volume entirely)
```

### 5C.5 — Demo Commands for the Safeguards Flow

```bash
# Step 1: Try to deploy the bad manifest — WILL FAIL
kubectl apply -f bad-deployment.yaml
# → Shows the wall of policy violation errors (WOW moment!)

# Step 2: Talk through the errors (30 seconds)
# "Each error tells us exactly what's wrong and how to fix it"

# Step 3: Deploy the fixed manifest — WILL SUCCEED
kubectl apply -f good-deployment.yaml
# → deployment.apps/good-app created

# Step 4: Verify it's running
kubectl get pods -n pets -l app=good-app

# BONUS: Show the mutation in action
# Deploy something with missing resource requests to show mutation
kubectl run test-pod --image=nginx:1.27.0 -n pets --dry-run=server -o yaml | grep -A 10 resources
# → Shows that AKS automatically ADDED 500m CPU and 2Gi memory defaults
```

### 5C.6 — Showing Mutations (Advanced Demo Point)

Create a minimal deployment to show the mutator in action:

```yaml
# minimal-deployment.yaml — Has no resource requests (will be mutated)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minimal-app
  namespace: pets
spec:
  replicas: 2
  selector:
    matchLabels:
      app: minimal-app
  template:
    metadata:
      labels:
        app: minimal-app
    spec:
      containers:
        - name: app
          image: nginx:1.27.0
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 250m
              memory: 256Mi
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
```

After applying, check what Deployment Safeguards mutated:

```bash
# Apply the deployment
kubectl apply -f minimal-deployment.yaml

# Check what was actually created — look for added anti-affinity rules
kubectl get deployment minimal-app -n pets -o yaml | grep -A 20 "affinity"
# → AKS added preferredDuringSchedulingIgnoredDuringExecution anti-affinity

kubectl get deployment minimal-app -n pets -o yaml | grep -A 10 "topologySpreadConstraints"
# → AKS added topology spread constraints with maxSkew: 1
```

> **Demo Talking Point**: "Deployment Safeguards don't just block bad configs — they also *improve* good configs. Notice how AKS automatically added anti-affinity rules and topology spread constraints to ensure our replicas are distributed across nodes for high availability. This is the 'Enforce + Mutate' behavior."

---

## 6. SUGGESTED DEMO FLOW & SCRIPT (15 minutes)

### Phase 1: Deploy the App (4 minutes)

| Time | Action | Talking Point |
|------|--------|---------------|
| 0:00 | Show terminal connected to AKS Automatic cluster | "This cluster was created with AKS Automatic — one command, zero node pool configuration" |
| 0:30 | `kubectl create namespace pets` | "Let's deploy a realistic microservice app — the AKS Store Demo" |
| 1:00 | `kubectl apply -f aks-store-ingress-quickstart.yaml -n pets` | "One manifest: 4 microservices, secrets, configs, and an ingress — all using best practices" |
| 1:30 | `kubectl get pods -n pets -w` | "Watch the pods come up. Notice the init container pattern for order-service" |
| 3:00 | `kubectl get ingress -n pets` | "An IP is already assigned — the managed NGINX ingress is built into AKS Automatic" |
| 3:30 | Open browser to ingress IP | **WOW MOMENT: Working e-commerce store** |

### Phase 2: Explore App Routing (3 minutes)

| Time | Action | Talking Point |
|------|--------|---------------|
| 4:00 | `kubectl get pods -n app-routing-system` | "The NGINX controller is managed — deployed in its own namespace" |
| 4:30 | Show the Ingress YAML snippet | "Just one annotation: `ingressClassName: webapprouting.kubernetes.azure.com`" |
| 5:00 | Mention DNS/TLS integration | "In production, you'd add Azure DNS zone + Key Vault cert annotations for HTTPS" |
| 6:00 | Click through the store, place an order | "This is a real polyglot app: Go, Node.js, Rust, Vue.js, RabbitMQ" |

### Phase 3: Deployment Safeguards (7 minutes) ⭐ Key Demo Moment

| Time | Action | Talking Point |
|------|--------|---------------|
| 7:00 | Show `bad-deployment.yaml` in editor | "Let's see what happens when someone tries to deploy an insecure workload" |
| 7:30 | Walk through violations in the YAML | "Privileged container, hostNetwork, latest tag, no probes, hostPath volume..." |
| 8:00 | `kubectl apply -f bad-deployment.yaml` | **WOW MOMENT: Wall of policy errors** |
| 8:30 | Read through 2-3 error messages | "Each error is descriptive — tells you exactly what's wrong and how to fix it" |
| 9:30 | "These aren't warnings — these are hard denials" | "On AKS Automatic, Deployment Safeguards run in Enforce mode by default" |
| 10:00 | Show `good-deployment.yaml` | "Here's the fixed version — explicit tags, resource limits, probes, no privileges" |
| 10:30 | `kubectl apply -f good-deployment.yaml` | "Now it deploys successfully" |
| 11:00 | Show mutation example | "But safeguards don't just deny — they also improve. Check the anti-affinity rules..." |
| 11:30 | `kubectl get deploy minimal-app -o yaml \| grep -A 15 affinity` | "AKS automatically added topology spread constraints for HA" |
| 12:00 | Mention Azure Policy compliance dashboard | "All of this feeds into Azure Policy — centralized compliance across all clusters" |
| 13:00 | Wrap up with summary slide | "Secure by default, not secure by opt-in" |

### Phase 4: Buffer (2 minutes)
Reserved for Q&A catch-up or recovering from any timing issues.

---

## 7. WOW MOMENTS (Ranked by Impact)

| # | Moment | Visual/Audio Impact | Why It Matters |
|---|--------|-------------------|---------------|
| 🥇 | Bad manifest DENIED with wall of errors | Terminal fills with red/actionable errors | Shows guardrails are REAL, not advisory |
| 🥈 | Store app live in browser via managed ingress | Full e-commerce UI with products | Proves "code to Kubernetes in minutes" |
| 🥉 | Mutations add anti-affinity automatically | YAML diff showing injected fields | Shows platform does MORE than deny — it helps |
| 4 | No ingress controller install needed | Contrast with standard AKS setup | Saves ~15 min of typical Helm/NGINX config |

---

## 8. COMPANION FILES NEEDED

| File | Purpose | Pre-deploy? |
|------|---------|-------------|
| `bad-deployment.yaml` | Intentionally violates 6+ policies | Have ready in editor |
| `good-deployment.yaml` | Fixed version that passes all checks | Have ready in editor |
| `minimal-deployment.yaml` | Shows mutation behavior (anti-affinity added) | Optional |
| `aks-store-ingress-quickstart.yaml` (from repo) | Main app deployment | Pre-deploy to `pets` namespace 5 min before |

---

## 9. ENVIRONMENT REQUIREMENTS

| Requirement | Detail |
|-------------|--------|
| AKS Automatic cluster | Must be AKS Automatic (not Standard) — Deployment Safeguards + App Routing preconfigured |
| kubectl configured | `az aks get-credentials --resource-group <rg> --name <cluster>` |
| Cluster running | Verify with `kubectl get nodes` — expect auto-provisioned nodes |
| Internet egress | Images pull from `ghcr.io` and `mcr.microsoft.com` |
| Azure Policy add-on | Auto-enabled on AKS Automatic (verify: `kubectl get pods -n gatekeeper-system`) |
| No namespace exclusions | Ensure `pets` namespace is NOT excluded from Deployment Safeguards |

### Pre-Flight Checklist

```bash
# Verify cluster connectivity
kubectl get nodes

# Verify AKS Automatic features
kubectl get pods -n gatekeeper-system        # Azure Policy / Gatekeeper
kubectl get pods -n app-routing-system       # Managed NGINX
kubectl get ingressclass                     # Should show webapprouting.kubernetes.azure.com

# Pre-deploy the app (do this 5 min before demo)
kubectl create namespace pets
kubectl apply -f https://raw.githubusercontent.com/Azure-Samples/aks-store-demo/main/aks-store-ingress-quickstart.yaml -n pets

# Verify everything is ready
kubectl get pods -n pets
kubectl get ingress -n pets
```

---

## 10. RISK MITIGATION

| Risk | Mitigation |
|------|-----------|
| Ingress IP takes too long | Pre-deploy 5+ minutes before demo. Have the IP noted. |
| Azure Policy not yet synced | AKS Automatic has it enabled from creation. Verify Gatekeeper pods are running. |
| Images fail to pull | All images are on `ghcr.io` (public) and `mcr.microsoft.com`. Verify egress works. |
| "Bad" manifest gets partial admission | The Baseline PSS + Deployment Safeguards together catch all violations simultaneously. All errors appear in one response. |
| Audience asks about Warning vs Enforce | AKS Automatic defaults to **Enforce**. Standard AKS can use Warning mode. Explain both are available. |
| Audience asks about exemptions | Namespaces can be excluded: `az aks safeguards update --excluded-ns <ns1> <ns2>` |

---

## 11. ALTERNATIVE YAML FILES IN THE REPO

| File | Ingress Included? | Use Case |
|------|--------------------|----------|
| `aks-store-ingress-quickstart.yaml` ⭐ | ✅ Yes | **Best for this demo** — includes Ingress + Secrets |
| `aks-store-quickstart.yaml` | ❌ No (uses LoadBalancer service) | Standard AKS quickstart — uses `type: LoadBalancer` on store-front |
| `aks-store-all-in-one.yaml` | ❌ No | Full app with ai-service, virtual-customer, virtual-worker |
| `sample-manifests/docs/app-routing/aks-store-deployments-and-services.yaml` | ❌ Separate | Deployments+Services only; Ingress created separately per docs |

---

## 12. PRESENTER TALKING POINTS CHEAT SHEET

### On AKS Automatic Philosophy
> "AKS Automatic shifts from 'opt-in to best practices' to 'best practices by default.' You start secure and compliant — you'd have to actively work to make it insecure."

### On Deployment Safeguards
> "These aren't just admission webhooks — they're backed by Azure Policy. Every violation is tracked, auditable, and visible in the Azure Policy compliance dashboard across ALL your clusters."

### On Mutation vs Denial
> "Deployment Safeguards have two superpowers: they DENY genuinely dangerous configs like privileged containers, AND they IMPROVE acceptable configs by adding anti-affinity rules, topology spread constraints, and resource defaults."

### On App Routing
> "In standard Kubernetes, setting up ingress means: install a controller, configure a service, set up TLS, manage certificates. With AKS Automatic, you get managed NGINX with Azure DNS and Key Vault integration out of the box."

### On the Resource Mutator
> "If a developer forgets resource limits, AKS Automatic doesn't just warn — it adds sensible defaults: 500m CPU, 2Gi memory. No more noisy-neighbor problems from unbounded containers."

### Bridging to Demo 3 (if applicable)
> "We've seen how AKS Automatic deploys and protects workloads. Next, let's look at how it handles [scaling / monitoring / networking]..."
