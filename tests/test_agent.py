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
        AIMessage(content="", tool_calls=[{"name": "lookup", "args": {"question": "followup"}, "id": str(i)} for i in range(7)]),
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
        assert len(json.dumps(prompt["evidence"])) <= agent.MAX_EVIDENCE_CHARS
        assert prompt["evidence"][0]["truncated"]
        return AIMessage(content='{"answer":"Evidence excerpt available."}')

    monkeypatch.setattr(agent, "_invoke", invoke)
    result = agent._answer({"question": "What changed?", "results": [{
        "tool": "query_fleet_data", "status": "ok", "citations": [{"source": "fixture"}],
        "data": [{"observed_at": datetime.now(timezone.utc), "text": "x" * 20000}],
    }]})
    assert result["answer"]["citations"] == [{"source": "fixture"}]
    assert "not assessed" in result["answer"]["answer"]


def test_context_retains_scope_and_only_selected_record_citations():
    rows = [{"kind": "sensor_summary", "groups": [{"reading_count": 8}], "scope": {"days": 7, "anchor": "2026-01-01"}}]
    rows += [{"kind": "sensor_reading", "id": i, "source": "fixture", "payload": "x" * 800} for i in range(20)]
    envelope = agent._context([{"tool": "query_fleet_data", "status": "ok", "source_time": "2026-01-01", "data": rows,
        "citations": [{"source": "fixture", "record_id": i} for i in range(20)]}])[0]
    assert envelope["source_time"] == "2026-01-01"
    assert envelope["data"][0]["scope"]["days"] == 7
    ids = {row.get("id") for row in envelope["data"]}
    assert all(c["record_id"] in ids for c in envelope["citations"])


def test_depot_listing_is_not_stock_assessment(monkeypatch):
    monkeypatch.setattr(agent, "_invoke", lambda *a, **kw: AIMessage(content='{"answer":"Depot listed."}'))
    result = agent._answer({"question": "Any stock?", "results": [{"tool": "query_parts", "status": "ok",
        "data": [{"resource": "depots", "records": [{"depot_id": "D1"}]}], "citations": []}]})
    assert "not assessed" in result["answer"]["answer"]


def test_followup_sees_discovered_part_number(monkeypatch):
    def invoke(messages, **kwargs):
        assert "FIXTURE-PN" in messages[-1].content
        return AIMessage(content="", tool_calls=[{"name": "query_parts", "args": {"part_number": "FIXTURE-PN"}, "id": "2"}])
    monkeypatch.setattr(agent, "_invoke", invoke)
    result = agent._followup({"question": "Find replacement stock", "results": [{"tool": "query_fleet_data", "status": "ok",
        "data": [{"part_number": "FIXTURE-PN"}], "citations": []}]})
    assert result["calls"][0]["args"] == {"part_number": "FIXTURE-PN"}


def test_context_prioritizes_hottest_groups_and_installed_parts():
    rows = [{"kind": "sensor_summary", "scope": {"days": 7}, "groups": [
        {"wheel_position": str(i), "max_peak_brake_temp_c": value}
        for i, value in enumerate([None, 100, 200, 300, 900, 800])]}]
    rows += [{"kind": "source_record", "source": "parts/depots", "record_key": "D1"},
             {"kind": "source_record", "source": "parts/installed_components", "record_key": "I1", "payload": {"part_number": "P1"}},
             {"kind": "sensor_reading", "id": "cool", "observed_at": "2026-01-03", "payload": {"peak_brake_temp_c": 50}},
             {"kind": "sensor_reading", "id": "hot", "observed_at": "2026-01-01", "payload": {"peak_brake_temp_c": 900}}]
    result = agent._context([{"tool": "query_fleet_data", "status": "ok", "data": rows, "citations": []}])[0]
    summary = next(row for row in result["data"] if row.get("kind") == "sensor_summary")
    assert [group["max_peak_brake_temp_c"] for group in summary["groups"]] == [900, 800]
    assert summary["groups_truncated"]
    assert next(row for row in result["data"] if row.get("kind") == "source_record")["record_key"] == "I1"
    assert next(row for row in result["data"] if row.get("kind") == "sensor_reading")["id"] == "hot"
    assert any(row.get("id") == "cool" for row in result["data"])


def test_maintenance_route_gets_fleet_documents_and_discovered_stock(monkeypatch):
    called = []

    def query_fleet_data(question: str) -> ToolResult:
        """Read synthetic fleet."""
        called.append("fleet")
        return ToolResult(status="ok", data=[{"kind": "source_record", "source": "parts/installed_components",
            "record_key": "I1", "payload": {"tail_number": "T1", "part_number": "KNOWN-PART"}}],
            citations=[{"source": "parts/installed_components", "record_id": "I1"}])

    def search_documents(query: str, limit: int = 3) -> ToolResult:
        """Read synthetic manual."""
        called.append("documents")
        return ToolResult(status="ok", data=[{"content": "Inspect brakes."}], citations=[{"source": "fixture-manual"}])

    def query_parts(part_number: str) -> ToolResult:
        """Read synthetic stock."""
        assert part_number == "KNOWN-PART"
        called.append("parts")
        return ToolResult(status="ok", data=[{"resource": "inventory", "records": [{"on_hand": 1}]}])

    def invoke(messages, *, planning):
        if planning:
            return AIMessage(content="", tool_calls=[{"name": "query_knowledge_graph", "args": {"question": "brakes"}, "id": "bad-route"}])
        return AIMessage(content='{"answer":"Inspect according to the cited manual; observed stock is 1."}')

    monkeypatch.setattr(agent, "HANDLERS", {fn.__name__: fn for fn in [query_fleet_data, search_documents, query_parts]})
    monkeypatch.setattr(agent, "_invoke", invoke)
    result = agent.run_query("Check brake temperatures, maintenance procedure and replacement stock for tail T1")
    assert called == ["fleet", "documents", "parts"]
    assert len(result["evidence"]) <= agent.MAX_TOOLS
    assert result["status"] == "ok"


def test_global_context_budget_preserves_status_time_and_valid_citations():
    results = []
    for tool in range(4):
        source = "fixture-" + str(tool)
        results.append({"tool": f"lookup{tool}", "status": "ok", "source_time": "2026-01-01",
            "data": [{"id": i, "source": source, "content": "x" * 600} for i in range(5)],
            "citations": [{"source": source, "record_id": i, "description": "y" * 400} for i in range(5)]})
    context = agent._context(results)
    assert len(json.dumps(context)) <= agent.MAX_EVIDENCE_CHARS
    assert all(item["status"] == "ok" and item["source_time"] == "2026-01-01" for item in context)
    for item in context:
        assert all(citation["record_id"] in {row["id"] for row in item["data"]} for citation in item["citations"])
