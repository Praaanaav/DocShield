import re
from collections import defaultdict

from docheal.models import ChunkKind, CodeChunk, DocSection, Link, LinkMethod

# A name that matches more chunks than this (like "run" or "get") is too
# generic to say anything about which code a doc section describes.
MAX_CANDIDATES = 3
# One route can legitimately have several endpoints (GET, POST, PUT, DELETE...).
MAX_ROUTE_CANDIDATES = 6

HTTP_METHODS = {
    "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE", "WEBSOCKET",
}
PARAM_RE = re.compile(r"\{[^}]*\}|<[^>]*>")  # {item_id} or <int:item_id>


def _last_part(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _normalize_route(route: str) -> str:
    return PARAM_RE.sub("{}", route.rstrip("/") or "/")


def route_matches(route: str, ref: str) -> bool:
    """True if a doc reference (/items/5 or /items/{id}) fits a route template."""
    if _normalize_route(route) == _normalize_route(ref):
        return True
    parts = PARAM_RE.split(route.rstrip("/") or "/")
    pattern = "[^/]+".join(re.escape(part) for part in parts)
    return re.fullmatch(pattern, ref.rstrip("/") or "/") is not None


def _methods(chunk: CodeChunk) -> set[str]:
    return set((chunk.http_method or "").split(","))


def _add_link(
    links: dict[tuple[str, str], Link], chunk: CodeChunk, section: DocSection, score: float
) -> None:
    key = (chunk.id, section.id)
    existing = links.get(key)
    if existing is None or score > existing.score:
        links[key] = Link(
            chunk_id=chunk.id,
            section_id=section.id,
            method=LinkMethod.EXPLICIT,
            score=score,
        )


def build_links(chunks: list[CodeChunk], sections: list[DocSection]) -> list[Link]:
    """Link doc sections to code chunks whose names or routes they mention."""
    by_qualified: dict[str, list[CodeChunk]] = defaultdict(list)
    by_short: dict[str, list[CodeChunk]] = defaultdict(list)
    for chunk in chunks:
        by_qualified[chunk.name].append(chunk)  # "Cache.clear_all"
        by_short[_last_part(chunk.name)].append(chunk)  # "clear_all"
    endpoints = [c for c in chunks if c.kind == ChunkKind.ENDPOINT and c.route]

    links: dict[tuple[str, str], Link] = {}
    for section in sections:
        mentioned_methods = {r for r in section.code_refs if r in HTTP_METHODS}
        for ref in section.code_refs:
            if ref.startswith("/"):
                candidates = [c for c in endpoints if route_matches(c.route, ref)]
                # "POST /items" should pick the POST endpoint, not the GET one.
                # If narrowing would leave nothing, keep all: the doc probably
                # names the wrong method, which is exactly what we want to catch.
                if mentioned_methods:
                    narrowed = [c for c in candidates if mentioned_methods & _methods(c)]
                    candidates = narrowed or candidates
                limit = MAX_ROUTE_CANDIDATES
            else:
                short = _last_part(ref)
                if short.startswith("__"):  # __init__ etc. appear everywhere
                    continue
                # Prefer an exact qualified match; fall back to the last part,
                # so `cache.set_item` still finds the method `Cache.set_item`.
                candidates = by_qualified.get(ref) or by_short.get(short, [])
                limit = MAX_CANDIDATES

            if not candidates or len(candidates) > limit:
                continue
            score = 1.0 / len(candidates)  # less sure when the name is ambiguous
            for chunk in candidates:
                _add_link(links, chunk, section, score)
    return list(links.values()) 