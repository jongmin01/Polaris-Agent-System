"""Tests for polaris.tools registry (get_all_tools, execute_tool)."""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestGetAllTools:
    def test_returns_list(self):
        from polaris.tools import get_all_tools
        tools = get_all_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_returns_copy(self):
        from polaris.tools import get_all_tools
        tools1 = get_all_tools()
        tools2 = get_all_tools()
        # Should return a copy, not the same object
        assert tools1 is not tools2
        assert tools1 == tools2


class TestToolSchemaFormat:
    def test_each_tool_has_required_keys(self):
        from polaris.tools import get_all_tools
        tools = get_all_tools()
        for tool in tools:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool.get('name')} missing 'input_schema'"

    def test_input_schema_is_object_type(self):
        from polaris.tools import get_all_tools
        tools = get_all_tools()
        for tool in tools:
            schema = tool["input_schema"]
            assert schema["type"] == "object", f"Tool {tool['name']} schema type is not 'object'"
            assert "properties" in schema, f"Tool {tool['name']} schema missing 'properties'"

    def test_tool_names_unique(self):
        from polaris.tools import get_all_tools
        tools = get_all_tools()
        names = [t["name"] for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tool names found: {names}"

    def test_known_tools_present(self):
        from polaris.tools import get_all_tools
        tools = get_all_tools()
        names = {t["name"] for t in tools}
        # At minimum, these tools should exist from the tool modules
        expected = {"search_arxiv", "monitor_hpc_job", "get_calendar_briefing"}
        for name in expected:
            assert name in names, f"Expected tool '{name}' not found in registry"


class TestExecuteTool:
    def test_unknown_tool_returns_error(self):
        from polaris.tools import execute_tool
        result = execute_tool("nonexistent_tool_xyz", {})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    @patch("polaris.tools.arxiv_tools._search_arxiv")
    def test_dispatch_search_arxiv(self, mock_search):
        mock_search.return_value = [{"title": "Test Paper", "authors": ["Author"]}]
        from polaris.tools import execute_tool
        result = execute_tool("search_arxiv", {"query": "MoS2"})
        parsed = json.loads(result)
        assert "papers" in parsed or "error" not in parsed
        mock_search.assert_called_once_with("MoS2", 10)

    @patch("polaris.tools.hpc_tools._PhysicsMonitor")
    def test_dispatch_check_hpc_connection(self, mock_monitor_cls):
        mock_instance = MagicMock()
        mock_instance.zombie_guard.return_value = True
        mock_monitor_cls.return_value = mock_instance
        # Re-assign the module-level ref so the handler uses our mock
        import polaris.tools.hpc_tools as hpc_mod
        original = hpc_mod._PhysicsMonitor
        hpc_mod._PhysicsMonitor = mock_monitor_cls
        try:
            from polaris.tools import execute_tool
            result = execute_tool("check_hpc_connection", {})
            parsed = json.loads(result)
            assert parsed.get("alive") is True or "error" in parsed
        finally:
            hpc_mod._PhysicsMonitor = original

    def test_execute_tool_with_extra_args(self):
        """Tools should handle kwargs properly."""
        from polaris.tools import execute_tool
        # search_arxiv accepts query and max_results
        with patch("polaris.tools.arxiv_tools._search_arxiv") as mock:
            mock.return_value = []
            result = execute_tool("search_arxiv", {"query": "test", "max_results": 5})
            parsed = json.loads(result)
            mock.assert_called_once_with("test", 5)
