#!/usr/bin/env python3
"""
Programmatic QA checks for generated infrastructure-as-code (Bicep/ARM).

Validates Bicep module structure, parameter completeness, security
patterns, naming conventions, and Azure best practices.

Usage:
    python scripts/infra_qa_checks.py <infra-dir> [--project-slug SLUG]

Exit codes:
    0 = CLEAN (no CRITICAL or MAJOR issues)
    1 = ISSUES_FOUND (at least one CRITICAL or MAJOR)
    2 = ERROR (infra directory not found)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ── Patterns ──────────────────────────────────────────────────────────────────

HARDCODED_SECRET_RE = re.compile(
    r"""(?:password|secret|key|token|connectionstring)\s*[:=]\s*['"][^'"]{8,}['"]""",
    re.IGNORECASE,
)

HARDCODED_IP_RE = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
)

# IPs that are acceptable (well-known non-routable)
ALLOWED_IPS = {"0.0.0.0", "127.0.0.1", "10.0.0.0", "255.255.255.255"}

PLACEHOLDER_RE = re.compile(
    r"xxxx|lorem\s+ipsum|placeholder|TODO|FIXME|insert\s+here|TBD|sample\s+text|changeme",
    re.IGNORECASE,
)

# Expected infrastructure patterns
SECURITY_PATTERNS = {
    "key_vault": re.compile(r"Microsoft\.KeyVault|keyVault|key\s*vault", re.IGNORECASE),
    "managed_identity": re.compile(
        r"Microsoft\.ManagedIdentity|managedIdentit|SystemAssigned|UserAssigned",
        re.IGNORECASE,
    ),
}

PERMISSION_PATTERNS = {
    "role_assignment": re.compile(r"Microsoft\.Authorization/roleAssignments|roleAssignment", re.IGNORECASE),
    "principal_id": re.compile(r"principalId", re.IGNORECASE),
    "owner_or_contributor": re.compile(r"Owner|Contributor", re.IGNORECASE),
}

NETWORK_PATTERNS = {
    "private_endpoint": re.compile(r"Microsoft\.Network/privateEndpoints|privateEndpoint", re.IGNORECASE),
    "nsg": re.compile(r"Microsoft\.Network/networkSecurityGroups|securityRules", re.IGNORECASE),
    "firewall": re.compile(r"firewall|ipRules|networkAcls", re.IGNORECASE),
    "public_network_access": re.compile(r"publicNetworkAccess", re.IGNORECASE),
    "vnet_integration": re.compile(r"virtualNetworkSubnetId|subnet|vnet", re.IGNORECASE),
}

COMPETITOR_RE = re.compile(
    r"\bAWS\b|Amazon\s+Web\s+Services|\bGCP\b|Google\s+Cloud",
    re.IGNORECASE,
)

# ── Check functions ───────────────────────────────────────────────────────────


def find_bicep_files(infra_dir: str) -> list[str]:
    """Find all .bicep files recursively."""
    results = []
    for root, _dirs, files in os.walk(infra_dir):
        for f in files:
            if f.endswith(".bicep"):
                results.append(os.path.join(root, f))
    return sorted(results)


def find_param_files(infra_dir: str) -> list[str]:
    """Find all .bicepparam files recursively."""
    results = []
    for root, _dirs, files in os.walk(infra_dir):
        for f in files:
            if f.endswith(".bicepparam"):
                results.append(os.path.join(root, f))
    return sorted(results)


def find_arm_files(infra_dir: str) -> list[str]:
    """Find all ARM template .json files recursively."""
    results = []
    for root, _dirs, files in os.walk(infra_dir):
        for f in files:
            if f.endswith(".json") and f != "package.json" and f != "tsconfig.json":
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read(500)
                    if '"$schema"' in content and "deploymentTemplate" in content:
                        results.append(filepath)
                except Exception:
                    pass
    return sorted(results)


def check_files_exist(infra_dir: str) -> list[dict]:
    """Verify that infra directory has Bicep or ARM files."""
    issues = []
    bicep_files = find_bicep_files(infra_dir)
    arm_files = find_arm_files(infra_dir)

    if not bicep_files and not arm_files:
        issues.append({
            "file": infra_dir,
            "severity": "CRITICAL",
            "check": "iac_files_exist",
            "message": "No Bicep (.bicep) or ARM template (.json) files found in infra directory",
        })
        return issues

    # Check for a main entry point
    main_bicep = os.path.join(infra_dir, "main.bicep")
    main_json = os.path.join(infra_dir, "main.json")
    if not os.path.exists(main_bicep) and not os.path.exists(main_json):
        issues.append({
            "file": infra_dir,
            "severity": "MAJOR",
            "check": "main_entrypoint",
            "message": "No main.bicep or main.json entry point found in infra root",
        })

    return issues


def check_bicep_syntax(infra_dir: str) -> list[dict]:
    """Run az bicep build on each .bicep file if az CLI is available."""
    issues = []

    if not shutil.which("az"):
        issues.append({
            "file": "runner",
            "severity": "MINOR",
            "check": "bicep_syntax",
            "message": "az CLI not available - skipping Bicep syntax validation",
        })
        return issues

    for filepath in find_bicep_files(infra_dir):
        relpath = os.path.relpath(filepath, infra_dir)
        try:
            result = subprocess.run(
                ["az", "bicep", "build", "--file", filepath, "--stdout"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip()[:300] if result.stderr else "Unknown error"
                issues.append({
                    "file": relpath,
                    "severity": "CRITICAL",
                    "check": "bicep_syntax",
                    "message": f"Bicep build failed: {error_msg}",
                })
        except subprocess.TimeoutExpired:
            issues.append({
                "file": relpath,
                "severity": "MINOR",
                "check": "bicep_syntax",
                "message": "Bicep build timed out after 30s",
            })
        except Exception as e:
            issues.append({
                "file": relpath,
                "severity": "MINOR",
                "check": "bicep_syntax",
                "message": f"Could not run Bicep build: {e}",
            })

    return issues


def check_param_files(infra_dir: str) -> list[dict]:
    """Check that parameter files exist for at least one environment."""
    issues = []
    param_files = find_param_files(infra_dir)

    if not param_files:
        # Also check for .parameters.json files (ARM style)
        arm_param_files = []
        for root, _dirs, files in os.walk(infra_dir):
            for f in files:
                if f.endswith(".parameters.json"):
                    arm_param_files.append(os.path.join(root, f))

        if not arm_param_files:
            issues.append({
                "file": infra_dir,
                "severity": "MAJOR",
                "check": "param_files_exist",
                "message": "No parameter files found (.bicepparam or .parameters.json). "
                           "At least one environment configuration is expected.",
            })

    return issues


def check_module_structure(infra_dir: str) -> list[dict]:
    """Check that infra uses a modular structure."""
    issues = []
    bicep_files = find_bicep_files(infra_dir)

    if not bicep_files:
        return issues

    modules_dir = os.path.join(infra_dir, "modules")
    if not os.path.isdir(modules_dir):
        # Check if main.bicep is very large (indicating it should be split)
        main_path = os.path.join(infra_dir, "main.bicep")
        if os.path.exists(main_path):
            size = os.path.getsize(main_path)
            if size > 10000:  # >10KB suggests it should be modularized
                issues.append({
                    "file": "main.bicep",
                    "severity": "MAJOR",
                    "check": "module_structure",
                    "message": f"main.bicep is {size} bytes but no modules/ directory exists. "
                               "Consider decomposing into modules (networking, security, compute, data, monitoring).",
                })

    return issues


def check_security_patterns(infra_dir: str) -> list[dict]:
    """Check that security best practices are followed."""
    issues = []
    bicep_files = find_bicep_files(infra_dir)
    arm_files = find_arm_files(infra_dir)
    all_iac = bicep_files + arm_files

    if not all_iac:
        return issues

    # Concatenate all IaC content
    all_content = ""
    for filepath in all_iac:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                all_content += f.read() + "\n"
        except Exception:
            pass

    # Check for Key Vault usage
    if not SECURITY_PATTERNS["key_vault"].search(all_content):
        issues.append({
            "file": infra_dir,
            "severity": "MAJOR",
            "check": "key_vault_present",
            "message": "No Key Vault resource or reference found. "
                       "Secrets should be stored in Azure Key Vault, not in app settings or code.",
        })

    # Check for managed identity
    if not SECURITY_PATTERNS["managed_identity"].search(all_content):
        issues.append({
            "file": infra_dir,
            "severity": "MAJOR",
            "check": "managed_identity_present",
            "message": "No managed identity configuration found. "
                       "Use managed identities (SystemAssigned or UserAssigned) instead of keys for Azure service auth.",
        })

    return issues


def check_hardcoded_secrets(infra_dir: str) -> list[dict]:
    """Check for hardcoded secrets, keys, and connection strings."""
    issues = []

    for root, _dirs, files in os.walk(infra_dir):
        for f in files:
            if not (f.endswith(".bicep") or f.endswith(".json") or f.endswith(".bicepparam")):
                continue
            filepath = os.path.join(root, f)
            relpath = os.path.relpath(filepath, infra_dir)
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                    for line_num, line in enumerate(fh, 1):
                        if HARDCODED_SECRET_RE.search(line):
                            issues.append({
                                "file": relpath,
                                "severity": "CRITICAL",
                                "check": "hardcoded_secret",
                                "message": f"Line {line_num}: Possible hardcoded secret/key/password",
                            })
                        # Check for hardcoded IPs (excluding well-known ones)
                        ip_matches = HARDCODED_IP_RE.findall(line)
                        for ip in ip_matches:
                            if ip not in ALLOWED_IPS and not ip.startswith("10.") and not ip.startswith("172."):
                                issues.append({
                                    "file": relpath,
                                    "severity": "MINOR",
                                    "check": "hardcoded_ip",
                                    "message": f"Line {line_num}: Hardcoded IP address {ip} - consider parameterizing",
                                })
            except Exception:
                pass

    return issues


def check_placeholders(infra_dir: str) -> list[dict]:
    """Check for placeholder text in IaC files."""
    issues = []

    for root, _dirs, files in os.walk(infra_dir):
        for f in files:
            if not (f.endswith(".bicep") or f.endswith(".json") or f.endswith(".bicepparam")):
                continue
            filepath = os.path.join(root, f)
            relpath = os.path.relpath(filepath, infra_dir)
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                matches = PLACEHOLDER_RE.findall(content)
                if matches:
                    unique = set(m.lower().strip() for m in matches)
                    issues.append({
                        "file": relpath,
                        "severity": "MAJOR",
                        "check": "placeholders",
                        "message": f"Placeholder text found: {', '.join(sorted(unique))}",
                    })
            except Exception:
                pass

    return issues


def check_competitor_references(infra_dir: str) -> list[dict]:
    """Check for AWS/GCP references in IaC."""
    issues = []

    for root, _dirs, files in os.walk(infra_dir):
        for f in files:
            if not (f.endswith(".bicep") or f.endswith(".json") or f.endswith(".bicepparam")):
                continue
            filepath = os.path.join(root, f)
            relpath = os.path.relpath(filepath, infra_dir)
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                if COMPETITOR_RE.search(content):
                    issues.append({
                        "file": relpath,
                        "severity": "MAJOR",
                        "check": "azure_mandate",
                        "message": "Contains competitor cloud references (AWS/GCP). Azure mandate violation.",
                    })
            except Exception:
                pass

    return issues


def check_resource_tags(infra_dir: str) -> list[dict]:
    """Check that resources include tagging."""
    issues = []
    bicep_files = find_bicep_files(infra_dir)

    if not bicep_files:
        return issues

    all_content = ""
    for filepath in bicep_files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                all_content += f.read() + "\n"
        except Exception:
            pass

    if "tags" not in all_content.lower():
        issues.append({
            "file": infra_dir,
            "severity": "MINOR",
            "check": "resource_tags",
            "message": "No resource tags found in Bicep files. "
                       "Consider adding tags for cost tracking and governance.",
        })

    return issues


def check_outputs(infra_dir: str) -> list[dict]:
    """Check that main Bicep module has outputs."""
    issues = []
    main_path = os.path.join(infra_dir, "main.bicep")

    if not os.path.exists(main_path):
        return issues

    try:
        with open(main_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if "output " not in content:
            issues.append({
                "file": "main.bicep",
                "severity": "MINOR",
                "check": "outputs_present",
                "message": "main.bicep has no output declarations. "
                           "Outputs are needed for downstream consumption (deploy scripts, app config).",
            })
    except Exception:
        pass

    return issues


def check_principal_permissions(infra_dir: str) -> list[dict]:
    """Check RBAC role assignment coverage and obvious over-privilege patterns."""
    issues = []
    bicep_files = find_bicep_files(infra_dir)
    arm_files = find_arm_files(infra_dir)
    all_iac = bicep_files + arm_files

    if not all_iac:
        return issues

    all_content = ""
    for filepath in all_iac:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                all_content += fh.read() + "\n"
        except Exception:
            pass

    # Expect role assignments when managed identities/principals are present.
    has_identity = SECURITY_PATTERNS["managed_identity"].search(all_content) is not None
    has_role_assignment = PERMISSION_PATTERNS["role_assignment"].search(all_content) is not None
    has_principal_ref = PERMISSION_PATTERNS["principal_id"].search(all_content) is not None

    if has_identity and not has_role_assignment:
        issues.append({
            "file": infra_dir,
            "severity": "MAJOR",
            "check": "principal_permissions",
            "message": "Managed identity is present but no role assignment resources were detected. "
                       "Grant explicit RBAC permissions for each principal/identity.",
        })

    if has_role_assignment and not has_principal_ref:
        issues.append({
            "file": infra_dir,
            "severity": "MAJOR",
            "check": "principal_permissions",
            "message": "Role assignment resource detected without clear principalId references. "
                       "Verify each assignment is bound to the intended principal/managed identity.",
        })

    # Flag potential broad roles for human review (heuristic).
    broad_role_hits = 0
    for filepath in all_iac:
        relpath = os.path.relpath(filepath, infra_dir)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                for line_num, line in enumerate(fh, 1):
                    if "roleDefinitionId" in line and PERMISSION_PATTERNS["owner_or_contributor"].search(line):
                        broad_role_hits += 1
                        issues.append({
                            "file": relpath,
                            "severity": "MINOR",
                            "check": "least_privilege",
                            "message": f"Line {line_num}: Owner/Contributor role reference found. "
                                       "Confirm least-privilege scoping is justified.",
                        })
        except Exception:
            pass

    if has_role_assignment and broad_role_hits == 0:
        # Soft signal that least-privilege could be in place; no issue.
        pass

    return issues


def check_network_visibility(infra_dir: str) -> list[dict]:
    """Check that network exposure and access paths are explicitly controlled."""
    issues = []
    bicep_files = find_bicep_files(infra_dir)
    arm_files = find_arm_files(infra_dir)
    all_iac = bicep_files + arm_files

    if not all_iac:
        return issues

    all_content = ""
    for filepath in all_iac:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                all_content += fh.read() + "\n"
        except Exception:
            pass

    has_private_endpoint = NETWORK_PATTERNS["private_endpoint"].search(all_content) is not None
    has_nsg = NETWORK_PATTERNS["nsg"].search(all_content) is not None
    has_firewall = NETWORK_PATTERNS["firewall"].search(all_content) is not None
    has_public_network_access = NETWORK_PATTERNS["public_network_access"].search(all_content) is not None
    has_vnet_integration = NETWORK_PATTERNS["vnet_integration"].search(all_content) is not None

    if not has_private_endpoint and not has_firewall and not has_nsg:
        issues.append({
            "file": infra_dir,
            "severity": "MAJOR",
            "check": "network_visibility",
            "message": "No private endpoints, firewall rules, or NSG rules detected. "
                       "Define explicit network visibility and restrictions.",
        })

    if has_public_network_access and not has_private_endpoint and not has_firewall:
        issues.append({
            "file": infra_dir,
            "severity": "MINOR",
            "check": "network_visibility",
            "message": "publicNetworkAccess is configured but no private endpoint/firewall controls were detected. "
                       "Validate that exposed services are intentionally reachable.",
        })

    if not has_vnet_integration:
        issues.append({
            "file": infra_dir,
            "severity": "MINOR",
            "check": "network_visibility",
            "message": "No clear VNet/subnet integration references found. "
                       "Confirm whether network isolation is required for this solution.",
        })

    return issues


# ── Main runner ───────────────────────────────────────────────────────────────

def run_all_checks(infra_dir: str, project_slug: str | None = None) -> dict:
    """Run all infra QA checks and return a structured report."""

    if not os.path.isdir(infra_dir):
        return {
            "status": "ERROR",
            "infra_dir": infra_dir,
            "project_slug": project_slug,
            "issues": [{
                "file": infra_dir,
                "severity": "CRITICAL",
                "check": "dir_exists",
                "message": f"Infrastructure directory does not exist: {infra_dir}",
            }],
            "summary": {"CRITICAL": 1, "MAJOR": 0, "MINOR": 0},
        }

    all_issues: list[dict] = []

    checks = [
        ("files_exist", lambda: check_files_exist(infra_dir)),
        ("bicep_syntax", lambda: check_bicep_syntax(infra_dir)),
        ("param_files", lambda: check_param_files(infra_dir)),
        ("module_structure", lambda: check_module_structure(infra_dir)),
        ("security_patterns", lambda: check_security_patterns(infra_dir)),
        ("principal_permissions", lambda: check_principal_permissions(infra_dir)),
        ("network_visibility", lambda: check_network_visibility(infra_dir)),
        ("hardcoded_secrets", lambda: check_hardcoded_secrets(infra_dir)),
        ("placeholders", lambda: check_placeholders(infra_dir)),
        ("competitor_refs", lambda: check_competitor_references(infra_dir)),
        ("resource_tags", lambda: check_resource_tags(infra_dir)),
        ("outputs", lambda: check_outputs(infra_dir)),
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
        "infra_dir": infra_dir,
        "project_slug": project_slug,
        "issues": all_issues,
        "issues_by_file": {k: v for k, v in sorted(by_file.items())},
        "summary": dict(summary),
    }


def format_report(report: dict) -> str:
    """Format the report as human-readable text."""
    lines = []
    lines.append("## Infrastructure QA Report")
    lines.append("")
    lines.append(f"**Status:** {report['status']}")
    lines.append(f"**Infra dir:** {report['infra_dir']}")
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
    parser = argparse.ArgumentParser(description="Infrastructure QA checks")
    parser.add_argument("infra_dir", help="Path to the infra directory to validate")
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

    report = run_all_checks(args.infra_dir, args.project_slug)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_report(report))

    sys.exit(
        0 if report["status"] == "CLEAN"
        else 2 if report["status"] == "ERROR"
        else 1
    )
