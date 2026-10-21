"""Export current AGE relationships as a standalone, offline PyVis page."""
import hashlib
from html import escape
import json
from pathlib import Path
import textwrap

from jinja2 import ChoiceLoader, FileSystemLoader
from pyvis.network import Network

from copilot.db import read_connection
from copilot.graph_store import _age, _cypher

COLORS = {"HAS_THRESHOLD": "#fbbf24", "REQUIRES_ACTION": "#fb7185",
          "CONTAINS": "#38bdf8", "INDICATES": "#c084fc", "HAS_STEP": "#34d399"}


def load_graph():
    with read_connection() as connection:
        rows = connection.execute("""SELECT t.id, t.subject, t.predicate, t.object,
            t.source, t.chunk_id, t.evidence, t.model FROM knowledge_triples t
            JOIN document_chunks d ON d.id=t.chunk_id
            WHERE d.injection_risk_score=0 AND d.source=t.source
            AND t.content_hash=encode(sha256(convert_to(d.content,'UTF8')),'hex')
            ORDER BY t.predicate,t.id""").fetchall()
        if not rows:
            return []
        _age(connection)
        ids = set(_cypher(connection, "maintenance_kb",
                         "MATCH ()-[r]->() RETURN r.triple_id", {}))
        return [row for row in rows if row["id"] in ids]


def render_graph(rows, output):
    graph = Network(height="100%", width="100%", directed=True,
                    bgcolor="#0b1220", font_color="#e2e8f0", cdn_resources="in_line")
    names = sorted({row[key] for row in rows for key in ("subject", "object")})
    identifiers = {name: hashlib.sha256(name.encode()).hexdigest() for name in names}
    for name in names:
        graph.add_node(identifiers[name], label=textwrap.fill(name, width=28),
                       name=name, title=escape(name), shape="box", margin=12,
                       color={"background": "#17263c", "border": "#526e94",
                              "highlight": {"background": "#164e63", "border": "#67e8f9"}})
    for row in rows:
        graph.add_edge(identifiers[row["subject"]], identifiers[row["object"]],
                       id=row["id"], label=row["predicate"].replace("_", " ").lower(),
                       predicate=row["predicate"], color=COLORS.get(row["predicate"], "#94a3b8"),
                       title=escape(row["predicate"] + "\n" + row["source"] + "\n" + row["evidence"]),
                       document_source=row["source"], chunk_id=row["chunk_id"], evidence=row["evidence"],
                       model=row["model"], subject=row["subject"], object=row["object"])
    graph.set_options(json.dumps({
        "interaction": {"hover": True, "navigationButtons": True, "keyboard": True},
        "nodes": {"font": {"size": 13, "face": "Arial", "color": "#e2e8f0"}},
        "edges": {"arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
                  "font": {"size": 10, "color": "#b8c8dd", "strokeWidth": 0, "align": "middle"},
                  "smooth": {"type": "dynamic"}},
        "physics": {"solver": "forceAtlas2Based", "forceAtlas2Based": {
            "gravitationalConstant": -70, "springLength": 170, "avoidOverlap": 0.7},
            "stabilization": {"iterations": 250}},
    }))
    graph.templateEnv.loader = ChoiceLoader([
        FileSystemLoader(Path(__file__).parent / "templates"), graph.templateEnv.loader])
    graph.path = "graph.html"
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(graph.generate_html(), encoding="utf-8")
    return {"status": "ok", "nodes": len(names), "relationships": len(rows), "output": str(output)}


def visualize(output="artifacts/maintenance-graph.html"):
    return render_graph(load_graph(), output)
