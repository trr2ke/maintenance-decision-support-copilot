CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sensor_readings (
    id text PRIMARY KEY,
    tail_number text,
    observed_at timestamptz,
    payload jsonb NOT NULL,
    source text NOT NULL
);
CREATE INDEX IF NOT EXISTS sensor_tail_time ON sensor_readings (tail_number, observed_at DESC);

CREATE TABLE IF NOT EXISTS maintenance_logs (
    id text PRIMARY KEY,
    tail_number text,
    occurred_at timestamptz,
    payload jsonb NOT NULL,
    injection_risk_score real NOT NULL DEFAULT 0 CHECK (injection_risk_score BETWEEN 0 AND 1),
    source text NOT NULL
);
CREATE INDEX IF NOT EXISTS maintenance_tail_time ON maintenance_logs (tail_number, occurred_at DESC);

CREATE TABLE IF NOT EXISTS source_records (
    source text NOT NULL,
    record_key text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (source, record_key)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id text PRIMARY KEY,
    content text NOT NULL,
    embedding vector(384),
    source text NOT NULL,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    injection_risk_score real NOT NULL DEFAULT 0 CHECK (injection_risk_score BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS knowledge_triples (
    id text PRIMARY KEY,
    subject text NOT NULL,
    predicate text NOT NULL,
    object text NOT NULL,
    source text NOT NULL
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    source text PRIMARY KEY,
    record_count integer NOT NULL CHECK (record_count >= 0),
    ingested_at timestamptz NOT NULL DEFAULT now()
);
