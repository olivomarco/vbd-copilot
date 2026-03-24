"""Smoke test configuration and fixtures.

These tests run against a live deployment. They are skipped unless the
``--live`` flag is passed to pytest. Set the ``API_BASE_URL`` environment
variable to the root URL of the deployed service (defaults to
``http://localhost:8000``).

Usage::

    API_BASE_URL=https://my-app.azurecontainerapps.io pytest tests/smoke/ -v --live
"""
from __future__ import annotations

import os
from typing import Generator

import pytest


# ---------------------------------------------------------------------------
# Pytest plugin hooks -- register the --live flag and the smoke marker
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the ``--live`` CLI flag for smoke tests."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run smoke tests against a live deployment.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``smoke`` marker so pytest does not warn about it."""
    config.addinivalue_line(
        "markers",
        "smoke: marks tests that hit a live deployment (select with --live)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip smoke tests unless ``--live`` was passed."""
    if config.getoption("--live"):
        return

    skip_marker = pytest.mark.skip(
        reason="Smoke tests require the --live flag to run."
    )
    for item in items:
        # Apply the skip to every test collected from within the smoke/ directory
        if "smoke" in str(item.fspath):
            item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url() -> str:
    """Resolve the deployment base URL from the environment.

    Falls back to ``http://localhost:8000`` when ``API_BASE_URL`` is not set.
    """
    url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def api_headers() -> dict[str, str]:
    """Standard JSON headers used by most API requests."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.fixture(scope="session")
def stream_headers() -> dict[str, str]:
    """Headers for SSE streaming requests."""
    return {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
