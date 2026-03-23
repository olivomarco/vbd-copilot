#!/usr/bin/env python3
"""
Programmatic QA checks for project documentation (README.md).

Validates that the README contains all required sections, paths match
the actual project tree, env vars are documented, and content quality
standards are met.

Usage:
    python scripts/docs_qa_checks.py <project-dir> [--project-slug SLUG]

Exit codes:
    0 = CLEAN (no CRITICAL or MAJOR issues)
    1 = ISSUES_FOUND (at least one CRITICAL or MAJOR)
    2 = ERROR (project directory not found)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# ── Required README sections ─────────────────────────────────────────────────

REQUIRED_SECTIONS = [
    {
        "name": "Project Overview",
        "patterns": [
            re.compile(r"^#+\s*(project\s+overview|overview|introduction|about)", re.IGNORECASE | re.MULTILINE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Prerequisites",
        "patterns": [
            re.compile(r"^#+\s*(prerequisites?|requirements?|what\s+you\s+need)", re.IGNORECASE | re.MULTILINE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Environment Setup",
        "patterns": [
            re.compile(r"^#+\s*(environment\s+setup|env\w*\s+setup|configuration|setup)", re.IGNORECASE | re.MULTILINE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Infrastructure Deployment",
        "patterns": [
            re.compile(r"^#+\s*(infrastructure\s+deploy|infra\w*\s+deploy|deploy\w*\s+infra)", re.IGNORECASE | re.MULTILINE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Application Deployment",
        "patterns": [
            re.compile(r"^#+\s*(application\s+deploy|app\w*\s+deploy|deploy\w*\s+app)", re.IGNORECASE | re.MULTILINE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Quick Deploy (deploy.sh)",
        "patterns": [
            re.compile(r"deploy\.sh", re.IGNORECASE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Validation (validate.sh)",
        "patterns": [
            re.compile(r"validate\.sh", re.IGNORECASE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Local Development",
        "patterns": [
            re.compile(r"^#+\s*(local\s+dev|local\s+development|running\s+locally|develop\w*\s+local)", re.IGNORECASE | re.MULTILINE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Demo Guide",
        "patterns": [
            re.compile(r"^#+\s*(demo|demo\s+guide|customer\s+demo|how\s+to\s+demo)", re.IGNORECASE | re.MULTILINE),
        ],
        "severity": "MAJOR",
    },
    {
        "name": "Troubleshooting",
        "patterns": [
            re.compile(r"^#+\s*(troubleshoot|common\s+issues|faq|known\s+issues)", re.IGNORECASE | re.MULTILINE),
        ],
        "severity": "MAJOR",
    },
]

PLACEHOLDER_RE = re.compile(
    r"xxxx|lorem\s+ipsum|placeholder|TODO|FIXME|insert\s+here|TBD|sample\s+text|changeme",
    re.IGNORECASE,
)

EMOJI_RE = re.compile(
    "[\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "\U00002600-\U000026FF"
    "]",
)

EM_DASH_RE = re.compile(r"\u2014")

# ── Helper: collect project file tree ─────────────────────────────────────────


def _collect_tree(project_dir: str, max_depth: int = 4) -> set[str]:
    """Collect relative paths of files/dirs in the project tree."""
    paths: set[str] = set()
    base = Path(project_dir)
    for root, dirs, files in os.walk(project_dir):
        depth = len(Path(root).relative_to(base).parts)
        if depth > max_depth:
            dirs.clear()
            continue
        # Skip node_modules, __pycache__, .git
        dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__", ".git", ".venv")]
        for f in files:
            relpath = os.path.relpath(os.path.join(root, f), project_dir)
            paths.add(relpath)
        for d in dirs:
            relpath = os.path.relpath(os.path.join(root, d), project_dir)
            paths.add(relpath + "/")
    return paths


# ── Check functions ───────────────────────────────────────────────────────────


def check_readme_exists(project_dir: str) -> list[dict]:
    """Verify README.md exists and is non-empty."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")

    if not os.path.exists(readme_path):
        issues.append({
            "file": "README.md",
            "severity": "CRITICAL",
            "check": "readme_exists",
            "message": "README.md not found in project root",
        })
    elif os.path.getsize(readme_path) == 0:
        issues.append({
            "file": "README.md",
            "severity": "CRITICAL",
            "check": "readme_empty",
            "message": "README.md exists but is empty",
        })
    elif os.path.getsize(readme_path) < 500:
        issues.append({
            "file": "README.md",
            "severity": "MAJOR",
            "check": "readme_too_short",
            "message": f"README.md is only {os.path.getsize(readme_path)} bytes - "
                       "expected a comprehensive document",
        })

    return issues


def check_required_sections(project_dir: str) -> list[dict]:
    """Check that README contains all required sections."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")

    if not os.path.exists(readme_path):
        return issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return issues

    for section in REQUIRED_SECTIONS:
        found = any(p.search(content) for p in section["patterns"])
        if not found:
            issues.append({
                "file": "README.md",
                "severity": section["severity"],
                "check": "required_section",
                "message": f"Missing required section: {section['name']}",
            })

    return issues


def check_path_references(project_dir: str) -> list[dict]:
    """Check that file paths mentioned in README actually exist."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")

    if not os.path.exists(readme_path):
        return issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return issues

    tree = _collect_tree(project_dir)

    # Find path-like references in backticks or after cd/cat/ls/source commands
    path_patterns = [
        # Backtick paths: `src/something.py`
        re.compile(r"`([a-zA-Z][\w./\-]+\.\w+)`"),
        # Backtick dirs: `src/`
        re.compile(r"`([a-zA-Z][\w./\-]+/)`"),
    ]

    referenced_paths: set[str] = set()
    for pattern in path_patterns:
        for match in pattern.finditer(content):
            path = match.group(1)
            # Skip URLs, env vars, code snippets
            if path.startswith("http") or "$" in path or "=" in path:
                continue
            # Skip common non-path patterns
            if path in ("e.g.", "i.e.", "etc."):
                continue
            referenced_paths.add(path)

    for ref_path in referenced_paths:
        # Check if the path exists (with or without trailing slash)
        normalized = ref_path.rstrip("/")
        exists = (
            normalized in tree
            or normalized + "/" in tree
            or ref_path in tree
            # Check parent dirs
            or any(t.startswith(normalized + "/") or t.startswith(normalized + os.sep) for t in tree)
        )
        if not exists and len(normalized.split("/")) > 1:
            # Only flag specific paths (not single filenames which might be abstract)
            issues.append({
                "file": "README.md",
                "severity": "MINOR",
                "check": "path_reference",
                "message": f"Referenced path `{ref_path}` not found in project tree",
            })

    return issues


def check_deploy_script_docs(project_dir: str) -> list[dict]:
    """Check that deploy.sh is properly documented in README."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")
    deploy_path = os.path.join(project_dir, "scripts", "deploy.sh")

    if not os.path.exists(readme_path) or not os.path.exists(deploy_path):
        return issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return issues

    if "deploy.sh" not in content:
        issues.append({
            "file": "README.md",
            "severity": "MAJOR",
            "check": "deploy_script_docs",
            "message": "README does not mention deploy.sh script",
        })
        return issues

    # Check that flags are documented
    flag_patterns = {
        "--help": re.compile(r"--help"),
        "--infra-only": re.compile(r"--infra-only"),
        "--app-only": re.compile(r"--app-only"),
    }
    for flag_name, flag_re in flag_patterns.items():
        if not flag_re.search(content):
            issues.append({
                "file": "README.md",
                "severity": "MINOR",
                "check": "deploy_flag_docs",
                "message": f"README does not document deploy.sh flag: {flag_name}",
            })

    return issues


def check_validate_script_docs(project_dir: str) -> list[dict]:
    """Check that validate.sh is properly documented in README."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")
    validate_path = os.path.join(project_dir, "tests", "validate.sh")

    if not os.path.exists(readme_path) or not os.path.exists(validate_path):
        return issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return issues

    if "validate.sh" not in content:
        issues.append({
            "file": "README.md",
            "severity": "MAJOR",
            "check": "validate_script_docs",
            "message": "README does not mention validate.sh script",
        })

    return issues


def check_placeholders(project_dir: str) -> list[dict]:
    """Check for placeholder text in README."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")

    if not os.path.exists(readme_path):
        return issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return issues

    matches = PLACEHOLDER_RE.findall(content)
    if matches:
        unique = set(m.lower().strip() for m in matches)
        issues.append({
            "file": "README.md",
            "severity": "MAJOR",
            "check": "placeholders",
            "message": f"Placeholder text found: {', '.join(sorted(unique))}",
        })

    return issues


def check_emoji(project_dir: str) -> list[dict]:
    """Check for emoji characters in README."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")

    if not os.path.exists(readme_path):
        return issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return issues

    emoji_matches = EMOJI_RE.findall(content)
    if emoji_matches:
        issues.append({
            "file": "README.md",
            "severity": "MINOR",
            "check": "emoji",
            "message": f"Found {len(emoji_matches)} emoji character(s) - remove for professional tone",
        })

    return issues


def check_em_dashes(project_dir: str) -> list[dict]:
    """Check for em-dash characters in README."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")

    if not os.path.exists(readme_path):
        return issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return issues

    em_dash_count = len(EM_DASH_RE.findall(content))
    if em_dash_count > 0:
        issues.append({
            "file": "README.md",
            "severity": "MINOR",
            "check": "em_dashes",
            "message": f"Found {em_dash_count} em-dash(es) - use hyphens instead",
        })

    return issues


def check_demo_guide_quality(project_dir: str) -> list[dict]:
    """Check that the demo guide has concrete examples, not just instructions."""
    issues = []
    readme_path = os.path.join(project_dir, "README.md")

    if not os.path.exists(readme_path):
        return issues

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return issues

    # Find demo section
    demo_re = re.compile(
        r"^#+\s*(demo|demo\s+guide|customer\s+demo|how\s+to\s+demo)(.*?)(?=^#+\s|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    demo_match = demo_re.search(content)
    if not demo_match:
        return issues  # Missing section already flagged by check_required_sections

    demo_content = demo_match.group(2)

    # Check for code blocks (sample commands/responses)
    if "```" not in demo_content:
        issues.append({
            "file": "README.md",
            "severity": "MAJOR",
            "check": "demo_examples",
            "message": "Demo guide section has no code blocks - "
                       "should include sample commands, API calls, and expected outputs",
        })

    # Check minimum length
    word_count = len(demo_content.split())
    if word_count < 50:
        issues.append({
            "file": "README.md",
            "severity": "MAJOR",
            "check": "demo_guide_length",
            "message": f"Demo guide is only {word_count} words - too short for a meaningful guide",
        })

    return issues


# ── Main runner ───────────────────────────────────────────────────────────────

def run_all_checks(project_dir: str, project_slug: str | None = None) -> dict:
    """Run all docs QA checks and return a structured report."""

    if not os.path.isdir(project_dir):
        return {
            "status": "ERROR",
            "project_dir": project_dir,
            "project_slug": project_slug,
            "issues": [{
                "file": project_dir,
                "severity": "CRITICAL",
                "check": "dir_exists",
                "message": f"Project directory does not exist: {project_dir}",
            }],
            "summary": {"CRITICAL": 1, "MAJOR": 0, "MINOR": 0},
        }

    all_issues: list[dict] = []

    checks = [
        ("readme_exists", lambda: check_readme_exists(project_dir)),
        ("required_sections", lambda: check_required_sections(project_dir)),
        ("path_references", lambda: check_path_references(project_dir)),
        ("deploy_script_docs", lambda: check_deploy_script_docs(project_dir)),
        ("validate_script_docs", lambda: check_validate_script_docs(project_dir)),
        ("placeholders", lambda: check_placeholders(project_dir)),
        ("emoji", lambda: check_emoji(project_dir)),
        ("em_dashes", lambda: check_em_dashes(project_dir)),
        ("demo_guide_quality", lambda: check_demo_guide_quality(project_dir)),
    ]

    for check_name, check_fn in checks:
        try:
            issues = check_fn()
            all_issues.extend(issues)
        except Exception as e:
            all_issues.append({
                "file": "runner",
                "severity": "MINOR",
                "check": check_name,
                "message": f"Check failed with error: {e}",
            })

    summary: dict[str, int] = defaultdict(int)
    for issue in all_issues:
        summary[issue["severity"]] += 1

    by_file: dict[str, list[dict]] = defaultdict(list)
    for issue in all_issues:
        by_file[issue["file"]].append(issue)

    has_critical_or_major = summary.get("CRITICAL", 0) > 0 or summary.get("MAJOR", 0) > 0
    status = "ISSUES_FOUND" if has_critical_or_major else "CLEAN"

    return {
        "status": status,
        "project_dir": project_dir,
        "project_slug": project_slug,
        "issues": all_issues,
        "issues_by_file": {k: v for k, v in sorted(by_file.items())},
        "summary": dict(summary),
    }


def format_report(report: dict) -> str:
    """Format the report as human-readable text."""
    lines = []
    lines.append("## Documentation QA Report")
    lines.append("")
    lines.append(f"**Status:** {report['status']}")
    lines.append(f"**Project dir:** {report['project_dir']}")
    if report.get("project_slug"):
        lines.append(f"**Project:** {report['project_slug']}")
    lines.append("")
    lines.append("### Summary")
    summary = report.get("summary", {})
    lines.append(f"- CRITICAL: {summary.get('CRITICAL', 0)}")
    lines.append(f"- MAJOR: {summary.get('MAJOR', 0)}")
    lines.append(f"- MINOR: {summary.get('MINOR', 0)}")
    lines.append("")

    if not report.get("issues"):
        lines.append("No issues found.")
    else:
        lines.append("### Issues by File")
        lines.append("")
        by_file = report.get("issues_by_file", {})
        for filename in sorted(by_file.keys()):
            file_issues = by_file[filename]
            lines.append(f"#### {filename}")
            for issue in file_issues:
                lines.append(
                    f"- **[{issue['severity']}]** ({issue['check']}) {issue['message']}"
                )
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Documentation QA checks")
    parser.add_argument("project_dir", help="Path to the project directory to validate")
    parser.add_argument(
        "--project-slug",
        default=None,
        help="Project slug for context",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of text",
    )
    args = parser.parse_args()

    report = run_all_checks(args.project_dir, args.project_slug)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_report(report))

    sys.exit(
        0 if report["status"] == "CLEAN"
        else 2 if report["status"] == "ERROR"
        else 1
    )
