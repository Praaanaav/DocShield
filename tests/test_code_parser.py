from docheal.code_parser import parse_source

SAMPLE = '''
def get_item(key: str, timeout: int = 30) -> str:
    """Fetch an item."""

    def helper():
        pass

    return key


class Cache:
    """A cache."""

    def clear_all(self) -> None:
        pass


async def fetch(url):
    pass
'''


def _by_id(chunks):
    return {c.id: c for c in chunks}


def test_finds_functions_classes_and_methods():
    chunks = parse_source(SAMPLE, "core.py")
    assert set(_by_id(chunks)) == {
        "core.py::get_item",
        "core.py::Cache",
        "core.py::Cache.clear_all",
        "core.py::fetch",
    }


def test_function_details():
    chunk = _by_id(parse_source(SAMPLE, "core.py"))["core.py::get_item"]
    assert "timeout" in chunk.signature
    assert "-> str" in chunk.signature
    assert chunk.docstring == "Fetch an item."
    assert chunk.source.startswith("def get_item")


def test_nested_helper_is_ignored():
    names = [c.name for c in parse_source(SAMPLE, "core.py")]
    assert "helper" not in names