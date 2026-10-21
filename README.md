# Maintenance Decision-Support Copilot

This repository contains independently authored readiness tooling and an execution
plan. Application development starts only when its execution phase is authorized.

The supplied session kit is a local prerequisite, not a repository artifact. Place
it in `rtx-ai-session-kit/` or configure `KIT_DIR` in an ignored local `.env` file.
Never publish the kit, its contents, or derived data in commits, PRs or CI output.
Use newly authored fixtures for hosted CI and local checks for supplied material.

See [EXECUTION_PLAN.md](EXECUTION_PLAN.md) for prerequisites, task ownership,
acceptance criteria and the branch/PR workflow.
