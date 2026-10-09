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
    
API = '''
@app.get("/items")
def list_items():
    pass


@app.post("/items")
def create_item():
    pass


@app.get("/items/{item_id}")
def read_item(item_id):
    pass
'''


def _api_links(docs):
    return build_links(parse_source(API, "api.py"), parse_markdown(docs, "api.md"))


def test_route_in_docs_links_to_endpoint():
    links = _api_links("# API\n\n## Read\n\nCall `GET /items/{id}` to read one.\n")
    assert _pairs(links) == {("api.py::read_item", "api.md#read")}


def test_http_method_narrows_a_shared_route():
    links = _api_links("# API\n\n## Create\n\nSend `POST /items` to create one.\n")
    assert _pairs(links) == {("api.py::create_item", "api.md#create")}


def test_concrete_url_matches_route_template():
    docs = "# API\n\n## Try it\n\n```bash\ncurl http://localhost:8000/items/5\n```\n"
    assert _pairs(_api_links(docs)) == {("api.py::read_item", "api.md#try-it")}
    
SETTINGS = '''
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    max_items: int = 1000
    debug: bool = False
'''


def _settings_links(docs):
    return build_links(parse_source(SETTINGS, "settings.py"), parse_markdown(docs, "cfg.md"))


def test_env_var_links_to_config_class():
    links = _settings_links("# Cfg\n\n## Limits\n\nSet `MAX_ITEMS=500` to limit items.\n")
    assert _pairs(links) == {("settings.py::AppSettings", "cfg.md#limits")}


def test_single_word_env_var_in_caps_links():
    links = _settings_links("# Cfg\n\n## Debugging\n\nSet `DEBUG=1` for logs.\n")
    assert _pairs(links) == {("settings.py::AppSettings", "cfg.md#debugging")}


def test_generic_lowercase_word_does_not_link():
    links = _settings_links("# Cfg\n\n## Debugging\n\nTurn on `debug` for logs.\n")
    assert links == []