"""Local, transactional source ingestion. Source text is never an instruction."""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def injection_risk(text: str) -> float:
    patterns = (r"ignore.{0,40}(previous|instructions|rules)",
                r"(system|assistant)\s*:", r"(reveal|print|send).{0,40}(secret|password|credential)",
                r"(override|bypass).{0,30}(safety|policy|instructions)")
    return min(1.0, sum(bool(re.search(p, text, re.I | re.S)) for p in patterns) * 0.5)


def stable_id(*values: object) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def chunks(text: str, size: int = 1200, overlap: int = 200):
    if not 0 <= overlap < size:
        raise ValueError("Invalid chunk overlap")
    for start in range(0, len(text), size - overlap):
        chunk = text[start:start + size].strip()
        if chunk:
            yield chunk
        if start + size >= len(text):
            break


def sensor_rows(path: Path, source: str):
    numeric = {"landing_weight_lb", "ambient_c", "brake_pressure_psi", "taxi_in_min",
               "peak_brake_temp_c", "residual_temp_30min_c"}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not all(row.get(k) for k in ("tail_number", "flight_id", "wheel_pos", "landing_utc")):
                raise ValueError("Sensor identifier or timestamp missing")
            for key in numeric:
                if row.get(key) and not math.isfinite(float(row[key])):
                    raise ValueError("Nonfinite sensor measurement")
            key = stable_id(source, *(row[k] for k in ("flight_id", "tail_number", "wheel_pos", "landing_utc")))
            yield key, row["tail_number"], timestamp(row["landing_utc"]), row


def maintenance_rows(path: Path, source: str):
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not all(isinstance(row.get(k), str) and row[k] for k in ("log_id", "tail_number", "date")):
                raise ValueError("Maintenance identifier or timestamp invalid")
            yield stable_id(source, row["log_id"]), row["tail_number"], timestamp(row["date"]), row


def sqlite_records(path: Path):
    def quote(name):
        return '"' + name.replace('"', '""') + '"'

    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        names = [r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for name in names:
            primary = [r[1] for r in sorted(connection.execute(f"PRAGMA table_info({quote(name)})"), key=lambda r: r[5]) if r[5]]
            duplicates = {}
            for row in connection.execute(f"SELECT * FROM {quote(name)}"):
                payload = {k: ({"base64": base64.b64encode(v).decode()} if isinstance(v, bytes) else v)
                           for k, v in dict(row).items()}
                # Full payload identity plus duplicate ordinal preserves no-PK tables losslessly.
                identity = stable_id(*[payload[k] for k in primary]) if primary else stable_id(payload)
                duplicates[identity] = duplicates.get(identity, 0) + 1
                yield name, f"{identity}:{duplicates[identity]}", payload


def ingest(kit_dir: Path | None = None) -> dict:
    from psycopg.types.json import Jsonb
    from sentence_transformers import SentenceTransformer
    from copilot.config import get_settings
    from copilot.db import connect, migrate

    settings = get_settings()
    root = Path(kit_dir or settings.kit_dir).resolve() / "data"
    sensors = sorted(root.rglob("*.csv"))
    logs = sorted(root.rglob("*.jsonl"))
    databases = sorted(root.rglob("*.db"))
    manuals = sorted((root / "manuals").rglob("*.md"))
    if not all((sensors, logs, databases, manuals)):
        raise ValueError("Required local source group missing")
    model = SentenceTransformer(settings.embedding_model, device="cpu", local_files_only=True)
    counts = {"sensor_readings": 0, "maintenance_logs": 0, "source_records": 0, "document_chunks": 0}
    with connect() as connection:
        migrate(connection)
        def record(source, count):
            connection.execute("INSERT INTO ingestion_log(source,record_count) VALUES (%s,%s) "
                               "ON CONFLICT(source) DO UPDATE SET record_count=excluded.record_count,ingested_at=now()", (source, count))

        for path in sensors:
            source = path.relative_to(root).as_posix()
            connection.execute("DELETE FROM sensor_readings WHERE source=%s", (source,))
            count = 0
            for key, tail, at, payload in sensor_rows(path, source):
                connection.execute("INSERT INTO sensor_readings(id,tail_number,observed_at,payload,source) VALUES (%s,%s,%s,%s,%s)",
                                   (key, tail, at, Jsonb(payload), source))
                count += 1
            counts["sensor_readings"] += count
            record(source, count)
        for path in logs:
            source = path.relative_to(root).as_posix()
            connection.execute("DELETE FROM maintenance_logs WHERE source=%s", (source,))
            count = 0
            for key, tail, at, payload in maintenance_rows(path, source):
                risk = injection_risk(json.dumps(payload))
                connection.execute("INSERT INTO maintenance_logs(id,tail_number,occurred_at,payload,injection_risk_score,source) VALUES (%s,%s,%s,%s,%s,%s)",
                                   (key, tail, at, Jsonb(payload), risk, source))
                count += 1
            counts["maintenance_logs"] += count
            record(source, count)
        for path in databases:
            source = path.relative_to(root).as_posix()
            # Clear this database's previous snapshot, including now-empty/removed tables.
            connection.execute("DELETE FROM source_records WHERE starts_with(source,%s)", (source + ":",))
            connection.execute("DELETE FROM ingestion_log WHERE starts_with(source,%s)", (source + ":",))
            per_table = {}
            for table, key, payload in sqlite_records(path):
                table_source = f"{source}:{table}"
                if table_source not in per_table:
                    connection.execute("DELETE FROM source_records WHERE source=%s", (table_source,))
                    per_table[table_source] = 0
                connection.execute("INSERT INTO source_records(source,record_key,payload) VALUES (%s,%s,%s)", (table_source, key, Jsonb(payload)))
                per_table[table_source] += 1
            for name, count in per_table.items():
                record(name, count)
                counts["source_records"] += count
        for path in manuals:
            source = path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8-sig")
            pieces = list(chunks(text))
            vectors = model.encode(pieces, normalize_embeddings=True, show_progress_bar=False) if pieces else []
            connection.execute("DELETE FROM document_chunks WHERE source=%s", (source,))
            for index, (piece, vector) in enumerate(zip(pieces, vectors)):
                values = vector.tolist()
                if len(values) != 384 or not all(math.isfinite(v) for v in values):
                    raise ValueError("Invalid embedding dimensions or values")
                connection.execute("INSERT INTO document_chunks(id,content,embedding,source,chunk_index,injection_risk_score) "
                                   "VALUES (%s,%s,%s::vector,%s,%s,%s)",
                                   (stable_id(source, index), piece, json.dumps(values), source, index, injection_risk(text)))
            record(source, len(pieces))
            counts["document_chunks"] += len(pieces)
    return counts


if __name__ == "__main__":
    try:
        print(json.dumps(ingest()))
    except Exception as error:
        # Provider exceptions may contain source text; keep console failures safe.
        raise SystemExit(f"Ingestion failed ({type(error).__name__})") from None
