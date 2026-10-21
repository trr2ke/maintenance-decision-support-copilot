"""Loopback-only web entry point for the existing evidence workflow."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request
from flask.json.provider import DefaultJSONProvider
import httpx
import psycopg
from psycopg.rows import dict_row

from copilot.agent import run_query
from copilot.config import ROOT, get_settings
from copilot.telemetry import flush_traces, trace_operation
from copilot.visualization import load_graph, render_graph

_query_lock = threading.Lock()
_graph_lock = threading.Lock()
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


class ISOJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return DefaultJSONProvider.default(value)


def _database_health(settings):
    with psycopg.connect(settings.postgres_url, connect_timeout=2,
                          options="-c default_transaction_read_only=on -c statement_timeout=1000",
                          row_factory=dict_row) as connection:
        row = connection.execute("""SELECT
            (SELECT count(*) FROM sensor_readings) AS sensor_readings,
            (SELECT count(*) FROM maintenance_logs) AS maintenance_logs,
            (SELECT count(*) FROM document_chunks) AS document_chunks,
            (SELECT count(*) FROM knowledge_triples) AS relationships,
            greatest((SELECT max(observed_at) FROM sensor_readings),
                     (SELECT max(occurred_at) FROM maintenance_logs)) AS source_time
        """).fetchone()
        return row


def _http_health(url, model=None):
    with httpx.Client(timeout=1.5, trust_env=False, follow_redirects=False) as client:
        response = client.get(url)
        response.raise_for_status()
        return model is None or any(item.get("name") == model
                                    for item in response.json().get("models", []))


def health_status():
    settings = get_settings()
    result = {"status": "degraded", "services": {"database": False, "parts": False, "model": False},
              "counts": {key: None for key in ("sensor_readings", "maintenance_logs", "document_chunks", "relationships")},
              "source_time": None}
    parsed = urlsplit(settings.llm_base_url)
    model_url = f"{parsed.scheme}://{parsed.netloc}/api/tags"
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {"database": pool.submit(_database_health, settings),
                   "parts": pool.submit(_http_health, settings.parts_api_url + "/health"),
                   "model": pool.submit(_http_health, model_url, settings.llm_model)}
        for service, future in pending.items():
            try:
                value = future.result()
                result["services"][service] = bool(value)
                if service == "database":
                    result["counts"] = {key: value[key] for key in result["counts"]}
                    result["source_time"] = value["source_time"]
            except Exception:
                pass
    if all(result["services"].values()):
        result["status"] = "ok"
    return result


def create_app():
    app = Flask(__name__)
    app.json = ISOJSONProvider(app)
    app.config.update(MAX_CONTENT_LENGTH=16384, GRAPH_OUTPUT=ROOT / ".local" / "artifacts" / "maintenance-graph.html")

    @app.before_request
    def local_only():
        try:
            if urlsplit(request.host_url).hostname not in _LOOPBACK:
                return jsonify(error="This application is available only on localhost."), 403
            if request.method == "POST":
                origin = request.headers.get("Origin")
                if origin and origin != request.host_url.rstrip("/"):
                    return jsonify(error="Cross-origin requests are not allowed."), 403
                if request.headers.get("Sec-Fetch-Site") == "cross-site":
                    return jsonify(error="Cross-site requests are not allowed."), 403
        except ValueError:
            return jsonify(error="Invalid local request."), 403

    @app.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="Request is too large."), 400

    @app.get("/")
    def index():
        return render_template("app.html")

    @app.get("/api/health")
    def health():
        try:
            return jsonify(health_status())
        except Exception:
            return jsonify(error="Local service status is unavailable."), 503

    @app.post("/api/query")
    def query():
        body = request.get_json(silent=True)
        question = body.get("question") if isinstance(body, dict) else None
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return jsonify(error="Provide a question of 1–2000 characters."), 400
        if not _query_lock.acquire(blocking=False):
            return jsonify(error="Another question is running. Try again when it finishes."), 409
        started = time.monotonic()
        try:
            with trace_operation("web.query") as span:
                result = run_query(question.strip())
                span.set_attribute("answer.status", result.get("status", "error"))
            return jsonify({**result, "elapsed_seconds": round(time.monotonic() - started, 2)})
        except Exception:
            return jsonify(error="The local query could not complete. Check service status and try again."), 503
        finally:
            try:
                flush_traces()
            except Exception:
                pass
            _query_lock.release()

    @app.get("/graph")
    def graph():
        try:
            with _graph_lock:
                output = Path(app.config["GRAPH_OUTPUT"])
                render_graph(load_graph(), output)
                # Read under the lock so another request cannot truncate this response.
                return app.response_class(output.read_text(encoding="utf-8"), mimetype="text/html")
        except Exception:
            return jsonify(error="The knowledge graph is unavailable. Check database status."), 503

    return app
