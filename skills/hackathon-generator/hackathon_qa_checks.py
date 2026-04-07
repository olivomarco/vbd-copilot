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

# Placeholder / TODO patterns
PLACEHOLDER_RE = re.compile(
    r"xxxx|lorem\s+ipsum|placeholder|TODO|FIXME|insert\s+here|TBD|sample\s+text",
    re.IGNORECASE,
)

# Emoji detection (common emoji Unicode ranges)
EMOJI_RE = re.compile(
    "[\U0001f600-\U0001f64f"
    "\U0001f300-\U0001f5ff"
    "\U0001f680-\U0001f6ff"
    "\U0001f900-\U0001f9ff"
    "\U00002702-\U000027b0"
    "\U0000fe00-\U0000fe0f"
    "\U0000200d"
    "\U00002600-\U000026ff"
    "]",
)

# Em-dash
EM_DASH_RE = re.compile(r"\u2014")

# Solution-revealing comment patterns inside code blocks
SOLUTION_COMMENT_RE = re.compile(
    r"(?:#|//|/\*|<!--)\s*(?:"
    r"step\s+\d|"  # "Step 1:", "Step 2", etc.
    r"todo\s*:\s*\w|"  # "TODO: implement X" (instructional, not placeholder)
    r"add\s+your\s+code|"  # "Add your code here"
    r"implement\s+(?:the|this|your)|"  # "Implement the function"
    r"connect\s+to\s+the|"  # "Connect to the database"
    r"use\s+the\s+\w+\s+to\s|"  # "Use the BlobServiceClient to"
    r"create\s+(?:a|the)\s+\w+\s+(?:client|connection|instance)|"  # "Create a ServiceBus client"
    r"initialize\s+the|"  # "Initialize the connection"
    r"call\s+the\s+\w+\s+(?:api|method|function|endpoint)|"  # "Call the createQueue API"
    r"set\s+up\s+(?:the|a)\s|"  # "Set up the authentication"
    r"configure\s+(?:the|a)\s|"  # "Configure the connection string"
    r"import\s+(?:the|a)\s+\w+\s+(?:sdk|library|package|module)"  # "Import the Azure SDK"
    r")",
    re.IGNORECASE,
)

# Patterns that directly reveal solutions in challenge text (outside code blocks)
SOLUTION_TEXT_RE = re.compile(
    r"(?:"
    r"the\s+solution\s+is|"
    r"here\s+is\s+the\s+(?:solution|answer|code)|"
    r"the\s+correct\s+(?:approach|answer|solution|implementation)\s+is|"
    r"you\s+(?:should|need\s+to|must)\s+(?:use|create|implement|configure|set\s+up)\s+(?:a\s+|the\s+)?\w+\s+(?:to|for|that)|"
    r"run\s+the\s+following\s+command(?:s)?\s*:"
    r")",
    re.IGNORECASE,
)

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
        issues.append(
            {
                "file": hackathon_dir,
                "severity": "CRITICAL",
                "check": "dir_exists",
                "message": f"Hackathon directory does not exist: {hackathon_dir}",
            }
        )
    return issues


def check_challenge_numbering(hackathon_dir: str) -> tuple[list[dict], list[int]]:
    """Check challenge files exist with sequential numbering from 00."""
    issues = []
    challenges_dir = os.path.join(hackathon_dir, "challenges")
    found_numbers: list[int] = []

    if not os.path.isdir(challenges_dir):
        issues.append(
            {
                "file": "challenges/",
                "severity": "CRITICAL",
                "check": "challenge_dir",
                "message": "challenges/ directory does not exist",
            }
        )
        return issues, found_numbers

    for fname in sorted(os.listdir(challenges_dir)):
        m = CHALLENGE_FILE_RE.match(fname)
        if m:
            found_numbers.append(int(m.group(1)))

    if not found_numbers:
        issues.append(
            {
                "file": "challenges/",
                "severity": "CRITICAL",
                "check": "challenge_count",
                "message": "No challenge files found (expected challenge-00.md, challenge-01.md, ...)",
            }
        )
        return issues, found_numbers

    if 0 not in found_numbers:
        issues.append(
            {
                "file": "challenges/",
                "severity": "CRITICAL",
                "check": "challenge_setup",
                "message": "challenge-00.md (setup/prerequisites) is missing",
            }
        )

    expected = list(range(min(found_numbers), max(found_numbers) + 1))
    missing = set(expected) - set(found_numbers)
    if missing:
        missing_files = [f"challenge-{n:02d}.md" for n in sorted(missing)]
        issues.append(
            {
                "file": "challenges/",
                "severity": "CRITICAL",
                "check": "challenge_sequence",
                "message": f"Gap in challenge numbering. Missing: {', '.join(missing_files)}",
            }
        )

    return issues, found_numbers


def check_challenge_count(
    found_numbers: list[int],
    expected: int | None,
) -> list[dict]:
    """Check challenge count matches expected."""
    issues = []
    actual = len(found_numbers)
    if expected is not None and expected > 0 and actual != expected:
        sev = "CRITICAL" if abs(actual - expected) > 2 else "MAJOR"
        issues.append(
            {
                "file": "challenges/",
                "severity": sev,
                "check": "challenge_count",
                "message": f"Expected {expected} challenges, found {actual}",
            }
        )
    return issues


def check_challenge_sections(
    hackathon_dir: str, challenge_numbers: list[int]
) -> list[dict]:
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
                issues.append(
                    {
                        "file": f"challenges/{fname}",
                        "severity": "MAJOR",
                        "check": "challenge_sections",
                        "message": f"Missing required section: {section}",
                    }
                )
    return issues


def check_coach_materials(hackathon_dir: str) -> list[dict]:
    """Check coach directory and required files."""
    issues = []
    coach_dir = os.path.join(hackathon_dir, "coach")

    if not os.path.isdir(coach_dir):
        issues.append(
            {
                "file": "coach/",
                "severity": "CRITICAL",
                "check": "coach_dir",
                "message": "coach/ directory does not exist",
            }
        )
        return issues

    for fname, required_sections in [
        ("facilitation-guide.md", FACILITATION_REQUIRED_SECTIONS),
        ("scoring-rubric.md", RUBRIC_REQUIRED_SECTIONS),
    ]:
        fpath = os.path.join(coach_dir, fname)
        if not os.path.isfile(fpath):
            issues.append(
                {
                    "file": f"coach/{fname}",
                    "severity": "CRITICAL",
                    "check": "coach_file",
                    "message": f"Coach file missing: {fname}",
                }
            )
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                text = f.read().lower()
        except Exception:
            continue
        for section in required_sections:
            if section not in text:
                issues.append(
                    {
                        "file": f"coach/{fname}",
                        "severity": "MAJOR",
                        "check": "coach_sections",
                        "message": f"Missing required content: {section}",
                    }
                )
    return issues


def check_devcontainer(hackathon_dir: str) -> list[dict]:
    """Check .devcontainer/ exists and devcontainer.json is valid."""
    issues = []
    dc_dir = os.path.join(hackathon_dir, ".devcontainer")

    if not os.path.isdir(dc_dir):
        issues.append(
            {
                "file": ".devcontainer/",
                "severity": "CRITICAL",
                "check": "devcontainer_dir",
                "message": ".devcontainer/ directory does not exist",
            }
        )
        return issues

    dc_json = os.path.join(dc_dir, "devcontainer.json")
    if not os.path.isfile(dc_json):
        issues.append(
            {
                "file": ".devcontainer/devcontainer.json",
                "severity": "CRITICAL",
                "check": "devcontainer_json",
                "message": "devcontainer.json does not exist",
            }
        )
        return issues

    try:
        with open(dc_json, "r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        issues.append(
            {
                "file": ".devcontainer/devcontainer.json",
                "severity": "CRITICAL",
                "check": "devcontainer_json_valid",
                "message": f"devcontainer.json is not valid JSON: {e}",
            }
        )
    return issues


def check_readme(hackathon_dir: str) -> list[dict]:
    """Check top-level README.md exists and has required sections."""
    issues = []
    readme = os.path.join(hackathon_dir, "README.md")

    if not os.path.isfile(readme):
        issues.append(
            {
                "file": "README.md",
                "severity": "CRITICAL",
                "check": "readme_exists",
                "message": "Top-level README.md does not exist",
            }
        )
        return issues

    try:
        with open(readme, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return issues

    text_lower = text.lower()
    for section in README_REQUIRED_SECTIONS:
        if section not in text_lower:
            issues.append(
                {
                    "file": "README.md",
                    "severity": "MAJOR",
                    "check": "readme_sections",
                    "message": f"README.md missing required section: {section}",
                }
            )

    # Check for challenge overview table
    if "|" not in text or "challenge" not in text_lower:
        issues.append(
            {
                "file": "README.md",
                "severity": "MAJOR",
                "check": "readme_table",
                "message": "README.md missing challenge overview table",
            }
        )
    return issues


def check_reference_architecture(hackathon_dir: str) -> list[dict]:
    """Check resources/reference-architecture.md exists."""
    issues = []
    ref_arch = os.path.join(hackathon_dir, "resources", "reference-architecture.md")

    if not os.path.isfile(ref_arch):
        issues.append(
            {
                "file": "resources/reference-architecture.md",
                "severity": "MAJOR",
                "check": "reference_architecture",
                "message": "resources/reference-architecture.md does not exist",
            }
        )
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
                    issues.append(
                        {
                            "file": rel_path,
                            "severity": "CRITICAL",
                            "check": "placeholder_text",
                            "message": (
                                f"Placeholder text '{match.group()}' at line {line_num}: "
                                f"{line.strip()[:100]}"
                            ),
                        }
                    )
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
                    issues.append(
                        {
                            "file": rel_path,
                            "severity": "MAJOR",
                            "check": "emoji",
                            "message": (
                                f"Emoji character U+{ord(match.group()):04X} at line {line_num}: "
                                f"{line.strip()[:100]}"
                            ),
                        }
                    )
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
                    issues.append(
                        {
                            "file": rel_path,
                            "severity": "MAJOR",
                            "check": "em_dash",
                            "message": f"Em-dash at line {line_num}: {line.strip()[:100]}",
                        }
                    )
    return issues


def check_cross_references(
    hackathon_dir: str, challenge_numbers: list[int]
) -> list[dict]:
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
                    issues.append(
                        {
                            "file": rel_path,
                            "severity": "MAJOR",
                            "check": "cross_reference",
                            "message": (
                                f"References challenge-{ref_num_str} which does not exist"
                            ),
                        }
                    )
    return issues


def _extract_code_blocks(text: str) -> list[tuple[int, str]]:
    """Extract fenced code blocks with their starting line numbers.

    Returns a list of (start_line, block_content) tuples.
    """
    blocks = []
    in_block = False
    block_start = 0
    block_lines: list[str] = []
    for line_num, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```") and not in_block:
            in_block = True
            block_start = line_num
            block_lines = []
        elif stripped.startswith("```") and in_block:
            in_block = False
            blocks.append((block_start, "\n".join(block_lines)))
        elif in_block:
            block_lines.append(line)
    return blocks


def check_solution_leakage_challenges(
    hackathon_dir: str,
    challenge_numbers: list[int],
) -> list[dict]:
    """Check challenge files for solution-revealing content."""
    issues = []
    coach_dir = os.path.join(hackathon_dir, "coach")

    for root, _dirs, files in os.walk(hackathon_dir):
        # Skip coach directory - solutions are allowed there
        if os.path.abspath(root).startswith(os.path.abspath(coach_dir)):
            continue
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

            # Check code blocks for solution-revealing comments
            for block_start, block_content in _extract_code_blocks(text):
                for i, line in enumerate(block_content.splitlines(), 1):
                    match = SOLUTION_COMMENT_RE.search(line)
                    if match:
                        issues.append(
                            {
                                "file": rel_path,
                                "severity": "MAJOR",
                                "check": "solution_comment",
                                "message": (
                                    f"Solution-revealing comment in code block at "
                                    f"line ~{block_start + i}: {line.strip()[:120]}"
                                ),
                            }
                        )

            # Check for commented-out solution code (lines that are ONLY
            # a comment containing what looks like executable code)
            for block_start, block_content in _extract_code_blocks(text):
                block_lines = block_content.splitlines()
                commented_code = 0
                total_lines = len([line for line in block_lines if line.strip()])
                for line in block_lines:
                    stripped = line.strip()
                    # Detect commented-out code: comment marker followed by
                    # code-like content (assignments, function calls, imports)
                    if re.match(
                        r"^(?:#|//)\s*(?:"
                        r"\w+\s*[=(]|"  # var = or func(
                        r"import\s|"  # import statements
                        r"from\s|"  # from X import
                        r"const\s|let\s|var\s|"  # JS declarations
                        r"return\s|"  # return statements
                        r"await\s"  # async calls
                        r")",
                        stripped,
                    ):
                        commented_code += 1
                if total_lines > 0 and commented_code >= 3:
                    issues.append(
                        {
                            "file": rel_path,
                            "severity": "CRITICAL",
                            "check": "commented_out_solution",
                            "message": (
                                f"Code block at line ~{block_start} contains "
                                f"{commented_code} lines of commented-out code "
                                f"(likely a hidden solution)"
                            ),
                        }
                    )

            # Check for solution-revealing text outside code blocks
            # (only in challenge files, not README)
            if CHALLENGE_FILE_RE.match(fname):
                for line_num, line in enumerate(text.splitlines(), 1):
                    match = SOLUTION_TEXT_RE.search(line)
                    if match:
                        issues.append(
                            {
                                "file": rel_path,
                                "severity": "MAJOR",
                                "check": "solution_text",
                                "message": (
                                    f"Solution-revealing text at line {line_num}: "
                                    f"{line.strip()[:120]}"
                                ),
                            }
                        )

    return issues


def check_starter_code_comments(hackathon_dir: str) -> list[dict]:
    """Check starter code for excessive or solution-revealing comments."""
    issues = []
    starter_dir = os.path.join(hackathon_dir, "resources", "starter")

    if not os.path.isdir(starter_dir):
        return issues

    for root, _dirs, files in os.walk(starter_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, hackathon_dir)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except Exception:
                continue

            # Detect comment lines based on file extension
            ext = os.path.splitext(fname)[1].lower()
            if ext in (".md", ".json", ".yaml", ".yml", ".toml", ".lock"):
                continue  # Skip config/doc files

            comment_prefixes = {
                ".py": ("#",),
                ".js": ("//",),
                ".ts": ("//",),
                ".jsx": ("//",),
                ".tsx": ("//",),
                ".cs": ("//",),
                ".java": ("//",),
                ".go": ("//",),
                ".rs": ("//",),
                ".sh": ("#",),
                ".bash": ("#",),
                ".rb": ("#",),
                ".bicep": ("//",),
                ".tf": ("#",),
            }
            prefixes = comment_prefixes.get(ext)
            if prefixes is None:
                continue

            total = 0
            comment_count = 0
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                total += 1
                if any(stripped.startswith(p) for p in prefixes):
                    comment_count += 1

            # Flag if more than 40% of non-empty lines are comments
            if total >= 5 and comment_count / total > 0.40:
                issues.append(
                    {
                        "file": rel_path,
                        "severity": "MAJOR",
                        "check": "excessive_comments",
                        "message": (
                            f"Excessive comments: {comment_count}/{total} non-empty "
                            f"lines ({comment_count * 100 // total}%) are comments. "
                            f"Starter code should be minimal scaffolding, not a guided walkthrough."
                        ),
                    }
                )

            # Check for solution-revealing comments in starter code
            for line_num, line in enumerate(lines, 1):
                stripped = line.strip()
                if any(stripped.startswith(p) for p in prefixes):
                    match = SOLUTION_COMMENT_RE.search(stripped)
                    if match:
                        issues.append(
                            {
                                "file": rel_path,
                                "severity": "CRITICAL",
                                "check": "starter_solution_comment",
                                "message": (
                                    f"Solution-revealing comment in starter code at "
                                    f"line {line_num}: {stripped[:120]}"
                                ),
                            }
                        )

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

    # Solution leakage checks
    all_issues.extend(
        check_solution_leakage_challenges(hackathon_dir, challenge_numbers)
    )
    all_issues.extend(check_starter_code_comments(hackathon_dir))

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
        "--expected-challenges",
        type=int,
        default=0,
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
