# Execution plan

Readiness setup is complete. Application development awaits explicit authorization.
Build a local, read-only assistant that combines fleet evidence, cited procedures
and parts availability. Expose shared tools through LangGraph and MCP.

## Before the session

- Run `scripts/startup.ps1` as documented in README; require the complete preflight to pass.
- Verify PostgreSQL/AGE/pgvector, parts API, Phoenix traces, cached embeddings and both models.
- Run the supplied smoke test at least 24 hours before the session and send its output through the agreed organizer channel. Keep detailed output local.
- Review/merge readiness PR #1 and obtain authorization for application development.

Validated 2026-10-21: full preflight and supplied smoke passed; 21 tests and GitHub
CI passed; database state survived container recreation. Recheck before execution.

## Tasks and PRs

Use one coordinator and up to three workers. Each task gets its own worktree,
branch, logical commits and draft PR. Workers may build against agreed interfaces
in parallel; integration and merges follow the dependencies below.

| Task / branch | Owner | Depends on | Done when |
|---|---|---|---|
| Schema / `feat/schema` | A | Readiness | Migrations, constraints and read-only tool access pass tests. |
| Ingestion / `feat/ingestion` | B | Schema for integration | Sources normalize correctly; repeat ingestion is idempotent; provenance is retained. |
| Retrieval / `feat/retrieval` | A | Schema + ingestion | Document search returns relevant evidence with valid source citations. |
| Agent + MCP / `feat/agent-mcp` | B | Ingestion + retrieval | Fleet, document, parts and fact tools work through both adapters and a real model. |
| CLI + acceptance / `test/acceptance` | C | Integrated tools | End-to-end, failure and factual checks pass; local traces explain failures. |

Coordinator owns shared configuration/interfaces and reviews each PR before merge.
Serialize shared GPU inference and service fault tests. Keep kit contents and
derived data local; publish only independently authored code, fixtures and safe summaries.

## Implementation essentials

- Agree typed tool inputs and a common result format before branching: status, data, citations, safe error and source time. Share handlers between LangGraph and MCP.
- Preserve text identifiers, wheel/time context, units, installed components, lots, reserved stock and supplier/transfer lead times. Reject invalid values without silently rounding identifiers.
- Use parameterized queries, read-only tools, bounded retries and an agent call limit. Treat retrieved instructions as untrusted data.
- Distinguish confirmed zero inventory from an unavailable service. Test the supplied parts API's timeout, slow, error and flaky modes; never expose its fault controls to the agent.
- Resolve relative time against an explicit dataset anchor. Cite measurements and procedures, and state missing or conflicting evidence.
- Test actual MCP discovery/invocation, exact tool arguments/results, citations, injection handling, repeat ingestion and dependency failures. Do not substitute skipped tests for acceptance.
- CLI is sufficient. Flask UI and LLM graph extraction are optional; document/relational retrieval must work if graph extraction is deferred.

## Three-hour budget

Allow 15 minutes for interfaces/ownership, 45 for schema/ingestion, 60 for
retrieval/agent/MCP, 45 for integration/review/tests and 15 for rehearsal.
Workers overlap independent work. Cut UI polish and graph extraction first;
retain MCP, citations, truthful failure handling and testing.
