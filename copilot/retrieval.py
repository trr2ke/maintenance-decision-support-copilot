"""Bounded, read-only evidence tools. Questions are never executed as SQL."""

from functools import lru_cache
import re

from copilot.config import get_settings
from copilot.contracts import ToolResult
from copilot.db import read_connection


def _unavailable():
    return ToolResult(status="unavailable", data=[], citations=[], error="Local evidence database is unavailable.")


def _citation(row, kind):
    return {"source": row["source"], "record_id": row.get("id", row.get("record_key")), "kind": kind}


def query_fleet_data(question: str, tail_number: str | None = None) -> ToolResult:
    """Return fleet summaries and recent evidence, anchored to the latest dataset timestamp."""
    if not question.strip() or len(question) > 4000:
        return ToolResult(status="error", data=[], citations=[], error="Provide a question of 1–4000 characters.")
    if tail_number is not None and (not tail_number.strip() or len(tail_number) > 64):
        return ToolResult(status="error", data=[], citations=[], error="Invalid tail number.")
    days_match = re.search(r"(?:last|past)\s+(\d{1,4})\s+days?", question, re.I)
    days = int(days_match.group(1)) if days_match else (7 if re.search(r"(?:last|past) week", question, re.I) else None)
    tail = tail_number.strip().upper() if tail_number else None
    try:
        with read_connection() as conn:
            anchor = conn.execute("""
                SELECT greatest((SELECT max(observed_at) FROM sensor_readings),
                    (SELECT max(occurred_at) FROM maintenance_logs)) AS anchor
            """).fetchone()["anchor"]
            filters = "(%s::text IS NULL OR upper(tail_number) = %s) AND (%s::int IS NULL OR observed_at >= %s::timestamptz - %s * interval '1 day')"
            params = (tail, tail, days, anchor, days)
            summary = conn.execute("""
                SELECT tail_number, payload->>'wheel_pos' AS wheel_position,
                    count(*) AS reading_count, min(observed_at) AS first_observed_at,
                    max(observed_at) AS last_observed_at,
                    avg(CASE WHEN payload->>'peak_brake_temp_c' ~ '^-?[0-9]+(\\.[0-9]+)?$'
                        THEN (payload->>'peak_brake_temp_c')::double precision END) AS mean_peak_brake_temp_c,
                    max(CASE WHEN payload->>'peak_brake_temp_c' ~ '^-?[0-9]+(\\.[0-9]+)?$'
                        THEN (payload->>'peak_brake_temp_c')::double precision END) AS max_peak_brake_temp_c
                FROM sensor_readings WHERE """ + filters + " GROUP BY tail_number, payload->>'wheel_pos' ORDER BY tail_number, wheel_position LIMIT 100", params).fetchall()
            sensors = conn.execute("SELECT id, tail_number, observed_at, payload, source FROM sensor_readings WHERE " + filters + " ORDER BY observed_at DESC NULLS LAST, id LIMIT 50", params).fetchall()
            logs = conn.execute("SELECT id, tail_number, occurred_at, payload, source FROM maintenance_logs WHERE " + filters.replace("observed_at", "occurred_at") + " AND injection_risk_score = 0 ORDER BY occurred_at DESC NULLS LAST, id LIMIT 30", params).fetchall()
            records = conn.execute("""
                SELECT source, record_key, payload FROM source_records
                WHERE to_tsvector('english', payload::text) @@ plainto_tsquery('english', %s)
                OR (%s::text IS NOT NULL AND upper(payload->>'tail_number') = %s)
                ORDER BY source, record_key LIMIT 30
            """, (question, tail, tail)).fetchall()
        data = []
        if summary:
            data.append({"kind": "sensor_summary", "groups": summary,
                         "scope": {"tail_number": tail, "days": days, "anchor": anchor},
                         "source": "sensor_readings", "group_limit": 100})
        data.extend({"kind": "sensor_reading", **row} for row in sensors)
        data.extend({"kind": "maintenance_log", **row} for row in logs)
        data.extend({"kind": "source_record", **row} for row in records)
        citations = [_citation(row, kind) for kind, rows in
                     (("sensor_reading", sensors), ("maintenance_log", logs), ("source_record", records)) for row in rows]
        return ToolResult(status="ok" if data else "empty", data=data, citations=citations,
                          source_time=anchor.isoformat() if anchor else None)
    except Exception:
        return _unavailable()


@lru_cache(maxsize=1)
def _embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(get_settings().embedding_model, device="cpu", local_files_only=True)


def search_documents(query: str, limit: int = 5) -> ToolResult:
    """Search trusted chunks using cached CPU embeddings, with lexical fallback."""
    if not query.strip() or len(query) > 4000 or not 1 <= limit <= 10:
        return ToolResult(status="error", data=[], citations=[], error="Query must be 1–4000 characters and limit 1–10.")
    try:
        embedding = _embedding_model().encode(query, normalize_embeddings=True).tolist()
        vector = "[" + ",".join(str(float(value)) for value in embedding) + "]"
    except Exception:
        vector = None
    try:
        with read_connection() as conn:
            rows = conn.execute("""
                SELECT id, content, source, chunk_index,
                    ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', %s)) AS lexical_score,
                    CASE WHEN %s::vector IS NOT NULL AND embedding IS NOT NULL
                         THEN 1 - (embedding <=> %s::vector) ELSE 0 END AS semantic_score
                FROM document_chunks
                WHERE injection_risk_score = 0
                AND (to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                     OR (%s::vector IS NOT NULL AND 1 - (embedding <=> %s::vector) >= 0.25))
                ORDER BY lexical_score DESC, semantic_score DESC, id LIMIT %s
            """, (query, vector, vector, query, vector, vector, limit)).fetchall()
        return ToolResult(status="ok" if rows else "empty", data=rows,
                          citations=[{**_citation(row, "document"), "chunk_index": row["chunk_index"]} for row in rows],
                          error="Semantic embeddings unavailable; lexical search used." if vector is None else None)
    except Exception:
        return _unavailable()


def query_knowledge_graph(question: str) -> ToolResult:
    """Search provenance-backed triples; no generated Cypher or graph inference."""
    if not question.strip() or len(question) > 4000:
        return ToolResult(status="error", data=[], citations=[], error="Provide a question of 1–4000 characters.")
    try:
        with read_connection() as conn:
            rows = conn.execute("""
                SELECT id, subject, predicate, object, source FROM knowledge_triples
                WHERE to_tsvector('english', subject || ' ' || predicate || ' ' || object)
                    @@ plainto_tsquery('english', %s)
                ORDER BY id LIMIT 30
            """, (question,)).fetchall()
        return ToolResult(status="ok" if rows else "empty", data=rows,
                          citations=[_citation(row, "triple") for row in rows])
    except Exception:
        return _unavailable()
