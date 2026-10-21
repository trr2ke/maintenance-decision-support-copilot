"""Synthetic graph fixtures; no supplied documents or external services."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from copilot import graph_store


def batch():
    return {"chunk_id": "fixture-1", "source": "synthetic", "content_hash": "abc",
            "model": "fixture-model", "triples": [{"subject": "valve", "predicate": "CONTAINS",
            "object": "seal", "evidence": "The valve contains a seal."}]}


def connection():
    conn = Mock()
    conn.transaction.return_value = nullcontext()
    conn.execute.return_value.fetchone.return_value = {"exists": 1}
    return conn


def test_duplicate_extractions_are_stored_once(monkeypatch):
    conn = connection()
    cypher = Mock(return_value=[])
    monkeypatch.setattr(graph_store, "_cypher", cypher)
    value = batch()
    value["triples"] *= 2
    assert graph_store.store_extractions(conn, [value]) == 1
    assert cypher.call_count == 2  # Delete prior edges, then create one edge.


def test_document_text_is_a_parameter_not_cypher(monkeypatch):
    conn = connection()
    cypher = Mock(return_value=[])
    monkeypatch.setattr(graph_store, "_cypher", cypher)
    value = batch()
    attack = "seal'}) DELETE n // $$"
    value["triples"][0]["object"] = attack
    graph_store.store_extractions(conn, [value])
    args = cypher.call_args.args
    assert attack not in args[2]
    assert args[3]["object"] == attack


def test_relationship_type_is_allowlisted(monkeypatch):
    monkeypatch.setattr(graph_store, "_cypher", Mock(return_value=[]))
    value = batch()
    value["triples"][0]["predicate"] = "CONTAINS] DELETE n //"
    with pytest.raises(ValueError, match="Unsupported"):
        graph_store.store_extractions(connection(), [value])


def test_empty_success_replaces_prior_data_and_records_checkpoint(monkeypatch):
    conn = connection()
    cypher = Mock(return_value=[])
    monkeypatch.setattr(graph_store, "_cypher", cypher)
    value = batch()
    value["triples"] = []
    assert graph_store.store_extractions(conn, [value]) == 0
    assert "DELETE r" in cypher.call_args.args[2]
    statements = [call.args[0] for call in conn.execute.call_args_list]
    assert any("DELETE FROM knowledge_triples" in statement for statement in statements)
    assert any("INSERT INTO graph_extractions" in statement for statement in statements)


def test_retrieval_requires_actual_age_edge(monkeypatch):
    conn = connection()
    conn.execute.return_value.fetchall.return_value = [{"id": "present"}, {"id": "missing"}]
    monkeypatch.setattr(graph_store, "_cypher", Mock(return_value=["present"]))
    assert graph_store.query_graph(conn, "seal") == [{"id": "present"}]
    selection = conn.execute.call_args_list[0].args[0]
    assert "d.injection_risk_score = 0" in selection
    assert "sha256" in selection
