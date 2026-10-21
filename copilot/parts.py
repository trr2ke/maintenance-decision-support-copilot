"""Read-only parts evidence; an outage never becomes zero inventory."""
from urllib.parse import quote
import math

import httpx

from copilot.config import get_settings
from copilot.contracts import ToolResult


def available_inventory(row: dict) -> dict:
    """Keep missing reservation counts distinct from confirmed available stock."""
    on_hand, reserved = row.get("qty_on_hand"), row.get("qty_reserved")
    valid = all(isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and value >= 0 for value in (on_hand, reserved))
    if not valid:
        return {**row, "available_quantity": None,
                "availability_note": "Available quantity unknown: missing or invalid stock/reservation count."}
    result = {**row, "available_quantity": max(0, on_hand - reserved)}
    if reserved > on_hand:
        result["availability_note"] = "Reservations exceed recorded on-hand stock; verify the discrepancy."
    return result


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
                if kind == "inventory":
                    rows = [available_inventory(row) for row in rows]
                if depot_id is not None and kind in {"inventory", "depots"}:
                    rows = [row for row in rows if str(row.get("depot_id")) == depot_id]
                evidence.append({"resource": kind, "records": rows})
                citations.append({"source": "parts_api", "uri": f"{base}/{route}", "depot_id": depot_id})
    except (httpx.HTTPError, ValueError) as exc:
        return ToolResult(status="unavailable", data=evidence, citations=citations,
                          error=f"Parts service unavailable ({type(exc).__name__}); stock is unknown.")
    return ToolResult(status="ok" if any(item["records"] for item in evidence) else "empty",
                      data=evidence, citations=citations)
