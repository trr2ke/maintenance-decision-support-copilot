ALTER TABLE knowledge_triples ADD COLUMN IF NOT EXISTS chunk_id text;
ALTER TABLE knowledge_triples ADD COLUMN IF NOT EXISTS evidence text;
ALTER TABLE knowledge_triples ADD COLUMN IF NOT EXISTS content_hash text;
ALTER TABLE knowledge_triples ADD COLUMN IF NOT EXISTS model text;
CREATE INDEX IF NOT EXISTS triples_chunk ON knowledge_triples (chunk_id);

CREATE TABLE IF NOT EXISTS graph_extractions (
    chunk_id text PRIMARY KEY,
    source text NOT NULL,
    content_hash text NOT NULL,
    model text NOT NULL,
    extracted_at timestamptz NOT NULL DEFAULT now()
);
