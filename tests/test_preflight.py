import copy

import pytest

from scripts import preflight


def tool_message():
    return {"tool_calls": [{"id": "independent-test-call", "type": "function", "function": {
        "name": "get_status", "arguments": '{"item_id":"DEMO-1"}'}}]}


def test_correct_tool_arguments_are_required():
    message = tool_message()
    assert preflight.valid_tool_call(message)["function"]["name"] == "get_status"
    message["tool_calls"][0]["function"]["arguments"] = '{"item_id":"DIFFERENT"}'
    with pytest.raises(preflight.CheckFailure, match="Wrong tool arguments"):
        preflight.valid_tool_call(message)


@pytest.mark.parametrize("value", [{}, {"content": "I would use a tool"}, {"tool_calls": []}])
def test_text_or_empty_output_is_not_a_tool_call(value):
    with pytest.raises(preflight.CheckFailure):
        preflight.valid_tool_call(value)


def test_wrong_tool_and_malformed_arguments_fail():
    message = tool_message()
    message["tool_calls"][0]["function"]["name"] = "unapproved_tool"
    with pytest.raises(preflight.CheckFailure, match="Wrong tool"):
        preflight.valid_tool_call(message)
    message = tool_message()
    message["tool_calls"][0]["function"]["arguments"] = "not json"
    with pytest.raises(preflight.CheckFailure, match="valid JSON"):
        preflight.valid_tool_call(message)


def test_multiple_calls_are_not_silently_accepted():
    message = tool_message()
    message["tool_calls"].append(copy.deepcopy(message["tool_calls"][0]))
    with pytest.raises(preflight.CheckFailure, match="exactly one"):
        preflight.valid_tool_call(message)


@pytest.mark.parametrize("url", ["https://example.com/v1", "http://localhost.example.com", "file:///local"])
def test_external_endpoint_rejected_before_kit_checks(url):
    with pytest.raises(preflight.CheckFailure):
        preflight.local_url(url)


def test_loopback_endpoint_allowed():
    assert preflight.local_url("http://127.0.0.1:11434/v1/") == "http://127.0.0.1:11434/v1"


def test_failure_exit_code_and_sensitive_exception_suppression(capsys):
    def failing_check():
        raise RuntimeError("private fixture detail that must stay local")
    assert preflight.run_checks([("first", failing_check), ("second", lambda: "ok")]) == 1
    output = capsys.readouterr().out
    assert "FAIL first: RuntimeError" in output
    assert "PASS second: ok" in output
    assert "private fixture" not in output


def test_all_successes_exit_zero():
    assert preflight.run_checks([("check", lambda: "ok")]) == 0


@pytest.mark.parametrize("answer", ['{"status":"not ready"}', 'already', 'not ready', '{}', '{"status":"ready","extra":true}'])
def test_contradictory_or_unstructured_final_answers_fail(answer):
    with pytest.raises(preflight.CheckFailure):
        preflight.valid_final_answer({"content": answer})


def test_exact_tool_result_is_preserved():
    preflight.valid_final_answer({"content": '{"status":"ready"}'})


def test_low_disk_space_blocks_readiness(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "disk_usage", lambda _: SimpleNamespace(free=19_000_000_000))
    with pytest.raises(preflight.CheckFailure, match="Free disk"):
        preflight.check_disk()
