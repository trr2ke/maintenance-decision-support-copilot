# Shared implementation contracts

This agreement defines future implementation; it does not claim handlers exist. Freeze it before workers branch. The coordinator owns changes, and adapters/tests change together. All published fixtures are independently authored.

## Configuration and requests

`KIT_DIR` is only for local ingestion/preflight. Serving tools use the database and configured local services rather than arbitrary file paths. Configure endpoints, model identity, embedding dimension and deadlines through root `.env.example`; keep credentials out of results.

Each request receives a UUID `request_id`, propagated through tools and spans. `POST /api/query` accepts bounded nonempty `question` and optional ISO8601 `as_of`. It returns `request_id`, `status`, `answer`, `citations`, `warnings`, `analysis_window` and `elapsed_ms`. Explicit intervals take priority; otherwise resolve a recent interval against the latest relevant dataset observation. Return that UTC interval and any source-timezone assumptions.

## One registry, four read-only tools

Define typed input/result models and derive MCP and agent schemas from one registry. Wrappers contain no separate business logic. Reject unknown fields, invalid enum values and out-of-bound values. Default to a 30-second per-tool deadline with at most two retries for transient HTTP failures, all within that deadline. Model/request deadlines come from measured readiness results. Bound each agent request to eight tool calls and report exhaustion.

| Tool | Inputs | Result data |
|---|---|---|
| `query_fleet_data` | `operation`: `sensor_summary`, `maintenance_history`, `installed_components`; text `tail_number`; optional UTC start/end and wheel; `limit` 1-100 | Typed records, applied interval, aggregation method and units. |
| `search_documents` | Bounded `query`; optional `part_number`; `limit` 1-10 | Chunk IDs, bounded excerpts, scores, locators, applicability and risk flags. |
| `get_parts_availability` | Text `part_number`; optional `depot_id`; positive integer `quantity_required` | Available/reserved stock, observation time, transfers, supplier lead time and availability state. |
| `query_knowledge_graph` | `operation`: `thresholds`, `actions`, `components`, `symptoms`, `procedures`; bounded `subject`; optional `part_number`; `limit` 1-20 | Validated facts, units/conditions, citations and backend (`age` or `relational`). |

Preserve legitimate identifier punctuation such as hyphens. Do not silently round identifiers or impose an invented tail-number range. Use explicit source rules and parameterized queries. Neither model questions nor retrieved documents become SQL, Cypher or tool names. Graph queries use fixed templates and validated bindings. Tools expose neither mutations nor fault controls.

## Common result envelope

Each handler returns `request_id`, `status`, typed `data`, `citations`, `warnings`, nullable `error`, UTC `observed_at` and nonnegative `elapsed_ms`.

`status` is `ok`, `empty`, `partial` or `error`. `empty` means a completed query found no matching evidence; it never means a dependency failed. A successful parts lookup returns `ok` with availability `available`, `insufficient` or `unavailable`, even for a confirmed zero quantity, because the inventory observation is evidence. A failed lookup returns availability `unknown` and status `error` or `partial`. No matching part returns `empty` with availability `unknown`. Preserve useful alternative-depot results even when the requested depot has no stock.

Use `partial` when some sources succeeded; identify missing evidence in warnings. `data` follows the chosen operation's schema rather than arbitrary prose. Errors contain `code`, safe `message` and `retryable`. Codes include `INVALID_ARGUMENT`, `DEPENDENCY_UNAVAILABLE`, `TIMEOUT`, `MODEL_PROTOCOL_ERROR`, `INSUFFICIENT_EVIDENCE` and `INTERNAL_ERROR`. Never invent data on failure or expose stack traces/credentials. MCP sets its transport error indicator for failed calls while preserving the envelope. Parity tests compare normalized payloads across adapters.

## Evidence and time

A citation has stable `source_id`, `source_type`, `locator`, `content_hash` and applicable `source_timestamp`. Types are `sensor`, `maintenance`, `part`, `inventory`, `document` and `validated_fact`. Locators identify record keys or document heading/line/page/chunk IDs, never absolute host paths. Derived facts link supporting chunks. Preserve units, threshold comparator, operating conditions and applicability; a bare number is not a validated rule.

`observed_at` records lookup time, not a claim that historical source data is current. Keep source timestamps separately. Final answers distinguish observations, cited procedures and inference; material measurements, thresholds and procedural recommendations resolve to returned citations. Missing evidence produces a stated gap. Answers do not authorize maintenance, operational release or inventory mutation.

## Ingestion and trust

Use stable keys/content hashes and an audit run ID. Re-ingesting unchanged inputs is idempotent. Schema-specific validators reject malformed/ambiguous values and record content-free reason codes. Preserve provenance and risk flags through retrieval and optional extraction. All retrieved/tool text remains untrusted data, regardless of heuristic scores.

## Required contract checks

- Registry, MCP discovery and agent tools have equivalent names, fields, enums and bounds.
- Both adapters return equivalent normalized success, empty, partial, invalid-input and dependency-failure results on independent fixtures.
- Final citations resolve; timestamp, unit and applicability checks catch unsupported conclusions.
- Retries, slow dependencies and iteration limits obey configured deadlines.
- Retrieved adversarial instructions cannot invoke unregistered tools, change query templates, disclose configuration or create side effects.

All published evidence uses synthetic fixtures. Local kit checks emit only aggregate results, with no supplied or derived content in CI or PRs.
