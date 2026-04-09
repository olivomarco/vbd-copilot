# Installation Guide

## Prerequisites

- A **GitHub Copilot** subscription (Individual, Business, or Enterprise) with CLI access
- The [**GitHub CLI** (`gh`)](https://cli.github.com/) installed and authenticated (`gh auth login`)
- For the **desktop app**: Node.js 18+ and npm, Python 3.11+, [`uv`](https://docs.astral.sh/uv/)
- For **plugin mode**: a GitHub Copilot client that supports `copilot plugin install`, plus [`uv`](https://docs.astral.sh/uv/) on your `PATH`
- For the **CLI**: one of Docker, GitHub Codespaces, or a native Python 3.11+ setup

---

## One-time setup: authenticate the GitHub CLI

Before using any run method, authenticate the GitHub CLI. If you already use GitHub Copilot in VS Code, you still need this step for Docker and native usage.

```bash
# Install the GitHub CLI (if not already present)
# macOS:  brew install gh
# Linux:  see https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Sign in - opens a browser for device-flow auth
gh auth login

# Verify it works
gh auth token                 # should print a token
gh copilot --version          # confirms Copilot extension works
```

This stores your GitHub OAuth token in your OS credential store (macOS Keychain, Windows Credential Manager) where `gh auth token` can retrieve it.

---

## Option A — Desktop App (experimental 🧪)

> [!CAUTION]
> The desktop UI is **experimental**. It works for most flows but may have rough edges, incomplete features, or unexpected behaviour. If something breaks, fall back to the [CLI options below](#option-c--cli-via-docker).

The desktop app gives you a graphical interface with form-based briefs, concurrent agent runs, inline output previews, and a full output library — all in a single window. It runs as an Electron shell around the existing Python backend.

### What you get

| Page | What it does |
|------|-------------|
| **Launchpad** | Form-based briefs — pick a workflow, fill in the details, hit go |
| **Agent Workspace** | Live conversation view with the running agent |
| **Mission Control** | Monitor multiple concurrent agent runs at once |
| **Output Library** | Browse all generated artifacts with inline previews (PPTX carousel, Markdown renderer, code explorer) |
| **Sessions** | Resume, inspect, and manage past sessions |
| **Settings** | Model selection, preferences |

### Setup

**1. Clone and install Python dependencies:**

```bash
git clone https://github.com/olivomarco/vbd-copilot.git
cd vbd-copilot
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

**2. Install system dependencies** (needed for PPTX thumbnail generation):

```bash
# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y libreoffice-impress poppler-utils

# macOS (via Homebrew)
brew install --cask libreoffice && brew install poppler

# Fedora / RHEL
sudo dnf install libreoffice-impress poppler-utils
```

**3. Install frontend dependencies:**

```bash
cd frontend
npm install
```

### Run with Electron (desktop window)

Open two terminals from the `frontend/` directory:

```bash
# Terminal 1 — Vite dev server
npm run dev

# Terminal 2 — Electron shell
npm run electron:dev
```

The Electron process spawns the Python backend on a random port, connects over WebSocket, and loads the React UI. The Vite dev server (port 5173) proxies API calls to the Python backend automatically.

### Run in the browser (no Electron)

If you prefer a browser tab over a desktop window:

```bash
# Start Vite dev server (auto-starts the Python backend on port 18080)
cd frontend && npm run dev
```

Then open `http://localhost:5173`. The Vite dev server proxies API calls to the Python backend automatically — no need to start it separately.

### Build the standalone Electron app

To package a distributable desktop application:

```bash
cd frontend
npm run electron:build
```

This compiles TypeScript, bundles the React frontend, and runs `electron-builder` to produce a platform-specific binary.

---

## Option B — Install as a GitHub Copilot plugin

If you want CSA-Copilot available inside GitHub Copilot itself, install it directly from the published GitHub repository. The plugin manifest lives at `.github/plugin/plugin.json`, so the repo installs cleanly from its URL with no extra path suffix.

```bash
# Install from the published repository
copilot plugin install olivomarco/vbd-copilot

# Verify it is available
copilot plugin list
```

Once installed, the CSA-Copilot agents become available inside Copilot. The same prompts shown later in this README work there too, for example:

```text
@slide-conductor Create a 30min L200 deck on Microsoft Fabric
@demo-conductor Build 2 demos on Azure Container Apps
@ai-solution-architect Design the architecture for a customer support copilot on Azure
```

Notes:

- The plugin ships a dedicated plugin package under `.github/plugin/`.
- The canonical agent definitions live in `agent_defs/` as `.agent.md` files, and the plugin manifest points at those directories directly.
- The plugin starts one local MCP server, `csa-tools`, which exposes the repo's custom tools: `bing_search`, all QA check runners, and the hackathon validator.
- The startup wrapper prefers a repo-local `.venv`, then falls back to `uv run`, then to `python3` if the required dependencies are already installed.
- The first tool invocation can take a little longer because `uv` may need to resolve the Python environment from `pyproject.toml`.

To remove the plugin later:

```bash
copilot plugin uninstall csa-copilot
```

---

## Option C — CLI via Docker

The Docker image bundles Python, LibreOffice, Poppler, and all pip dependencies. Nothing else to install. This is the easiest way to run the CLI.

```bash
# Clone the repo
git clone https://github.com/olivomarco/vbd-copilot.git
cd vbd-copilot

# Build the image (first time only, ~1 GB)
docker build -t csa-copilot .

# Run the CLI (macOS / Linux)
docker run -it --rm \
  -e GITHUB_TOKEN=$(gh auth token) \
  -v "$(pwd)/outputs:/app/outputs" \
  csa-copilot
```

**Windows (CMD):** The `$(…)` syntax doesn't work in CMD. Copy your token manually:

```cmd
gh auth token
# Copy the output, then:
docker run -it --rm -e GITHUB_TOKEN=YOUR_TOKEN_HERE -v "%cd%/outputs:/app/outputs" csa-copilot
```

**Windows (PowerShell):**

```powershell
docker run -it --rm -e GITHUB_TOKEN=$(gh auth token) -v "${PWD}/outputs:/app/outputs" csa-copilot
```

| Parameter | Purpose |
|-----------|---------|
| `-e GITHUB_TOKEN=$(gh auth token)` | Passes your GitHub auth token into the container |
| `./outputs` -> `/app/outputs` | Generated `.pptx`, demo guides, and scripts persist on your host |

> [!TIP]
> Add an alias for convenience:
>
> ```bash
> alias csa='docker run -it --rm -e GITHUB_TOKEN=$(gh auth token) -v "$(pwd)/outputs:/app/outputs" csa-copilot'
> ```
>
> Then just run `csa` from inside the repo.

> [!NOTE]
> **Why `GITHUB_TOKEN`?** On native installs, the Copilot CLI reads tokens from your OS credential store
> (macOS Keychain / Windows Credential Manager). Docker containers cannot access the host credential
> store, so the token is passed via environment variable instead. The `gh auth token` command extracts
> it for you automatically.

---

## Option D — CLI via GitHub Codespaces (zero install)

If you don't want to install anything locally, open the repo in a Codespace. The dev container installs all system and Python dependencies automatically.

1. Go to the repo on GitHub and click **Code** -> **Codespaces** -> **Create codespace on main**
2. Wait for the container to build (~2-3 minutes the first time)
3. In the Codespace terminal, run:

```bash
python app.py
```

That's it - LibreOffice, Poppler, and all Python packages are pre-installed by the dev container.

> [!NOTE]
> Codespaces requires a GitHub plan with Codespaces minutes (free tier includes 60h/month for individual accounts).

---

## Option E — CLI native install

For users who prefer running the CLI directly on their machine without containers.

**System dependencies** (install once):

```bash
# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y libreoffice-impress poppler-utils

# macOS (via Homebrew)
brew install --cask libreoffice && brew install poppler

# Fedora / RHEL
sudo dnf install libreoffice-impress poppler-utils
```

**Python setup:**

```bash
cd vbd-copilot
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

**Run:**

```bash
python app.py
```
