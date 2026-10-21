import httpx

from copilot import parts


def install_transport(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(parts.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))


def test_inventory_keeps_reservations_and_lots(monkeypatch):
    def handler(request):
        if request.url.path.startswith("/inventory"):
            return httpx.Response(200, json=[{"depot_id": "D1", "qty_on_hand": 3, "qty_reserved": 3, "lot_number": "L1"}, {"depot_id": "D2", "qty_on_hand": 4}])
        return httpx.Response(200, json={"part_number": "P1"} if request.url.path.startswith("/parts") else [])
    install_transport(monkeypatch, handler)
    result = parts.query_parts("P1", "D1")
    assert result.status == "ok"
    assert result.data[1]["records"] == [{"depot_id": "D1", "qty_on_hand": 3, "qty_reserved": 3, "lot_number": "L1", "available_quantity": 0}]
    assert len(result.citations) == 3


def test_outage_is_unknown_not_empty(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(503))
    result = parts.query_parts("P1")
    assert result.status == "unavailable"
    assert "unknown" in result.error


def test_empty_depot_inventory_not_manufactured_zero(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(200, json=[]))
    result = parts.query_parts("P1", "missing")
    assert result.status == "empty"
    assert all(row["records"] == [] for row in result.data)
