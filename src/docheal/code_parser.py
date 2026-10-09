import ast
from pathlib import Path

from docheal.models import ChunkKind, CodeChunk

SKIP_DIRS = {
    ".venv", "venv", "__pycache__", ".git", "node_modules",
    "build", "dist", "tests", "test",
}


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = ast.unparse(node.args)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({args}){returns}"


def _class_signature(node: ast.ClassDef) -> str:
    bases = ", ".join(ast.unparse(b) for b in node.bases)
    return f"class {node.name}({bases})" if bases else f"class {node.name}"


def parse_source(source: str, file_path: str) -> list[CodeChunk]:
    """Extract functions, methods and classes from Python source text."""
    tree = ast.parse(source)
    chunks: list[CodeChunk] = []

    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{node.name}"
                chunks.append(
                    CodeChunk(
                        id=f"{file_path}::{qualname}",
                        file_path=file_path,
                        name=qualname,
                        kind=ChunkKind.FUNCTION,
                        signature=_function_signature(node),
                        docstring=ast.get_docstring(node),
                        source=ast.get_source_segment(source, node) or "",
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                    )
                )
                # We do not look inside functions: nested helpers are internal.
            elif isinstance(node, ast.ClassDef):
                qualname = f"{prefix}{node.name}"
                chunks.append(
                    CodeChunk(
                        id=f"{file_path}::{qualname}",
                        file_path=file_path,
                        name=qualname,
                        kind=ChunkKind.CLASS,
                        signature=_class_signature(node),
                        docstring=ast.get_docstring(node),
                        source=ast.get_source_segment(source, node) or "",
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                    )
                )
                visit(node.body, prefix=f"{qualname}.")

    visit(tree.body)
    return chunks


def parse_file(path: Path, root: Path) -> list[CodeChunk]:
    relative = path.relative_to(root).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
        return parse_source(source, relative)
    except (SyntaxError, UnicodeDecodeError):
        return []  # skip files we can't read, instead of crashing


def parse_directory(root: Path) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        chunks.extend(parse_file(path, root))
    return chunks