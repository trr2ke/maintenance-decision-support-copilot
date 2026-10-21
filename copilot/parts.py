"""Read-only parts evidence; an outage never becomes zero inventory."""
from urllib.parse import quote

import httpx

from copilot.config import get_settings
from copilot.contracts import ToolResult


def query_parts(part_number: str | None = None, depot_id: str | None = None) -> ToolResult:
    """Look up part metadata, inventory and supply, or list depots without a part number."""
    base = get_settings().parts_api_url
    routes = ["depots"] if not part_number else [
        f"{kind}/{quote(part_number, safe='')}" for kind in ("parts", "inventory", "supply")
    ]
    evidence, citations = [], []
    try:
        with httpx.Client(timeout=3.0, trust_env=False, follow_redirects=False) as client:
            for route in routes:
                response = client.get(f"{base}/{route}")
                if response.status_code == 404:
                    return ToolResult(status="empty", error="Part was not found; stock is unknown.")
                response.raise_for_status()
                payload = response.json()
                rows = payload if isinstance(payload, list) else [payload]
                if not all(isinstance(row, dict) for row in rows):
                    raise ValueError("Invalid parts response")
                kind = route.split("/")[0]
                if depot_id is not None and kind in {"inventory", "depots"}:
                    rows = [row for row in rows if str(row.get("depot_id")) == depot_id]
                evidence.append({"resource": kind, "records": rows})
                citations.append({"source": "parts_api", "uri": f"{base}/{route}", "depot_id": depot_id})
    except (httpx.HTTPError, ValueError) as exc:
        return ToolResult(status="unavailable", data=evidence, citations=citations,
                          error=f"Parts service unavailable ({type(exc).__name__}); stock is unknown.")
    return ToolResult(status="ok" if any(item["records"] for item in evidence) else "empty",
                      data=evidence, citations=citations)
