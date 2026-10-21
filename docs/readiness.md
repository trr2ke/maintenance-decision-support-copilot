# Readiness verification: 2026-10-21

Scope: local prerequisites and future execution plan. No application tables,
ingestion pipeline, agent, MCP business tools or UI have been implemented.

The final PowerShell startup check, using `-NoStart`, exited zero and reported
`PREREQUISITES READY`. All individual checks passed:

| Check | Evidence |
| --- | --- |
| Disk | 20.32 GB free (decimal); enforced again on every preflight |
| Python | 3.12.7; declared runtime installed; imports and `pip check` passed |
| Supplied sources | Local presence, structure and SQLite integrity passed; no contents published |
| Database | PostgreSQL 18.6, AGE 1.8.0, pgvector 0.8.6; actual Cypher/vector queries passed |
| Persistence | Cluster identity and extension OIDs survived container recreation with the named volume retained |
| Services | Parts health plus database-backed route, Phoenix health and all Compose service health checks passed |
| Tracing | Exported independent synthetic OK/ERROR spans; API readback matched trace/span IDs and statuses |
| Embeddings | Cached MiniLM loaded offline on CPU and produced 384 dimensions |
| Primary model | `maintenance-gemma4:12b`; exact tool arguments and structured final result passed in 7.00 seconds |
| Fallback model | `maintenance-llama32:3b`; exact tool arguments and structured final result passed in 3.30 seconds |
| Supplied smoke | Passed using root environment overrides; detailed output remains in ignored `.local/` |
| Readiness unit tests | 21 passed, zero skipped; independent fixtures only |
| GitHub CI | Readiness tooling workflow passed on PR #1; no supplied material used |
| Shell/configuration | PowerShell parsed, Bash syntax checked, Compose validated, staged whitespace checked |

Model timing above is from the final preflight, not a performance guarantee.
See [model evidence](model-readiness.md) for cold/warm LangChain results and
required settings. Both model aliases cap context at 4,096 tokens. The final
readiness response uses JSON mode; application answer quality, citations and
longer contexts remain implementation acceptance work.

The supplied source tree and `.env` are ignored and absent from tracked paths.
The initial public Git baseline contains only independently authored project
instructions and exclusions. The readiness PR adds independently authored setup
code, tests and planning documents; hosted CI never receives the kit.

[Readiness PR #1](https://github.com/trr2ke/maintenance-decision-support-copilot/pull/1)
is open for review. An independent agent review found no remaining prerequisite
blocker after the final checks.

Before application execution: review/merge the readiness PR, explicitly authorize
implementation, assign workers to worktrees and freeze contracts. Confirm the
smoke-test timing against the session date and send its output yourself through
the agreed organizer channel. Runtime readiness must be rechecked before use.
