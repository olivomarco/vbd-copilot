"""Tests for tools.py - custom tool implementations."""

import json
import os
import pytest
from unittest.mock import MagicMock

from tools import (
    _parse_bing_results,
    _bing_html_search,
    _bing_api_search,
    _fetch_url,
    BingSearchParams,
    RunPptxQaChecksParams,
    RunDemoQaChecksParams,
    RunArchitectureQaChecksParams,
    RunInfraQaChecksParams,
    RunPipelineQaChecksParams,
    RunDocsQaChecksParams,
)


class TestParseBingResults:
    """Tests for the HTML parsing helper."""

    def test_parse_empty_html(self):
        results = _parse_bing_results("", 5)
        assert results == []

    def test_parse_single_result(self):
        html = """
        <li class="b_algo">
            <h2><a href="https://example.com">Example Title</a></h2>
            <cite>https://example.com</cite>
            <p>This is a snippet about example.</p>
        </li>
        """
        results = _parse_bing_results(html, 5)
        assert len(results) == 1
        assert results[0]["title"] == "Example Title"
        assert "example.com" in results[0]["url"]
        assert "snippet" in results[0]["snippet"]

    def test_parse_multiple_results(self):
        html = """
        <li class="b_algo">
            <h2><a href="https://a.com">Title A</a></h2>
            <cite>https://a.com</cite>
            <p>Snippet A</p>
        </li>
        <li class="b_algo">
            <h2><a href="https://b.com">Title B</a></h2>
            <cite>https://b.com</cite>
            <p>Snippet B</p>
        </li>
        """
        results = _parse_bing_results(html, 5)
        assert len(results) == 2

    def test_parse_respects_max_results(self):
        html = """
        <li class="b_algo"><h2><a>A</a></h2><cite>a.com</cite><p>a</p></li>
        <li class="b_algo"><h2><a>B</a></h2><cite>b.com</cite><p>b</p></li>
        <li class="b_algo"><h2><a>C</a></h2><cite>c.com</cite><p>c</p></li>
        """
        results = _parse_bing_results(html, 2)
        assert len(results) == 2

    def test_parse_html_entities(self):
        html = """
        <li class="b_algo">
            <h2><a>Title &amp; More</a></h2>
            <cite>example.com</cite>
            <p>Text with &lt;html&gt; entities</p>
        </li>
        """
        results = _parse_bing_results(html, 5)
        assert results[0]["title"] == "Title & More"

    def test_parse_cite_without_protocol(self):
        html = """
        <li class="b_algo">
            <h2><a>Title</a></h2>
            <cite>example.com/path</cite>
            <p>Snippet</p>
        </li>
        """
        results = _parse_bing_results(html, 5)
        assert results[0]["url"].startswith("https://")

    def test_parse_cite_with_breadcrumb(self):
        html = """
        <li class="b_algo">
            <h2><a>Title</a></h2>
            <cite>example.com \u203a path \u203a page</cite>
            <p>Snippet</p>
        </li>
        """
        results = _parse_bing_results(html, 5)
        assert "/" in results[0]["url"]


class TestBingSearchHelpers:

    def test_bing_html_search_no_network(self, monkeypatch):
        """Without network, _bing_html_search should raise."""
        import urllib.request
        def failing_urlopen(*args, **kwargs):
            raise ConnectionError("no network")
        monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen)
        with pytest.raises(ConnectionError):
            _bing_html_search("test", 5)

    def test_bing_api_search_no_network(self, monkeypatch):
        """Without network, _bing_api_search should raise."""
        import urllib.request
        def failing_urlopen(*args, **kwargs):
            raise ConnectionError("no network")
        monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen)
        with pytest.raises(ConnectionError):
            _bing_api_search("test", 5, "fake-key")

    def test_bing_search_params_max_cap(self):
        params = BingSearchParams(query="test", max_results=20)
        assert params.max_results == 20

    def test_fetch_url_no_network(self, monkeypatch):
        import urllib.request
        def failing_urlopen(*args, **kwargs):
            raise ConnectionError("no network")
        monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen)
        with pytest.raises(ConnectionError):
            _fetch_url("https://example.com")

    def test_bing_html_search_builds_correct_url(self, monkeypatch):
        """Verify the URL built for Bing HTML search."""
        captured_urls = []
        import urllib.request
        original_urlopen = urllib.request.urlopen
        class FakeResponse:
            headers = MagicMock()
            headers.get_content_charset = MagicMock(return_value="utf-8")
            def read(self, max_bytes=None):
                return b"<html></html>"
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        def capture_urlopen(req, **kwargs):
            captured_urls.append(req.full_url if hasattr(req, 'full_url') else str(req))
            return FakeResponse()
        monkeypatch.setattr(urllib.request, "urlopen", capture_urlopen)
        results = _bing_html_search("azure aks", 3)
        assert len(captured_urls) == 1
        assert "bing.com" in captured_urls[0]
        assert "azure" in captured_urls[0]

    def test_bing_api_search_parses_response(self, monkeypatch):
        """Verify _bing_api_search parses API JSON correctly."""
        import urllib.request
        api_response = json.dumps({
            "webPages": {
                "value": [
                    {"name": "Result 1", "url": "https://example.com/1", "snippet": "Snippet 1"},
                    {"name": "Result 2", "url": "https://example.com/2", "snippet": "Snippet 2"},
                ]
            }
        }).encode("utf-8")
        class FakeResponse:
            def read(self):
                return api_response
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse())
        results = _bing_api_search("test", 5, "fake-key")
        assert len(results) == 2
        assert results[0]["title"] == "Result 1"
        assert results[1]["url"] == "https://example.com/2"


class TestQaToolParamValidation:

    def test_pptx_qa_params(self):
        p = RunPptxQaChecksParams(pptx_path="/tmp/test.pptx", expected_slides=10)
        assert p.pptx_path == "/tmp/test.pptx"
        assert p.expected_slides == 10

    def test_demo_qa_params_defaults(self):
        p = RunDemoQaChecksParams(guide_path="/tmp/guide.md")
        assert p.companion_dir == ""
        assert p.expected_demos == 0

    def test_demo_qa_params_full(self):
        p = RunDemoQaChecksParams(guide_path="/tmp/g.md", companion_dir="/tmp/scripts", expected_demos=3)
        assert p.companion_dir == "/tmp/scripts"
        assert p.expected_demos == 3

    def test_architecture_qa_params(self):
        p = RunArchitectureQaChecksParams(docs_dir="/tmp/docs")
        assert p.project_slug == ""

    def test_architecture_qa_params_with_slug(self):
        p = RunArchitectureQaChecksParams(docs_dir="/tmp/docs", project_slug="my-proj")
        assert p.project_slug == "my-proj"

    def test_infra_qa_params(self):
        p = RunInfraQaChecksParams(infra_dir="/tmp/infra")
        assert p.project_slug == ""

    def test_pipeline_qa_params(self):
        p = RunPipelineQaChecksParams(project_dir="/tmp/proj")
        assert p.project_slug == ""

    def test_docs_qa_params(self):
        p = RunDocsQaChecksParams(project_dir="/tmp/proj")
        assert p.project_slug == ""
