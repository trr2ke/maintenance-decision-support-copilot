"""Run with python -m copilot; source data stays on this machine."""
import argparse
import json
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local maintenance evidence assistant")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Create the application tables")
    commands.add_parser("ingest", help="Load the configured local kit idempotently")
    extraction = commands.add_parser("extract", help="Extract cited relationships with local models into Apache AGE")
    extraction.add_argument("--force", action="store_true", help="Re-extract unchanged document chunks")
    ask = commands.add_parser("ask", help="Ask a question using local evidence")
    ask.add_argument("question")
    commands.add_parser("mcp", help="Serve shared tools over MCP stdio")
    args = parser.parse_args(argv)
    try:
        if args.command == "migrate":
            from copilot.db import migrate
            migrate()
            print(json.dumps({"status": "ok", "action": "migrate"}))
        elif args.command == "ingest":
            from copilot.ingestion import ingest
            print(json.dumps(ingest(), default=str))
        elif args.command == "extract":
            from copilot.extraction import extract_graph
            result = extract_graph(force=args.force)
            print(json.dumps(result))
            return 0 if result["status"] == "ok" else 1
        elif args.command == "mcp":
            from copilot.mcp_server import main as serve
            serve()
        else:
            from copilot.agent import run_query
            from copilot.telemetry import trace_operation, flush_traces
            with trace_operation("copilot.query") as span:
                result = run_query(args.question)
                span.set_attribute("answer.status", result.get("status", "error"))
            flush_traces()
            print(json.dumps(result, ensure_ascii=False, default=str))
            return 0 if result.get("status") == "ok" else 1
    except Exception as exc:
        # Do not print database URLs, source records or model bodies in errors.
        print(json.dumps({"status": "error", "error": type(exc).__name__}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
