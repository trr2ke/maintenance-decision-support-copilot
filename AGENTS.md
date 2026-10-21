# Contributor and agent instructions

- Work only on the authorized phase. Readiness setup does not authorize building
  the application. Read EXECUTION_PLAN.md before accepting an implementation task.
- Use one coordinator and at most three workers. Each implementation task gets an
  isolated worktree, branch, explicit file ownership and a draft PR. The initial
  readiness bootstrap may use non-overlapping file ownership in the existing tree.
- The supplied kit must remain local. Do not read data/manual contents into cloud
  agent context or publish any supplied kit files, excerpts, data-bearing output,
  extracted facts, embeddings, screenshots or traces. Write independent fixtures.
- Never stage the whole tree. Stage explicit owned paths, inspect staged diffs and
  confirm kit files, secrets and local artifacts are excluded before a commit/push.
- Do not modify the supplied kit. Put configuration overrides and new code here.
- Shared dependency files, interfaces and migrations have one owner. Coordinate
  changes before editing another task's files. Review PRs before merging.
- The coordinator owns shared local services. Serialize model inference and
  service fault tests; use separate databases for concurrent integration tests.
- Use parameterized queries and explicit timeouts. Preserve source attribution.
- A passing readiness test is not an application acceptance result. Do not hide
  missing application functionality behind permanently skipped tests.
- PRs describe the problem, final behavior and actual checks. Report test skips,
  unverified assumptions and local-only checks without including kit contents.
