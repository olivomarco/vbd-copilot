#!/usr/bin/env python3
"""
Programmatic QA checks for generated architecture documentation.

Validates that all expected architecture files exist, are well-formed,
and meet content quality standards.  Follows the same pattern as
pptx_qa_checks.py and demo_qa_checks.py.

Usage:
    python scripts/architecture_qa_checks.py <docs-dir> [--project-slug SLUG]

Exit codes:
    0 = CLEAN (no CRITICAL or MAJOR issues)
    1 = ISSUES_FOUND (at least one CRITICAL or MAJOR)
    2 = ERROR (docs directory not found)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

# ── Expected architecture files ───────────────────────────────────────────────

EXPECTED_FILES = [
    "executive-brief.md",
    "solution-design.md",
    "architecture-diagram.drawio",
    "data-assessment.md",
    "responsible-ai.md",
    "cost-estimation.md",
    "delivery-plan.md",
]

MD_FILES = [f for f in EXPECTED_FILES if f.endswith(".md")]
DRAWIO_FILES = [f for f in EXPECTED_FILES if f.endswith(".drawio")]

# ── Patterns ──────────────────────────────────────────────────────────────────

PLACEHOLDER_RE = re.compile(
    r"xxxx|lorem\s+ipsum|placeholder|TODO|FIXME|insert\s+here|TBD|sample\s+text",
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


# ── Check functions ───────────────────────────────────────────────────────────

def check_expected_files(docs_dir: str) -> list[dict]:
    """Verify all expected architecture files exist and are non-empty."""
    issues = []
    for filename in EXPECTED_FILES:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.exists(filepath):
            issues.append({
                "file": filename,
                "severity": "CRITICAL",
                "check": "file_exists",
                "message": f"Expected file missing: {filename}",
            })
        elif os.path.getsize(filepath) == 0:
            issues.append({
                "file": filename,
                "severity": "CRITICAL",
                "check": "file_exists",
                "message": f"File is empty (0 bytes): {filename}",
            })
    return issues


def check_drawio_valid(docs_dir: str) -> list[dict]:
    """Validate that .drawio files are well-formed XML with expected structure."""
    issues = []
    for filename in DRAWIO_FILES:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            issues.append({
                "file": filename,
                "severity": "CRITICAL",
                "check": "drawio_readable",
                "message": f"Cannot read file: {e}",
            })
            continue

        # Must be valid XML
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            issues.append({
                "file": filename,
                "severity": "CRITICAL",
                "check": "drawio_xml",
                "message": f"Invalid XML: {e}",
            })
            continue

        # Root element should be <mxfile> or <mxGraphModel>
        if root.tag not in ("mxfile", "mxGraphModel"):
            issues.append({
                "file": filename,
                "severity": "CRITICAL",
                "check": "drawio_structure",
                "message": f"Root element is <{root.tag}>, expected <mxfile> or <mxGraphModel>",
            })
            continue

        # Should contain at least one diagram/page
        diagrams = root.findall(".//diagram")
        if root.tag == "mxfile" and len(diagrams) == 0:
            issues.append({
                "file": filename,
                "severity": "CRITICAL",
                "check": "drawio_structure",
                "message": "No <diagram> elements found in <mxfile>",
            })
            continue

        # Should contain mxCell elements (actual shapes/content)
        cells = root.findall(".//mxCell")
        graph_models = root.findall(".//mxGraphModel")
        if len(cells) == 0 and len(graph_models) == 0:
            issues.append({
                "file": filename,
                "severity": "MAJOR",
                "check": "drawio_content",
                "message": "Diagram has no visible cells or graph models - may be empty",
            })

        # Check for reasonable number of shapes (at least a few components)
        user_cells = [c for c in cells if c.get("vertex") == "1" or c.get("edge") == "1"]
        if 0 < len(user_cells) < 3:
            issues.append({
                "file": filename,
                "severity": "MAJOR",
                "check": "drawio_content",
                "message": f"Diagram has only {len(user_cells)} shapes/edges - likely too sparse",
            })

    return issues


def check_md_structure(docs_dir: str) -> list[dict]:
    """Check that markdown files have proper heading structure."""
    issues = []
    for filename in MD_FILES:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        # Must have a top-level heading
        if not re.search(r"^#\s+", content, re.MULTILINE):
            issues.append({
                "file": filename,
                "severity": "MAJOR",
                "check": "md_structure",
                "message": "Missing top-level heading (# Title)",
            })

        # Must have at least one section heading
        sections = re.findall(r"^##\s+", content, re.MULTILINE)
        if len(sections) < 2:
            issues.append({
                "file": filename,
                "severity": "MAJOR",
                "check": "md_structure",
                "message": f"Only {len(sections)} section headings - expected at least 2",
            })

    return issues


def check_md_length(docs_dir: str) -> list[dict]:
    """Check that markdown files have reasonable content length."""
    min_words = {
        "executive-brief.md": 300,
        "solution-design.md": 800,
        "data-assessment.md": 300,
        "responsible-ai.md": 300,
        "cost-estimation.md": 150,
        "delivery-plan.md": 200,
    }
    issues = []
    for filename in MD_FILES:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        word_count = len(content.split())
        expected = min_words.get(filename, 150)
        if word_count < expected:
            severity = "CRITICAL" if word_count < expected // 2 else "MAJOR"
            issues.append({
                "file": filename,
                "severity": severity,
                "check": "md_length",
                "message": f"Only {word_count} words (expected at least {expected})",
            })

    return issues


def check_placeholders(docs_dir: str) -> list[dict]:
    """Scan all files for leftover placeholder/TODO text."""
    issues = []
    for filename in EXPECTED_FILES:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.exists(filepath):
            continue
        if filename.endswith(".drawio"):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            for match in PLACEHOLDER_RE.finditer(line):
                issues.append({
                    "file": filename,
                    "severity": "CRITICAL",
                    "check": "placeholder_text",
                    "message": (
                        f"Placeholder text '{match.group()}' at line {line_num}: "
                        f"{line.strip()[:100]}"
                    ),
                })
    return issues


def check_emoji(docs_dir: str) -> list[dict]:
    """Scan markdown files for emoji characters."""
    issues = []
    for filename in MD_FILES:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            for match in EMOJI_RE.finditer(line):
                issues.append({
                    "file": filename,
                    "severity": "MAJOR",
                    "check": "emoji",
                    "message": (
                        f"Emoji character U+{ord(match.group()):04X} at line {line_num}: "
                        f"{line.strip()[:100]}"
                    ),
                })
    return issues


def check_em_dashes(docs_dir: str) -> list[dict]:
    """Scan markdown files for em-dashes."""
    issues = []
    for filename in MD_FILES:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            for match in EM_DASH_RE.finditer(line):
                issues.append({
                    "file": filename,
                    "severity": "MAJOR",
                    "check": "em_dash",
                    "message": f"Em-dash at line {line_num}: {line.strip()[:100]}",
                })
    return issues


def check_azure_references(docs_dir: str) -> list[dict]:
    """Verify architecture documents reference Azure services (not AWS/GCP)."""
    issues = []
    competitor_re = re.compile(
        r"\b(AWS|Amazon Web Services|S3|Lambda|EC2|GCP|Google Cloud"
        r"|BigQuery|Cloud Run|Cloud Functions)\b",
        re.IGNORECASE,
    )
    azure_re = re.compile(r"\b(Azure|Microsoft|Entra|Cosmos DB|Bicep)\b", re.IGNORECASE)

    for filename in MD_FILES:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        # Check for competitor cloud references
        for line_num, line in enumerate(content.splitlines(), 1):
            for match in competitor_re.finditer(line):
                issues.append({
                    "file": filename,
                    "severity": "CRITICAL",
                    "check": "azure_mandate",
                    "message": (
                        f"Non-Azure cloud reference '{match.group()}' at line {line_num}: "
                        f"{line.strip()[:100]}"
                    ),
                })

    # Check that solution-design.md mentions Azure at least once
    arch_path = os.path.join(docs_dir, "solution-design.md")
    if os.path.exists(arch_path):
        try:
            with open(arch_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if not azure_re.search(content):
                issues.append({
                    "file": "solution-design.md",
                    "severity": "CRITICAL",
                    "check": "azure_mandate",
                    "message": "Solution design does not mention any Azure/Microsoft services",
                })
        except Exception:
            pass

    return issues


def check_executive_brief(docs_dir: str) -> list[dict]:
    """Validate that executive-brief.md has required sections."""
    issues = []
    filepath = os.path.join(docs_dir, "executive-brief.md")
    if not os.path.exists(filepath):
        return issues  # Missing file is caught by check_expected_files

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        issues.append({
            "file": "executive-brief.md",
            "severity": "CRITICAL",
            "check": "executive_brief_readable",
            "message": f"Cannot read file: {e}",
        })
        return issues

    content_lower = content.lower()
    required_concepts = [
        ("business challenge", "business challenge or problem statement"),
        ("recommended", "recommended solution or projects"),
        ("impact", "expected business impact or ROI"),
        ("timeline", "high-level timeline"),
        ("next step", "next steps or call to action"),
    ]
    for keyword, description in required_concepts:
        if keyword not in content_lower:
            issues.append({
                "file": "executive-brief.md",
                "severity": "MAJOR",
                "check": "executive_brief_sections",
                "message": f"Missing expected content: {description}",
            })

    return issues


def check_data_assessment(docs_dir: str) -> list[dict]:
    """Validate that data-assessment.md has required sections."""
    issues = []
    filepath = os.path.join(docs_dir, "data-assessment.md")
    if not os.path.exists(filepath):
        return issues  # Missing file is caught by check_expected_files

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        issues.append({
            "file": "data-assessment.md",
            "severity": "CRITICAL",
            "check": "data_assessment_readable",
            "message": f"Cannot read file: {e}",
        })
        return issues

    content_lower = content.lower()
    required_concepts = [
        ("data source", "required data sources"),
        ("quality", "data quality prerequisites"),
        ("privacy", "privacy and compliance"),
        ("integration", "integration points"),
    ]
    for keyword, description in required_concepts:
        if keyword not in content_lower:
            issues.append({
                "file": "data-assessment.md",
                "severity": "MAJOR",
                "check": "data_assessment_sections",
                "message": f"Missing expected content: {description}",
            })

    return issues


def check_responsible_ai(docs_dir: str) -> list[dict]:
    """Validate that responsible-ai.md has required sections."""
    issues = []
    filepath = os.path.join(docs_dir, "responsible-ai.md")
    if not os.path.exists(filepath):
        return issues  # Missing file is caught by check_expected_files

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        issues.append({
            "file": "responsible-ai.md",
            "severity": "CRITICAL",
            "check": "responsible_ai_readable",
            "message": f"Cannot read file: {e}",
        })
        return issues

    content_lower = content.lower()
    required_concepts = [
        ("fairness", "fairness and bias assessment"),
        ("transparency", "transparency and explainability"),
        ("human", "human oversight or human-in-the-loop"),
        ("monitor", "model monitoring"),
    ]
    for keyword, description in required_concepts:
        if keyword not in content_lower:
            issues.append({
                "file": "responsible-ai.md",
                "severity": "MAJOR",
                "check": "responsible_ai_sections",
                "message": f"Missing expected content: {description}",
            })

    return issues


def check_cross_references(docs_dir: str) -> list[dict]:
    """Check that docs cross-reference each other where expected."""
    issues = []

    # solution-design.md should reference the diagram
    arch_path = os.path.join(docs_dir, "solution-design.md")
    if os.path.exists(arch_path):
        try:
            with open(arch_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if "architecture-diagram" not in content.lower() and "drawio" not in content.lower():
                issues.append({
                    "file": "solution-design.md",
                    "severity": "MINOR",
                    "check": "cross_reference",
                    "message": "Does not reference the architecture-diagram.drawio file",
                })
        except Exception:
            pass

    return issues


# ── Main runner ───────────────────────────────────────────────────────────────

def run_all_checks(docs_dir: str, project_slug: str | None = None) -> dict:
    """Run all architecture QA checks and return a structured report."""

    if not os.path.isdir(docs_dir):
        return {
            "status": "ERROR",
            "docs_dir": docs_dir,
            "project_slug": project_slug,
            "issues": [{
                "file": docs_dir,
                "severity": "CRITICAL",
                "check": "dir_exists",
                "message": f"Documentation directory does not exist: {docs_dir}",
            }],
            "summary": {"CRITICAL": 1, "MAJOR": 0, "MINOR": 0},
        }

    all_issues: list[dict] = []

    checks = [
        ("expected_files", lambda: check_expected_files(docs_dir)),
        ("drawio_valid", lambda: check_drawio_valid(docs_dir)),
        ("md_structure", lambda: check_md_structure(docs_dir)),
        ("md_length", lambda: check_md_length(docs_dir)),
        ("placeholders", lambda: check_placeholders(docs_dir)),
        ("emoji", lambda: check_emoji(docs_dir)),
        ("em_dashes", lambda: check_em_dashes(docs_dir)),
        ("azure_references", lambda: check_azure_references(docs_dir)),
        ("executive_brief", lambda: check_executive_brief(docs_dir)),
        ("data_assessment", lambda: check_data_assessment(docs_dir)),
        ("responsible_ai", lambda: check_responsible_ai(docs_dir)),
        ("cross_references", lambda: check_cross_references(docs_dir)),
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

    # Summarize
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
        "docs_dir": docs_dir,
        "project_slug": project_slug,
        "expected_files": EXPECTED_FILES,
        "issues": all_issues,
        "issues_by_file": {k: v for k, v in sorted(by_file.items())},
        "summary": dict(summary),
    }


def format_report(report: dict) -> str:
    """Format the report as human-readable text."""
    lines = []
    lines.append("## Architecture QA Report")
    lines.append("")
    lines.append(f"**Status:** {report['status']}")
    lines.append(f"**Docs dir:** {report['docs_dir']}")
    if report.get("project_slug"):
        lines.append(f"**Project:** {report['project_slug']}")
    lines.append("")
    lines.append("### Expected Files")
    for f in report.get("expected_files", EXPECTED_FILES):
        filepath = os.path.join(report["docs_dir"], f)
        exists = "✓" if os.path.exists(filepath) else "✗"
        lines.append(f"  {exists} {f}")
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
    parser = argparse.ArgumentParser(description="Architecture documentation QA checks")
    parser.add_argument("docs_dir", help="Path to the docs directory to validate")
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

    report = run_all_checks(args.docs_dir, args.project_slug)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_report(report))

    sys.exit(
        0 if report["status"] == "CLEAN"
        else 2 if report["status"] == "ERROR"
        else 1
    )
