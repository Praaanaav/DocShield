import ast
import textwrap
from pathlib import Path

from docheal.models import ChunkKind, CliOption, CodeChunk, ConfigField

SKIP_DIRS = {
    ".venv", "venv", "__pycache__", ".git", "node_modules",
    "build", "dist", "tests", "test",
}

HTTP_VERBS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}
ROUTE_ATTRS = HTTP_VERBS | {"route", "api_route", "websocket"}

CONFIG_NAME_SUFFIXES = ("Config", "Configuration", "Settings", "Options")
MODEL_BASES = {"BaseModel", "TypedDict"}

CLI_DECORATORS = {"command", "group"}  # @click.command(), @app.command() (typer)
CLICK_MARKERS = {"option", "argument"}
TYPER_MARKERS = {"Option", "Argument"}


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


def _tail_name(node: ast.expr) -> str:
    """'pydantic.BaseModel' -> 'BaseModel', 'Generic[T]' -> 'Generic'."""
    return ast.unparse(node).split("[")[0].rsplit(".", 1)[-1]


def _decorator_tail(decorator: ast.expr) -> str:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    return _tail_name(target)


# --- endpoints -------------------------------------------------------------


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


# --- config schemas --------------------------------------------------------


def _is_dataclass(node: ast.ClassDef) -> bool:
    return any(_decorator_tail(decorator) == "dataclass" for decorator in node.decorator_list)


def _is_config_class(node: ast.ClassDef) -> bool:
    bases = {_tail_name(base) for base in node.bases}
    if "BaseSettings" in bases:
        return True
    structured = _is_dataclass(node) or bool(bases & MODEL_BASES)
    return structured and node.name.endswith(CONFIG_NAME_SUFFIXES)


def _field_default(value: ast.expr | None) -> str | None:
    """Source text of a field's default, or None if the field is required."""
    if value is None:
        return None
    if isinstance(value, ast.Call) and _tail_name(value.func) in {"Field", "field"}:
        for keyword in value.keywords:
            if keyword.arg == "default":
                return ast.unparse(keyword.value)
            if keyword.arg == "default_factory":
                return f"{ast.unparse(keyword.value)}()"
        if value.args and ast.unparse(value.args[0]) != "...":
            return ast.unparse(value.args[0])
        return None  # Field(...) or Field(description=...) means required
    return ast.unparse(value)


def _config_fields(node: ast.ClassDef) -> list[ConfigField]:
    fields: list[ConfigField] = []
    for statement in node.body:
        if not isinstance(statement, ast.AnnAssign):
            continue
        if not isinstance(statement.target, ast.Name):
            continue
        name = statement.target.id
        annotation = ast.unparse(statement.annotation)
        if name.startswith("_") or annotation.startswith(("ClassVar", "typing.ClassVar")):
            continue
        fields.append(
            ConfigField(name=name, type=annotation, default=_field_default(statement.value))
        )
    return fields


# --- CLI commands ----------------------------------------------------------


def _keyword_source(call: ast.Call, name: str) -> str | None:
    """Source text of a keyword argument, e.g. default=30 -> "30"."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return ast.unparse(keyword.value)
    return None


def _keyword_help(call: ast.Call) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == "help":
            return _string_constant(keyword.value) or ast.unparse(keyword.value)
    return None


def _flag_strings(call: ast.Call) -> list[str]:
    """String arguments like "-t", "--timeout" or "--shout/--no-shout"."""
    flags: list[str] = []
    for arg in call.args:
        text = _string_constant(arg)
        if text:
            flags.extend(part for part in text.split("/") if part.startswith("-"))
    return flags


def _option_from_call(call: ast.Call) -> CliOption | None:
    """Build an option from add_argument(...), click.option(...) or click.argument(...)."""
    flags = _flag_strings(call)
    if not flags:  # a positional argument such as add_argument("key")
        names = [text for arg in call.args if (text := _string_constant(arg))]
        flags = names[:1]
    if not flags:
        return None
    return CliOption(
        flags=flags,
        default=_keyword_source(call, "default"),
        help=_keyword_help(call),
    )


def _argparse_options(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[CliOption]:
    calls = sorted(
        (
            child
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "add_argument"
        ),
        key=lambda call: (call.lineno, call.col_offset),  # keep source order
    )
    options = [_option_from_call(call) for call in calls]
    return [option for option in options if option]


def _click_options(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[CliOption]:
    options: list[CliOption] = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and _tail_name(decorator.func) in CLICK_MARKERS:
            option = _option_from_call(decorator)
            if option:
                options.append(option)
    return options


def _params_with_defaults(args: ast.arguments) -> list[tuple[ast.arg, ast.expr | None]]:
    positional = args.posonlyargs + args.args
    padding: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    pairs = list(zip(positional, padding + list(args.defaults)))
    pairs += list(zip(args.kwonlyargs, args.kw_defaults))
    return pairs


def _annotated_marker(annotation: ast.expr | None) -> ast.Call | None:
    """Typer's modern style: timeout: Annotated[int, typer.Option("--timeout")] = 30."""
    if isinstance(annotation, ast.Subscript) and _tail_name(annotation.value) == "Annotated":
        elements = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else []
        for element in elements[1:]:
            if isinstance(element, ast.Call) and _tail_name(element.func) in TYPER_MARKERS:
                return element
    return None


def _typer_default(call: ast.Call) -> str | None:
    """Default inside typer.Option(3, ...) or typer.Option(default=3)."""
    default = _keyword_source(call, "default")
    if default is not None:
        return default
    if call.args:
        first = call.args[0]
        is_flag = (_string_constant(first) or "").startswith("-")
        is_required = isinstance(first, ast.Constant) and first.value is Ellipsis
        if not is_flag and not is_required:
            return ast.unparse(first)
    return None


def _typer_options(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[CliOption]:
    """Typer builds its options from the function's parameters."""
    options: list[CliOption] = []
    for param, default in _params_with_defaults(node.args):
        name = param.arg
        annotation = ast.unparse(param.annotation) if param.annotation else ""
        if name in {"self", "cls", "ctx", "context"} or annotation.endswith("Context"):
            continue

        marker = _annotated_marker(param.annotation)
        default_text = ast.unparse(default) if default is not None else None
        if (
            marker is None
            and isinstance(default, ast.Call)
            and _tail_name(default.func) in TYPER_MARKERS
        ):
            marker = default
            default_text = _typer_default(default)

        if marker is not None and _tail_name(marker.func) == "Argument":
            flags = [name]
        elif marker is not None:
            flags = _flag_strings(marker) or [f"--{name.replace('_', '-')}"]
        elif default is None:
            flags = [name]  # a required plain parameter is a positional argument
        else:
            flags = [f"--{name.replace('_', '-')}"]

        help_text = _keyword_help(marker) if marker is not None else None
        options.append(CliOption(flags=flags, default=default_text, help=help_text))
    return options


def _cli_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[CliOption] | None:
    """The command's options if this function defines a CLI command, else None."""
    if any(_decorator_tail(d) in CLI_DECORATORS for d in node.decorator_list):
        is_click = any(
            isinstance(d, ast.Call) and _tail_name(d.func) in CLICK_MARKERS
            for d in node.decorator_list
        )
        return _click_options(node) if is_click else _typer_options(node)
    return _argparse_options(node) or None


# --- main parser -----------------------------------------------------------


def parse_source(source: str, file_path: str) -> list[CodeChunk]:
    """Extract functions, methods, endpoints, CLI commands, config schemas and classes."""
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
        config_fields: list[ConfigField] | None = None,
        cli_options: list[CliOption] | None = None,
    ) -> CodeChunk:
        # A node's own line number points at "def"/"class", not at its
        # decorators, so look at the decorators too. For endpoints the route
        # lives there, and for click commands so do the options.
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
            config_fields=config_fields or [],
            cli_options=cli_options or [],
        )

    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{node.name}"
                signature = _function_signature(node)
                endpoint = _endpoint_info(node)
                cli_options = None if endpoint else _cli_info(node)
                if endpoint:
                    route, method = endpoint
                    chunks.append(
                        make_chunk(
                            node, qualname, ChunkKind.ENDPOINT, signature,
                            route=route, http_method=method,
                        )
                    )
                elif cli_options is not None:
                    chunks.append(
                        make_chunk(
                            node, qualname, ChunkKind.CLI, signature,
                            cli_options=cli_options,
                        )
                    )
                else:
                    chunks.append(make_chunk(node, qualname, ChunkKind.FUNCTION, signature))
                # We do not look inside functions: nested helpers are internal.
            elif isinstance(node, ast.ClassDef):
                qualname = f"{prefix}{node.name}"
                signature = _class_signature(node)
                if _is_config_class(node):
                    chunks.append(
                        make_chunk(
                            node, qualname, ChunkKind.CONFIG, signature,
                            config_fields=_config_fields(node),
                        )
                    )
                else:
                    chunks.append(make_chunk(node, qualname, ChunkKind.CLASS, signature))
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