"""Configuration deliberately restricts supplied evidence to local services."""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def local_endpoint(value: str, *, database: bool = False) -> str:
    parsed = urlsplit(value)
    schemes = {"postgresql"} if database else {"http", "https"}
    if parsed.scheme not in schemes or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Service endpoints must use loopback addresses")
    if not database and (parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("HTTP endpoints cannot contain credentials, queries or fragments")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    postgres_url: str = "postgresql://agent:agent@127.0.0.1:5432/agent"
    kit_dir: Path = ROOT / "rtx-ai-session-kit"
    parts_api_url: str = "http://127.0.0.1:8085"
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_model: str = "maintenance-gemma4:12b"
    llm_fallback_model: str = "maintenance-llama32:3b"
    llm_timeout_seconds: float = 60.0
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    phoenix_collector_endpoint: str = "http://127.0.0.1:6006"

    def __post_init__(self):
        local_endpoint(self.postgres_url, database=True)
        for endpoint in (self.parts_api_url, self.llm_base_url, self.phoenix_collector_endpoint):
            local_endpoint(endpoint)
        if not 0 < self.llm_timeout_seconds <= 120:
            raise ValueError("Model timeout must be between zero and 120 seconds")


def get_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False)
    kit = Path(os.getenv("KIT_DIR", str(ROOT / "rtx-ai-session-kit"))).expanduser()
    return Settings(
        postgres_url=os.getenv("POSTGRES_URL", Settings.postgres_url),
        kit_dir=(ROOT / kit).resolve() if not kit.is_absolute() else kit.resolve(),
        parts_api_url=os.getenv("PARTS_API_URL", Settings.parts_api_url),
        llm_base_url=os.getenv("LLM_BASE_URL", Settings.llm_base_url),
        llm_model=os.getenv("LLM_MODEL", Settings.llm_model),
        llm_fallback_model=os.getenv("LLM_FALLBACK_MODEL", Settings.llm_fallback_model),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        embedding_model=os.getenv("EMBEDDING_MODEL", Settings.embedding_model),
        phoenix_collector_endpoint=os.getenv("PHOENIX_COLLECTOR_ENDPOINT", Settings.phoenix_collector_endpoint),
    )
