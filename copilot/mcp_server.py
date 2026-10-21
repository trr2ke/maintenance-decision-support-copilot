"""Run with python -m copilot.mcp_server; only read-only evidence tools are exposed."""
from functools import wraps

from mcp.server.fastmcp import FastMCP
from opentelemetry.trace import Status, StatusCode

from copilot.parts import query_parts
from copilot.contracts import ToolResult
from copilot.telemetry import configure_tracing, flush_traces, trace_operation


def query_fleet_data(question: str, tail_number: str | None = None) -> ToolResult:
    """Query fleet observations and maintenance history with provenance."""
    from copilot.retrieval import query_fleet_data as handler
    return handler(question, tail_number)


def search_documents(query: str, limit: int = 5) -> ToolResult:
    """Search local maintenance documents and return cited excerpts."""
    from copilot.retrieval import search_documents as handler
    return handler(query, limit)


def query_knowledge_graph(question: str) -> ToolResult:
    """Query relationships between aircraft, faults and components."""
    from copilot.retrieval import query_knowledge_graph as handler
    return handler(question)


def _traced(handler):
    @wraps(handler)
    def invoke(*args, **kwargs):
        with trace_operation(f"tool.{handler.__name__}") as span:
            result = handler(*args, **kwargs)
            span.set_attribute("tool.status", result.status)
            if result.status in {"error", "unavailable"}:
                span.set_status(Status(StatusCode.ERROR, "Evidence unavailable"))
            return result
    return invoke


HANDLERS = {name: _traced(handler) for name, handler in {
    "query_fleet_data": query_fleet_data,
    "search_documents": search_documents,
    "query_knowledge_graph": query_knowledge_graph,
    "query_parts": query_parts,
}.items()}
mcp = FastMCP("maintenance-decision-support")
for handler in HANDLERS.values():
    mcp.tool()(handler)

def main():
    configure_tracing()
    try:
        mcp.run(transport="stdio")
    finally:
        flush_traces()


if __name__ == "__main__":
    main()
