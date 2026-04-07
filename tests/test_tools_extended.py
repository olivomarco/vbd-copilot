"""Extended tests for tools.py — covers tool handler execution via ToolInvocation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tools import (
    bing_search,
    run_pptx_qa_checks,
    run_demo_qa_checks,
    run_architecture_qa_checks,
    run_infra_qa_checks,
    run_pipeline_qa_checks,
    run_docs_qa_checks,
    run_hackathon_qa_checks,
)


def _inv(args: dict) -> dict:
    """Build a minimal ToolInvocation dict."""
    return {"arguments": args}


async def _call(tool, args: dict) -> dict:
    """Call a Tool's handler with a ToolInvocation and return the result dict."""
    return await tool.handler(_inv(args))


def _text(result: dict) -> str:
    """Extract the text result from a ToolResult dict."""
    return result.get("textResultForLlm", "")


# ---------------------------------------------------------------------------
# bing_search
# ---------------------------------------------------------------------------


class TestBingSearchTool:
    @pytest.mark.asyncio
    async def test_html_fallback(self, monkeypatch):
        monkeypatch.delenv("BING_API_KEY", raising=False)
        with patch(
            "tools._bing_html_search",
            return_value=[
                {"title": "Test", "url": "https://test.com", "snippet": "result"}
            ],
        ):
            result = await _call(bing_search, {"query": "test", "max_results": 3})
        text = _text(result)
        data = json.loads(text)
        assert "results" in data
        assert len(data["results"]) == 1

    @pytest.mark.asyncio
    async def test_api_when_key_set(self, monkeypatch):
        monkeypatch.setenv("BING_API_KEY", "fake-key")
        with patch(
            "tools._bing_api_search",
            return_value=[{"title": "API", "url": "https://api.com", "snippet": "s"}],
        ):
            result = await _call(bing_search, {"query": "test", "max_results": 3})
        text = _text(result)
        data = json.loads(text)
        assert len(data["results"]) == 1

    @pytest.mark.asyncio
    async def test_caps_at_10(self, monkeypatch):
        monkeypatch.delenv("BING_API_KEY", raising=False)
        with patch("tools._bing_html_search", return_value=[]) as mock:
            await _call(bing_search, {"query": "test", "max_results": 20})
        assert mock.call_args[0][1] == 15  # cap(10) + 5

    @pytest.mark.asyncio
    async def test_no_results(self, monkeypatch):
        monkeypatch.delenv("BING_API_KEY", raising=False)
        with patch("tools._bing_html_search", return_value=[]):
            result = await _call(bing_search, {"query": "x", "max_results": 5})
        data = json.loads(_text(result))
        assert data["results"] == []
        assert "note" in data

    @pytest.mark.asyncio
    async def test_exception_returns_error(self, monkeypatch):
        monkeypatch.delenv("BING_API_KEY", raising=False)
        with patch(
            "tools._bing_html_search", side_effect=ConnectionError("no network")
        ):
            result = await _call(bing_search, {"query": "test", "max_results": 5})
        data = json.loads(_text(result))
        assert "error" in data


# ---------------------------------------------------------------------------
# QA tool runners
# ---------------------------------------------------------------------------


class TestRunPptxQaChecksTool:
    @pytest.mark.asyncio
    async def test_run_success(self):
        mock_result = MagicMock(returncode=0, stdout="CLEAN: No issues found")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(
                run_pptx_qa_checks, {"pptx_path": "/tmp/t.pptx", "expected_slides": 10}
            )
        assert "CLEAN" in _text(result)

    @pytest.mark.asyncio
    async def test_returncode_2(self):
        mock_result = MagicMock(returncode=2, stdout="", stderr="Script error")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(
                run_pptx_qa_checks, {"pptx_path": "/tmp/t.pptx", "expected_slides": 10}
            )
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            result = await _call(
                run_pptx_qa_checks, {"pptx_path": "/tmp/t.pptx", "expected_slides": 10}
            )
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_script_not_found(self):
        with patch("os.path.exists", return_value=False):
            result = await _call(
                run_pptx_qa_checks, {"pptx_path": "/tmp/t.pptx", "expected_slides": 10}
            )
        assert "not found" in _text(result)


class TestRunDemoQaChecksTool:
    @pytest.mark.asyncio
    async def test_run_success(self):
        mock_result = MagicMock(returncode=0, stdout="CLEAN")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_demo_qa_checks, {"guide_path": "/tmp/g.md"})
        assert "CLEAN" in _text(result)

    @pytest.mark.asyncio
    async def test_with_options(self):
        mock_result = MagicMock(returncode=0, stdout="OK")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            await _call(
                run_demo_qa_checks,
                {
                    "guide_path": "/tmp/g.md",
                    "companion_dir": "/tmp/s",
                    "expected_demos": 3,
                },
            )
        cmd = mock_run.call_args[0][0]
        assert "--companion-dir" in cmd
        assert "--expected-demos" in cmd

    @pytest.mark.asyncio
    async def test_returncode_2(self):
        mock_result = MagicMock(returncode=2, stdout="", stderr="error")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_demo_qa_checks, {"guide_path": "/tmp/g.md"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            result = await _call(run_demo_qa_checks, {"guide_path": "/tmp/g.md"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_script_not_found(self):
        with patch("os.path.exists", return_value=False):
            result = await _call(run_demo_qa_checks, {"guide_path": "/tmp/g.md"})
        assert "not found" in _text(result)


class TestRunArchitectureQaChecksTool:
    @pytest.mark.asyncio
    async def test_run_success(self):
        mock_result = MagicMock(returncode=0, stdout="CLEAN")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_architecture_qa_checks, {"docs_dir": "/tmp/d"})
        assert "CLEAN" in _text(result)

    @pytest.mark.asyncio
    async def test_with_slug(self):
        mock_result = MagicMock(returncode=0, stdout="OK")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            await _call(
                run_architecture_qa_checks, {"docs_dir": "/tmp/d", "project_slug": "p"}
            )
        assert "--project-slug" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_returncode_2(self):
        mock_result = MagicMock(returncode=2, stdout="", stderr="error")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_architecture_qa_checks, {"docs_dir": "/tmp/d"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            result = await _call(run_architecture_qa_checks, {"docs_dir": "/tmp/d"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_script_not_found(self):
        with patch("os.path.exists", return_value=False):
            result = await _call(run_architecture_qa_checks, {"docs_dir": "/tmp/d"})
        assert "not found" in _text(result)


class TestRunInfraQaChecksTool:
    @pytest.mark.asyncio
    async def test_run_success(self):
        mock_result = MagicMock(returncode=0, stdout="CLEAN")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_infra_qa_checks, {"infra_dir": "/tmp/i"})
        assert "CLEAN" in _text(result)

    @pytest.mark.asyncio
    async def test_with_slug(self):
        mock_result = MagicMock(returncode=0, stdout="OK")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            await _call(
                run_infra_qa_checks, {"infra_dir": "/tmp/i", "project_slug": "p"}
            )
        assert "--project-slug" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_returncode_2(self):
        mock_result = MagicMock(returncode=2, stdout="", stderr="error")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_infra_qa_checks, {"infra_dir": "/tmp/i"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            result = await _call(run_infra_qa_checks, {"infra_dir": "/tmp/i"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_script_not_found(self):
        with patch("os.path.exists", return_value=False):
            result = await _call(run_infra_qa_checks, {"infra_dir": "/tmp/i"})
        assert "not found" in _text(result)


class TestRunPipelineQaChecksTool:
    @pytest.mark.asyncio
    async def test_run_success(self):
        mock_result = MagicMock(returncode=0, stdout="CLEAN")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_pipeline_qa_checks, {"project_dir": "/tmp/p"})
        assert "CLEAN" in _text(result)

    @pytest.mark.asyncio
    async def test_with_slug(self):
        mock_result = MagicMock(returncode=0, stdout="OK")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            await _call(
                run_pipeline_qa_checks, {"project_dir": "/tmp/p", "project_slug": "p"}
            )
        assert "--project-slug" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_returncode_2(self):
        mock_result = MagicMock(returncode=2, stdout="", stderr="error")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_pipeline_qa_checks, {"project_dir": "/tmp/p"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            result = await _call(run_pipeline_qa_checks, {"project_dir": "/tmp/p"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_script_not_found(self):
        with patch("os.path.exists", return_value=False):
            result = await _call(run_pipeline_qa_checks, {"project_dir": "/tmp/p"})
        assert "not found" in _text(result)


class TestRunDocsQaChecksTool:
    @pytest.mark.asyncio
    async def test_run_success(self):
        mock_result = MagicMock(returncode=0, stdout="CLEAN")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_docs_qa_checks, {"project_dir": "/tmp/p"})
        assert "CLEAN" in _text(result)

    @pytest.mark.asyncio
    async def test_with_slug(self):
        mock_result = MagicMock(returncode=0, stdout="OK")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            await _call(
                run_docs_qa_checks, {"project_dir": "/tmp/p", "project_slug": "p"}
            )
        assert "--project-slug" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_returncode_2(self):
        mock_result = MagicMock(returncode=2, stdout="", stderr="error")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_docs_qa_checks, {"project_dir": "/tmp/p"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            result = await _call(run_docs_qa_checks, {"project_dir": "/tmp/p"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_script_not_found(self):
        with patch("os.path.exists", return_value=False):
            result = await _call(run_docs_qa_checks, {"project_dir": "/tmp/p"})
        assert "not found" in _text(result)


class TestRunHackathonQaChecksTool:
    @pytest.mark.asyncio
    async def test_run_success(self):
        mock_result = MagicMock(returncode=0, stdout="CLEAN")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_hackathon_qa_checks, {"hackathon_dir": "/tmp/h"})
        assert "CLEAN" in _text(result)

    @pytest.mark.asyncio
    async def test_with_expected_challenges(self):
        mock_result = MagicMock(returncode=0, stdout="OK")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            await _call(
                run_hackathon_qa_checks,
                {"hackathon_dir": "/tmp/h", "expected_challenges": 5},
            )
        assert "--expected-challenges" in mock_run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_returncode_2(self):
        mock_result = MagicMock(returncode=2, stdout="", stderr="error")
        with patch("subprocess.run", return_value=mock_result):
            result = await _call(run_hackathon_qa_checks, {"hackathon_dir": "/tmp/h"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            result = await _call(run_hackathon_qa_checks, {"hackathon_dir": "/tmp/h"})
        assert "ERROR" in _text(result)

    @pytest.mark.asyncio
    async def test_script_not_found(self):
        with patch("os.path.exists", return_value=False):
            result = await _call(run_hackathon_qa_checks, {"hackathon_dir": "/tmp/h"})
        assert "not found" in _text(result)
