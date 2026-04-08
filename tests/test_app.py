"""Tests for app.py - output file detection helper."""

import time

from app import _find_new_outputs, _INTERESTING_SUFFIXES, _SKIP_DIRS, _AGENT_OUTPUT_DIRS


class TestFindNewOutputs:
    def test_finds_pptx_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        (tmp_path / "test.pptx").write_bytes(b"PK")
        found = _find_new_outputs(since)
        assert len(found) == 1
        assert found[0].name == "test.pptx"

    def test_finds_md_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        (tmp_path / "guide.md").write_text("# Guide")
        found = _find_new_outputs(since)
        assert len(found) == 1

    def test_keeps_non_plan_md(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        (tmp_path / "guide.md").write_text("guide content")
        found = _find_new_outputs(since)
        assert len(found) == 1

    def test_skips_plan_suffix(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        (tmp_path / "something-plan.md").write_text("plan")
        found = _find_new_outputs(since)
        assert len(found) == 0  # This has "-plan.md" in the name

    def test_skips_fragments_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        frag_dir = tmp_path / ".fragments"
        frag_dir.mkdir()
        (frag_dir / "part1.py").write_text("code")
        found = _find_new_outputs(since)
        assert len(found) == 0

    def test_skips_uninteresting_suffix(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        found = _find_new_outputs(since)
        assert len(found) == 0

    def test_skips_old_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        pptx = tmp_path / "old.pptx"
        pptx.write_bytes(b"PK")
        import os

        # Set mtime to far in the past
        old_time = time.time() - 3600
        os.utime(pptx, (old_time, old_time))
        since = time.time()
        found = _find_new_outputs(since)
        assert len(found) == 0

    def test_empty_outputs_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        found = _find_new_outputs(time.time())
        assert found == []

    def test_interesting_suffixes_constant(self):
        assert ".pptx" in _INTERESTING_SUFFIXES
        assert ".md" in _INTERESTING_SUFFIXES
        assert ".py" in _INTERESTING_SUFFIXES
        assert ".bicep" in _INTERESTING_SUFFIXES
        assert ".json" in _INTERESTING_SUFFIXES
        assert ".yaml" in _INTERESTING_SUFFIXES
        assert ".sh" in _INTERESTING_SUFFIXES

    def test_skip_dirs_constant(self):
        assert ".fragments" in _SKIP_DIRS

    def test_finds_nested_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        subdir = tmp_path / "project" / "src"
        subdir.mkdir(parents=True)
        (subdir / "main.py").write_text("print('hello')")
        found = _find_new_outputs(since)
        assert len(found) == 1

    def test_agent_scoped_slides_only(self, tmp_path, monkeypatch):
        """slide-conductor should only see files under slides/, not hackathons/."""
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "deck.pptx").write_bytes(b"PK")
        hack_dir = tmp_path / "hackathons" / "my-hack"
        hack_dir.mkdir(parents=True)
        (hack_dir / "challenge-00.md").write_text("challenge")
        found = _find_new_outputs(since, agent_name="slide-conductor")
        assert len(found) == 1
        assert found[0].name == "deck.pptx"

    def test_agent_scoped_hackathon_only(self, tmp_path, monkeypatch):
        """hackathon-conductor should only see files under hackathons/, not slides/."""
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "deck.pptx").write_bytes(b"PK")
        hack_dir = tmp_path / "hackathons" / "my-hack"
        hack_dir.mkdir(parents=True)
        (hack_dir / "challenge-00.md").write_text("challenge")
        found = _find_new_outputs(since, agent_name="hackathon-conductor")
        assert len(found) == 1
        assert found[0].name == "challenge-00.md"

    def test_no_agent_scans_everything(self, tmp_path, monkeypatch):
        """Without agent_name, all output dirs are scanned (backward compat)."""
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "deck.pptx").write_bytes(b"PK")
        hack_dir = tmp_path / "hackathons" / "my-hack"
        hack_dir.mkdir(parents=True)
        (hack_dir / "challenge-00.md").write_text("challenge")
        found = _find_new_outputs(since)
        assert len(found) == 2

    def test_unknown_agent_scans_everything(self, tmp_path, monkeypatch):
        """An unknown agent name falls back to scanning all of outputs/."""
        monkeypatch.setattr("app.OUTPUTS_DIR", tmp_path)
        since = time.time() - 1
        (tmp_path / "file.md").write_text("content")
        found = _find_new_outputs(since, agent_name="unknown-agent")
        assert len(found) == 1

    def test_agent_output_dirs_mapping(self):
        """Verify all expected agent mappings exist."""
        assert _AGENT_OUTPUT_DIRS["slide-conductor"] == "slides"
        assert _AGENT_OUTPUT_DIRS["hackathon-conductor"] == "hackathons"
        assert _AGENT_OUTPUT_DIRS["demo-conductor"] == "demos"
