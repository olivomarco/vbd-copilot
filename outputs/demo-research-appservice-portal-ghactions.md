# DEEP Demo Research: Azure App Service — Portal Quickstart Deploy + GitHub Actions CI/CD

**Level:** L200 (clicks/CLI, guided portal walkthrough)  
**Target Duration:** ~7 minutes  
**Mode:** DEEP research  
**Date:** 2025-01-24

---

## 1. EXECUTIVE SUMMARY

This demo showcases the end-to-end developer experience of creating an Azure App Service Web App via the portal and configuring GitHub Actions CI/CD through the Deployment Center — all without writing a single line of deployment code. The audience sees a live web app running in ~3 minutes and continuous deployment flowing in ~4 more minutes.

**WOW Moments:**
1. 🎯 App is live on the internet in under 3 minutes from portal creation
2. 🔄 Deployment Center auto-generates a complete GitHub Actions workflow YAML — zero manual config
3. ⚡ A 1-line code change triggers automatic CI/CD pipeline visible in both GitHub Actions tab AND Azure portal Deployment Center logs
4. 🔒 User-assigned managed identity (OpenID Connect) is the new default — no more stored secrets

---

## 2. SAMPLE REPOSITORIES EVALUATED

### Option A: Node.js (RECOMMENDED for demo)
| Attribute | Detail |
|---|---|
| **Repo** | `Azure-Samples/nodejs-docs-hello-world` |
| **URL** | https://github.com/Azure-Samples/nodejs-docs-hello-world |
| **Files** | `index.js` (Express app, ~180 lines), `package.json` |
| **Default output** | Returns "Hello World!" at `/` and "Fabrikam Bank API" at `/api` |
| **Framework** | Express.js with body-parser, cors |
| **Port** | `process.env.PORT \|\| 3000` (App Service compatible out of the box) |
| **Runnability** | ⭐⭐⭐⭐⭐ Works immediately on App Service, no build step needed |
| **Visual Impact** | ⭐⭐⭐ Basic text output; good for "it works" proof |
| **Demo Advantage** | Has API endpoints (`/api/accounts`) making it look like a real app |

**package.json key details:**
```json
{
  "name": "app-service-hello-world",
  "scripts": { "start": "node index.js" },
  "dependencies": {
    "body-parser": "^1.19.0",
    "cors": "^2.8.5",
    "express": "^4.17.1"
  },
  "engines": { "node": ">=10" }
}
```

### Option B: Python (simpler, but equally effective)
| Attribute | Detail |
|---|---|
| **Repo** | `Azure-Samples/python-docs-hello-world` |
| **URL** | https://github.com/Azure-Samples/python-docs-hello-world |
| **Files** | `app.py` (6 lines!), `requirements.txt` (just `Flask`) |
| **Default output** | Returns "Hello, World!" |
| **Runnability** | ⭐⭐⭐⭐⭐ Minimal Flask app, works instantly |
| **Visual Impact** | ⭐⭐⭐ Same text output |
| **Demo Advantage** | Only 6 lines of code — incredibly clean to show on screen |

**app.py (entire file):**
```python
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello, World!"
```

### RECOMMENDATION
Use **Node.js** for audience familiarity and richer API endpoints, OR **Python** if the audience is data/ML-focused and you want to emphasize simplicity (6-line app).

---

## 3. PREREQUISITES — What to Pre-Create vs. Create Live

### PRE-CREATED (before demo):
| Item | Why Pre-Create | Setup Command/Action |
|---|---|---|
| **Azure subscription** | Cannot create live | Have active subscription ready |
| **GitHub account** | OAuth flow is slow live | Already logged in on browser |
| **Fork of sample repo** | Need your own repo for CI/CD writes | Fork `Azure-Samples/nodejs-docs-hello-world` to your personal/org GitHub |
| **Browser tabs pre-loaded** | Save time | Tab 1: Azure Portal, Tab 2: GitHub repo, Tab 3: (empty for app URL) |
| **Azure Portal signed in** | Avoid MFA delays | Pre-authenticated session |

### CREATED LIVE (during demo):
| Item | Why Create Live | Time Cost |
|---|---|---|
| **Resource Group** | Part of the portal flow, shows organization | 10 seconds (inline) |
| **App Service Plan** | Shows pricing tier selection (Free F1) | 10 seconds (inline) |
| **Web App** | THE core demo action | ~90 seconds total |
| **Deployment Center config** | THE CI/CD demo action | ~60 seconds |

### ENVIRONMENT REQUIREMENTS
- **Browser:** Edge or Chrome (latest), signed into Azure Portal + GitHub
- **Screen resolution:** 1920×1080+ recommended (portal blades are wide)
- **Network:** Reliable internet (deployment takes 30-60s)
- **Azure RBAC:** Owner or Contributor + User Access Administrator on subscription (needed for managed identity creation in Deployment Center)

---

## 4. DEMO SCENARIO — DETAILED STEP-BY-STEP

### PHASE 1: Create Web App in Azure Portal (~3 min)

#### Step 1.1: Navigate to Create Resource
- **Portal URL:** `https://portal.azure.com/#create/Microsoft.WebSite`
- **Alternative path:** Portal Home → `+ Create a resource` → Search "Web App" → Click `Create`
- **Talking Point:** *"Azure App Service is Microsoft's fully managed platform for hosting web applications. Let's create one right now."*

#### Step 1.2: Basics Tab — Project Details
| Field | Value | Notes |
|---|---|---|
| **Subscription** | (your subscription) | Pre-selected |
| **Resource Group** | Click `Create new` → type `rg-demo-appservice` | *"Resource groups are logical containers — think of them as folders for your cloud resources."* |

#### Step 1.3: Basics Tab — Instance Details
| Field | Value | Notes |
|---|---|---|
| **Name** | `demo-webapp-<unique>` (e.g., `demo-webapp-contoso-2025`) | Must be globally unique; becomes `<name>.azurewebsites.net` |
| **Publish** | `Code` | (default) |
| **Runtime stack** | `Node 20 LTS` or `Node 22 LTS` | *"App Service supports Node, Python, .NET, Java, PHP, Ruby — all the major stacks."* |
| **Operating System** | `Linux` | (recommended for Node/Python; cheaper) |
| **Region** | `East US` or nearest | *"Choose a region close to your users."* |

**Talking Point:** *"Notice I'm choosing Node 20 LTS — App Service handles the runtime for us. No Docker, no VMs, no patches to manage."*

#### Step 1.4: Basics Tab — Pricing Plan
| Field | Value | Notes |
|---|---|---|
| **Linux Plan** | Click `Create new` → `plan-demo-appservice` | |
| **Pricing plan** | `Free F1` | ⚠️ Click the dropdown to show options |

**Available tiers to highlight (don't select, just show the dropdown):**
- **Free F1:** 60 CPU min/day, 1 GB RAM — perfect for dev/test
- **Basic B1:** $13/month, custom domains, manual scale — good for small apps
- **Standard S1:** $70/month, auto-scale, staging slots — production ready
- **Premium P1v3:** $138/month, enhanced performance, VNet integration

**Talking Point:** *"For this demo I'll use the Free tier — zero cost. In production you'd typically start with Basic or Standard for custom domains and SSL."*

#### Step 1.5: Deployment Tab (NEW — important for demo!)
| Field | Value | Notes |
|---|---|---|
| **Continuous deployment** | `Enable` | 🎯 **THIS IS NEW** — you can configure GitHub Actions during creation! |
| **GitHub account** | Authorize/select your account | |
| **Organization** | Your GitHub org/username | |
| **Repository** | `nodejs-docs-hello-world` (your fork) | |
| **Branch** | `main` | |
| **Authentication type** | `User-assigned identity` | Default; uses OpenID Connect (OIDC) — no stored secrets! |

**Talking Point:** *"Here's the magic — I can configure CI/CD right during creation. Azure will auto-generate a GitHub Actions workflow file and commit it to my repo. Notice it uses OpenID Connect with managed identity — that means no secrets stored in GitHub."*

> **ALTERNATIVE FLOW:** Skip the Deployment tab during creation → configure it later via Deployment Center (Phase 2). This is better for showing the two-step story: "first create, then add CI/CD."

#### Step 1.6: Skip remaining tabs, Review + Create
- Click **Review + create**
- Review the summary panel (good time to highlight what's being created)
- Click **Create**
- Wait ~30-60 seconds for deployment

**Talking Point:** *"Azure is now provisioning our App Service Plan, the Web App, and if we enabled CI/CD, it's also setting up the managed identity and committing the workflow file to GitHub."*

#### Step 1.7: Go to Resource → Browse
- Click **Go to resource** when deployment completes
- In the Overview blade, click the **Default domain** URL (e.g., `https://demo-webapp-contoso-2025.azurewebsites.net`)
- 🎯 **WOW MOMENT:** Browser shows "Hello World!" (or the default App Service placeholder page)

**Talking Point:** *"And just like that — we have a live web application running on Azure, with a public URL, HTTPS by default, and it took us about 2 minutes."*

---

### PHASE 2: Configure GitHub Actions CI/CD via Deployment Center (~2 min)

> **Note:** If you configured CI/CD in the Deployment tab during creation, skip to Phase 3 and just show the Deployment Center Logs tab. The flow below assumes you did NOT enable it during creation.

#### Step 2.1: Open Deployment Center
- From the App Service blade, left sidebar → **Deployment** section → **Deployment Center**
- **Talking Point:** *"The Deployment Center is your one-stop shop for configuring how code gets to your app."*

#### Step 2.2: Settings Tab — Configure Source
| Field | Value |
|---|---|
| **Source** | `GitHub` |
| **Authorize** | Click `Authorize` if first time (OAuth popup) |
| **Organization** | Your GitHub username/org |
| **Repository** | `nodejs-docs-hello-world` |
| **Branch** | `main` |
| **Build provider** | `GitHub Actions` (default) |
| **Authentication type** | `User-assigned identity` (recommended) |
| **Preview file** | 🎯 Click this to show the auto-generated YAML! |

#### Step 2.3: Preview the Auto-Generated Workflow YAML
**Talking Point:** *"Before I save, let me show you what Azure is about to commit to my repo..."*

Click **Preview file** — this shows the auto-generated `.github/workflows/` YAML file. The generated workflow looks approximately like this:

```yaml
# Docs for the Azure Web Apps Deploy action:
# https://github.com/Azure/webapps-deploy
# More GitHub Actions for Azure: https://github.com/Azure/actions

name: Build and deploy Node.js app to Azure Web App - demo-webapp-contoso-2025

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js version
        uses: actions/setup-node@v4
        with:
          node-version: '20.x'

      - name: npm install, build, and test
        run: |
          npm install
          npm run build --if-present
          npm run test --if-present

      - name: Zip artifact for deployment
        run: zip release.zip ./* -r

      - name: Upload artifact for deployment job
        uses: actions/upload-artifact@v4
        with:
          name: node-app
          path: release.zip

  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment:
      name: 'Production'
      url: ${{ steps.deploy-to-webapp.outputs.webapp-url }}

    steps:
      - name: Download artifact from build job
        uses: actions/download-artifact@v4
        with:
          name: node-app

      - name: Unzip artifact for deployment
        run: unzip release.zip

      - name: Login to Azure
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: 'Deploy to Azure Web App'
        id: deploy-to-webapp
        uses: azure/webapps-deploy@v3
        with:
          app-name: 'demo-webapp-contoso-2025'
          slot-name: 'Production'
          package: .
```

**Key talking points about the YAML:**
1. *"Two jobs: build and deploy — standard CI/CD pattern"*
2. *"Triggered on push to main AND has workflow_dispatch for manual runs"*
3. *"Uses `azure/login@v2` with OpenID Connect — no passwords or PATs stored"*
4. *"Secrets (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`) are auto-created in GitHub"*
5. *"Uses `azure/webapps-deploy@v3` — the official Azure deployment action"*

#### Step 2.4: Save
- Click **Save** at the top
- **What happens behind the scenes:**
  1. Azure creates a user-assigned managed identity
  2. Creates federated credential linking GitHub repo ↔ Azure identity
  3. Adds `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` as GitHub secrets
  4. Commits the workflow YAML file to `.github/workflows/` in your repo
  5. The commit triggers the first workflow run

**Talking Point:** *"One click of Save just did 5 things: created a managed identity, configured federated auth, set up GitHub secrets, committed the workflow file, and kicked off the first deployment. All zero-touch."*

---

### PHASE 3: Show the CI/CD Pipeline Running (~1 min)

#### Step 3.1: Show in Deployment Center Logs Tab
- Stay in Deployment Center → click the **Logs** tab
- Shows deployment history with commit hash, status, timestamp
- Click a log entry to see details

#### Step 3.2: Show in GitHub Actions Tab
- Switch to browser Tab 2 (GitHub repo)
- Click the **Actions** tab
- Shows the workflow run in progress (or recently completed)
- Click into the run to show the build/deploy jobs
- 🎯 **WOW MOMENT:** The workflow YAML file appeared in the repo automatically (check `.github/workflows/` in Code tab)

**Talking Point:** *"Here in GitHub Actions, we can see our CI/CD pipeline running. Azure committed this workflow file automatically. Every push to main will now trigger a build and deploy."*

---

### PHASE 4: Make a Code Change — Live CI/CD (~2 min)

#### Step 4.1: Edit code in GitHub (browser)
- Navigate to `index.js` in the GitHub repo
- Click the ✏️ pencil icon to edit
- Change line ~58 from:
  ```javascript
  return res.send("Hello World!");
  ```
  to:
  ```javascript
  return res.send("Hello from Azure App Service! 🚀");
  ```
- Click **Commit changes** → Commit directly to `main`

**Talking Point:** *"I'm making a simple change right in the GitHub browser editor. In real life this would be a pull request, but for the demo let's commit directly."*

#### Step 4.2: Watch the Pipeline
- Click the **Actions** tab — new workflow run appears immediately
- Show it progressing through build → deploy stages (~60-90 seconds)

#### Step 4.3: Refresh the App
- Switch to Tab 3 with the app URL
- Refresh the page
- 🎯 **WOW MOMENT:** Shows "Hello from Azure App Service! 🚀"

**Talking Point:** *"From code change to live update — that's continuous deployment. No manual steps, no SSH, no FTP. Just push code and Azure handles the rest."*

---

## 5. ALTERNATIVE: CLI-ONLY QUICK DEPLOY (for backup/speed)

If the portal is slow or you want a faster backup option:

```bash
# Clone the sample
git clone https://github.com/Azure-Samples/nodejs-docs-hello-world.git
cd nodejs-docs-hello-world

# Deploy in one command (creates RG + Plan + App + deploys code)
az webapp up --sku F1 --name demo-webapp-$(date +%s) --runtime "NODE:20-lts"

# Output includes the URL — open it!
```

**`az webapp up` does everything:**
- Creates a resource group (default name based on region)
- Creates an App Service plan (Free F1)
- Creates the Web App
- Zip-deploys the code
- Caches config in `.azure/config` for subsequent runs

---

## 6. AUTO-GENERATED WORKFLOW YAML DEEP DIVE

### For Node.js (what Deployment Center generates):
```yaml
name: Build and deploy Node.js app to Azure Web App - <app-name>

on:
  push:
    branches: [ main ]
  workflow_dispatch:

permissions:
  id-token: write    # Required for OIDC token
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20.x'
      - run: |
          npm install
          npm run build --if-present
          npm run test --if-present
      - run: zip release.zip ./* -r
      - uses: actions/upload-artifact@v4
        with:
          name: node-app
          path: release.zip

  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment:
      name: 'Production'
      url: ${{ steps.deploy-to-webapp.outputs.webapp-url }}
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: node-app
      - run: unzip release.zip
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - uses: azure/webapps-deploy@v3
        with:
          app-name: '<app-name>'
          slot-name: 'Production'
          package: .
```

### For Python (if using Python sample):
```yaml
name: Build and deploy Python app to Azure Web App - <app-name>

on:
  push:
    branches: [ main ]
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - run: zip release.zip ./* -r
      - uses: actions/upload-artifact@v4
        with:
          name: python-app
          path: release.zip

  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment:
      name: 'Production'
      url: ${{ steps.deploy-to-webapp.outputs.webapp-url }}
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: python-app
      - run: unzip release.zip
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - uses: azure/webapps-deploy@v3
        with:
          app-name: '<app-name>'
          slot-name: 'Production'
          package: .
```

### Authentication Methods Comparison:
| Method | Security | Setup Complexity | Portal Support |
|---|---|---|---|
| **User-assigned identity (OIDC)** | ⭐⭐⭐⭐⭐ Short-lived tokens | Auto-configured by portal | ✅ Default |
| **Publish profile** | ⭐⭐⭐ Long-lived XML credential | Download from portal → paste as GitHub secret | ✅ When basic auth enabled |
| **Service principal** | ⭐⭐⭐⭐ App registration required | Manual CLI setup | ❌ Manual only |

---

## 7. PRESENTER VISUAL FLOW — SCREEN-BY-SCREEN

| Time | Screen | What Audience Sees | Presenter Action | Talking Point |
|------|--------|-------------------|-----------------|---------------|
| 0:00 | Azure Portal Home | Clean portal dashboard | Navigate to Create Resource | *"Let's build and deploy a web app in under 7 minutes"* |
| 0:30 | Create Web App - Basics | Form with subscription, RG, name fields | Fill in Instance Details | *"App Service handles the infrastructure — just pick your runtime"* |
| 1:30 | Create Web App - Basics | Pricing plan dropdown | Show tier options, select Free F1 | *"Free tier for dev, Basic for small prod, Standard for auto-scale"* |
| 2:00 | Create Web App - Deployment | GitHub integration panel | Enable continuous deployment, select repo | *"CI/CD configured right at creation time — and it uses OIDC, not stored secrets"* |
| 2:30 | Create Web App - Review | Summary of all settings | Click Create | *"Review looks good — creating now"* |
| 3:00 | Deployment in progress | Blue progress bar | Wait (fill with talking) | *"Azure is provisioning the plan, app, and setting up the GitHub connection"* |
| 3:30 | Resource created | "Your deployment is complete" | Click Go to resource | *"Done! Let's see our app"* |
| 3:45 | App Service Overview | Overview blade with URL | Click Default domain URL | *"Here's our public URL with HTTPS included"* |
| 4:00 | Browser - App | "Hello World!" text | Pause for effect | *"🎯 Live on the internet. HTTPS. Zero server management."* |
| 4:15 | Deployment Center | Logs tab showing deployment | Show latest deployment entry | *"The Deployment Center shows all deployments — linked to GitHub commits"* |
| 4:45 | GitHub - Actions tab | Workflow runs list | Click into workflow run | *"Here's the GitHub side — our CI/CD pipeline ran automatically"* |
| 5:15 | GitHub - index.js | Source code | Click edit pencil, change text | *"Let's trigger CI/CD with a real code change"* |
| 5:45 | GitHub - Commit | Commit dialog | Commit to main | *"In production, this would be a PR — but for the demo, straight to main"* |
| 6:00 | GitHub - Actions | New run in progress | Show build → deploy stages | *"Pipeline kicked off instantly on the push event"* |
| 6:30 | Browser - App | Refreshed page | Refresh to show updated text | *"🎯 Code change → CI/CD → Live in production. That's the power of App Service + GitHub Actions"* |
| 7:00 | Wrap up | Any screen | Summarize | *"We created an app, configured CI/CD, and deployed a change — all in 7 minutes, no infrastructure management"* |

---

## 8. DEMO EVALUATION SCORECARD

| Criteria | Score | Notes |
|---|---|---|
| **Runnability** | ⭐⭐⭐⭐⭐ 5/5 | Works first time, every time with Free tier. Sample repos are maintained by Azure team. |
| **Visual Impact** | ⭐⭐⭐⭐ 4/5 | Portal UI is visually rich. GitHub Actions running live is compelling. App output is plain text (could customize). |
| **Level Calibration** | ✅ L200 | All portal clicks + one browser edit. No CLI required. Perfect for decision-maker / IT-pro audience. |
| **Customer Relevance** | ⭐⭐⭐⭐⭐ 5/5 | Every customer deploys web apps. CI/CD is table-stakes. This shows Azure's integrated developer experience. |
| **Risk of Failure** | ⭐⭐⭐⭐ Low | Main risks: (1) GitHub OAuth timeout, (2) unique name collision, (3) RBAC insufficient for managed identity. Pre-fork + pre-auth eliminates most. |
| **Time Predictability** | ⭐⭐⭐⭐ 4/5 | Portal creation: 60-90s. GitHub Actions run: 60-120s. Total 5-8 min depending on Azure speed. |

---

## 9. RISK MITIGATION & TROUBLESHOOTING

| Risk | Mitigation |
|---|---|
| **GitHub OAuth fails or is slow** | Pre-authorize GitHub in Deployment Center before the demo (connect + disconnect) |
| **App name already taken** | Use timestamped names: `demo-app-{mmdd}-{hhmm}` |
| **Free tier quota exceeded** | Delete old demo apps. F1 allows only 10 apps per region. |
| **Managed identity creation fails** | Ensure demo account has Owner or Contributor + User Access Administrator. Or pre-create the identity. |
| **GitHub Actions run is slow** | Have a pre-completed run ready to show. Use "workflow_dispatch" to trigger manual runs. |
| **Portal is slow/loading** | Have `az webapp up` CLI command ready as backup (see Section 5) |
| **App shows default page instead of Hello World** | First deployment may take 1-2 min. Show Log Stream (Monitoring > Log stream) while waiting. |

---

## 10. CLEANUP COMMANDS

```bash
# Delete everything in one command
az group delete --name rg-demo-appservice --yes --no-wait

# Or via portal: Resource Group > Delete resource group
```

---

## 11. SOURCE DOCUMENTATION SUMMARY

### Source 1: Quickstart Node.js (learn.microsoft.com/azure/app-service/quickstart-nodejs)
- **Covers:** VS Code, CLI (`az webapp up`), Portal, and FTP deployment methods
- **Portal steps:** Create Resource > Web App > Basics tab (name, Node 20/22 LTS, Linux, Free F1) > Review + Create
- **Key insight:** `az webapp up --sku F1 --name <name>` is the fastest CLI path (creates everything in one command)
- **Runtime recommendation:** Node 24 LTS is now listed as recommended in docs

### Source 2: Deploy GitHub Actions (learn.microsoft.com/azure/app-service/deploy-github-actions)
- **Covers:** Manual workflow setup with OpenID Connect, publish profile, or service principal
- **Key insight:** GitHub Actions deployment is now integrated into the Create Web App wizard (Deployment tab)
- **Authentication:** User-assigned identity (OIDC) is recommended; publish profile works when basic auth is enabled
- **Workflow template:** Uses `azure/login@v2` + `azure/webapps-deploy@v3`

### Source 3: Continuous Deployment (learn.microsoft.com/azure/app-service/deploy-continuous-deployment)
- **Covers:** Deployment Center configuration for GitHub, Bitbucket, Azure Repos, Local Git
- **Key insight:** GitHub Actions is the DEFAULT build provider for GitHub source (not Kudu anymore)
- **User-assigned identity:** Portal auto-creates federated credential, sets GitHub secrets, commits workflow YAML
- **Build providers:** GitHub Actions (default for GitHub), App Service Build Service (Kudu), Azure Pipelines
- **Repository requirements:** Node.js needs `server.js`, `app.js`, or `package.json` with start script; Python needs `*.py` + `requirements.txt`

---

## 12. COMPANION FILES FOR THIS DEMO

| File Type | Suggested Name | Purpose |
|---|---|---|
| **Pre-demo checklist** | `pre-demo-checklist.md` | Fork repo, verify RBAC, pre-auth GitHub, test app name availability |
| **Presenter notes** | `presenter-notes.md` | Talking points keyed to each screen transition |
| **Backup CLI script** | `backup-deploy.sh` | `az webapp up` commands in case portal fails |
| **Slide deck** | `appservice-cicd-intro.pptx` | 2-3 intro slides before live demo, architecture diagram after |
| **Post-demo resources** | `resources.md` | Links to docs, Learn modules, sample repos |

