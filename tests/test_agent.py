import json
from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from copilot import agent
from copilot.contracts import ToolResult


def test_graph_preserves_citations_and_caps_calls(monkeypatch):
    calls = []

    def lookup(question: str) -> ToolResult:
        """Read independent test evidence."""
        calls.append(question)
        return ToolResult(status="ok", data=[{"value": 7}], citations=[{"source": "fixture"}])

    monkeypatch.setattr(agent, "HANDLERS", {"lookup": lookup})
    responses = iter([
        AIMessage(content="", tool_calls=[{"name": "lookup", "args": {"question": "fixture"}, "id": str(i)} for i in range(7)]),
        AIMessage(content=json.dumps({"answer": "The observed value is 7."})),
    ])
    monkeypatch.setattr(agent, "_invoke", lambda *a, **kw: next(responses))
    result = agent.run_query("What is the observation?")
    assert len(calls) == 4
    assert result["status"] == "ok"
    assert result["citations"] == [{"source": "fixture"}] * 4


def test_unknown_tool_and_missing_evidence_do_not_invent_stock(monkeypatch):
    monkeypatch.setattr(agent, "_invoke", lambda *a, **kw: AIMessage(content="", tool_calls=[
        {"name": "admin_fault", "args": {}, "id": "1"},
    ]))
    result = agent.run_query("Is stock available?")
    assert result["status"] == "unavailable"
    assert "unknown" in result["answer"]
    assert result["citations"] == []


def test_fallback_uses_json_final_without_tools(monkeypatch):
    seen = []

    class FakeModel:
        def __init__(self, **kwargs):
            seen.append(kwargs)
            self.model = kwargs["model"]

        def bind(self, **kwargs):
            assert kwargs == {"response_format": {"type": "json_object"}}
            return self

        def invoke(self, messages):
            if "gemma" in self.model:
                raise TimeoutError
            return AIMessage(content='{"answer":"Insufficient evidence."}')

    monkeypatch.setattr(agent, "ChatOpenAI", FakeModel)
    assert agent._invoke([], planning=False) is not None
    assert seen[0]["reasoning_effort"] == "none"
    assert "reasoning_effort" not in seen[1]
    assert all(item["max_retries"] == 0 for item in seen)


def test_final_prompt_bounds_evidence_and_serializes_database_timestamps(monkeypatch):
    def invoke(messages, **kwargs):
        prompt = json.loads(messages[-1].content)
        assert len(prompt["evidence"][0]["excerpt"]) <= agent.MAX_EVIDENCE_CHARS
        assert prompt["evidence"][0]["truncated"]
        return AIMessage(content='{"answer":"Evidence excerpt available."}')

    monkeypatch.setattr(agent, "_invoke", invoke)
    result = agent._answer({"question": "What changed?", "results": [{
        "tool": "query_fleet_data", "status": "ok", "citations": [{"source": "fixture"}],
        "data": [{"observed_at": datetime.now(timezone.utc), "text": "x" * 20000}],
    }]})
    assert result["answer"]["citations"] == [{"source": "fixture"}]
    assert "not assessed" in result["answer"]["answer"]
