"""
Custom tools for VBD-Copilot.

Most capabilities are provided by the Copilot CLI's built-in tools:
  - web_fetch         -> fetch any URL from the internet
  - str_replace_editor -> view/create/edit files
  - bash              -> run shell commands
  - grep / glob       -> search code
  - ask_user          -> ask the user questions
  - task              -> invoke subagents (used by conductors to delegate work)
  - report_intent     -> declare current intent

Custom tools defined here:
  1. bing_search          - web search (CLI has no built-in equivalent)
  2. run_pptx_qa_checks   - programmatic layout/content QA on .pptx files
  3. run_demo_qa_checks   - programmatic QA on demo packages (guide + scripts)

Subagent invocation:
  Conductors delegate to subagents via the CLI's built-in 'task' tool.
  Subagents (infer=False) are registered in custom_agents and the CLI
  handles the lifecycle (fresh context, isolated prompt, tools, events).
  No custom delegation tools are needed - the 'task' tool handles it.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request

from pydantic import BaseModel, Field

from copilot import define_tool

log = logging.getLogger(__name__)

# Shared SSL context (for Bing HTML scraping fallback)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_REQUEST_TIMEOUT = 15


# =============================================================================
# Bing Search
# =============================================================================

def _fetch_url(url: str, *, max_bytes: int = 200_000) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; CopilotSDKResearchBot/1.0; "
                "+https://github.com/github/copilot-sdk)"
            ),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT, context=_SSL_CTX) as resp:
        raw = resp.read(max_bytes)
    charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def _parse_bing_results(html_str: str, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    parts = re.split(r'<li\s+class="b_algo"[^>]*>', html_str)
    for block in parts[1 : max_results + 1]:
        url = ""
        m_cite = re.search(r"<cite[^>]*>(.*?)</cite>", block, re.S)
        if m_cite:
            cite_text = re.sub(r"<[^>]+>", "", m_cite.group(1)).strip()
            cite_url = cite_text.replace(" \u203a ", "/").replace("\u203a", "/").strip()
            if not cite_url.startswith("http"):
                cite_url = "https://" + cite_url
            url = cite_url
        title = ""
        m_h2 = re.search(r"<h2[^>]*>\s*<a[^>]*>(.*?)</a>", block, re.S)
        if m_h2:
            title = re.sub(r"<[^>]+>", "", m_h2.group(1)).strip()
            title = html.unescape(title)
        if not url and not title:
            continue
        snippet = ""
        h2_end = block.find("</h2>")
        search_after = block[h2_end:] if h2_end > 0 else block
        m_snip = re.search(r"<p\b[^>]*>(.*?)</p>", search_after, re.S)
        if m_snip:
            snippet = re.sub(r"<[^>]+>", "", m_snip.group(1)).strip()
            snippet = html.unescape(snippet)
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _bing_api_search(query: str, count: int, api_key: str) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({"q": query, "count": count, "mkt": "en-US"})
    url = f"https://api.bing.microsoft.com/v7.0/search?{params}"
    req = urllib.request.Request(url, headers={
        "Ocp-Apim-Subscription-Key": api_key,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT, context=_SSL_CTX) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results: list[dict[str, str]] = []
    for item in data.get("webPages", {}).get("value", []):
        results.append({
            "title": item.get("name", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", ""),
        })
    return results


def _bing_html_search(query: str, count: int) -> list[dict[str, str]]:
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://www.bing.com/search?q={encoded_q}&count={count}"
    raw_html = _fetch_url(url)
    return _parse_bing_results(raw_html, count)


class BingSearchParams(BaseModel):
    query: str = Field(description="The search query to send to Bing")
    max_results: int = Field(default=5, description="Maximum results to return (max 10)")


@define_tool(
    description=(
        "Search the web via Bing. Returns results with title, URL, and snippet. "
        "Use the built-in web_fetch tool to read full content of interesting URLs. "
        "Set BING_API_KEY env var for best results."
    )
)
def bing_search(params: BingSearchParams) -> str:
    cap = min(params.max_results, 10)
    api_key = os.environ.get("BING_API_KEY", "")
    try:
        if api_key:
            all_results = _bing_api_search(params.query, cap + 5, api_key)
        else:
            all_results = _bing_html_search(params.query, cap + 5)
    except Exception as exc:
        return json.dumps({"error": f"Bing search failed: {exc}"})
    final = all_results[:cap]
    if not final:
        return json.dumps({"results": [], "note": "No results found."})
    return json.dumps({"results": final, "total": len(final)}, indent=2)


RESEARCH_TOOLS = [bing_search]


# =============================================================================
# PPTX QA - Programmatic Checks
# =============================================================================


class RunPptxQaChecksParams(BaseModel):
    pptx_path: str = Field(description="Path to the .pptx file to QA")
    expected_slides: int = Field(
        description="Expected number of slides",
    )


@define_tool(
    description=(
        "Run automated layout and content checks on a generated .pptx file. "
        "Checks for: shape overflow, placeholder text, speaker notes, font sizes, "
        "text overflow, shape overlap, empty frames, content margins, text density, "
        "and slide count. Returns a structured report with CRITICAL/MAJOR/MINOR issues. "
        "Exit code 0 = CLEAN, 1 = ISSUES_FOUND."
    )
)
def run_pptx_qa_checks(params: RunPptxQaChecksParams) -> str:
    import subprocess
    qa_script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "scripts", "pptx_qa_checks.py")

    if not os.path.exists(qa_script):
        return f"ERROR: QA script not found at {qa_script}"

    try:
        result = subprocess.run(
            [sys.executable, qa_script, params.pptx_path,
             "--expected-slides", str(params.expected_slides)],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout
        if result.returncode == 2:
            output = f"ERROR running QA checks:\n{result.stderr}\n"
        return output
    except Exception as e:
        return f"ERROR running QA checks: {e}"


SLIDE_TOOLS = [run_pptx_qa_checks]


# =============================================================================
# Demo QA - Programmatic Checks
# =============================================================================


class RunDemoQaChecksParams(BaseModel):
    guide_path: str = Field(description="Path to the main demo guide .md file")
    companion_dir: str = Field(
        default="",
        description="Path to companion scripts directory (auto-detected from guide path if empty)",
    )
    expected_demos: int = Field(
        default=0,
        description="Expected number of demos (0 to skip count check)",
    )


@define_tool(
    description=(
        "Run automated QA checks on a generated demo package (guide .md + companion "
        "scripts). Checks for: placeholder text, emoji, em-dashes, script syntax "
        "(bash -n / py_compile), file cross-references, guide structure, script headers, "
        "and demo count. Returns a structured report with CRITICAL/MAJOR/MINOR issues. "
        "Exit code 0 = CLEAN, 1 = ISSUES_FOUND."
    )
)
def run_demo_qa_checks(params: RunDemoQaChecksParams) -> str:
    import subprocess
    qa_script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "scripts", "demo_qa_checks.py")

    if not os.path.exists(qa_script):
        return f"ERROR: Demo QA script not found at {qa_script}"

    cmd = [sys.executable, qa_script, params.guide_path]
    if params.companion_dir:
        cmd.extend(["--companion-dir", params.companion_dir])
    if params.expected_demos and params.expected_demos > 0:
        cmd.extend(["--expected-demos", str(params.expected_demos)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout
        if result.returncode == 2:
            output = f"ERROR running demo QA checks:\n{result.stderr}\n"
        return output
    except Exception as e:
        return f"ERROR running demo QA checks: {e}"


DEMO_TOOLS = [run_demo_qa_checks]


# =============================================================================
# Exported tool groups
# =============================================================================

ALL_CUSTOM_TOOLS = RESEARCH_TOOLS + SLIDE_TOOLS + DEMO_TOOLS
