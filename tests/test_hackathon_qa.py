"""Tests for hackathon QA checks."""

import importlib.util
import json
import os
import pytest
from pathlib import Path

# Load hackathon_qa_checks from the skill directory (hyphenated dir name
# cannot be a normal Python import).
_QA_SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "hackathon-generator" / "hackathon_qa_checks.py"
_spec = importlib.util.spec_from_file_location("hackathon_qa_checks", _QA_SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
run_all_checks = _mod.run_all_checks


def _create_valid_hackathon(base: Path, num_challenges: int = 3) -> Path:
    """Create a minimal valid hackathon structure for testing."""
    hack_dir = base / "test-hackathon"
    hack_dir.mkdir()

    # README.md
    (hack_dir / "README.md").write_text(
        "# Test Hackathon\n\n## Prerequisites\n\nAzure subscription.\n\n"
        "## Challenges\n\n| # | Title | Time | Difficulty |\n"
        "|---|-------|------|------------|\n"
        "| 00 | Setup | 20 min | Easy |\n"
        "| 01 | First | 30 min | Easy |\n"
        "| 02 | Second | 40 min | Medium |\n"
    )

    # .devcontainer
    dc_dir = hack_dir / ".devcontainer"
    dc_dir.mkdir()
    (dc_dir / "devcontainer.json").write_text(
        json.dumps({"name": "Test Hack", "image": "mcr.microsoft.com/devcontainers/base:ubuntu"})
    )
    (dc_dir / "Dockerfile").write_text("FROM ubuntu:22.04\nRUN apt-get update\n")

    # challenges
    challenges_dir = hack_dir / "challenges"
    challenges_dir.mkdir()
    for i in range(num_challenges):
        difficulty = "Easy" if i <= 1 else "Medium"
        (challenges_dir / f"challenge-{i:02d}.md").write_text(
            f"# Challenge {i:02d}: Test Challenge {i}\n\n"
            f"**Difficulty:** {difficulty}\n\n"
            "## Introduction\n\nThis is a test.\n\n"
            "## Description\n\nDo the thing.\n\n"
            "## Success Criteria\n\n- [ ] Thing is done\n\n"
            "## Learning Resources\n\n"
            "- [MS Learn](https://learn.microsoft.com)\n"
        )

    # coach
    coach_dir = hack_dir / "coach"
    coach_dir.mkdir()
    (coach_dir / "facilitation-guide.md").write_text(
        "# Facilitation Guide\n\n## Agenda\n\n- 09:00 Setup\n- 09:30 Challenge 01\n"
    )
    (coach_dir / "scoring-rubric.md").write_text(
        "# Scoring Rubric\n\n## Challenge 00\n\nDone / Partially Done / Not Done\n"
    )

    # resources
    resources_dir = hack_dir / "resources"
    resources_dir.mkdir()
    (resources_dir / "reference-architecture.md").write_text(
        "# Reference Architecture\n\nParticipants build a web app on Azure.\n"
    )

    return hack_dir


class TestHackathonQaChecks:

    def test_valid_hackathon_passes(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path)
        report = run_all_checks(str(hack_dir))
        assert report["status"] == "CLEAN"
        assert report["summary"]["CRITICAL"] == 0
        assert report["summary"]["MAJOR"] == 0
        assert report["challenge_count"] == 3

    def test_nonexistent_dir_errors(self, tmp_path):
        report = run_all_checks(str(tmp_path / "nonexistent"))
        assert report["status"] == "ERROR"
        assert report["summary"]["CRITICAL"] >= 1

    def test_missing_challenges_dir(self, tmp_path):
        hack_dir = tmp_path / "hack"
        hack_dir.mkdir()
        (hack_dir / "README.md").write_text("# Hack\n## Prerequisites\n## Challenges\n| a | b |\n")
        (hack_dir / ".devcontainer").mkdir()
        (hack_dir / ".devcontainer" / "devcontainer.json").write_text("{}")
        (hack_dir / "coach").mkdir()
        (hack_dir / "coach" / "facilitation-guide.md").write_text("# Guide\n## Agenda\n")
        (hack_dir / "coach" / "scoring-rubric.md").write_text("# Rubric\n## Challenge\n")
        (hack_dir / "resources").mkdir()
        (hack_dir / "resources" / "reference-architecture.md").write_text("# Arch\n")
        report = run_all_checks(str(hack_dir))
        assert report["status"] == "ISSUES_FOUND"
        challenge_issues = [i for i in report["issues"] if i["check"] == "challenge_dir"]
        assert len(challenge_issues) >= 1

    def test_gap_in_numbering(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path)
        # Remove challenge-01 (creates gap 00, 02)
        os.remove(str(hack_dir / "challenges" / "challenge-01.md"))
        report = run_all_checks(str(hack_dir))
        assert report["status"] == "ISSUES_FOUND"
        seq_issues = [i for i in report["issues"] if i["check"] == "challenge_sequence"]
        assert len(seq_issues) >= 1

    def test_placeholder_text_detected(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path)
        # Add placeholder text to a challenge
        challenge_path = hack_dir / "challenges" / "challenge-01.md"
        text = challenge_path.read_text()
        challenge_path.write_text(text + "\nTODO: finish this section\n")
        report = run_all_checks(str(hack_dir))
        assert report["status"] == "ISSUES_FOUND"
        placeholder_issues = [i for i in report["issues"] if i["check"] == "placeholder_text"]
        assert len(placeholder_issues) >= 1

    def test_missing_challenge_sections(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path)
        # Overwrite challenge-01 with minimal content missing required sections
        (hack_dir / "challenges" / "challenge-01.md").write_text(
            "# Challenge 01: Broken\n\nJust some text with no sections.\n"
        )
        report = run_all_checks(str(hack_dir))
        assert report["status"] == "ISSUES_FOUND"
        section_issues = [
            i for i in report["issues"]
            if i["check"] == "challenge_sections" and "challenge-01" in i["file"]
        ]
        assert len(section_issues) >= 1

    def test_invalid_devcontainer_json(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path)
        (hack_dir / ".devcontainer" / "devcontainer.json").write_text("not valid json {{{")
        report = run_all_checks(str(hack_dir))
        assert report["status"] == "ISSUES_FOUND"
        dc_issues = [i for i in report["issues"] if i["check"] == "devcontainer_json_valid"]
        assert len(dc_issues) >= 1

    def test_missing_coach_materials(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path)
        os.remove(str(hack_dir / "coach" / "facilitation-guide.md"))
        report = run_all_checks(str(hack_dir))
        assert report["status"] == "ISSUES_FOUND"
        coach_issues = [i for i in report["issues"] if i["check"] == "coach_file"]
        assert len(coach_issues) >= 1

    def test_expected_challenge_count_mismatch(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path, num_challenges=3)
        report = run_all_checks(str(hack_dir), expected_challenges=5)
        assert report["status"] == "ISSUES_FOUND"
        count_issues = [i for i in report["issues"] if i["check"] == "challenge_count"]
        assert len(count_issues) >= 1

    def test_expected_challenge_count_match(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path, num_challenges=3)
        report = run_all_checks(str(hack_dir), expected_challenges=3)
        assert report["status"] == "CLEAN"

    def test_missing_reference_architecture(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path)
        os.remove(str(hack_dir / "resources" / "reference-architecture.md"))
        report = run_all_checks(str(hack_dir))
        assert report["status"] == "ISSUES_FOUND"
        ref_issues = [i for i in report["issues"] if i["check"] == "reference_architecture"]
        assert len(ref_issues) >= 1

    def test_broken_cross_reference(self, tmp_path):
        hack_dir = _create_valid_hackathon(tmp_path, num_challenges=3)
        # Add a reference to a non-existent challenge
        challenge_path = hack_dir / "challenges" / "challenge-02.md"
        text = challenge_path.read_text()
        challenge_path.write_text(text + "\nSee challenge-99 for more details.\n")
        report = run_all_checks(str(hack_dir))
        xref_issues = [i for i in report["issues"] if i["check"] == "cross_reference"]
        assert len(xref_issues) >= 1
