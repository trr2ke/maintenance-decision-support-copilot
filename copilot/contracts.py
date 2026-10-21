"""The same evidence envelope is used by CLI, LangGraph and MCP."""
from typing import Literal

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    status: Literal["ok", "empty", "unavailable", "error"]
    data: list[dict] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    error: str | None = None
    source_time: str | None = None
