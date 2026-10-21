from html.parser import HTMLParser

from copilot.visualization import render_graph


def test_graph_embeds_assets_and_escapes_untrusted_source_text(tmp_path):
    hostile = '</script><script src="https://example.invalid/steal.js"></script>'
    rows = [{"id": "edge-1", "subject": "Assembly A", "predicate": "CONTAINS",
             "object": hostile, "source": "synthetic.md", "chunk_id": "chunk-1",
             "evidence": hostile, "model": "test"}]
    output = tmp_path / "graph.html"
    result = render_graph(rows, output)
    assert result["nodes"] == 2 and result["relationships"] == 1
    page = output.read_text(encoding="utf-8")
    assert hostile not in page
    assert "connect-src 'none'" in page
    assert "\\u003c/script\\u003e" in page

    class Resources(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "script":
                assert not attrs.get("src")
            if tag == "link":
                assert not attrs.get("href")
    Resources().feed(page)
