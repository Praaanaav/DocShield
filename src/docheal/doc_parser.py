import keyword
import re
from pathlib import Path

from docheal.models import DocSection

ROUTE_RE = re.compile(r"(?<![\w.:/])/[\w\-./{}:<>]*")
URL_PATH_RE = re.compile(r"https?://[^/\s'\"]+(/[\w\-./{}:<>%]*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
FLAG_RE = re.compile(r"(?<![\w-])--[A-Za-z][A-Za-z0-9-]*")
SKIP_DIRS = {".venv", "venv", ".git", "node_modules", "build", "dist", "site"}
IGNORED_WORDS = {"True", "False", "None"}

def _routes_in(segment: str) -> set[str]:
    """Find URL paths like /items/{id}, including the path part of full URLs."""
    found = set(ROUTE_RE.findall(segment)) | set(URL_PATH_RE.findall(segment))
    cleaned = {route.rstrip(".,:;") for route in found}
    return {route for route in cleaned if len(route) > 1}

def extract_code_refs(text: str) -> list[str]:
    """Collect names that look like code: inline `code` spans, fenced blocks, CLI flags, routes."""
    refs: set[str] = set()
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        segments = [line] if in_fence else INLINE_CODE_RE.findall(line)
        for segment in segments:
            refs.update(FLAG_RE.findall(segment))
            refs.update(_routes_in(segment))  # <- new
            for token in IDENT_RE.findall(segment):
                if len(token) < 2 or keyword.iskeyword(token) or token in IGNORED_WORDS:
                    continue
                refs.add(token)
    return sorted(refs)

def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"\s+", "-", slug) or "section"


def parse_markdown(text: str, file_path: str) -> list[DocSection]:
    """Split markdown into sections, one per heading."""
    lines = text.splitlines()

    # Pass 1: find headings, ignoring anything inside fenced code blocks.
    headings: list[tuple[int, int, str]] = []  # (line index, level, title)
    in_fence = False
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append((i, len(match.group(1)), match.group(2).strip()))

    sections: list[DocSection] = []

    # Text before the first heading becomes an intro section.
    first = headings[0][0] if headings else len(lines)
    intro = "\n".join(lines[:first])
    if intro.strip():
        sections.append(
            DocSection(
                id=f"{file_path}#_intro",
                file_path=file_path,
                heading_path=[],
                content=intro,
                start_line=1,
                end_line=first,
                code_refs=extract_code_refs(intro),
            )
        )

    # Pass 2: each heading owns the lines up to the next heading.
    stack: list[tuple[int, str]] = []
    seen: dict[str, int] = {}
    for n, (start, level, title) in enumerate(headings):
        end = headings[n + 1][0] if n + 1 < len(headings) else len(lines)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))

        slug = _slugify(title)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        if count:
            slug = f"{slug}-{count}"

        content = "\n".join(lines[start:end])
        sections.append(
            DocSection(
                id=f"{file_path}#{slug}",
                file_path=file_path,
                heading_path=[t for _, t in stack],
                content=content,
                start_line=start + 1,
                end_line=end,
                code_refs=extract_code_refs(content),
            )
        )
    return sections


def parse_markdown_file(path: Path, root: Path) -> list[DocSection]:
    relative = path.relative_to(root).as_posix()
    try:
        return parse_markdown(path.read_text(encoding="utf-8"), relative)
    except UnicodeDecodeError:
        return []


def parse_docs_directory(root: Path) -> list[DocSection]:
    sections: list[DocSection] = []
    for path in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        sections.extend(parse_markdown_file(path, root))
    return sections