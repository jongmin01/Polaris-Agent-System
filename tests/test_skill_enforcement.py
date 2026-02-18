"""Tests for skill tool enforcement and chaining in router."""

from types import SimpleNamespace
from unittest.mock import patch


class _FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self.response


class _FakeClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_FakeCompletions(response))


def _make_response(content="final", finish_reason="stop", tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(finish_reason=finish_reason, message=msg)
    return SimpleNamespace(choices=[choice])


@patch("polaris.router.PolarisRouter._init_ollama")
@patch("polaris.router.PolarisRouter._load_tools")
@patch("polaris.router.PolarisRouter._init_memory")
@patch("polaris.router.PolarisRouter._init_feedback")
@patch("polaris.router.PolarisRouter._init_fact_extractor")
@patch("polaris.router.PolarisRouter._init_vault_reader")
def test_requires_tool_blocks_when_no_successful_tool(
    _mock_vault,
    _mock_fact,
    _mock_feedback,
    _mock_memory,
    _mock_tools,
    _mock_ollama,
):
    from polaris.router import PolarisRouter

    router = PolarisRouter()
    router.tools = [
        {
            "name": "monitor_hpc_job",
            "description": "x",
            "input_schema": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}, "path": {"type": "string"}},
                "required": ["job_id", "path"],
            },
        }
    ]
    router.skill_registry = SimpleNamespace(
        match=lambda _: [
            {
                "name": "hpc_monitor",
                "requires_tool": True,
                "strict_mode": True,
                "tool_chain": ["monitor_hpc_job"],
                "tools_required": ["monitor_hpc_job"],
            }
        ]
    )

    response = _make_response(content="hallucinated", finish_reason="stop")
    router.client = _FakeClient(response)

    result = router._route_ollama("계산 상태 알려줘")
    assert "도구 실행 결과" in result["response"]


@patch("polaris.router.PolarisRouter._init_ollama")
@patch("polaris.router.PolarisRouter._load_tools")
@patch("polaris.router.PolarisRouter._init_memory")
@patch("polaris.router.PolarisRouter._init_feedback")
@patch("polaris.router.PolarisRouter._init_fact_extractor")
@patch("polaris.router.PolarisRouter._init_vault_reader")
def test_preflight_zero_arg_tool_allows_final_response(
    _mock_vault,
    _mock_fact,
    _mock_feedback,
    _mock_memory,
    _mock_tools,
    _mock_ollama,
):
    from polaris.router import PolarisRouter

    router = PolarisRouter()
    router.tools = [
        {
            "name": "check_hpc_connection",
            "description": "x",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }
    ]
    router.skill_registry = SimpleNamespace(
        match=lambda _: [
            {
                "name": "hpc_monitor",
                "requires_tool": True,
                "strict_mode": True,
                "tool_chain": ["check_hpc_connection"],
                "tools_required": ["check_hpc_connection"],
            }
        ]
    )

    response = _make_response(content="정상 응답", finish_reason="stop")
    router.client = _FakeClient(response)

    with patch.object(router, "_execute_tool", return_value='{"alive": true}'):
        result = router._route_ollama("HPC 연결 확인")

    assert result["response"] == "정상 응답"
    assert "check_hpc_connection" in result["tools_used"]


@patch("polaris.router.PolarisRouter._init_ollama")
@patch("polaris.router.PolarisRouter._load_tools")
@patch("polaris.router.PolarisRouter._init_memory")
@patch("polaris.router.PolarisRouter._init_feedback")
@patch("polaris.router.PolarisRouter._init_fact_extractor")
@patch("polaris.router.PolarisRouter._init_vault_reader")
def test_requires_tool_limits_model_tool_set(
    _mock_vault,
    _mock_fact,
    _mock_feedback,
    _mock_memory,
    _mock_tools,
    _mock_ollama,
):
    from polaris.router import PolarisRouter

    router = PolarisRouter()
    router.tools = [
        {
            "name": "search_arxiv",
            "description": "x",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "analyze_emails",
            "description": "x",
            "input_schema": {
                "type": "object",
                "properties": {"emails": {"type": "array"}},
                "required": ["emails"],
            },
        },
    ]
    router.skill_registry = SimpleNamespace(
        match=lambda _: [
            {
                "name": "arxiv_analysis",
                "requires_tool": True,
                "strict_mode": True,
                "tool_chain": ["search_arxiv"],
                "tools_required": ["search_arxiv"],
            }
        ]
    )

    response = _make_response(content="도구 필요", finish_reason="stop")
    client = _FakeClient(response)
    router.client = client

    result = router._route_ollama("논문 분석해줘")

    sent_tools = client.chat.completions.last_kwargs.get("tools", [])
    sent_names = [t["function"]["name"] for t in sent_tools]
    assert sent_names == ["search_arxiv"]
    assert "도구 실행 결과" in result["response"]
