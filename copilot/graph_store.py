"""Atomic provenance storage and parameterized Apache AGE graph access."""

import hashlib
import json
import uuid

from psycopg import sql


PREDICATES = frozenset({"HAS_THRESHOLD", "REQUIRES_ACTION", "CONTAINS", "INDICATES", "HAS_STEP"})


def _age(conn):
    conn.execute("LOAD 'age'")
    conn.execute("SET LOCAL search_path = ag_catalog, public")


def _cypher(conn, graph_name, query, parameters):
    # AGE accepts parameters only through a prepared statement's agtype argument.
    # The query is application-owned; document strings exist only in the value map.
    name = sql.Identifier("graph_" + uuid.uuid4().hex)
    conn.execute(sql.SQL("PREPARE {}(agtype) AS SELECT * FROM cypher({}, $$ {} $$, $1) AS (value agtype)").format(
        name, sql.Literal(graph_name), sql.SQL(query)))
    rows = conn.execute(sql.SQL("EXECUTE {}({}::agtype)").format(
        name, sql.Literal(json.dumps(parameters)))).fetchall()
    conn.execute(sql.SQL("DEALLOCATE {}").format(name))
    return [json.loads(row["value"]) for row in rows]


def store_extractions(conn, batches, *, graph_name="maintenance_kb"):
    """Replace each chunk's triples and AGE edges together; caller controls commit."""
    count = 0
    with conn.transaction():
        _age(conn)
        # Serialize graph initialization and replacements across extraction processes.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (graph_name,))
        if not conn.execute("SELECT 1 FROM ag_graph WHERE name = %s", (graph_name,)).fetchone():
            conn.execute("SELECT create_graph(%s)", (graph_name,))
        for batch in batches:
            _cypher(conn, graph_name,
                    "MATCH ()-[r]->() WHERE r.chunk_id = $chunk_id DELETE r RETURN count(*)",
                    {"chunk_id": batch["chunk_id"]})
            conn.execute("DELETE FROM knowledge_triples WHERE chunk_id = %s", (batch["chunk_id"],))
            seen = set()
            for triple in batch["triples"]:
                predicate = triple["predicate"]
                if predicate not in PREDICATES:
                    raise ValueError("Unsupported graph predicate")
                identity = [batch["chunk_id"], triple["subject"], predicate, triple["object"], triple["evidence"]]
                triple_id = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
                if triple_id in seen:
                    continue
                seen.add(triple_id)
                conn.execute("""INSERT INTO knowledge_triples
                    (id, subject, predicate, object, source, chunk_id, evidence, content_hash, model)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (triple_id, triple["subject"], predicate, triple["object"], batch["source"],
                     batch["chunk_id"], triple["evidence"], batch["content_hash"], batch["model"]))
                _cypher(conn, graph_name,
                        "MERGE (s:Entity {name: $subject}) MERGE (o:Entity {name: $object}) "
                        f"CREATE (s)-[r:{predicate} {{triple_id: $id, source: $source, "
                        "chunk_id: $chunk_id, evidence: $evidence}]->(o) RETURN r.triple_id",
                        {**triple, "id": triple_id, "source": batch["source"], "chunk_id": batch["chunk_id"]})
                count += 1
            conn.execute("""INSERT INTO graph_extractions (chunk_id, source, content_hash, model)
                VALUES (%s,%s,%s,%s) ON CONFLICT (chunk_id) DO UPDATE SET
                source=excluded.source, content_hash=excluded.content_hash, model=excluded.model,
                extracted_at=now()""", (batch["chunk_id"], batch["source"], batch["content_hash"], batch["model"]))
    return count


def query_graph(conn, question, *, graph_name="maintenance_kb"):
    """Return current, safe document evidence whose corresponding AGE edges exist."""
    rows = conn.execute("""SELECT t.id, t.subject, t.predicate, t.object, t.source,
        t.chunk_id, t.evidence, t.content_hash, t.model, 'local_model' AS extraction_method
        FROM knowledge_triples t JOIN document_chunks d ON d.id = t.chunk_id
        WHERE d.injection_risk_score = 0 AND d.source = t.source
        AND t.content_hash = encode(sha256(convert_to(d.content, 'UTF8')), 'hex')
        AND to_tsvector('english', t.subject || ' ' || t.predicate || ' ' || t.object)
            @@ plainto_tsquery('english', %s) ORDER BY t.id LIMIT 30""", (question,)).fetchall()
    if not rows:
        return []
    _age(conn)
    ids = set(_cypher(conn, graph_name,
                     "MATCH ()-[r]->() WHERE r.triple_id IN $ids RETURN r.triple_id",
                     {"ids": [row["id"] for row in rows]}))
    return [row for row in rows if row["id"] in ids]
