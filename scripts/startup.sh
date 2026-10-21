#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_exe="${PYTHON_EXE:-}"
if [[ -z "$python_exe" ]]; then
  for candidate in .venv/bin/python .venv/Scripts/python.exe \
    "${KIT_DIR:-rtx-ai-session-kit}/.venv/bin/python" \
    "${KIT_DIR:-rtx-ai-session-kit}/.venv/Scripts/python.exe"; do
    if [[ -x "$candidate" ]]; then python_exe="$candidate"; break; fi
  done
fi
if [[ -z "$python_exe" ]]; then
  echo 'Python environment missing. Follow README setup or set PYTHON_EXE.' >&2
  exit 1
fi
docker compose -f compose.yaml up -d --build --wait --wait-timeout 120
"$python_exe" -B scripts/preflight.py --kit-smoke
