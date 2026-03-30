#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import (  # noqa: E402
    BingSearchParams,
    RunArchitectureQaChecksParams,
    RunDemoQaChecksParams,
    RunDocsQaChecksParams,
    RunHackathonQaChecksParams,
    RunInfraQaChecksParams,
    RunPipelineQaChecksParams,
    RunPptxQaChecksParams,
    bing_search as sdk_bing_search,
    run_architecture_qa_checks as sdk_run_architecture_qa_checks,
    run_demo_qa_checks as sdk_run_demo_qa_checks,
    run_docs_qa_checks as sdk_run_docs_qa_checks,
    run_hackathon_qa_checks as sdk_run_hackathon_qa_checks,
    run_infra_qa_checks as sdk_run_infra_qa_checks,
    run_pipeline_qa_checks as sdk_run_pipeline_qa_checks,
    run_pptx_qa_checks as sdk_run_pptx_qa_checks,
)


mcp = FastMCP("csa-tools")


@mcp.tool()
def bing_search(query: str, max_results: int = 5) -> str:
    return sdk_bing_search(BingSearchParams(query=query, max_results=max_results))


@mcp.tool()
def run_pptx_qa_checks(pptx_path: str, expected_slides: int) -> str:
    return sdk_run_pptx_qa_checks(
        RunPptxQaChecksParams(
            pptx_path=pptx_path,
            expected_slides=expected_slides,
        )
    )


@mcp.tool()
def run_demo_qa_checks(
    guide_path: str,
    companion_dir: str = "",
    expected_demos: int = 0,
) -> str:
    return sdk_run_demo_qa_checks(
        RunDemoQaChecksParams(
            guide_path=guide_path,
            companion_dir=companion_dir,
            expected_demos=expected_demos,
        )
    )


@mcp.tool()
def run_architecture_qa_checks(docs_dir: str, project_slug: str = "") -> str:
    return sdk_run_architecture_qa_checks(
        RunArchitectureQaChecksParams(
            docs_dir=docs_dir,
            project_slug=project_slug,
        )
    )


@mcp.tool()
def run_infra_qa_checks(infra_dir: str, project_slug: str = "") -> str:
    return sdk_run_infra_qa_checks(
        RunInfraQaChecksParams(
            infra_dir=infra_dir,
            project_slug=project_slug,
        )
    )


@mcp.tool()
def run_pipeline_qa_checks(project_dir: str, project_slug: str = "") -> str:
    return sdk_run_pipeline_qa_checks(
        RunPipelineQaChecksParams(
            project_dir=project_dir,
            project_slug=project_slug,
        )
    )


@mcp.tool()
def run_docs_qa_checks(project_dir: str, project_slug: str = "") -> str:
    return sdk_run_docs_qa_checks(
        RunDocsQaChecksParams(
            project_dir=project_dir,
            project_slug=project_slug,
        )
    )


@mcp.tool()
def run_hackathon_qa_checks(hackathon_dir: str, expected_challenges: int = 0) -> str:
    return sdk_run_hackathon_qa_checks(
        RunHackathonQaChecksParams(
            hackathon_dir=hackathon_dir,
            expected_challenges=expected_challenges,
        )
    )


if __name__ == "__main__":
    mcp.run()