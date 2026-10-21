from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from copilot import retrieval


@pytest.mark.parametrize("tool,args", [
    (retrieval.query_fleet_data, ("",)),
    (retrieval.query_fleet_data, ("fleet", "")),
    (retrieval.search_documents, ("brakes", 0)),
    (retrieval.search_documents, ("brakes", 11)),
    (retrieval.query_knowledge_graph, ("",)),
])
def test_invalid_requests_are_rejected(tool, args):
    assert tool(*args).status == "error"


def test_database_failure_does_not_claim_empty_evidence(monkeypatch):
    def fail():
        raise ConnectionError("private connection credentials")
    monkeypatch.setattr(retrieval, "read_connection", fail)
    result = retrieval.query_fleet_data("latest readings")
    assert result.status == "unavailable"
    assert "private" not in result.model_dump_json()


def test_fleet_anchor_provenance_and_parameter_binding(monkeypatch):
    anchor = datetime(2025, 1, 10, tzinfo=timezone.utc)
    answers = iter([
        {"anchor": anchor}, [],
        [{"id": "independent-1", "source": "fixture.csv", "payload": {"temperature": 10}}],
        [], [],
    ])
    calls = []
    class Connection:
        def execute(self, sql, params=None):
            calls.append((sql, params))
            self.answer = next(answers)
            return self
        def fetchone(self):
            return self.answer
        def fetchall(self):
            return self.answer
    @contextmanager
    def connection():
        yield Connection()
    monkeypatch.setattr(retrieval, "read_connection", connection)
    malicious_tail = "'; DROP TABLE sensor_readings; --"
    result = retrieval.query_fleet_data("last 7 days", malicious_tail)
    assert result.status == "ok"
    assert result.source_time == anchor.isoformat()
    assert result.citations[0]["record_id"] == "independent-1"
    assert all(malicious_tail not in sql for sql, _ in calls)
    assert calls[1][1][2] == 7


def test_lexical_fallback_is_disclosed_and_cited(monkeypatch):
    monkeypatch.setattr(retrieval, "_embedding_model", lambda: (_ for _ in ()).throw(OSError()))
    class Connection:
        def execute(self, sql, params):
            assert params[1] is None
            return self
        def fetchall(self):
            return [{"id": "chunk-1", "source": "fixture.md", "chunk_index": 0, "content": "Inspect brakes."}]
    @contextmanager
    def connection():
        yield Connection()
    monkeypatch.setattr(retrieval, "read_connection", connection)
    result = retrieval.search_documents("brakes")
    assert result.status == "ok"
    assert "lexical" in result.error
    assert result.citations[0]["source"] == "fixture.md"


@pytest.mark.parametrize("question,days", [
    ("recent brake temperatures", 7), ("tail DEMO-1 lately", 7),
    ("past month", 30), ("last two weeks", 14), ("yesterday", 1),
    ("last 3 days", 3), ("all records", None),
])
def test_relative_time_windows(question, days):
    assert retrieval._time_window(question) == days


def test_unsupported_relative_time_is_not_silently_all_time():
    result = retrieval.query_fleet_data("last 12 hours")
    assert result.status == "error"


@pytest.mark.parametrize("question,expected", [
    ("tail UNKNOWN lately", "UNKNOWN"),
    ("tail DEMO-1's recent temperatures", "DEMO-1"),
    ('tail number "DEMO-2" lately', "DEMO-2"),
])
def test_implicit_tail_never_broadens_to_entire_fleet(monkeypatch, question, expected):
    bound_tails = []
    class Connection:
        def execute(self, sql, params=None):
            if params:
                bound_tails.append(params[0])
            return self
        def fetchone(self):
            return {"anchor": None}
        def fetchall(self):
            return []
    @contextmanager
    def connection():
        yield Connection()
    monkeypatch.setattr(retrieval, "read_connection", connection)
    result = retrieval.query_fleet_data(question)
    assert result.status == "empty"
    assert bound_tails[:3] == [expected] * 3


def test_incomplete_tail_request_is_rejected():
    assert retrieval.query_fleet_data("recent readings for tail").status == "error"
