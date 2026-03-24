#!/usr/bin/env python3
"""
Programmatic QA checks for generated hackathon packages.

Runs a battery of validation checks on the hackathon directory structure,
challenge files, coach materials, and dev container config.
Returns a structured JSON report with severity-tagged findings.

Usage:
    python skills/hackathon-generator/hackathon_qa_checks.py <hackathon-dir> [--expected-challenges N]

Exit codes:
    0 = CLEAN (no CRITICAL or MAJOR issues)
    1 = ISSUES_FOUND (at least one CRITICAL or MAJOR)
    2 = ERROR (could not open directory)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Placeholder / TODO patterns
PLACEHOLDER_RE = re.compile(
    r"xxxx|lorem\s+ipsum|placeholder|TODO|FIXME|insert\s+here|TBD|sample\s+text",
    re.IGNORECASE,
)

# Emoji detection (common emoji Unicode ranges)
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

# Em-dash
EM_DASH_RE = re.compile(r"\u2014")

# Challenge file pattern
CHALLENGE_FILE_RE = re.compile(r"^challenge-(\d{2})\.md$")

# Required sections in challenge files
CHALLENGE_REQUIRED_SECTIONS = [
    "introduction",
    "description",
    "success criteria",
    "learning resources",
]

# Required sections in facilitation guide
FACILITATION_REQUIRED_SECTIONS = [
    "agenda",
]

# Required sections in scoring rubric
RUBRIC_REQUIRED_SECTIONS = [
    "challenge",
]

# Required sections in top-level README
README_REQUIRED_SECTIONS = [
    "challenges",
    "prerequisites",
]


def check_dir_exists(hackathon_dir: str) -> list[dict]:
    """Check that the hackathon directory exists."""
    issues = []
    if not os.path.isdir(hackathon_dir):
        issues.append({
            "file": hackathon_dir,
            "severity": "CRITICAL",
            "check": "dir_exists",
            "message": f"Hackathon directory does not exist: {hackathon_dir}",
        })
    return issues


def check_challenge_numbering(hackathon_dir: str) -> tuple[list[dict], list[int]]:
    """Check challenge files exist with sequential numbering from 00."""
    issues = []
    challenges_dir = os.path.join(hackathon_dir, "challenges")
    found_numbers: list[int] = []

    if not os.path.isdir(challenges_dir):
        issues.append({
            "file": "challenges/",
            "severity": "CRITICAL",
            "check": "challenge_dir",
            "message": "challenges/ directory does not exist",
        })
        return issues, found_numbers

    for fname in sorted(os.listdir(challenges_dir)):
        m = CHALLENGE_FILE_RE.match(fname)
        if m:
            found_numbers.append(int(m.group(1)))

    if not found_numbers:
        issues.append({
            "file": "challenges/",
            "severity": "CRITICAL",
            "check": "challenge_count",
            "message": "No challenge files found (expected challenge-00.md, challenge-01.md, ...)",
        })
        return issues, found_numbers

    if 0 not in found_numbers:
        issues.append({
            "file": "challenges/",
            "severity": "CRITICAL",
            "check": "challenge_setup",
            "message": "challenge-00.md (setup/prerequisites) is missing",
        })

    expected = list(range(min(found_numbers), max(found_numbers) + 1))
    missing = set(expected) - set(found_numbers)
    if missing:
        missing_files = [f"challenge-{n:02d}.md" for n in sorted(missing)]
        issues.append({
            "file": "challenges/",
            "severity": "CRITICAL",
            "check": "challenge_sequence",
            "message": f"Gap in challenge numbering. Missing: {', '.join(missing_files)}",
        })

    return issues, found_numbers


def check_challenge_count(
    found_numbers: list[int], expected: int | None,
) -> list[dict]:
    """Check challenge count matches expected."""
    issues = []
    actual = len(found_numbers)
    if expected is not None and expected > 0 and actual != expected:
        sev = "CRITICAL" if abs(actual - expected) > 2 else "MAJOR"
        issues.append({
            "file": "challenges/",
            "severity": sev,
            "check": "challenge_count",
            "message": f"Expected {expected} challenges, found {actual}",
        })
    return issues


def check_challenge_sections(hackathon_dir: str, challenge_numbers: list[int]) -> list[dict]:
    """Check each challenge file has required sections."""
    issues = []
    for num in challenge_numbers:
        fname = f"challenge-{num:02d}.md"
        fpath = os.path.join(hackathon_dir, "challenges", fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                text = f.read().lower()
        except Exception:
            continue

        for section in CHALLENGE_REQUIRED_SECTIONS:
            if section not in text:
                issues.append({
                    "file": f"challenges/{fname}",
                    "severity": "MAJOR",
                    "check": "challenge_sections",
                    "message": f"Missing required section: {section}",
                })
    return issues


def check_coach_materials(hackathon_dir: str) -> list[dict]:
    """Check coach directory and required files."""
    issues = []
    coach_dir = os.path.join(hackathon_dir, "coach")

    if not os.path.isdir(coach_dir):
        issues.append({
            "file": "coach/",
            "severity": "CRITICAL",
            "check": "coach_dir",
            "message": "coach/ directory does not exist",
        })
        return issues

    for fname, required_sections in [
        ("facilitation-guide.md", FACILITATION_REQUIRED_SECTIONS),
        ("scoring-rubric.md", RUBRIC_REQUIRED_SECTIONS),
    ]:
        fpath = os.path.join(coach_dir, fname)
        if not os.path.isfile(fpath):
            issues.append({
                "file": f"coach/{fname}",
                "severity": "CRITICAL",
                "check": "coach_file",
                "message": f"Coach file missing: {fname}",
            })
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                text = f.read().lower()
        except Exception:
            continue
        for section in required_sections:
            if section not in text:
                issues.append({
                    "file": f"coach/{fname}",
                    "severity": "MAJOR",
                    "check": "coach_sections",
                    "message": f"Missing required content: {section}",
                })
    return issues


def check_devcontainer(hackathon_dir: str) -> list[dict]:
    """Check .devcontainer/ exists and devcontainer.json is valid."""
    issues = []
    dc_dir = os.path.join(hackathon_dir, ".devcontainer")

    if not os.path.isdir(dc_dir):
        issues.append({
            "file": ".devcontainer/",
            "severity": "CRITICAL",
            "check": "devcontainer_dir",
            "message": ".devcontainer/ directory does not exist",
        })
        return issues

    dc_json = os.path.join(dc_dir, "devcontainer.json")
    if not os.path.isfile(dc_json):
        issues.append({
            "file": ".devcontainer/devcontainer.json",
            "severity": "CRITICAL",
            "check": "devcontainer_json",
            "message": "devcontainer.json does not exist",
        })
        return issues

    try:
        with open(dc_json, "r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        issues.append({
            "file": ".devcontainer/devcontainer.json",
            "severity": "CRITICAL",
            "check": "devcontainer_json_valid",
            "message": f"devcontainer.json is not valid JSON: {e}",
        })
    return issues


def check_readme(hackathon_dir: str) -> list[dict]:
    """Check top-level README.md exists and has required sections."""
    issues = []
    readme = os.path.join(hackathon_dir, "README.md")

    if not os.path.isfile(readme):
        issues.append({
            "file": "README.md",
            "severity": "CRITICAL",
            "check": "readme_exists",
            "message": "Top-level README.md does not exist",
        })
        return issues

    try:
        with open(readme, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return issues

    text_lower = text.lower()
    for section in README_REQUIRED_SECTIONS:
        if section not in text_lower:
            issues.append({
                "file": "README.md",
                "severity": "MAJOR",
                "check": "readme_sections",
                "message": f"README.md missing required section: {section}",
            })

    # Check for challenge overview table
    if "|" not in text or "challenge" not in text_lower:
        issues.append({
            "file": "README.md",
            "severity": "MAJOR",
            "check": "readme_table",
            "message": "README.md missing challenge overview table",
        })
    return issues


def check_reference_architecture(hackathon_dir: str) -> list[dict]:
    """Check resources/reference-architecture.md exists."""
    issues = []
    ref_arch = os.path.join(hackathon_dir, "resources", "reference-architecture.md")

    if not os.path.isfile(ref_arch):
        issues.append({
            "file": "resources/reference-architecture.md",
            "severity": "MAJOR",
            "check": "reference_architecture",
            "message": "resources/reference-architecture.md does not exist",
        })
    return issues


def check_placeholders(hackathon_dir: str) -> list[dict]:
    """Scan all markdown files for placeholder text."""
    issues = []
    for root, _dirs, files in os.walk(hackathon_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, hackathon_dir)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                continue
            for line_num, line in enumerate(text.splitlines(), 1):
                for match in PLACEHOLDER_RE.finditer(line):
                    issues.append({
                        "file": rel_path,
                        "severity": "CRITICAL",
                        "check": "placeholder_text",
                        "message": (
                            f"Placeholder text '{match.group()}' at line {line_num}: "
                            f"{line.strip()[:100]}"
                        ),
                    })
    return issues


def check_emoji(hackathon_dir: str) -> list[dict]:
    """Scan all markdown files for emoji."""
    issues = []
    for root, _dirs, files in os.walk(hackathon_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, hackathon_dir)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                continue
            for line_num, line in enumerate(text.splitlines(), 1):
                for match in EMOJI_RE.finditer(line):
                    issues.append({
                        "file": rel_path,
                        "severity": "MAJOR",
                        "check": "emoji",
                        "message": (
                            f"Emoji character U+{ord(match.group()):04X} at line {line_num}: "
                            f"{line.strip()[:100]}"
                        ),
                    })
    return issues


def check_em_dashes(hackathon_dir: str) -> list[dict]:
    """Scan all markdown files for em-dashes."""
    issues = []
    for root, _dirs, files in os.walk(hackathon_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, hackathon_dir)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                continue
            for line_num, line in enumerate(text.splitlines(), 1):
                for match in EM_DASH_RE.finditer(line):
                    issues.append({
                        "file": rel_path,
                        "severity": "MAJOR",
                        "check": "em_dash",
                        "message": f"Em-dash at line {line_num}: {line.strip()[:100]}",
                    })
    return issues


def check_cross_references(hackathon_dir: str, challenge_numbers: list[int]) -> list[dict]:
    """Check that cross-references between challenges are valid."""
    issues = []
    for root, _dirs, files in os.walk(hackathon_dir):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, hackathon_dir)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                continue
            # Find references to challenge-NN
            refs = re.findall(r"challenge-(\d{2})", text)
            for ref_num_str in refs:
                ref_num = int(ref_num_str)
                if ref_num not in challenge_numbers:
                    issues.append({
                        "file": rel_path,
                        "severity": "MAJOR",
                        "check": "cross_reference",
                        "message": (
                            f"References challenge-{ref_num_str} which does not exist"
                        ),
                    })
    return issues


def run_all_checks(
    hackathon_dir: str,
    expected_challenges: int | None = None,
) -> dict:
    """Run all hackathon QA checks and return a structured report."""

    # Phase 0: directory existence
    dir_issues = check_dir_exists(hackathon_dir)
    if dir_issues:
        return {
            "status": "ERROR",
            "hackathon_dir": hackathon_dir,
            "issues": dir_issues,
            "summary": {"CRITICAL": len(dir_issues), "MAJOR": 0, "MINOR": 0},
        }

    all_issues: list[dict] = []

    # Structural checks
    numbering_issues, challenge_numbers = check_challenge_numbering(hackathon_dir)
    all_issues.extend(numbering_issues)
    all_issues.extend(check_challenge_count(challenge_numbers, expected_challenges))
    all_issues.extend(check_challenge_sections(hackathon_dir, challenge_numbers))
    all_issues.extend(check_coach_materials(hackathon_dir))
    all_issues.extend(check_devcontainer(hackathon_dir))
    all_issues.extend(check_readme(hackathon_dir))
    all_issues.extend(check_reference_architecture(hackathon_dir))

    # Content quality checks
    all_issues.extend(check_placeholders(hackathon_dir))
    all_issues.extend(check_emoji(hackathon_dir))
    all_issues.extend(check_em_dashes(hackathon_dir))
    all_issues.extend(check_cross_references(hackathon_dir, challenge_numbers))

    # Summarize
    summary = {"CRITICAL": 0, "MAJOR": 0, "MINOR": 0}
    for issue in all_issues:
        sev = issue.get("severity", "MINOR")
        if sev in summary:
            summary[sev] += 1

    has_problems = summary["CRITICAL"] > 0 or summary["MAJOR"] > 0
    status = "ISSUES_FOUND" if has_problems else "CLEAN"

    return {
        "status": status,
        "hackathon_dir": hackathon_dir,
        "challenge_count": len(challenge_numbers),
        "issues": all_issues,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Hackathon QA checks")
    parser.add_argument("hackathon_dir", help="Path to the hackathon directory")
    parser.add_argument(
        "--expected-challenges", type=int, default=0,
        help="Expected number of challenges (0 to skip count check)",
    )
    args = parser.parse_args()

    expected = args.expected_challenges if args.expected_challenges > 0 else None
    report = run_all_checks(args.hackathon_dir, expected)

    print(json.dumps(report, indent=2))

    if report["status"] == "ERROR":
        sys.exit(2)
    elif report["status"] == "ISSUES_FOUND":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
