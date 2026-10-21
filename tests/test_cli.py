import json
import sys
from contextlib import contextmanager
from types import SimpleNamespace

from copilot.__main__ import main


def test_cli_emits_safe_errors_without_source_or_credentials(monkeypatch, capsys):
    def fail():
        raise RuntimeError("password=private-source")
    monkeypatch.setitem(sys.modules, "copilot.db", SimpleNamespace(migrate=fail))
    assert main(["migrate"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.err) == {"status": "error", "error": "RuntimeError"}
    assert "private" not in captured.out + captured.err


def test_partial_answer_remains_visible_and_returns_failure(monkeypatch, capsys):
    @contextmanager
    def operation(name):
        yield SimpleNamespace(set_attribute=lambda *args: None)
    monkeypatch.setitem(sys.modules, "copilot.telemetry", SimpleNamespace(trace_operation=operation, flush_traces=lambda: None))
    monkeypatch.setitem(sys.modules, "copilot.agent", SimpleNamespace(run_query=lambda q: {
        "status": "partial", "answer": "Stock is unknown.", "citations": []}))
    assert main(["ask", "Check stock"]) == 1
    assert json.loads(capsys.readouterr().out)["answer"] == "Stock is unknown."
