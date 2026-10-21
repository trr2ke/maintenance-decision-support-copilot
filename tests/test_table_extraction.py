import pytest

from copilot.extraction import validate_triples
from copilot.table_extraction import extract_table_triples


TABLE = """| Protrusion (mm) | Status |
| --- | --- |
| < -0.25 mm | Inspect before release |
| -0.25 to 1.75 mm inclusive | Acceptable only when unloaded |
| > 1.75 mm | Replace immediately |
"""


def test_every_threshold_and_status_is_preserved_exactly():
    triples = extract_table_triples(TABLE)
    mappings = [(item["subject"], item["object"]) for item in triples
                if item["predicate"] == "INDICATES"]
    assert mappings == [
        ("< -0.25 mm", "Inspect before release"),
        ("-0.25 to 1.75 mm inclusive", "Acceptable only when unloaded"),
        ("> 1.75 mm", "Replace immediately"),
    ]
    thresholds = [item for item in triples if item["predicate"] == "HAS_THRESHOLD"]
    assert [item["object"] for item in thresholds] == [pair[0] for pair in mappings]
    assert all(item["subject"] == "Protrusion (mm)" for item in thresholds)
    assert validate_triples({"triples": triples}, TABLE) == (triples, 0)


def test_markdown_formatting_alignment_and_escaped_pipes_are_verbatim():
    source = "**Status** | `Gap`\n:--- | ---:\n**Hold** \\| inspect | **<= 0.125 in**\n"
    triples = extract_table_triples(source)
    assert triples[0]["subject"] == "**<= 0.125 in**"
    assert triples[0]["object"] == "**Hold** \\| inspect"
    assert triples[1]["subject"] == "`Gap`"
    assert validate_triples({"triples": triples}, source) == (triples, 0)


def test_does_not_guess_headers_for_split_table_fragments():
    head, tail = TABLE.split("| -0.25 to", 1)
    assert len(extract_table_triples(head)) == 2
    assert extract_table_triples("| -0.25 to" + tail) == []
    assert len(extract_table_triples(head + "| -0.25 to" + tail)) == 6


@pytest.mark.parametrize("source", [
    "| Item | Status |\n| --- | --- |\n| Valve | Open |",
    "| Gap | Result |\n| --- | --- |\n| < 2 mm | Hold |",
    "| Gap | Status |\n| invalid | --- |\n| < 2 mm | Hold |",
    "| Gap | Status |\n| --- | --- |\n| < 2 mm | |",
    "| Gap | Status |\n| --- | --- |\n| < 2 mm | Hold | extra |",
])
def test_unrelated_or_malformed_tables_are_not_interpreted(source):
    assert extract_table_triples(source) == []


def test_long_tables_keep_every_status_without_fabricated_header_quotations():
    source = "| Gap | Status |\n| --- | --- |\n" + "".join(
        f"| = {number}.01 mm | Inspect the fitting before release |\n" for number in range(15))
    triples = extract_table_triples(source)
    assert len([item for item in triples if item["predicate"] == "INDICATES"]) == 15
    assert all(item["evidence"] in source for item in triples)
    assert all(len(item["evidence"]) <= 500 for item in triples)
    for item in triples:
        assert validate_triples({"triples": [item]}, source) == ([item], 0)


def test_separate_tables_do_not_leak_headers():
    source = TABLE + "\n| Clearance | Status |\n| --- | --- |\n| >= 8 mm | Stop |\n"
    thresholds = [item for item in extract_table_triples(source)
                  if item["predicate"] == "HAS_THRESHOLD"]
    assert thresholds[-1]["subject"] == "Clearance"
    assert thresholds[-1]["object"] == ">= 8 mm"
