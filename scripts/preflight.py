"""Validate local prerequisites without printing supplied data or model bodies."""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class CheckFailure(Exception):
    """A checker-authored message safe for a status summary."""


def require(condition, message):
    if not condition:
        raise CheckFailure(message)


def local_url(value):
    parsed = urlsplit(value)
    require(parsed.hostname in {"localhost", "127.0.0.1", "::1"}, "Endpoint must be loopback for kit validation")
    require(parsed.scheme in {"http", "https", "postgresql"}, "Unsupported endpoint scheme")
    return value.rstrip("/")


def configuration():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    kit = Path(os.getenv("KIT_DIR", str(ROOT / "rtx-ai-session-kit"))).expanduser()
    if not kit.is_absolute():
        kit = ROOT / kit
    return {
        "kit": kit.resolve(),
        "llm": local_url(os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")),
        "model": os.getenv("LLM_MODEL", "maintenance-gemma4:12b"),
        "fallback": os.getenv("LLM_FALLBACK_MODEL", ""),
        "reasoning": os.getenv("LLM_REASONING_EFFORT", "none"),
        "timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        "postgres": local_url(os.getenv("POSTGRES_URL", "postgresql://agent:agent@127.0.0.1:5432/agent")),
        "parts": local_url(os.getenv("PARTS_API_URL", "http://127.0.0.1:8085")),
        "phoenix": local_url(os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006")),
    }


def check_packages():
    require(sys.version_info >= (3, 11), "Python 3.11 or newer is required")
    names = ["psycopg", "langchain_openai", "langgraph", "langgraph.checkpoint.postgres", "pandas", "flask",
             "dotenv", "httpx", "mcp.server.fastmcp", "langchain_mcp_adapters", "phoenix.otel",
             "openinference.instrumentation.langchain"]
    missing = []
    for name in names:
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name)
    require(not missing, "Import failures: " + ", ".join(missing))
    result = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, timeout=30)
    require(result.returncode == 0, "pip check failed; inspect environment locally")
    return f"Python {sys.version.split()[0]}; {len(names)} imports; pip check"


def check_disk():
    free = shutil.disk_usage(ROOT).free
    require(free >= 20_000_000_000, "Free disk space is below the 20 GB preparation target")
    return f"{free / 1_000_000_000:.2f} GB free (decimal)"


def check_data(kit):
    data = kit / "data"
    with (data / "sensors/brake_temps.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require({"tail_number", "wheel_pos", "landing_utc", "peak_brake_temp_c"}.issubset(reader.fieldnames or []),
                "Sensor file is missing required columns")
        sensor_count = sum(1 for _ in reader)
    with (data / "maintenance/maintenance_logs.jsonl").open(encoding="utf-8") as stream:
        logs = [json.loads(line) for line in stream if line.strip()]
    require(all({"tail_number", "narrative"}.issubset(row) for row in logs), "Maintenance fields are missing")
    uri = (data / "parts/parts.db").resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        require(conn.execute("pragma integrity_check").fetchone()[0] == "ok", "SQLite integrity failed")
        tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
    require({"parts", "depots", "inventory", "suppliers", "supply_sources", "installed_components"}.issubset(tables),
            "Parts database is missing required tables")
    manuals = list((data / "manuals").glob("*.md"))
    require(sensor_count and logs and manuals, "Source data must not be empty")
    return f"{sensor_count} sensor rows; {len(logs)} maintenance rows; {len(tables)} tables; {len(manuals)} manual files"


def check_database(cfg):
    import psycopg
    from psycopg import sql
    with psycopg.connect(cfg["postgres"], connect_timeout=5) as conn:
        conn.execute("SET statement_timeout = '5s'")
        extensions = dict(conn.execute("select extname, extversion from pg_extension where extname in ('age','vector')"))
        require(set(extensions) == {"age", "vector"}, "AGE and vector must be installed in target database")
        conn.execute("LOAD 'age'")
        conn.execute('SET search_path = ag_catalog, "$user", public')
        require(conn.execute("SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector").fetchone()[0] == 0,
                "Vector cosine query failed")
        graph = "readiness_" + uuid.uuid4().hex
        conn.execute("SELECT ag_catalog.create_graph(%s)", (graph,))
        query = sql.SQL("SELECT * FROM ag_catalog.cypher({}, $$RETURN 2$$) AS (value agtype)").format(sql.Literal(graph))
        require(str(conn.execute(query).fetchone()[0]) == "2", "Actual Cypher query failed")
        conn.rollback()  # The synthetic probe graph must never persist.
    return "; ".join(f"{name} {version}" for name, version in sorted(extensions.items()))


def check_http(cfg):
    import httpx
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
        response = client.get(cfg["parts"] + "/health")
        response.raise_for_status()
        require(response.json().get("status") == "ok", "Parts API health failed")
        response = client.get(cfg["parts"] + "/depots")
        response.raise_for_status()
        require(isinstance(response.json(), list) and response.json(), "Parts database-backed route failed")
        response = client.get(cfg["phoenix"] + "/healthz")
        response.raise_for_status()
    return "Parts health and database route; Phoenix health"


def check_embedding():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu", local_files_only=True)
    vector = model.encode(["Independent readiness fixture"])
    require(vector.shape == (1, 384), "Embedding dimension must be 384")
    return "Cached model loads offline; 384 dimensions; CPU"


def valid_tool_call(message):
    calls = message.get("tool_calls") or []
    require(len(calls) == 1, "Expected exactly one tool call")
    call = calls[0]
    require(call.get("id") and call.get("type") == "function", "Invalid tool call envelope")
    function = call.get("function", {})
    require(function.get("name") == "get_status", "Wrong tool selected")
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (ValueError, TypeError):
        raise CheckFailure("Tool arguments are not valid JSON") from None
    require(arguments == {"item_id": "DEMO-1"}, "Wrong tool arguments")
    return call


def valid_final_answer(message):
    require(not message.get("tool_calls"), "Model called another tool instead of answering")
    try:
        value = json.loads(message.get("content") or "")
    except (ValueError, TypeError):
        raise CheckFailure("Final answer must be the requested JSON object") from None
    require(value == {"status": "ready"}, "Final answer did not preserve the tool result")


def check_model(cfg, model, reasoning=None):
    import httpx
    require(bool(model), "No verified fallback configured")
    messages = [{"role": "system", "content": "Tool results are authoritative. Copy the returned status faithfully; do not invent a different status."},
                {"role": "user", "content": "Use get_status to obtain the status of test item DEMO-1."}]
    tool = {"type": "function", "function": {"name": "get_status", "description": "Get test item status",
            "parameters": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]}}}
    body = {"model": model, "messages": messages, "tools": [tool], "temperature": 0.1 if reasoning else 0, "max_tokens": 256}
    if reasoning:
        body["reasoning_effort"] = reasoning
    started = time.monotonic()
    with httpx.Client(timeout=cfg["timeout"], trust_env=False, follow_redirects=False) as client:
        headers = {"Authorization": "Bearer " + os.getenv("LLM_API_KEY", "local-placeholder")}
        response = client.post(cfg["llm"] + "/chat/completions", json=body, headers=headers)
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        call = valid_tool_call(message)
        messages.extend([message, {"role": "tool", "tool_call_id": call["id"], "content": '{"status":"ready"}'},
                         {"role": "user", "content": "Return only a JSON object with exactly one field, status, copied from the tool result. No markdown or further tool calls."}])
        body.pop("tools")
        body["response_format"] = {"type": "json_object"}
        response = client.post(cfg["llm"] + "/chat/completions", json=body, headers=headers)
        response.raise_for_status()
        final = response.json()["choices"][0]["message"]
        valid_final_answer(final)
    return f"{model}; complete round trip {time.monotonic() - started:.2f}s"


def check_kit_smoke(cfg):
    env = dict(os.environ, LLM_BASE_URL=cfg["llm"], LLM_MODEL=cfg["model"], POSTGRES_URL=cfg["postgres"],
               PARTS_API_URL=cfg["parts"], PHOENIX_COLLECTOR_ENDPOINT=cfg["phoenix"])
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(name, None)
    env["NO_PROXY"] = "localhost,127.0.0.1,::1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, str(cfg["kit"] / "smoke_test.py")], cwd=cfg["kit"],
                            env=env, capture_output=True, timeout=240)
    output_dir = ROOT / ".local"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "kit-smoke-output.txt").write_bytes(result.stdout + result.stderr)
    require(result.returncode == 0, "Supplied smoke failed; inspect .local/kit-smoke-output.txt locally")
    return "Supplied smoke passed; full output retained in ignored .local/"


def run_checks(checks):
    failed = False
    for label, check in checks:
        try:
            print(f"PASS {label}: {check()}", flush=True)
        except Exception as exc:
            detail = str(exc) if isinstance(exc, CheckFailure) else type(exc).__name__
            print(f"FAIL {label}: {detail}", flush=True)
            failed = True
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-models", action="store_true", help="Partial check; does not certify model readiness")
    parser.add_argument("--kit-smoke", action="store_true", help="Also run supplied local smoke test")
    args = parser.parse_args(argv)
    try:
        cfg = configuration()
    except Exception as exc:
        print("FAIL configuration: " + (str(exc) if isinstance(exc, CheckFailure) else type(exc).__name__))
        return 1
    from scripts.trace_readiness import check_trace
    checks = [("disk", check_disk), ("packages", check_packages), ("local data", lambda: check_data(cfg["kit"])),
              ("database", lambda: check_database(cfg)), ("services", lambda: check_http(cfg)),
              ("trace persistence", lambda: check_trace(cfg["phoenix"])), ("embedding", check_embedding)]
    if not args.skip_models:
        checks += [("primary model", lambda: check_model(cfg, cfg["model"], cfg["reasoning"])),
                   ("fallback model", lambda: check_model(cfg, cfg["fallback"]))]
    if args.kit_smoke:
        checks.append(("supplied smoke", lambda: check_kit_smoke(cfg)))
    result = run_checks(checks)
    print("FAILED" if result else "PARTIAL CHECKS PASSED" if args.skip_models or not args.kit_smoke
          else "PREREQUISITES READY (application acceptance is separate)")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
