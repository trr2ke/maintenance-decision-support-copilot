import pytest

from copilot.extraction import validate_triples, source_passages, resolve_evidence

TEXT = "If pressure exceeds 17 kPa, inspect valve B. Assembly Z contains valve B."


def triple(**changes):
    return {"subject": "Assembly Z", "predicate": "CONTAINS", "object": "valve B",
            "evidence": "Assembly Z contains valve B.", **changes}


def test_exact_source_grounding_and_deduplication():
    result, rejected = validate_triples({"triples": [triple(), triple()]}, TEXT)
    assert result == [triple()]
    assert rejected == 0


@pytest.mark.parametrize("changes", [
    {"object": "valve C"}, {"evidence": "Assembly Z contains valve C."},
    {"predicate": "DELETE"}, {"subject": ""}, {"object": 17},
    {"evidence": "If pressure exceeds 170 kPa, inspect valve B."},
])
def test_ungrounded_or_invalid_relationships_are_rejected(changes):
    result, rejected = validate_triples({"triples": [triple(**changes)]}, TEXT)
    assert result == []
    assert rejected == 1


def test_quote_whitespace_can_be_normalized_without_changing_words():
    result, _ = validate_triples({"triples": [triple(evidence="Assembly Z\ncontains valve B.")]}, TEXT)
    assert len(result) == 1


def test_malformed_envelope_fails_instead_of_caching_empty_success():
    with pytest.raises(ValueError):
        validate_triples({"triples": "none"}, TEXT)


def test_case_sensitive_units_cannot_be_changed():
    item = triple(subject="current", predicate="HAS_THRESHOLD", object="17 MA", evidence="current exceeds 17 MA")
    assert validate_triples({"triples": [item]}, "current exceeds 17 mA") == ([], 1)


def test_passage_references_attach_the_original_text():
    passages = source_passages(TEXT)
    payload = {"triples": [{"subject": "Assembly Z", "predicate": "CONTAINS", "object": "valve B", "evidence_id": 0}]}
    accepted, rejected = validate_triples(resolve_evidence(payload, passages), TEXT)
    assert accepted[0]["evidence"] == TEXT
    assert rejected == 0


@pytest.mark.parametrize("reference", [-1, 99, True, "0"])
def test_invalid_passage_references_are_rejected(reference):
    payload = {"triples": [{"subject": "Assembly Z", "predicate": "CONTAINS", "object": "valve B", "evidence_id": reference}]}
    assert validate_triples(resolve_evidence(payload, [TEXT]), TEXT) == ([], 1)
