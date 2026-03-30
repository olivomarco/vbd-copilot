# Installation Guide

## Prerequisites

- A **GitHub Copilot** subscription (Individual, Business, or Enterprise) with CLI access
- The [**GitHub CLI** (`gh`)](https://cli.github.com/) installed and authenticated (`gh auth login`)
- For **plugin mode**: a GitHub Copilot client that supports `copilot plugin install`, plus [`uv`](https://docs.astral.sh/uv/) on your `PATH`
- **One** of the following run methods:
  - **GitHub Copilot plugin** - install directly from `olivomarco/vbd-copilot`
  - **Docker** (recommended) - just Docker Desktop / Docker Engine
  - **GitHub Codespaces** - nothing to install, runs in the browser
  - **Native** - Python 3.11+, LibreOffice Impress, Poppler on your machine

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

## Option A - Install as a GitHub Copilot plugin

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

## Option B - Docker (recommended for the standalone TUI)

The Docker image bundles Python, LibreOffice, Poppler, and all pip dependencies. Nothing else to install.

```bash
# Clone the repo
git clone https://github.com/olivomarco/vbd-copilot.git
cd vbd-copilot

# Build the image (first time only, ~1 GB)
docker build -t csa-copilot .

# Run the TUI
docker run -it --rm \
  -e GITHUB_TOKEN=$(gh auth token) \
  -v "$(pwd)/outputs:/app/outputs" \
  csa-copilot
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

## Option C - GitHub Codespaces (zero install)

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

## Option D - Native install

For users who prefer running directly on their machine without containers.

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
