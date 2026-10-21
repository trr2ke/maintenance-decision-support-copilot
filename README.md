# Maintenance Decision-Support Copilot

Local maintenance evidence assistant with a CLI and shared LangGraph/MCP tools. See
[EXECUTION_PLAN.md](EXECUTION_PLAN.md) for the build and PR sequence.
Keep the supplied kit in ignored `rtx-ai-session-kit/`, or set `KIT_DIR` in `.env`.
Kit contents, credentials and derived data must stay out of Git and hosted CI.

## Run on this workstation

With the configured Python environment, run:

```powershell
python -m copilot migrate
python -m copilot ingest
python -m copilot extract
python -m copilot ask "Summarize recent brake temperatures and relevant procedures for tail 412."
python -m copilot mcp
```

Use `KIT_DIR` in `.env` when running from a separate worktree. Ingestion is
transactional and repeatable. Answers include local evidence and citations;
missing evidence or failed services remain explicitly unknown. Phoenix receives
operation status traces without prompts or source text. `extract` uses the local
models to populate Apache AGE with quoted, source-linked relationships. Unchanged
chunks are cached; `extract --force` refreshes them. Model-extracted relations
require verification against their quotations. The web UI remains deferred.

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/startup.ps1
```

This starts the services and runs the full preflight, including the supplied
smoke test. Use `-NoStart` for running services or `-SkipModels` for a partial
check. Full smoke output stays in `.local/kit-smoke-output.txt`.

## Fresh setup

Requires Python 3.12, Docker Linux containers and Ollama. Create `.env` from
`.env.example` only if it does not exist, then configure local paths/endpoints.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-test.txt
ollama pull gemma4:12b
ollama create maintenance-gemma4:12b -f scripts/models/gemma4.Modelfile
ollama pull llama3.2:3b
ollama create maintenance-llama32:3b -f scripts/models/llama32.Modelfile
.\.venv\Scripts\python.exe -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')"
```

Startup selects the root `.venv`, then the default kit's `.venv`; pass
`-PythonExe` to use another interpreter. `.env` selects the kit location, not
that interpreter. Dependency pins cover direct packages, not a transitive lock.

Both model aliases use a 4K context and 60-second request timeout. Use Gemma at
temperature 0.1 with `reasoning_effort="none"`; use Llama at temperature 0 with
no reasoning parameter. For structured final results, remove bound tools and
use JSON response mode. These checks establish tool compatibility, not answer quality.

Run tests with the selected interpreter: `python -m pytest -q`. Hosted CI uses
only independent fixtures. Services bind to localhost; database volumes persist
across container recreation. To stop them without removing data:
`docker compose stop`.
