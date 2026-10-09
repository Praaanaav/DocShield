from docheal.doc_parser import extract_code_refs, parse_markdown

SAMPLE = '''# Usage

Intro text.

## Fetching items

Use `get_item(key, timeout=30)` to fetch an item.

```python
cache.get_item("a")
```

## Clearing the cache

Call `clear_all()` to remove every item.

```
# not a heading
```
'''


def _by_id(sections):
    return {s.id: s for s in sections}


def test_sections_and_heading_paths():
    sections = parse_markdown(SAMPLE, "usage.md")
    assert [s.id for s in sections] == [
        "usage.md#usage",
        "usage.md#fetching-items",
        "usage.md#clearing-the-cache",
    ]
    assert sections[1].heading_path == ["Usage", "Fetching items"]


def test_line_numbers():
    section = _by_id(parse_markdown(SAMPLE, "usage.md"))["usage.md#fetching-items"]
    assert section.start_line == 5
    assert section.end_line == 12


def test_code_refs_from_inline_and_fenced_code():
    section = _by_id(parse_markdown(SAMPLE, "usage.md"))["usage.md#fetching-items"]
    assert "get_item" in section.code_refs
    assert "timeout" in section.code_refs
    assert "cache.get_item" in section.code_refs
    assert "clear_all" not in section.code_refs


def test_plain_words_are_not_refs():
    assert extract_code_refs("Use the function to fetch an item.") == []


def test_cli_flags_are_refs():
    assert "--max-wait" in extract_code_refs("Pass `--max-wait 60` to wait longer.")


def test_duplicate_headings_get_unique_ids():
    text = "# A\n\n## Notes\n\nx\n\n# B\n\n## Notes\n\ny\n"
    ids = [s.id for s in parse_markdown(text, "d.md")]
    assert len(ids) == len(set(ids))