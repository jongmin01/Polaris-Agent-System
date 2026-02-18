"""Shared pytest fixtures for Polaris v2 tests."""

import os
import tempfile
import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary SQLite database path."""
    return str(tmp_path / "test_trace.db")


@pytest.fixture(autouse=True)
def no_api_keys(monkeypatch):
    """Ensure no real API keys are used during tests."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
