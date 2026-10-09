from pathlib import Path

import pytest

from docheal.index import INDEX_VERSION, Index, build_index, load_index, save_index


def _make_project(root: Path) -> None:
    (root / "docs").mkdir()
    (root / "core.py").write_text(
        "def get_item(key, timeout=30):\n    pass\n", encoding="utf-8"
    )
    (root / "docs" / "usage.md").write_text(
        "# Usage\n\n## Fetching\n\nUse `get_item()` to fetch.\n", encoding="utf-8"
    )


def test_build_index_finds_chunks_sections_and_links(tmp_path):
    _make_project(tmp_path)
    index = build_index(tmp_path)
    assert [c.id for c in index.chunks] == ["core.py::get_item"]
    assert len(index.sections) == 2
    assert [(l.chunk_id, l.section_id) for l in index.links] == [
        ("core.py::get_item", "docs/usage.md#fetching")
    ]


def test_save_and_load_roundtrip(tmp_path):
    _make_project(tmp_path)
    index = build_index(tmp_path)
    path = tmp_path / ".docheal" / "index.json"  # folder doesn't exist yet
    save_index(index, path)
    assert load_index(path) == index


def test_same_input_gives_identical_file(tmp_path):
    _make_project(tmp_path)
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    save_index(build_index(tmp_path), first)
    save_index(build_index(tmp_path), second)
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_sections_for_chunk(tmp_path):
    _make_project(tmp_path)
    index = build_index(tmp_path)
    found = index.sections_for_chunk("core.py::get_item")
    assert [s.id for s in found] == ["docs/usage.md#fetching"]
    assert index.sections_for_chunk("core.py::missing") == []


def test_load_rejects_unknown_version(tmp_path):
    path = tmp_path / "index.json"
    save_index(Index(version=INDEX_VERSION + 1), path)
    with pytest.raises(ValueError):
        load_index(path)