from docheal.models import (
    ChunkKind,
    CodeChunk,
    DocSection,
    Link,
    LinkMethod,
)


def test_code_chunk_roundtrip_json():
    chunk = CodeChunk(
        id="src/fastcache/core.py::get_item",
        file_path="src/fastcache/core.py",
        name="get_item",
        kind=ChunkKind.FUNCTION,
        signature="def get_item(key: str, timeout: int = 30) -> Item",
        source="def get_item(key, timeout=30): ...",
        start_line=10,
        end_line=14,
    )
    restored = CodeChunk.model_validate_json(chunk.model_dump_json())
    assert restored == chunk


def test_doc_section_defaults():
    section = DocSection(
        id="docs/usage.md#fetching-items",
        file_path="docs/usage.md",
        heading_path=["Usage", "Fetching items"],
        content="Use `get_item` to fetch an item.",
        start_line=3,
        end_line=6,
    )
    assert section.code_refs == []


def test_link_defaults():
    link = Link(
        chunk_id="src/fastcache/core.py::get_item",
        section_id="docs/usage.md#fetching-items",
        method=LinkMethod.EXPLICIT,
    )
    assert link.score == 1.0