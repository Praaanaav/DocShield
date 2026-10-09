from pathlib import Path

from pydantic import BaseModel, Field

from docheal.code_parser import parse_directory
from docheal.doc_parser import parse_docs_directory
from docheal.linker import build_links
from docheal.models import CodeChunk, DocSection, Link

# Bump this when the saved format changes, so old files are rejected, not misread.
INDEX_VERSION = 1


class Index(BaseModel):
    version: int = INDEX_VERSION
    chunks: list[CodeChunk] = Field(default_factory=list)
    sections: list[DocSection] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)

    def sections_for_chunk(self, chunk_id: str) -> list[DocSection]:
        """Doc sections linked to a code chunk, most certain link first."""
        by_id = {section.id: section for section in self.sections}
        linked = sorted(
            (link for link in self.links if link.chunk_id == chunk_id),
            key=lambda link: -link.score,
        )
        return [by_id[link.section_id] for link in linked]


def build_index(code_root: Path, docs_root: Path | None = None) -> Index:
    """Parse code and docs, link them, and bundle everything into an Index."""
    chunks = parse_directory(code_root)
    sections = parse_docs_directory(docs_root or code_root)
    links = sorted(
        build_links(chunks, sections),
        key=lambda link: (link.section_id, link.chunk_id),
    )
    return Index(chunks=chunks, sections=sections, links=links)


def save_index(index: Index, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(index.model_dump_json(indent=2), encoding="utf-8")


def load_index(path: Path) -> Index:
    index = Index.model_validate_json(path.read_text(encoding="utf-8"))
    if index.version != INDEX_VERSION:
        raise ValueError(
            f"Index version {index.version} is not supported (expected {INDEX_VERSION}). "
            "Rebuild the index."
        )
    return index