from enum import Enum

from pydantic import BaseModel, Field


class ChunkKind(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    ENDPOINT = "endpoint"
    CONFIG = "config"
    CLI = "cli"


class CodeChunk(BaseModel):
    id: str  # stable ID: "src/fastcache/core.py::get_item"
    file_path: str
    name: str
    kind: ChunkKind
    signature: str  # e.g. "def get_item(key: str, timeout: int = 30) -> Item"
    docstring: str | None = None
    source: str  # full source text of the chunk
    start_line: int
    end_line: int


class DocSection(BaseModel):
    id: str  # stable ID: "docs/usage.md#fetching-items"
    file_path: str
    heading_path: list[str]  # ["Usage", "Fetching items"]
    content: str  # raw markdown of the section
    start_line: int
    end_line: int
    code_refs: list[str] = Field(default_factory=list)  # names it mentions


class LinkMethod(str, Enum):
    EXPLICIT = "explicit"  # section literally mentions the symbol
    EMBEDDING = "embedding"  # found via similarity


class Link(BaseModel):
    chunk_id: str
    section_id: str
    method: LinkMethod
    score: float = 1.0  # 1.0 for explicit; cosine similarity for embeddings


class VerdictLabel(str, Enum):
    STALE = "stale"
    ACCURATE = "accurate"
    UNSURE = "unsure"


class Verdict(BaseModel):
    section_id: str
    chunk_id: str
    label: VerdictLabel
    evidence: str  # what exactly is wrong (or why it's still accurate)
    change_type: str | None = None  # e.g. "rename", "default_changed", "removed"