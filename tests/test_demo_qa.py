"""Tests for demo_qa_checks.py — demo guide QA validation."""

import importlib.util
from pathlib import Path


# Load demo_qa_checks from the skill directory (hyphenated dir name).
_QA_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "demo-generator"
    / "demo_qa_checks.py"
)
_spec = importlib.util.spec_from_file_location("demo_qa_checks", _QA_SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_all_checks = _mod.run_all_checks
check_guide_exists = _mod.check_guide_exists
check_demo_count = _mod.check_demo_count
check_placeholders = _mod.check_placeholders
check_emoji = _mod.check_emoji
check_em_dashes = _mod.check_em_dashes
check_guide_structure = _mod.check_guide_structure
check_guide_length = _mod.check_guide_length
check_companion_dir_exists = _mod.check_companion_dir_exists
format_report = _mod.format_report


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_GUIDE = """\
# GitHub Copilot Demo Guide

This guide walks through a hands-on demonstration of GitHub Copilot features
for developers and architects looking to accelerate their workflow using
AI-powered code completion and chat-based assistance in Visual Studio Code.

## Prerequisites

- Active Azure subscription with contributor access to a resource group
- Visual Studio Code installed with the GitHub Copilot extension enabled
- GitHub account with Copilot license (Individual or Business)
- Node.js 18+ installed locally for the sample project
- Basic familiarity with TypeScript and REST API development

| # | Demo | Duration | Difficulty |
|---|------|----------|------------|
| 1 | Introduction to Copilot | 10 min | Easy |
| 2 | Advanced Features | 15 min | Medium |

## Demo 1: Introduction to Copilot

In this demo we explore the core code completion features of GitHub Copilot
including inline suggestions, tab completion, and basic prompt engineering.

### Step 1: Open VS Code and verify the environment
1. Launch Visual Studio Code from your applications folder
2. Open the integrated terminal using Ctrl+backtick on Windows or Cmd+backtick on Mac
3. Verify that the Copilot icon appears in the status bar at the bottom right
4. If the icon shows a warning, click it to sign in with your GitHub account
5. Open the sample project folder that was cloned during prerequisites setup

### Step 2: Experience your first Copilot suggestion
1. Create a new TypeScript file called userService.ts in the src directory
2. Type a function signature such as async function getUserById
3. Observe the ghost text suggestion that appears automatically from Copilot
4. Press Tab to accept the suggestion or Escape to dismiss it
5. Try writing a JSDoc comment above the function and watch Copilot complete it
6. Experiment with writing descriptive function names to get better suggestions

### Step 3: Explore multiple suggestions
1. Open the Copilot completions panel with Ctrl+Enter to see alternatives
2. Review each suggestion and pick the most appropriate one
3. Discuss with the audience how context influences suggestion quality

## Demo 2: Advanced Features

This demo covers multi-file context awareness and the Copilot Chat experience
for more complex development scenarios including refactoring and architecture.

### Step 1: Multi-file context awareness
1. Open two related files such as userService.ts and userController.ts
2. Write a new endpoint in the controller that calls the service
3. Notice how Copilot understands the types and methods from the other file
4. Ask Copilot to refactor the code to use dependency injection patterns
5. Review the suggested changes and discuss trade-offs with the audience

### Step 2: Using Copilot Chat for architecture discussions
1. Open the Copilot Chat panel from the sidebar or with Ctrl+Shift+I
2. Ask Copilot Chat to explain the current project architecture
3. Request suggestions for improving error handling across the codebase
4. Use the /fix command on a file with known issues to see inline fixes
5. Demonstrate the /tests command to generate unit tests automatically
"""


def _write_guide(tmp_path: Path, content: str = VALID_GUIDE) -> Path:
    guide = tmp_path / "test-demos.md"
    guide.write_text(content)
    return guide


# ── check_guide_exists ────────────────────────────────────────────────────────


class TestGuideExists:
    def test_exists(self, tmp_path):
        guide = _write_guide(tmp_path)
        issues = check_guide_exists(str(guide))
        assert issues == []

    def test_missing(self, tmp_path):
        issues = check_guide_exists(str(tmp_path / "nonexistent.md"))
        assert len(issues) == 1
        assert issues[0]["severity"] == "CRITICAL"

    def test_empty_file(self, tmp_path):
        guide = tmp_path / "empty.md"
        guide.write_text("")
        issues = check_guide_exists(str(guide))
        assert len(issues) == 1
        assert issues[0]["severity"] == "CRITICAL"


# ── check_demo_count ──────────────────────────────────────────────────────────


class TestDemoCount:
    def test_correct_count(self):
        issues = check_demo_count(VALID_GUIDE, expected=2)
        assert issues == []

    def test_wrong_count(self):
        issues = check_demo_count(VALID_GUIDE, expected=5)
        assert len(issues) == 1
        assert issues[0]["check"] == "demo_count"

    def test_no_demos(self):
        issues = check_demo_count("# Just a title\n\nSome text.", expected=None)
        assert any(i["severity"] == "CRITICAL" for i in issues)

    def test_no_expected(self):
        issues = check_demo_count(VALID_GUIDE, expected=None)
        assert issues == []


# ── check_placeholders ────────────────────────────────────────────────────────


class TestPlaceholders:
    def test_clean_text(self):
        issues = check_placeholders("Azure Kubernetes overview", "test.md")
        assert issues == []

    def test_todo(self):
        issues = check_placeholders("TODO: finish this section", "test.md")
        assert len(issues) >= 1
        assert issues[0]["severity"] == "CRITICAL"

    def test_fixme(self):
        issues = check_placeholders("FIXME add content here", "test.md")
        assert len(issues) >= 1

    def test_lorem(self):
        issues = check_placeholders("Lorem ipsum dolor sit amet", "test.md")
        assert len(issues) >= 1


# ── check_emoji ───────────────────────────────────────────────────────────────


class TestEmoji:
    def test_no_emoji(self):
        issues = check_emoji("Clean text without emoji", "test.md")
        assert issues == []

    def test_detects_emoji(self):
        issues = check_emoji("Rocket launch \U0001f680 today!", "test.md")
        assert len(issues) >= 1
        assert issues[0]["check"] == "emoji"


# ── check_em_dashes ──────────────────────────────────────────────────────────


class TestEmDashes:
    def test_no_dashes(self):
        issues = check_em_dashes("Normal text - with hyphens", "test.md")
        assert issues == []

    def test_detects_em_dash(self):
        issues = check_em_dashes("Text \u2014 with em dash", "test.md")
        assert len(issues) >= 1
        assert issues[0]["check"] == "em_dash"


# ── check_guide_structure ─────────────────────────────────────────────────────


class TestGuideStructure:
    def test_valid_structure(self):
        issues = check_guide_structure(VALID_GUIDE)
        assert issues == []

    def test_missing_title(self):
        text = "No title here\n\n## Demo 1\n\n1. Step\n"
        issues = check_guide_structure(text)
        title_issues = [i for i in issues if "heading" in i["message"].lower()]
        assert len(title_issues) >= 1

    def test_missing_prerequisites(self):
        text = "# Title\n\n## Demo 1: Intro\n\n### Step 1\n1. Do something\n"
        issues = check_guide_structure(text)
        prereq = [i for i in issues if "prerequisit" in i["message"].lower()]
        assert len(prereq) >= 1

    def test_demo_without_steps(self):
        text = (
            "# Title\n\n## Prerequisites\n\nStuff\n\n"
            "| a | b |\n|---|---|\n\n"
            "## Demo 1: Intro\n\nJust some text without steps.\n"
        )
        issues = check_guide_structure(text)
        step_issues = [i for i in issues if "steps" in i["message"].lower()]
        assert len(step_issues) >= 1


# ── check_guide_length ────────────────────────────────────────────────────────


class TestGuideLength:
    def test_adequate_length(self):
        issues = check_guide_length(VALID_GUIDE, expected_demos=2)
        assert issues == []

    def test_too_short(self):
        issues = check_guide_length("Very short.", expected_demos=None)
        assert any(i["severity"] == "CRITICAL" for i in issues)


# ── check_companion_dir_exists ────────────────────────────────────────────────


class TestCompanionDir:
    def test_none_companion(self):
        issues = check_companion_dir_exists(None, expected_demos=2)
        assert issues == []

    def test_missing_dir(self, tmp_path):
        issues = check_companion_dir_exists(str(tmp_path / "nope"), expected_demos=2)
        assert len(issues) == 1
        assert issues[0]["severity"] == "CRITICAL"

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "companions"
        d.mkdir()
        issues = check_companion_dir_exists(str(d), expected_demos=2)
        assert len(issues) == 1

    def test_dir_with_files(self, tmp_path):
        d = tmp_path / "companions"
        d.mkdir()
        (d / "demo-1-setup.sh").write_text("#!/bin/bash\necho hello")
        issues = check_companion_dir_exists(str(d), expected_demos=1)
        assert issues == []


# ── run_all_checks (integration) ─────────────────────────────────────────────


class TestRunAllChecks:
    def test_valid_guide(self, tmp_path):
        guide = _write_guide(tmp_path)
        report = run_all_checks(str(guide), expected_demos=2)
        assert report["status"] == "CLEAN"
        assert report["summary"].get("CRITICAL", 0) == 0
        assert report["summary"].get("MAJOR", 0) == 0

    def test_nonexistent_guide(self, tmp_path):
        report = run_all_checks(str(tmp_path / "nope.md"))
        assert report["status"] == "ERROR"

    def test_guide_with_placeholders(self, tmp_path):
        content = VALID_GUIDE + "\nTODO: add more content\n"
        guide = _write_guide(tmp_path, content)
        report = run_all_checks(str(guide))
        assert report["status"] == "ISSUES_FOUND"
        placeholder_issues = [
            i for i in report["issues"] if i["check"] == "placeholder_text"
        ]
        assert len(placeholder_issues) >= 1

    def test_report_keys(self, tmp_path):
        guide = _write_guide(tmp_path)
        report = run_all_checks(str(guide))
        assert "status" in report
        assert "guide" in report
        assert "issues" in report
        assert "summary" in report

    def test_with_companion_dir(self, tmp_path):
        guide = _write_guide(tmp_path)
        comp = tmp_path / "test"  # auto-detected from "test-demos.md" → "test"
        comp.mkdir()
        (comp / "demo-1-setup.sh").write_text("#!/bin/bash\necho setup\n")
        report = run_all_checks(str(guide), companion_dir=str(comp), expected_demos=2)
        assert "status" in report


# ── format_report ─────────────────────────────────────────────────────────────


class TestFormatReport:
    def test_clean_format(self):
        report = {
            "status": "CLEAN",
            "guide": "test.md",
            "companion_dir": None,
            "expected_demos": 2,
            "issues": [],
            "issues_by_file": {},
            "summary": {"CRITICAL": 0, "MAJOR": 0, "MINOR": 0},
        }
        text = format_report(report)
        assert "CLEAN" in text

    def test_format_with_issues(self):
        report = {
            "status": "ISSUES_FOUND",
            "guide": "test.md",
            "companion_dir": "/tmp/comp",
            "expected_demos": 3,
            "issues": [
                {
                    "file": "guide",
                    "severity": "CRITICAL",
                    "check": "demo_count",
                    "message": "wrong",
                }
            ],
            "issues_by_file": {
                "guide": [
                    {
                        "file": "guide",
                        "severity": "CRITICAL",
                        "check": "demo_count",
                        "message": "wrong",
                    }
                ]
            },
            "summary": {"CRITICAL": 1, "MAJOR": 0, "MINOR": 0},
        }
        text = format_report(report)
        assert "ISSUES_FOUND" in text
        assert "CRITICAL" in text
