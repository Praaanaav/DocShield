from docheal.code_parser import parse_source
from docheal.doc_parser import parse_markdown
from docheal.linker import build_links

CODE = '''
def get_item(key, timeout=30):
    pass


class Cache:
    def set_item(self, key, value):
        pass

    def clear_all(self):
        pass
'''

DOCS = '''# Usage

## Fetching items

Use `get_item(key, timeout=30)` to fetch an item.

## Storing items

Call `cache.set_item("a", "1")` to store a value.

## Clearing

Call `Cache.clear_all()` to clear.

## Install

Run `pip install fastcache`.
'''


def _pairs(links):
    return {(link.chunk_id, link.section_id) for link in links}


def _links_for(code, docs):
    return build_links(parse_source(code, "core.py"), parse_markdown(docs, "usage.md"))


def test_exact_name_match():
    links = _links_for(CODE, DOCS)
    match = [
        link
        for link in links
        if link.chunk_id == "core.py::get_item"
        and link.section_id == "usage.md#fetching-items"
    ]
    assert len(match) == 1
    assert match[0].score == 1.0


def test_dotted_instance_call_links_to_method():
    pairs = _pairs(_links_for(CODE, DOCS))
    assert ("core.py::Cache.set_item", "usage.md#storing-items") in pairs


def test_qualified_name_matches_exactly():
    pairs = _pairs(_links_for(CODE, DOCS))
    assert ("core.py::Cache.clear_all", "usage.md#clearing") in pairs


def test_unrelated_sections_get_no_links():
    section_ids = {link.section_id for link in _links_for(CODE, DOCS)}
    assert "usage.md#install" not in section_ids
    assert "usage.md#usage" not in section_ids


def test_generic_names_are_skipped():
    code = "\n".join(f"class C{i}:\n    def run(self):\n        pass\n" for i in range(4))
    assert _links_for(code, "# T\n\nCall `run()` now.\n") == []


def test_ambiguous_match_gets_lower_score():
    code = (
        "class A:\n    def run(self):\n        pass\n\n"
        "class B:\n    def run(self):\n        pass\n"
    )
    links = _links_for(code, "# T\n\nCall `run()` now.\n")
    assert len(links) == 2
    assert all(link.score == 0.5 for link in links)


def test_no_duplicate_links():
    code = "def get_item():\n    pass\n"
    links = _links_for(code, "# T\n\nUse `get_item()` or `lib.get_item()`.\n")
    assert len(links) == 1