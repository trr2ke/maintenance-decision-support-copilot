"""Web boundaries use independent fixtures; no services or supplied data."""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from copilot import web


@pytest.fixture
def app(monkeypatch, tmp_path):
    @contextmanager
    def trace(_name):
        yield Mock()
    monkeypatch.setattr(web, "trace_operation", trace)
    monkeypatch.setattr(web, "flush_traces", Mock())
    application = web.create_app()
    application.config.update(TESTING=True, GRAPH_OUTPUT=tmp_path / "graph.html")
    return application


@pytest.mark.parametrize("body", [None, [], {}, {"question": False}, {"question": " "}, {"question": "x" * 2001}])
def test_invalid_query_does_not_run(app, monkeypatch, body):
    run = Mock()
    monkeypatch.setattr(web, "run_query", run)
    response = app.test_client().post("/api/query", json=body)
    assert response.status_code == 400
    run.assert_not_called()


@pytest.mark.parametrize("status", ["ok", "partial", "unavailable"])
def test_query_preserves_evidence_and_iso_dates(app, monkeypatch, status):
    result = {"status": status, "answer": "Fixture answer", "citations": [{"source": "fixture"}],
              "evidence": [{"source_time": datetime(2026, 1, 2, tzinfo=timezone.utc)}]}
    run = Mock(return_value=result)
    monkeypatch.setattr(web, "run_query", run)
    response = app.test_client().post("/api/query", json={"question": " fixture question "})
    assert response.status_code == 200
    assert response.json["status"] == status
    assert response.json["citations"] == result["citations"]
    assert response.json["evidence"][0]["source_time"] == "2026-01-02T00:00:00+00:00"
    assert response.json["elapsed_seconds"] >= 0
    assert response.headers["Cache-Control"] == "no-store"
    run.assert_called_once_with("fixture question")


def test_shared_lock_and_failure_release(app, monkeypatch):
    monkeypatch.setattr(web, "run_query", Mock(side_effect=RuntimeError("private source content")))
    web._query_lock.acquire()
    try:
        assert app.test_client().post("/api/query", json={"question": "fixture"}).status_code == 409
    finally:
        web._query_lock.release()
    response = app.test_client().post("/api/query", json={"question": "fixture"})
    assert response.status_code == 503
    assert "private source" not in response.text
    assert not web._query_lock.locked()
    web.flush_traces.assert_called_once()


@pytest.mark.parametrize("base,origin", [
    ("http://foreign.example", None), ("http://localhost", "http://foreign.example"),
    ("http://localhost", "null"), ("http://localhost", "http://localhost:9000"),
    ("http://127.0.0.1", "http://localhost"),
])
def test_foreign_requests_rejected(app, base, origin):
    headers = {"Origin": origin} if origin else {}
    response = app.test_client().post("/api/query", base_url=base, headers=headers, json={"question": "fixture"})
    assert response.status_code == 403


def test_matching_origin_accepted_and_large_body_rejected(app, monkeypatch):
    monkeypatch.setattr(web, "run_query", Mock(return_value={"status": "ok"}))
    client = app.test_client()
    assert client.post("/api/query", headers={"Origin": "http://localhost"}, json={"question": "fixture"}).status_code == 200
    assert client.post("/api/query", data="x" * 20000, content_type="application/json").status_code == 400
    assert client.post("/api/query", headers={"Sec-Fetch-Site": "cross-site"}, json={"question": "fixture"}).status_code == 403
    assert client.get("/api/health", base_url="http://foreign.example").status_code == 403


def test_health_failure_keeps_counts_unknown(app, monkeypatch):
    monkeypatch.setattr(web, "_database_health", Mock(side_effect=RuntimeError("secret")))
    monkeypatch.setattr(web, "_http_health", Mock(return_value=True))
    result = app.test_client().get("/api/health").json
    assert result["status"] == "degraded"
    assert result["services"] == {"database": False, "parts": True, "model": True}
    assert all(value is None for value in result["counts"].values())
    assert "secret" not in str(result)


def test_health_success_and_model_missing(app, monkeypatch):
    row = {"sensor_readings": 8, "maintenance_logs": 2, "document_chunks": 3,
           "relationships": 1, "source_time": datetime(2026, 1, 2, tzinfo=timezone.utc)}
    monkeypatch.setattr(web, "_database_health", Mock(return_value=row))
    monkeypatch.setattr(web, "_http_health", lambda _url, model=None: model is None)
    result = app.test_client().get("/api/health").json
    assert result["services"]["database"] is True
    assert result["services"]["model"] is False
    assert result["counts"]["sensor_readings"] == 8
    assert result["source_time"] == row["source_time"].isoformat()
    monkeypatch.setattr(web, "_http_health", lambda *_args: True)
    assert app.test_client().get("/api/health").json["status"] == "ok"


def test_graph_uses_local_output_and_safe_failure(app, monkeypatch):
    monkeypatch.setattr(web, "load_graph", Mock(return_value=[]))
    monkeypatch.setattr(web, "render_graph", lambda rows, output: output.write_text("<html>Fixture graph</html>", encoding="utf-8"))
    response = app.test_client().get("/graph")
    assert response.status_code == 200
    assert "Fixture graph" in response.text
    monkeypatch.setattr(web, "load_graph", Mock(side_effect=RuntimeError("private data")))
    response = app.test_client().get("/graph")
    assert response.status_code == 503
    assert "private data" not in response.text
