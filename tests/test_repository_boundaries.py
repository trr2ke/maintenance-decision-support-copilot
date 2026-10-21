from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def test_no_supplied_kit_or_local_artifacts_are_tracked():
    paths = git("ls-files", "-z").split("\0")
    forbidden = ("rtx-ai-session-kit/", ".local/", ".venv/", "data/", "traces/", "embeddings/")
    assert not [path for path in paths if path.startswith(forbidden) or path == ".env"]


def test_sensitive_and_generated_paths_are_ignored():
    paths = ["rtx-ai-session-kit/.env", "rtx-ai-session-kit/README.md", "rtx-ai-session-kit/data/example.csv",
             ".env", ".local/kit-smoke-output.txt", ".venv/example", "artifacts/example.json"]
    ignored = git("check-ignore", "--", *paths).splitlines()
    assert set(ignored) == set(paths)
