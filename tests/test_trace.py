"""Tests for polaris.trace_logger.TraceLogger."""

import json
import pytest
from polaris.trace_logger import TraceLogger


@pytest.fixture
def logger(tmp_db):
    """Create a TraceLogger backed by a temporary DB."""
    return TraceLogger(db_path=tmp_db)


def _insert_sample(logger, tool="search_arxiv", session_id="sess-1", thought="thinking"):
    logger.log(
        thought=thought,
        tool=tool,
        args={"query": "MoS2"},
        result="ok",
        approval_level="AUTO",
        approved_by="system",
        session_id=session_id,
    )


class TestLogInsertion:
    def test_insert_and_retrieve(self, logger):
        _insert_sample(logger)
        rows = logger.get_recent(limit=10)
        assert len(rows) == 1
        assert rows[0]["tool"] == "search_arxiv"
        assert rows[0]["session_id"] == "sess-1"
        assert rows[0]["thought"] == "thinking"
        assert rows[0]["approval_level"] == "AUTO"

    def test_args_stored_as_json(self, logger):
        _insert_sample(logger)
        rows = logger.get_recent(limit=1)
        parsed = json.loads(rows[0]["args"])
        assert parsed == {"query": "MoS2"}

    def test_timestamp_populated(self, logger):
        _insert_sample(logger)
        rows = logger.get_recent(limit=1)
        assert rows[0]["timestamp"] is not None
        assert "T" in rows[0]["timestamp"]  # ISO format


class TestBySession:
    def test_filter_by_session(self, logger):
        _insert_sample(logger, session_id="sess-A")
        _insert_sample(logger, session_id="sess-A")
        _insert_sample(logger, session_id="sess-B")

        results = logger.by_session("sess-A")
        assert len(results) == 2
        assert all(r["session_id"] == "sess-A" for r in results)

    def test_empty_session(self, logger):
        _insert_sample(logger, session_id="sess-A")
        results = logger.by_session("sess-NONE")
        assert len(results) == 0


class TestByTool:
    def test_filter_by_tool(self, logger):
        _insert_sample(logger, tool="search_arxiv")
        _insert_sample(logger, tool="search_arxiv")
        _insert_sample(logger, tool="analyze_emails")

        results = logger.by_tool("search_arxiv")
        assert len(results) == 2
        assert all(r["tool"] == "search_arxiv" for r in results)

    def test_unknown_tool(self, logger):
        _insert_sample(logger, tool="search_arxiv")
        results = logger.by_tool("nonexistent")
        assert len(results) == 0


class TestByDateRange:
    def test_range_query(self, logger):
        # Insert entries (timestamps are auto-generated as UTC ISO)
        _insert_sample(logger)
        _insert_sample(logger)

        rows = logger.get_recent(limit=10)
        # Use a wide range that includes now
        results = logger.by_date_range("2020-01-01", "2099-12-31")
        assert len(results) == 2

    def test_empty_range(self, logger):
        _insert_sample(logger)
        results = logger.by_date_range("2000-01-01", "2000-01-02")
        assert len(results) == 0


class TestExportJson:
    def test_export_all(self, logger):
        _insert_sample(logger, tool="tool_a")
        _insert_sample(logger, tool="tool_b")

        exported = logger.export_json()
        data = json.loads(exported)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_export_by_session(self, logger):
        _insert_sample(logger, session_id="s1")
        _insert_sample(logger, session_id="s2")

        exported = logger.export_json(session_id="s1")
        data = json.loads(exported)
        assert len(data) == 1
        assert data[0]["session_id"] == "s1"

    def test_export_empty(self, logger):
        exported = logger.export_json()
        data = json.loads(exported)
        assert data == []


class TestGetRecent:
    def test_limit_respected(self, logger):
        for i in range(10):
            _insert_sample(logger, tool=f"tool_{i}")

        results = logger.get_recent(limit=5)
        assert len(results) == 5

    def test_most_recent_first(self, logger):
        _insert_sample(logger, tool="first")
        _insert_sample(logger, tool="second")
        _insert_sample(logger, tool="third")

        results = logger.get_recent(limit=3)
        # Most recent (highest ID) should come first
        assert results[0]["tool"] == "third"
        assert results[2]["tool"] == "first"

    def test_empty_db(self, logger):
        results = logger.get_recent(limit=10)
        assert results == []
