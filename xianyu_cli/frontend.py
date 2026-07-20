"""Frontend API usage scanner used by CLI coverage audits."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xianyu_cli.exceptions import CliError
from xianyu_cli.openapi import Operation, feature_key, list_operations
from xianyu_cli.webmap import WEB_PAGES


@dataclass(frozen=True)
class FrontendEndpoint:
    method: str
    path: str
    source: str


@dataclass(frozen=True)
class FrontendApiFunction:
    module: str
    name: str
    method: str
    path: str
    source: str


@dataclass(frozen=True)
class ApiCall:
    name: str
    args: str
    first_arg: str
    line: int


@dataclass(frozen=True)
class FunctionSection:
    name: str
    start: int
    end: int
    line: int
    exported: bool


def audit_frontend_endpoints(openapi: dict[str, Any], frontend_root: str | Path) -> list[dict[str, object]]:
    """Compare frontend API calls with OpenAPI operations and page feature mapping."""
    operations = list_operations(openapi)
    mapped_features = {feature for page in WEB_PAGES for feature in page.features}
    rows: dict[tuple[str, str], dict[str, object]] = {}

    for endpoint in scan_frontend_endpoints(frontend_root):
        key = (endpoint.method, endpoint.path)
        row = rows.setdefault(key, _audit_row(endpoint, operations, mapped_features))
        sources = str(row["sources"])
        if endpoint.source not in sources.split(", "):
            row["sources"] = f"{sources}, {endpoint.source}" if sources else endpoint.source
    return sorted(rows.values(), key=lambda row: (str(row["status"]), str(row["path"]), str(row["method"])))


def scan_frontend_endpoints(frontend_root: str | Path) -> list[FrontendEndpoint]:
    root = Path(frontend_root)
    if not root.exists():
        raise CliError(f"前端源码目录不存在：{frontend_root}")

    endpoints: dict[tuple[str, str, str], FrontendEndpoint] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix not in {".ts", ".tsx"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for endpoint in _scan_file(path, text):
            endpoints[(endpoint.method, endpoint.path, endpoint.source)] = endpoint
    return sorted(endpoints.values(), key=lambda item: (item.path, item.method, item.source))


def scan_frontend_api_functions(frontend_root: str | Path) -> list[FrontendApiFunction]:
    """List exported frontend API functions and the HTTP calls they perform."""
    root = Path(frontend_root)
    if not root.exists():
        raise CliError(f"前端源码目录不存在：{frontend_root}")

    functions: dict[tuple[str, str, str, str, str], FrontendApiFunction] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix not in {".ts", ".tsx"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for function in _scan_file_api_functions(path, text):
            key = (function.module, function.name, function.method, function.path, function.source)
            functions[key] = function
    return sorted(functions.values(), key=lambda item: (item.module, item.name, item.path, item.method))


def _audit_row(
    endpoint: FrontendEndpoint,
    operations: list[Operation],
    mapped_features: set[str],
) -> dict[str, object]:
    operation = match_operation(endpoint, operations)
    feature = feature_key(endpoint.path)
    if not operation:
        status = "missing_openapi"
        operation_id = ""
    elif feature not in mapped_features:
        status = "unmapped_feature"
        operation_id = operation.operation_id
    else:
        status = "ok"
        operation_id = operation.operation_id
    return {
        "status": status,
        "method": endpoint.method,
        "path": endpoint.path,
        "feature": feature,
        "operation_id": operation_id,
        "sources": endpoint.source,
    }


def _scan_file(path: Path, text: str) -> list[FrontendEndpoint]:
    bindings = _collect_bindings(text)
    aliases = _collect_request_aliases(text)
    endpoints = []
    if path.name != "batchLogFactory.ts":
        for call in _find_api_calls(text, aliases):
            method = _call_method(call, aliases)
            for raw_path in _resolve_expression(call.first_arg, bindings):
                endpoint_path = _normalize_api_path(raw_path)
                if endpoint_path:
                    endpoints.append(FrontendEndpoint(method, endpoint_path, _source(path, call.line)))
        endpoints.extend(_find_returned_api_paths(path, text, bindings))
    endpoints.extend(_find_batch_log_endpoints(path, text))
    return endpoints


def _scan_file_api_functions(path: Path, text: str) -> list[FrontendApiFunction]:
    if path.name == "batchLogFactory.ts":
        return []

    bindings = _collect_bindings(text)
    aliases = _collect_request_aliases(text)
    endpoint_map = _function_endpoint_map(text, bindings, aliases)
    functions = []
    for section in _function_sections(text):
        if section.exported:
            functions.extend(_api_functions_from_section(path, section, endpoint_map))
    functions.extend(_find_batch_log_api_functions(path, text))
    return functions


def _collect_request_aliases(text: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    pattern = re.compile(r"import\s*\{([^}]+)\}\s*from\s*['\"][^'\"]*utils/request['\"]")
    for match in pattern.finditer(text):
        for item in match.group(1).split(","):
            imported, local = _parse_import_item(item)
            if imported in {"get", "post", "put", "del", "delete", "patch", "fetch"} and local != imported:
                aliases[local] = imported
    return aliases


def _parse_import_item(raw: str) -> tuple[str, str]:
    item = raw.strip()
    if not item:
        return "", ""
    if " as " not in item:
        return item, item
    imported, local = item.split(" as ", 1)
    return imported.strip(), local.strip()


def _collect_bindings(text: str) -> dict[str, list[str]]:
    bindings: dict[str, list[str]] = {}
    pattern = re.compile(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*(.+)$")
    for line in text.splitlines():
        match = pattern.search(line.strip())
        if not match:
            continue
        expression = match.group(2).rstrip(",")
        if not _is_path_binding_expression(expression, bindings):
            continue
        values = _resolve_expression(expression, bindings)
        if values:
            bindings[match.group(1)] = values
    return bindings


def _function_sections(text: str) -> list[FunctionSection]:
    pattern = re.compile(
        r"^(export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\b"
        r"|^(export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    sections = []
    for index, match in enumerate(matches):
        name = match.group(2) or match.group(4)
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        line = text.count("\n", 0, start) + 1
        exported = bool(match.group(1) or match.group(3))
        sections.append(FunctionSection(name, start, end, line, exported))
    return sections


def _api_functions_from_section(
    path: Path,
    section: FunctionSection,
    endpoint_map: dict[str, list[tuple[str, str]]],
) -> list[FrontendApiFunction]:
    module = path.stem
    source = _source(path, section.line)
    return [
        FrontendApiFunction(module, section.name, method, endpoint_path, source)
        for method, endpoint_path in endpoint_map.get(section.name, [])
    ]


def _function_endpoint_map(
    text: str,
    bindings: dict[str, list[str]],
    aliases: dict[str, str],
) -> dict[str, list[tuple[str, str]]]:
    sections = _function_sections(text)
    endpoints = {
        section.name: _endpoint_specs_from_text(text[section.start : section.end], bindings, aliases)
        for section in sections
    }
    known_names = {section.name for section in sections}
    for _ in range(4):
        changed = False
        for section in sections:
            current = list(endpoints.get(section.name, []))
            for callee in _called_local_functions(text[section.start : section.end], known_names - {section.name}):
                current.extend(endpoints.get(callee, []))
            unique = _unique_endpoint_specs(current)
            if unique != endpoints.get(section.name, []):
                endpoints[section.name] = unique
                changed = True
        if not changed:
            break
    return endpoints


def _endpoint_specs_from_text(
    text: str,
    bindings: dict[str, list[str]],
    aliases: dict[str, str],
) -> list[tuple[str, str]]:
    endpoints = []
    for call in _find_api_calls(text, aliases):
        method = _call_method(call, aliases)
        for raw_path in _resolve_expression(call.first_arg, bindings):
            endpoint_path = _normalize_api_path(raw_path)
            if endpoint_path:
                endpoints.append((method, endpoint_path))
    endpoints.extend(("GET", endpoint_path) for _, endpoint_path in _returned_api_paths(text, bindings))
    return _unique_endpoint_specs(endpoints)


def _called_local_functions(text: str, names: set[str]) -> list[str]:
    calls = []
    for match in re.finditer(r"\b([A-Za-z_$][\w$]*)\s*\(", text):
        name = match.group(1)
        if name in names and name not in calls:
            calls.append(name)
    return calls


def _unique_endpoint_specs(endpoints: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return list(dict.fromkeys(endpoints))


def _find_api_calls(text: str, aliases: dict[str, str] | None = None) -> list[ApiCall]:
    calls = []
    aliases = aliases or {}
    names = sorted({"get", "post", "put", "del", "delete", "patch", "fetch", *aliases}, key=len, reverse=True)
    pattern = re.compile(rf"(?:(?:axios|request)\.)?\b({'|'.join(re.escape(name) for name in names)})\b")
    for match in pattern.finditer(text):
        open_index = text.find("(", match.end())
        if open_index < 0 or _has_blocking_token(text[match.end() : open_index]):
            continue
        args, close_index = _extract_parenthesized(text, open_index)
        if close_index < 0:
            continue
        parts = _split_top_level_args(args)
        if parts:
            calls.append(ApiCall(match.group(1), args, parts[0], text.count("\n", 0, match.start()) + 1))
    return calls


def _find_returned_api_paths(path: Path, text: str, bindings: dict[str, list[str]]) -> list[FrontendEndpoint]:
    endpoints = []
    for line_number, endpoint_path in _returned_api_paths(text, bindings):
        endpoints.append(FrontendEndpoint("GET", endpoint_path, _source(path, line_number)))
    return endpoints


def _returned_api_paths(text: str, bindings: dict[str, list[str]]) -> list[tuple[int, str]]:
    paths = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        expression = _returned_expression(line, bindings)
        if not expression:
            continue
        for raw_path in _resolve_expression(expression, bindings):
            endpoint_path = _normalize_api_path(raw_path)
            if endpoint_path:
                paths.append((line_number, endpoint_path))
    return paths


def _returned_expression(line: str, bindings: dict[str, list[str]]) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("return "):
        return None
    expression = stripped.removeprefix("return ").strip()
    if expression.startswith(("'", '"', "`")) or expression in bindings:
        return expression
    return None


def _find_batch_log_endpoints(path: Path, text: str) -> list[FrontendEndpoint]:
    endpoints = []
    for spec in _batch_log_specs(text):
        if spec["batches"]:
            endpoints.append(FrontendEndpoint("GET", f"/api/v1/admin/{spec['batches']}", _source(path, spec["line"])))
            endpoints.append(
                FrontendEndpoint("GET", f"/api/v1/admin/{spec['batches']}/{{batch_id}}", _source(path, spec["line"]))
            )
        if spec["clear_logs"]:
            endpoints.append(FrontendEndpoint("DELETE", f"/api/v1/admin/{spec['clear_logs']}", _source(path, spec["line"])))
    return endpoints


def _find_batch_log_api_functions(path: Path, text: str) -> list[FrontendApiFunction]:
    specs = {str(spec["variable"]): spec for spec in _batch_log_specs(text)}
    functions = []
    pattern = re.compile(r"^\s*export\s+const\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\.(\w+)", re.MULTILINE)
    for match in pattern.finditer(text):
        spec = specs.get(match.group(2))
        endpoint = _batch_log_export_endpoint(spec, match.group(3)) if spec else None
        if endpoint:
            method, endpoint_path = endpoint
            line = text.count("\n", 0, match.start()) + 1
            functions.append(FrontendApiFunction(path.stem, match.group(1), method, endpoint_path, _source(path, line)))
    return functions


def _batch_log_specs(text: str) -> list[dict[str, object]]:
    specs = []
    pattern = re.compile(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*createBatchLogApi[\s\S]*?\(\s*\{([\s\S]*?)\}\s*\)")
    for match in pattern.finditer(text):
        specs.append(
            {
                "variable": match.group(1),
                "line": text.count("\n", 0, match.start()) + 1,
                "batches": _object_string_property(match.group(2), "batches"),
                "clear_logs": _object_string_property(match.group(2), "clearLogs"),
            }
        )
    return specs


def _batch_log_export_endpoint(spec: dict[str, object], member: str) -> tuple[str, str] | None:
    batches = str(spec.get("batches") or "")
    clear_logs = str(spec.get("clear_logs") or "")
    if member == "getBatches" and batches:
        return "GET", f"/api/v1/admin/{batches}"
    if member == "getBatchDetail" and batches:
        return "GET", f"/api/v1/admin/{batches}/{{batch_id}}"
    if member == "clearLogs" and clear_logs:
        return "DELETE", f"/api/v1/admin/{clear_logs}"
    return None


def _resolve_expression(expression: str, bindings: dict[str, list[str]]) -> list[str]:
    expression = expression.strip().rstrip(",")
    if not expression:
        return []
    if expression in bindings:
        return bindings[expression]
    if expression.startswith(("'", '"')) and len(expression) >= 2:
        return [_strip_string(expression)]
    if expression.startswith("`"):
        return [_resolve_template(_strip_template(expression), bindings)]
    if "?" in expression and ":" in expression:
        return _resolve_ternary(expression, bindings)
    return [_resolve_template(value, bindings) for value in _string_like_values(expression)]


def _is_path_binding_expression(expression: str, bindings: dict[str, list[str]]) -> bool:
    expression = expression.strip()
    if expression in bindings:
        return True
    if expression.startswith(("'", '"', "`")):
        return True
    return "?" in expression and ":" in expression and any(quote in expression for quote in ("'", '"', "`"))


def _resolve_ternary(expression: str, bindings: dict[str, list[str]]) -> list[str]:
    _, _, branches = expression.partition("?")
    truthy, _, falsy = branches.partition(":")
    return [*(_resolve_expression(truthy, bindings)), *(_resolve_expression(falsy, bindings))]


def _string_like_values(expression: str) -> list[str]:
    values = []
    for quote in ("'", '"'):
        values.extend(match.group(1) for match in re.finditer(rf"{quote}([^ {quote}]*?/api/v1[^ {quote}]*){quote}", expression))
    values.extend(_strip_template(match.group(0)) for match in re.finditer(r"`[^`]*?/api/v1[^`]*`", expression))
    return values


def _resolve_template(value: str, bindings: dict[str, list[str]]) -> str:
    def replace(match: re.Match[str]) -> str:
        expression = match.group(1).strip()
        if expression in bindings and len(bindings[expression]) == 1:
            return bindings[expression][0]
        return f"{{{_placeholder_name(expression)}}}"

    return re.sub(r"\$\{([^}]+)\}", replace, value)


def _normalize_api_path(path: str) -> str | None:
    path = path.strip().rstrip(";")
    if not path.startswith("/api/v1"):
        return None
    path = re.sub(r"\$\{.*$", "", path)
    path = re.sub(
        r"\{(?:buildBatchesQuery|params|query|queryString|qs|searchParams|suffix|toString)\}$",
        "",
        path,
    )
    path = path.split("?", 1)[0].rstrip("/")
    return re.sub(r":([A-Za-z_][\w]*)", r"{\1}", path)


def match_operation(endpoint: FrontendEndpoint | FrontendApiFunction, operations: list[Operation]) -> Operation | None:
    for operation in operations:
        if operation.method == endpoint.method and _paths_match(endpoint.path, operation.path):
            return operation
    return None


def _paths_match(frontend_path: str, operation_path: str) -> bool:
    frontend_segments = frontend_path.strip("/").split("/")
    operation_segments = operation_path.strip("/").split("/")
    if len(frontend_segments) != len(operation_segments):
        return False
    return all(_segments_match(frontend, operation) for frontend, operation in zip(frontend_segments, operation_segments))


def _segments_match(frontend_segment: str, operation_segment: str) -> bool:
    return (
        frontend_segment == operation_segment
        or re.fullmatch(r"\{[^}]+\}", frontend_segment) is not None
        or re.fullmatch(r"\{[^}]+\}", operation_segment) is not None
    )


def _call_method(call: ApiCall, aliases: dict[str, str] | None = None) -> str:
    name = (aliases or {}).get(call.name, call.name)
    if name == "del" or name == "delete":
        return "DELETE"
    if name == "fetch":
        match = re.search(r"\bmethod\s*:\s*['\"]([A-Za-z]+)['\"]", call.args)
        return match.group(1).upper() if match else "GET"
    return name.upper()


def _split_top_level_args(args: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote = ""
    for index, char in enumerate(args):
        quote = _next_quote_state(args, index, quote)
        if quote:
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(args[start:index].strip())
            start = index + 1
    tail = args[start:].strip()
    return [*parts, tail] if tail else parts


def _extract_parenthesized(text: str, open_index: int) -> tuple[str, int]:
    depth = 0
    quote = ""
    for index in range(open_index, len(text)):
        char = text[index]
        quote = _next_quote_state(text, index, quote)
        if quote:
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_index + 1 : index], index
    return "", -1


def _next_quote_state(text: str, index: int, quote: str) -> str:
    char = text[index]
    if char not in "'\"`":
        return quote
    if index > 0 and text[index - 1] == "\\":
        return quote
    if not quote:
        return char
    return "" if quote == char else quote


def _strip_string(expression: str) -> str:
    quote = expression[0]
    end = expression.find(quote, 1)
    return expression[1:end] if end > 0 else expression.strip(quote)


def _strip_template(expression: str) -> str:
    end = expression.find("`", 1)
    return expression[1:end] if expression.startswith("`") and end > 0 else expression.strip("`")


def _placeholder_name(expression: str) -> str:
    names = re.findall(r"[A-Za-z_$][\w$]*", expression)
    if len(names) > 1 and names[0] in {"encodeURIComponent", "Number", "String"}:
        return names[1]
    if len(names) > 1 and names[-1] in {"toString", "trim"}:
        return names[-2]
    return names[-1] if names else "value"


def _object_string_property(raw_object: str, key: str) -> str | None:
    match = re.search(rf"\b{key}\s*:\s*['\"]([^'\"]+)['\"]", raw_object)
    return match.group(1) if match else None


def _has_blocking_token(raw: str) -> bool:
    return any(token in raw for token in ("=", "=>"))


def _source(path: Path, line: int) -> str:
    return f"{path}:{line}"
