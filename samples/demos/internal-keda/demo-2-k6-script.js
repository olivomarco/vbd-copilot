// =============================================================================
// demo-2-k6-script.js
// KEDA + Prometheus Demo - k6 Staged Load Profile
//
// Usage (from within cluster via k6 operator, or externally with SERVICE_IP):
//
//   # Option A: Run inside the cluster (recommended for demo)
//   #   1. Deploy k6 operator or use a temporary pod:
//   kubectl run k6-load \
//     --image=grafana/k6:latest \
//     --restart=Never \
//     --namespace=demo \
//     --overrides='{"spec":{"containers":[{"name":"k6-load","image":"grafana/k6:latest","command":["k6","run","-"],"stdin":true,"tty":true}]}}' \
//     -it --rm -- k6 run - < demo-2-k6-script.js
//
//   # Option B: Run with a NodePort or LoadBalancer Service IP
//   export SERVICE_URL="http://<EXTERNAL_IP>"
//   k6 run -e SERVICE_URL=$SERVICE_URL demo-2-k6-script.js
//
//   # Option C: Quick load via hey (no k6 required)
//   kubectl run load-gen \
//     --image=alpine/hey \
//     --restart=Never \
//     --namespace=demo \
//     -- hey -z 5m -c 50 http://demo-app.demo.svc.cluster.local/
//
// Load profile (total ~5 minutes):
//   0:00 - 1:00   Ramp from 0 to 50 virtual users
//   1:00 - 4:00   Hold at 50 virtual users (sustained load)
//   4:00 - 5:00   Ramp from 50 back to 0
//
// Expected KEDA behavior:
//   - Pods 0 -> ~8-10 during ramp-up (rate ~47 req/s / threshold 5 = 10 replicas)
//   - Pods hold at max during sustained phase
//   - Pods step down during ramp-down
//   - Pods return to 0 after cooldownPeriod (60s post last request)
//
// Watch scaling in a separate terminal:
//   watch -n 3 kubectl get pods -n demo
//   watch -n 5 kubectl get hpa -n demo
//
// Prerequisites:
//   - k6 installed: https://grafana.com/docs/k6/latest/get-started/installation/
//   - demo-app Service reachable at TARGET_URL
// =============================================================================

import http from 'k6/http';
import { check, sleep } from 'k6';

// Override TARGET_URL via env var for external runs:
//   k6 run -e TARGET_URL=http://<EXTERNAL_IP> demo-2-k6-script.js
const TARGET_URL = __ENV.TARGET_URL || 'http://demo-app.demo.svc.cluster.local/';

export let options = {
  stages: [
    { duration: '1m', target: 50 },   // Ramp up   - watch pods climb
    { duration: '3m', target: 50 },   // Hold load - show stable replica count
    { duration: '1m', target: 0 },    // Ramp down - watch pods begin to drain
  ],
  thresholds: {
    // Soft thresholds for demo visibility - not hard failures
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.05'],
  },
};

export default function () {
  const res = http.get(TARGET_URL);

  // Log non-200 responses during demo so audience sees live feedback
  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  // 0.1s sleep -> each VU fires ~10 req/s -> 50 VUs = ~500 req/s to service
  // KEDA will see this via rate() and scale accordingly
  sleep(0.1);
}
