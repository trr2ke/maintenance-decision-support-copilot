import pytest

from copilot.parts import available_inventory


@pytest.mark.parametrize("on_hand,reserved,available", [(3, 3, 0), (5, 2, 3), (0, 1, 0)])
def test_reserved_stock_is_not_available(on_hand, reserved, available):
    result = available_inventory({"qty_on_hand": on_hand, "qty_reserved": reserved, "lot_number": "independent-lot"})
    assert result["available_quantity"] == available
    assert result["qty_reserved"] == reserved
    assert result["lot_number"] == "independent-lot"
    if reserved > on_hand:
        assert "discrepancy" in result["availability_note"]


@pytest.mark.parametrize("reserved", [None, float("nan"), -1, True, "2"])
def test_invalid_reservations_leave_availability_unknown(reserved):
    result = available_inventory({"qty_on_hand": 5, "qty_reserved": reserved})
    assert result["available_quantity"] is None
    assert "unknown" in result["availability_note"]
