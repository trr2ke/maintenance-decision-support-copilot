# Maintenance Decision-Support Copilot

This repository contains independently authored readiness tooling and an execution
plan. Application development starts only when its execution phase is authorized.

The supplied session kit is a local prerequisite, not a repository artifact. Place
it in `rtx-ai-session-kit/` or configure `KIT_DIR` in an ignored local `.env` file.
Never publish the kit, its contents, or derived data in commits, PRs or CI output.
Use newly authored fixtures for hosted CI and local checks for supplied material.

See [EXECUTION_PLAN.md](EXECUTION_PLAN.md) for prerequisites, task ownership,
acceptance criteria and the branch/PR workflow.

## Local setup

Use Python 3.12 and Docker with Linux containers. The current workstation uses
`rtx-ai-session-kit/.venv/Scripts/python.exe`. On a fresh workstation, create a
root `.venv` and install the independently maintained dependency list:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-test.txt
Copy-Item .env.example .env
```

Do not overwrite an existing `.env`. Keep configured endpoints local. Follow
[model readiness](docs/model-readiness.md) to pull source models and create the
verified aliases. Download the embedding model once before offline use:

```powershell
.\.venv\Scripts\python.exe -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')"
```

For the already prepared workstation, start/check services and run the complete
preflight, including the supplied smoke test:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\startup.ps1
```

Startup chooses a root `.venv`, then the local kit's `.venv`. To reuse an
environment elsewhere, pass `-PythonExe 'C:\path\to\python.exe'`. `KIT_DIR` in
`.env` selects data and the Compose mount, not the interpreter. Git Bash/Linux
users can set `PYTHON_EXE` and run `bash scripts/startup.sh`.
The command above permits local scripts for that PowerShell process only; it
does not change the machine's execution policy.

`-NoStart` checks services already running; `-SkipModels` is an explicitly partial
check and does not run the supplied model smoke test. Failures return nonzero.
Full smoke output stays in ignored `.local/kit-smoke-output.txt`; share it with
session organizers yourself through the agreed channel. Re-run before the
session; a successful setup check does not certify application behavior.

## Validation and collaboration

```powershell
.\rtx-ai-session-kit\.venv\Scripts\python.exe -m pytest -q
```

The hosted CI suite uses only new synthetic fixtures. Local preflight checks
source integrity, extensions and actual graph/vector queries, service endpoints,
persisted synthetic traces, offline embeddings and both model tool round trips.
Model tests use per-request deadlines; a two-call round trip may consume twice
that limit. There is no application implementation or application test suite yet.

See [infrastructure](infra/README.md) for pinned services and persistence checks,
[shared contracts](docs/contracts.md) for planned interfaces, and
[AGENTS.md](AGENTS.md) for worktree ownership and commit/PR rules.
