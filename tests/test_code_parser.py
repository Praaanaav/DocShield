from docheal.code_parser import parse_source
from docheal.models import ChunkKind

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
    
ENDPOINTS = '''
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
def read_item(item_id: int):
    """Read one item."""
    return {}


@app.post("/items", status_code=201)
async def create_item(item: dict):
    return item


@app.route("/health", methods=["GET", "HEAD"])
def health():
    return "ok"


@app.route("/ping")
def ping():
    return "pong"


@mock.patch("module.thing")
def not_an_endpoint():
    pass
'''


def test_endpoint_detection():
    chunks = _by_id(parse_source(ENDPOINTS, "api.py"))
    read = chunks["api.py::read_item"]
    assert read.kind == ChunkKind.ENDPOINT
    assert read.route == "/items/{item_id}"
    assert read.http_method == "GET"
    assert chunks["api.py::create_item"].route == "/items"
    assert chunks["api.py::create_item"].http_method == "POST"
    assert chunks["api.py::health"].http_method == "GET,HEAD"
    assert chunks["api.py::ping"].http_method == "GET"


def test_non_route_decorator_stays_a_function():
    chunk = _by_id(parse_source(ENDPOINTS, "api.py"))["api.py::not_an_endpoint"]
    assert chunk.kind == ChunkKind.FUNCTION
    assert chunk.route is None


def test_chunk_includes_its_decorator():
    chunk = _by_id(parse_source(ENDPOINTS, "api.py"))["api.py::read_item"]
    assert chunk.source.startswith('@app.get("/items/{item_id}")')
    lines = ENDPOINTS.splitlines()
    assert lines[chunk.start_line - 1].startswith("@app.get")
    
CONFIGS = '''
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """App settings."""

    database_url: str
    debug: bool = False
    max_items: int = Field(1000, description="Upper limit")
    tags: list[str] = Field(default_factory=list)
    _private: int = 0


@dataclass
class CacheConfig:
    ttl: int = 300
    names: list[str] = field(default_factory=list)


class ItemSchema(BaseModel):
    name: str


class PlainSettings:
    value = 1
'''


def test_settings_class_is_config_with_fields():
    chunk = _by_id(parse_source(CONFIGS, "settings.py"))["settings.py::AppSettings"]
    assert chunk.kind == ChunkKind.CONFIG
    fields = {f.name: f for f in chunk.config_fields}
    assert list(fields) == ["database_url", "debug", "max_items", "tags"]
    assert fields["database_url"].default is None
    assert fields["debug"].type == "bool"
    assert fields["debug"].default == "False"
    assert fields["max_items"].default == "1000"
    assert fields["tags"].default == "list()"


def test_dataclass_with_config_name_is_config():
    chunk = _by_id(parse_source(CONFIGS, "settings.py"))["settings.py::CacheConfig"]
    assert chunk.kind == ChunkKind.CONFIG
    assert {f.name: f.default for f in chunk.config_fields} == {
        "ttl": "300",
        "names": "list()",
    }


def test_ordinary_classes_stay_classes():
    chunks = _by_id(parse_source(CONFIGS, "settings.py"))
    assert chunks["settings.py::ItemSchema"].kind == ChunkKind.CLASS
    assert chunks["settings.py::PlainSettings"].kind == ChunkKind.CLASS
    assert chunks["settings.py::ItemSchema"].config_fields == []