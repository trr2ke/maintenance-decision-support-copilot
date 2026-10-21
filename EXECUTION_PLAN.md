# Maintenance Decision-Support Copilot: Execution Plan

## Authorization and scope

Readiness fixes and this plan are authorized. Application implementation remains on hold until the user gives the green light. Preparing infrastructure, checking models and opening a readiness PR do not authorize application development.

The required demonstration is a local, read-only assistant that joins sensor and maintenance evidence, retrieves cited procedures, checks parts availability and explains uncertainty. Expose the same tools through the agent and MCP. A web UI and LLM-generated knowledge graph are secondary to a correct, cited tool workflow. The assistant does not release aircraft, perform maintenance, reserve inventory or create work orders; future actions require separate authorization and reviewed contracts.

## Phase 0: readiness before the timed build

Finish preparation before the three-hour implementation window. Provisioning, downloads, model selection and the supplied smoke test at least 24 hours before the session are preparation time. An arithmetic prompt or advertised tool support is not a model acceptance test.

Use root `compose.yaml`, `infra/`, startup wrappers and `scripts/preflight.py`. Keep the supplied kit unchanged. Copy `.env.example` to ignored `.env`; set `KIT_DIR` to the local kit. Use environment configuration for all paths, models and endpoints. Root configuration includes `LLM_BASE_URL`, `LLM_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_REASONING_EFFORT` and `LLM_TIMEOUT_SECONDS`. Direct dependency pins document the tested runtime; they are not a complete transitive lockfile.

### Exit checklist and evidence

Checked items were validated on 2026-10-21; they certify prerequisites, not application behavior. Record dated, sanitized results in the readiness PR; consult `docs/model-readiness.md` for measured model outcomes. Re-run runtime gates before the session.

- [x] A sanitized Git baseline exists remotely. Readiness uses `chore/execution-readiness`.
- [ ] Branch/PR creation and authentication work; kit, credentials, environments and generated artifacts are excluded.
- [x] Declared dependencies import and `pip check` passes in the chosen interpreter.
- [x] Compose validates and all services become healthy. Startup resolves repository-relative paths, checks native exit codes and fails clearly. Alternate interpreter paths use `-PythonExe`/`PYTHON_EXE`.
- [x] Pinned PostgreSQL contains AGE and pgvector; actual graph/vector queries work. Cluster identity and extension OIDs survive container recreation without volume deletion, with PGDATA inside the persistent mount.
- [x] Parts API responds locally. Phoenix accepts synthetic OK/ERROR spans whose IDs and statuses are retrieved through its API.
- [x] Cached MiniLM produces 384-dimensional vectors on CPU. Application query/ingestion consistency remains an implementation gate.
- [x] Supplied smoke test passed locally on 2026-10-21. Detailed output is retained only in ignored `.local/`; publish only a pass/fail summary.
- [ ] Confirm the smoke run is at least 24 hours before the actual session and send its output through the agreed organizer channel; session timing/submission is not established by these local checks.
- [x] Primary and fallback complete tool selection, schema-valid arguments, execution and factual final answers on independent synthetic requests through LangChain `/v1`. Cold/warm measurements and final JSON-mode requirements are recorded in `docs/model-readiness.md`.
- [x] At least 20 GB (decimal) free disk space after setup; the preflight rechecks this changing value.
- [ ] Shared contracts in [docs/contracts.md](docs/contracts.md) are frozen, file ownership assigned and local-only checks available without exposing supplied contents to cloud agents.
- [ ] User explicitly authorizes application implementation.

If the model cannot complete the required tool cycle within its configured deadline, the demonstration is not ready. A tested deterministic router would require explicit agreement to reduced scope; do not silently substitute one. Use the measured local model alias and reasoning settings from the readiness report, not an untested model name from an old plan.

## Local data boundary

The supplied kit and derived material remain local: no Git, PR bodies, hosted CI, cloud-agent prompts, screenshots or external traces containing kit files, excerpts, rows, extracted facts or embeddings. Inspect explicitly staged paths and diffs before every commit. Cloud coding agents use independently authored schemas and fixtures. Local processes validate supplied material and return aggregate pass/fail information only. A local human resolves any mapping ambiguity requiring source-content inspection and provides a content-free interface correction.

Inference and Phoenix tracing stay local; services bind to loopback. The coordinator owns shared services and GPU scheduling. Concurrent integration workers use separate synthetic databases. Never copy the kit into worktrees; configure an absolute local `KIT_DIR` where needed.

## Architecture and shared interfaces

Local sources -> validated repeatable ingestion -> relational tables/vector chunks -> shared typed tool registry -> LangGraph and MCP adapters -> CLI demonstration, with optional Flask UI. Local spans cover request, model, tools, database and retrieval boundaries.

AGE is an optional evidence backend. Preserve cited facts relationally so graph failure can use the same fact contract. LLM extraction is optional: the mandatory demonstration obtains procedures and thresholds from cited documents and states when no validated fact exists. It must not invent facts to satisfy a graph demonstration.

Four required capabilities are fleet queries, document retrieval, parts availability and evidence-fact lookup. One registry owns their schemas and handlers. MCP discovery and invocation must work through an actual client; MCP is a required deliverable, not a stub. See the contract document for requests, results, errors and provenance.

## Implementation tasks and acceptance

### A. Schema and migrations

Use parameterized SQL and fixed allowlisted query templates; never execute model-written SQL or Cypher. Preserve legitimate hyphenated part numbers. Cap rows and statement duration. Tools use a read-only database role, while ingestion uses a separate write role.

| Entity | Mapping and checks |
|---|---|
| Sensors | Text tail identifier, wheel/position, event time, temperature, units and operating conditions; preserve per-wheel observations and source precision. |
| Maintenance | Text tail identifier, event time, narrative, source reference and injection flags. |
| Parts | Preserve source nomenclature, part number/category, supplier relationships and lead times; document display-name mapping. |
| Depots/inventory | Part/depot, available/reserved quantities, transfer duration and source observation time. Establish whether quantity is gross or net before deriving availability. |
| Installed components | Tail, position/component, part, lot/serial and installation dates where present; enforce relationships. |
| Document chunks | Stable IDs, hash, source locator, heading/line/page, units/conditions, embedding model/dimension and risk flags. |
| Validated facts | Subject/predicate/object, units, conditions/applicability, supporting chunk IDs, extraction provenance and validation state. |
| Ingestion audit | Run ID, hashes, schema version, accepted/rejected counts, safe error codes and completion state. |

Done: migrations work on an empty synthetic database; constraints, read-only access and failure/rollback behavior are tested. Validate source-field coverage locally before declaring mappings complete.

### B. Ingestion and data quality

Normalize identifiers as strings under explicit source rules; preserve leading zeros unless the schema says otherwise. Do not assume three-digit tails or silently truncate fractional values with `int(float(...))`. Reject invalid integers, non-finite measurements, impossible quantities and ambiguous timestamps. Normalize aware times to UTC; document the timezone used for naive sources.

Use transactions, stable source keys/content hashes and upserts. Re-ingesting unchanged input must not duplicate or alter records. Test foreign keys, missing values, duplicate input and partial-run recovery. Quarantine failures with provenance and content-free reason codes.

Bound chunk length/overlap and retain source locators. Flag suspicious instructions before retrieval/extraction, but treat all retrieved text as untrusted even if pattern checks pass. Heuristics are not a security guarantee. Independent adversarial fixtures must prove that retrieved instructions cannot override the task, disclose secrets or change tool permissions.

Done: repeatable synthetic ingestion and local-only source coverage/integrity checks. No kit facts or derived snapshots in repository tests.

### C. Agent, tools and MCP

Implement shared typed handlers before adapters. Fleet queries support per-wheel/time-window comparisons and maintenance history. Resolve “lately” against an explicit analysis anchor, normally the latest relevant dataset time, and return the actual interval rather than silently using today's date.

Parts results cover installed-part context, lot where applicable, available/reserved stock, transfers and supplier lead times. Retry only transient faults within one overall deadline. Confirmed zero availability is distinct from timeout/error: failed checks mean unknown availability. Fault controls belong only to the local test harness, never model tools.

Use a bounded LangGraph loop, validated tool arguments and evidence-linked answers. Missing evidence produces an explicit limitation. MCP discovery and live invocation must return the same normalized schemas/results/errors as the agent adapters.

Done: real selected model completes the multi-step synthetic workflow; tools remain read-only, failures are truthful and latency is bounded.

### D. Retrieval and optional graph

Verify ranking on independent fixtures, embedding dimension compatibility, source filtering and citation locators. Facts retain units and conditions; uncertain extractions cannot become validated rules. Optional extraction uses one shared-GPU worker, structured validation, bounded retries and a failure circuit breaker.

Done: procedures/thresholds are retrievable with valid citations. If AGE/extraction is deferred, fact lookup uses validated relational facts or returns unavailable and the demonstration uses cited documents. State the actual mode; do not claim graph coverage that does not exist.

### E. Presentation, tracing and acceptance

CLI is the minimum presentation. Optional Flask endpoints are `GET /`, `POST /api/query` and `GET /api/health`, using the shared response contract. Show citations, source times, uncertainty and dependency failures. Separate liveness from dependency readiness.

Verify a complete synthetic trace in local Phoenix, including tool errors/latency. Do not log secrets or full retrieved content; kit-bearing traces stay local.

Replace permanent skips with executable tests. Hosted CI may explicitly deselect local integration tests; running those locally remains a release gate. Required scenarios:

1. Synthetic elevated per-wheel readings, matching maintenance and a conditional procedure produce correct values, interval, units and citations.
2. Normal readings, absent history and conflicting evidence do not yield unsupported diagnoses or maintenance authorization.
3. Stock success, zero stock, reservations, alternate depots and lead times yield distinct results.
4. Parts timeout, error, slow and flaky modes obey retry/deadline limits, recover after reset and never turn unknown stock into zero.
5. Invalid identifiers, hyphenated part numbers, query injection and retrieved prompt injection preserve validation and read-only boundaries.
6. MCP discovery/invocation matches agent schemas/errors. Check actual model calls, argument values, final facts and citations, not just status/text presence.
7. Re-ingestion, persistence, fallback retrieval, local trace export and missing dependencies behave as documented.
8. Local-only supplied-data demonstration passes factual checks computed locally. Publish only aggregate outcomes and limitations.

## Multi-agent execution and PR workflow

Use one coordinator and up to three workers. Readiness bootstrap may use non-overlapping files in the existing tree; application tasks require individual worktrees, branches and draft PRs from the reviewed baseline.

| Task/branch | Owner | Dependencies | Owned scope |
|---|---|---|---|
| Readiness / `chore/execution-readiness` | Coordinator | Existing baseline | Plan, environment, infrastructure and prerequisites |
| A / `feat/schema` | Worker A | Readiness merged; implementation authorized | Migrations, database access and fixtures |
| B / `feat/ingestion` | Worker B | Frozen contracts; A for integration | Ingestion and its tests |
| E UI / `feat/presentation` | Worker C | Response contract | CLI/UI against independent stubs |
| D / `feat/retrieval` | Worker A | A + B | Retrieval/fact handlers and tests |
| C / `feat/agent-mcp` | Worker B | B; D for integrated checks | Registry, agent, MCP, parts client and tests |
| E acceptance / `test/acceptance` | Worker C | A + B + C + D | Acceptance harness, tracing and demonstration |

Coordinator owns shared dependency/configuration files, contracts, CI, service lifecycle and merges. Each worker owns task tests. Shared files/migrations have one owner; request a handoff rather than editing another scope. Create worktrees outside the repository. Serialize shared GPU inference, kit checks and fault tests.

For every task: open a draft PR early, make logical commits with explicit staged paths, attach sanitized checks and obtain independent review. Coordinator merges only after gates pass and updates dependent branches. Merge readiness -> A -> B -> D -> C -> acceptance; presentation can merge when contract compatibility passes. Workers may develop ahead using fixtures, but integration evidence requires merged dependencies.

Hosted CI uses only independent fixtures, import checks, contract tests and unit tests. Local integration covers services, GPU/model, MCP and supplied inputs. Report counts and deselections; an empty/skipped suite cannot satisfy a required gate. PRs explain resulting behavior, actual validation and unresolved limits.

### Three-hour wall-clock budget after authorization

| Window | Work and checkpoint |
|---|---|
| 0-15 min | Coordinator freezes ownership/contracts and branches; A schema, B ingestion stubs, C presentation stubs. |
| 15-55 min | A schema review/merge then retrieval setup; B ingestion; C synthetic acceptance harness. |
| 55-100 min | B ingestion review/merge then agent/MCP; A retrieval; C presentation/tracing tests. |
| 100-135 min | Retrieval and agent/MCP reviews/merges; coordinator runs serial integration. |
| 135-165 min | Acceptance/fault tests, local factual validation and reviewed fixes. |
| 165-180 min | Final merge verification, demo rehearsal and limitations report. |

Reviews, integration and conflicts consume this budget. At minute 100, cut optional UI polish and LLM extraction before MCP, citations, parts failure semantics or tests. If required gates cannot pass, report incomplete scope rather than weakening tests or asserting success. An unverified fallback model is never on the critical path.
