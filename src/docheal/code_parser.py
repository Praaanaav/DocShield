import ast
import textwrap
from pathlib import Path

from docheal.models import ChunkKind, CodeChunk

SKIP_DIRS = {
    ".venv", "venv", "__pycache__", ".git", "node_modules",
    "build", "dist", "tests", "test",
}

HTTP_VERBS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}
ROUTE_ATTRS = HTTP_VERBS | {"route", "api_route", "websocket"}


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = ast.unparse(node.args)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({args}){returns}"


def _class_signature(node: ast.ClassDef) -> str:
    bases = ", ".join(ast.unparse(b) for b in node.bases)
    return f"class {node.name}({bases})" if bases else f"class {node.name}"


def _string_constant(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _methods_from_keyword(call: ast.Call) -> list[str]:
    """Read methods=["GET", "POST"] from a decorator call."""
    for keyword in call.keywords:
        if keyword.arg == "methods" and isinstance(
            keyword.value, (ast.List, ast.Tuple, ast.Set)
        ):
            methods = [_string_constant(element) for element in keyword.value.elts]
            return [m.upper() for m in methods if m]
    return []


def _endpoint_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, str] | None:
    """Return (route, http_method) if a decorator looks like @app.get("/path")."""
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Attribute):
            continue
        attr = decorator.func.attr
        if attr not in ROUTE_ATTRS:
            continue

        path = None
        if decorator.args:
            path = _string_constant(decorator.args[0])
        else:
            for keyword in decorator.keywords:
                if keyword.arg == "path":
                    path = _string_constant(keyword.value)
        # Real routes start with "/". This also rejects look-alikes such as
        # @mock.patch("module.thing").
        if path is None or not path.startswith("/"):
            continue

        if attr in HTTP_VERBS:
            method = attr.upper()
        elif attr == "websocket":
            method = "WEBSOCKET"
        else:
            method = ",".join(_methods_from_keyword(decorator)) or "GET"
        return path, method
    return None


def parse_source(source: str, file_path: str) -> list[CodeChunk]:
    """Extract functions, methods, endpoints and classes from Python source text."""
    tree = ast.parse(source)
    source_lines = source.splitlines()
    chunks: list[CodeChunk] = []

    def make_chunk(
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        qualname: str,
        kind: ChunkKind,
        signature: str,
        route: str | None = None,
        http_method: str | None = None,
    ) -> CodeChunk:
        # A node's own line number points at "def", not at its decorators,
        # so look at the decorators too. For endpoints the route lives there.
        start = min([d.lineno for d in node.decorator_list] + [node.lineno])
        end = node.end_lineno or node.lineno
        return CodeChunk(
            id=f"{file_path}::{qualname}",
            file_path=file_path,
            name=qualname,
            kind=kind,
            signature=signature,
            docstring=ast.get_docstring(node),
            source=textwrap.dedent("\n".join(source_lines[start - 1 : end])),
            start_line=start,
            end_line=end,
            route=route,
            http_method=http_method,
        )

    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{node.name}"
                signature = _function_signature(node)
                endpoint = _endpoint_info(node)
                if endpoint:
                    route, method = endpoint
                    chunks.append(
                        make_chunk(
                            node, qualname, ChunkKind.ENDPOINT, signature,
                            route=route, http_method=method,
                        )
                    )
                else:
                    chunks.append(make_chunk(node, qualname, ChunkKind.FUNCTION, signature))
                # We do not look inside functions: nested helpers are internal.
            elif isinstance(node, ast.ClassDef):
                qualname = f"{prefix}{node.name}"
                chunks.append(
                    make_chunk(node, qualname, ChunkKind.CLASS, _class_signature(node))
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