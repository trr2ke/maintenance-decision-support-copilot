import pytest

from copilot.config import Settings, local_endpoint
from copilot.contracts import ToolResult


@pytest.mark.parametrize("endpoint", ["https://example.com", "http://127.0.0.1.example.com", "file:///tmp/x", "http://user:secret@localhost", "http://localhost?redirect=1"])
def test_external_or_ambiguous_http_endpoints_are_rejected(endpoint):
    with pytest.raises(ValueError):
        local_endpoint(endpoint)


def test_defaults_are_local_and_timeout_bounded():
    assert Settings().llm_model == "maintenance-gemma4:12b"
    with pytest.raises(ValueError):
        Settings(llm_timeout_seconds=0)


def test_unavailable_is_not_empty_inventory():
    result = ToolResult(status="unavailable", error="Parts service unavailable")
    assert result.status != "empty"
    assert result.data == []
