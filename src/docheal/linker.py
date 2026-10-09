from collections import defaultdict

from docheal.models import CodeChunk, DocSection, Link, LinkMethod

# A name that matches more chunks than this (like "run" or "get") is too
# generic to say anything about which code a doc section describes.
MAX_CANDIDATES = 3


def _last_part(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def build_links(chunks: list[CodeChunk], sections: list[DocSection]) -> list[Link]:
    """Link doc sections to code chunks whose names they mention."""
    by_qualified: dict[str, list[CodeChunk]] = defaultdict(list)
    by_short: dict[str, list[CodeChunk]] = defaultdict(list)
    for chunk in chunks:
        by_qualified[chunk.name].append(chunk)  # "Cache.clear_all"
        by_short[_last_part(chunk.name)].append(chunk)  # "clear_all"

    links: dict[tuple[str, str], Link] = {}
    for section in sections:
        for ref in section.code_refs:
            short = _last_part(ref)
            if short.startswith("__"):  # __init__ etc. appear everywhere
                continue

            # Prefer an exact qualified match; fall back to the last part,
            # so `cache.set_item` still finds the method `Cache.set_item`.
            candidates = by_qualified.get(ref) or by_short.get(short, [])
            if not candidates or len(candidates) > MAX_CANDIDATES:
                continue

            score = 1.0 / len(candidates)  # less sure when the name is ambiguous
            for chunk in candidates:
                key = (chunk.id, section.id)
                existing = links.get(key)
                if existing is None or score > existing.score:
                    links[key] = Link(
                        chunk_id=chunk.id,
                        section_id=section.id,
                        method=LinkMethod.EXPLICIT,
                        score=score,
                    )
    return list(links.values())