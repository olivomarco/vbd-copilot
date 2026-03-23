#!/usr/bin/env python3
"""
Programmatic QA checks for CI/CD pipelines, deploy scripts, and validation scripts.

Validates workflow YAML structure, deploy script patterns, validation
script patterns, secret handling, and automation best practices.

Usage:
    python scripts/pipeline_qa_checks.py <project-dir> [--project-slug SLUG]

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
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ── Patterns ──────────────────────────────────────────────────────────────────

HARDCODED_SECRET_RE = re.compile(
    r"""(?:password|secret|key|token|api_key)\s*[:=]\s*['"][^'"]{8,}['"]""",
    re.IGNORECASE,
)

PLACEHOLDER_RE = re.compile(
    r"xxxx|lorem\s+ipsum|placeholder|TODO|FIXME|insert\s+here|TBD|changeme",
    re.IGNORECASE,
)

# Deploy script required patterns
DEPLOY_REQUIRED = {
    "set_euo_pipefail": re.compile(r"set\s+-euo\s+pipefail"),
    "help_flag": re.compile(r"--help"),
    "infra_only_flag": re.compile(r"--infra-only"),
    "app_only_flag": re.compile(r"--app-only"),
    "deploy_infra_func": re.compile(r"deploy_infra\s*\("),
    "deploy_app_func": re.compile(r"deploy_app\s*\("),
    "az_cli_check": re.compile(r"az\s|which\s+az|command\s+-v\s+az"),
}

# Validate script required patterns
VALIDATE_REQUIRED = {
    "set_euo_pipefail": re.compile(r"set\s+-euo\s+pipefail"),
    "live_flag": re.compile(r"--live"),
    "validate_infra_func": re.compile(r"validate_infra\s*\("),
    "run_unit_tests_func": re.compile(r"run_unit_tests\s*\("),
    "run_smoke_tests_func": re.compile(r"run_smoke_tests\s*\("),
}

# ── Check functions ───────────────────────────────────────────────────────────


def find_workflow_files(project_dir: str) -> list[str]:
    """Find GitHub Actions or Azure DevOps workflow files."""
    results = []
    # GitHub Actions
    gh_dir = os.path.join(project_dir, ".github", "workflows")
    if os.path.isdir(gh_dir):
        for f in sorted(os.listdir(gh_dir)):
            if f.endswith((".yml", ".yaml")):
                results.append(os.path.join(gh_dir, f))
    # Also check infra/.github/workflows (some projects nest it)
    infra_gh_dir = os.path.join(project_dir, "infra", ".github", "workflows")
    if os.path.isdir(infra_gh_dir):
        for f in sorted(os.listdir(infra_gh_dir)):
            if f.endswith((".yml", ".yaml")):
                results.append(os.path.join(infra_gh_dir, f))
    # Azure DevOps
    for root, _dirs, files in os.walk(project_dir):
        for f in files:
            if f in ("azure-pipelines.yml", "azure-pipelines.yaml"):
                results.append(os.path.join(root, f))
    return sorted(set(results))


def check_workflows_exist(project_dir: str) -> list[dict]:
    """Verify CI/CD workflow files exist."""
    issues = []
    workflows = find_workflow_files(project_dir)

    if not workflows:
        issues.append({
            "file": project_dir,
            "severity": "MAJOR",
            "check": "workflows_exist",
            "message": "No CI/CD workflow files found (.github/workflows/*.yml or azure-pipelines.yml)",
        })

    return issues


def check_yaml_syntax(project_dir: str) -> list[dict]:
    """Validate YAML syntax of workflow files."""
    issues = []
    workflows = find_workflow_files(project_dir)

    for filepath in workflows:
        relpath = os.path.relpath(filepath, project_dir)
        try:
            # Use Python's yaml module if available, otherwise basic check
            import yaml
            with open(filepath, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except ImportError:
            # Fallback: just check it's parseable text
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                if not content.strip():
                    issues.append({
                        "file": relpath,
                        "severity": "CRITICAL",
                        "check": "yaml_syntax",
                        "message": "Workflow file is empty",
                    })
            except Exception as e:
                issues.append({
                    "file": relpath,
                    "severity": "CRITICAL",
                    "check": "yaml_syntax",
                    "message": f"Cannot read file: {e}",
                })
        except yaml.YAMLError as e:
            issues.append({
                "file": relpath,
                "severity": "CRITICAL",
                "check": "yaml_syntax",
                "message": f"Invalid YAML: {str(e)[:200]}",
            })
        except Exception as e:
            issues.append({
                "file": relpath,
                "severity": "MINOR",
                "check": "yaml_syntax",
                "message": f"Could not validate YAML: {e}",
            })

    return issues


def check_workflow_triggers(project_dir: str) -> list[dict]:
    """Check that workflows have appropriate triggers."""
    issues = []
    workflows = find_workflow_files(project_dir)

    for filepath in workflows:
        relpath = os.path.relpath(filepath, project_dir)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # GitHub Actions should have 'on:' trigger
            if ".github" in filepath:
                if not re.search(r"^on:", content, re.MULTILINE):
                    issues.append({
                        "file": relpath,
                        "severity": "MAJOR",
                        "check": "workflow_trigger",
                        "message": "GitHub Actions workflow missing 'on:' trigger definition",
                    })

            # Check for hardcoded secrets
            if HARDCODED_SECRET_RE.search(content):
                issues.append({
                    "file": relpath,
                    "severity": "CRITICAL",
                    "check": "hardcoded_secret",
                    "message": "Workflow contains hardcoded secret/key/password",
                })

        except Exception:
            pass

    return issues


def check_workflow_secret_handling(project_dir: str) -> list[dict]:
    """Check that secrets are referenced securely."""
    issues = []
    workflows = find_workflow_files(project_dir)

    for filepath in workflows:
        relpath = os.path.relpath(filepath, project_dir)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # Look for plain text that looks like it should be a secret
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if HARDCODED_SECRET_RE.search(line):
                    issues.append({
                        "file": relpath,
                        "severity": "CRITICAL",
                        "check": "secret_handling",
                        "message": f"Line {line_num}: Possible hardcoded secret in workflow",
                    })

        except Exception:
            pass

    return issues


def check_deploy_script(project_dir: str) -> list[dict]:
    """Validate deploy.sh script structure and patterns."""
    issues = []

    deploy_path = os.path.join(project_dir, "scripts", "deploy.sh")
    if not os.path.exists(deploy_path):
        issues.append({
            "file": "scripts/deploy.sh",
            "severity": "CRITICAL",
            "check": "deploy_script_exists",
            "message": "Deploy script not found at scripts/deploy.sh",
        })
        return issues

    try:
        with open(deploy_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        issues.append({
            "file": "scripts/deploy.sh",
            "severity": "CRITICAL",
            "check": "deploy_script_read",
            "message": f"Cannot read deploy script: {e}",
        })
        return issues

    if not content.strip():
        issues.append({
            "file": "scripts/deploy.sh",
            "severity": "CRITICAL",
            "check": "deploy_script_empty",
            "message": "Deploy script is empty",
        })
        return issues

    # Check shebang
    if not content.startswith("#!/"):
        issues.append({
            "file": "scripts/deploy.sh",
            "severity": "MAJOR",
            "check": "deploy_shebang",
            "message": "Deploy script missing shebang (#!/usr/bin/env bash or #!/bin/bash)",
        })

    # Check required patterns
    for pattern_name, pattern in DEPLOY_REQUIRED.items():
        if not pattern.search(content):
            severity = "CRITICAL" if pattern_name == "set_euo_pipefail" else "MAJOR"
            issues.append({
                "file": "scripts/deploy.sh",
                "severity": severity,
                "check": f"deploy_{pattern_name}",
                "message": f"Deploy script missing required pattern: {pattern_name}",
            })

    # Check for bash syntax
    try:
        result = subprocess.run(
            ["bash", "-n", deploy_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip()[:200] if result.stderr else "Unknown error"
            issues.append({
                "file": "scripts/deploy.sh",
                "severity": "CRITICAL",
                "check": "deploy_bash_syntax",
                "message": f"Bash syntax error: {error_msg}",
            })
    except Exception:
        pass

    # Check for placeholders
    if PLACEHOLDER_RE.search(content):
        issues.append({
            "file": "scripts/deploy.sh",
            "severity": "MAJOR",
            "check": "deploy_placeholders",
            "message": "Deploy script contains placeholder text (TODO/TBD/FIXME/changeme)",
        })

    # Check executable permission
    if not os.access(deploy_path, os.X_OK):
        issues.append({
            "file": "scripts/deploy.sh",
            "severity": "MINOR",
            "check": "deploy_executable",
            "message": "Deploy script is not executable (chmod +x)",
        })

    return issues


def check_validate_script(project_dir: str) -> list[dict]:
    """Validate tests/validate.sh script structure and patterns."""
    issues = []

    validate_path = os.path.join(project_dir, "tests", "validate.sh")
    if not os.path.exists(validate_path):
        issues.append({
            "file": "tests/validate.sh",
            "severity": "CRITICAL",
            "check": "validate_script_exists",
            "message": "Validation script not found at tests/validate.sh",
        })
        return issues

    try:
        with open(validate_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        issues.append({
            "file": "tests/validate.sh",
            "severity": "CRITICAL",
            "check": "validate_script_read",
            "message": f"Cannot read validation script: {e}",
        })
        return issues

    if not content.strip():
        issues.append({
            "file": "tests/validate.sh",
            "severity": "CRITICAL",
            "check": "validate_script_empty",
            "message": "Validation script is empty",
        })
        return issues

    # Check shebang
    if not content.startswith("#!/"):
        issues.append({
            "file": "tests/validate.sh",
            "severity": "MAJOR",
            "check": "validate_shebang",
            "message": "Validation script missing shebang",
        })

    # Check required patterns
    for pattern_name, pattern in VALIDATE_REQUIRED.items():
        if not pattern.search(content):
            severity = "CRITICAL" if pattern_name == "set_euo_pipefail" else "MAJOR"
            issues.append({
                "file": "tests/validate.sh",
                "severity": severity,
                "check": f"validate_{pattern_name}",
                "message": f"Validation script missing required pattern: {pattern_name}",
            })

    # Check for bash syntax
    try:
        result = subprocess.run(
            ["bash", "-n", validate_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip()[:200] if result.stderr else "Unknown error"
            issues.append({
                "file": "tests/validate.sh",
                "severity": "CRITICAL",
                "check": "validate_bash_syntax",
                "message": f"Bash syntax error: {error_msg}",
            })
    except Exception:
        pass

    # Check executable permission
    if not os.access(validate_path, os.X_OK):
        issues.append({
            "file": "tests/validate.sh",
            "severity": "MINOR",
            "check": "validate_executable",
            "message": "Validation script is not executable (chmod +x)",
        })

    return issues


def check_placeholders_in_workflows(project_dir: str) -> list[dict]:
    """Check for placeholder text in workflow files."""
    issues = []
    workflows = find_workflow_files(project_dir)

    for filepath in workflows:
        relpath = os.path.relpath(filepath, project_dir)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if PLACEHOLDER_RE.search(content):
                issues.append({
                    "file": relpath,
                    "severity": "MAJOR",
                    "check": "workflow_placeholders",
                    "message": "Workflow contains placeholder text (TODO/TBD/FIXME/changeme)",
                })
        except Exception:
            pass

    return issues


# ── Main runner ───────────────────────────────────────────────────────────────

def run_all_checks(project_dir: str, project_slug: str | None = None) -> dict:
    """Run all pipeline QA checks and return a structured report."""

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
        ("workflows_exist", lambda: check_workflows_exist(project_dir)),
        ("yaml_syntax", lambda: check_yaml_syntax(project_dir)),
        ("workflow_triggers", lambda: check_workflow_triggers(project_dir)),
        ("secret_handling", lambda: check_workflow_secret_handling(project_dir)),
        ("deploy_script", lambda: check_deploy_script(project_dir)),
        ("validate_script", lambda: check_validate_script(project_dir)),
        ("workflow_placeholders", lambda: check_placeholders_in_workflows(project_dir)),
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
    lines.append("## Pipeline & Automation QA Report")
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
    parser = argparse.ArgumentParser(description="Pipeline & automation QA checks")
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
