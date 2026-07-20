"""OpenAPI helpers for route discovery and operation calls."""
from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from typing import Any

from xianyu_cli.exceptions import CliError


@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    operation_id: str
    summary: str
    tags: list[str]
    raw: dict[str, Any]


def list_operations(openapi: dict[str, Any]) -> list[Operation]:
    operations: list[Operation] = []
    paths = openapi.get("paths") or {}
    if not isinstance(paths, dict):
        return operations

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, spec in path_item.items():
            if method.lower() not in {"get", "post", "put", "delete", "patch"} or not isinstance(spec, dict):
                continue
            operations.append(
                Operation(
                    method=method.upper(),
                    path=path,
                    operation_id=str(spec.get("operationId") or f"{method}_{path}"),
                    summary=str(spec.get("summary") or ""),
                    tags=[str(tag) for tag in spec.get("tags") or []],
                    raw=spec,
                )
            )
    return sorted(operations, key=lambda item: (item.tags, item.path, item.method))


def find_operation(openapi: dict[str, Any], operation_id: str) -> Operation:
    for operation in list_operations(openapi):
        if operation.operation_id == operation_id:
            return operation
    raise CliError(f"未找到 operationId：{operation_id}")


def feature_key(path: str) -> str:
    normalized = path.strip("/")
    if normalized.startswith("api/v1/"):
        normalized = normalized[len("api/v1/"):]
    if not normalized:
        return "root"
    return normalized.split("/", 1)[0] or "root"


def operation_slug(operation: Operation) -> str:
    key = feature_key(operation.path)
    relative = operation.path.strip("/")
    if relative.startswith("api/v1/"):
        relative = relative[len("api/v1/"):]
    if relative.startswith(f"{key}/"):
        relative = relative[len(key) + 1:]
    elif relative == key:
        relative = ""

    method_prefix = {
        "GET": "get",
        "POST": "post",
        "PUT": "put",
        "DELETE": "delete",
        "PATCH": "patch",
    }.get(operation.method, operation.method.lower())

    if not relative:
        return {
            "GET": "list",
            "POST": "create",
            "PUT": "update",
            "DELETE": "delete",
            "PATCH": "patch",
        }.get(operation.method, method_prefix)

    sanitized = re.sub(r"[{}]", "", relative)
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "-", sanitized).strip("-").lower()
    return f"{method_prefix}-{sanitized}" if sanitized else method_prefix


def operation_inputs(operation: Operation) -> str:
    parts: list[str] = []
    for location in ("path", "query"):
        names = _parameter_names(operation, location)
        if names:
            parts.append(f"{location}:{','.join(names)}")

    body = _request_body_type(operation)
    if body:
        parts.append(body)
    return " ".join(parts)


def operation_is_smoke_safe(operation: Operation) -> bool:
    """Return true when an operation is safe for automatic smoke requests."""
    if operation.method != "GET" or "{" in operation.path or operation.raw.get("requestBody"):
        return False
    return not _required_parameters(operation) and _operation_returns_json(operation)


def operation_command_template(
    openapi: dict[str, Any],
    operation: Operation,
    command_parts: list[str],
    *,
    include_optional: bool = False,
) -> str:
    """Build an executable-ish CLI command for an OpenAPI operation."""
    parts = [*command_parts, *_operation_argument_parts(openapi, operation, include_optional=include_optional)]
    return " ".join(shlex.quote(part) for part in parts)


def _operation_argument_parts(
    openapi: dict[str, Any], operation: Operation, *, include_optional: bool
) -> list[str]:
    parts: list[str] = []
    for parameter in _parameters(operation, "path"):
        parts.extend(["-p", f"{parameter['name']}=<{parameter['name']}>"])
    for parameter in _parameters(operation, "query"):
        if include_optional or parameter.get("required"):
            parts.extend(["-q", f"{parameter['name']}=<{parameter['name']}>"])
    parts.extend(_request_body_parts(openapi, operation, include_optional=include_optional))
    return parts


def _parameter_names(operation: Operation, location: str) -> list[str]:
    names = []
    for parameter in _parameters(operation, location):
        name = str(parameter.get("name") or "")
        if name:
            names.append(f"{name}*" if parameter.get("required") else name)
    return names


def _parameters(operation: Operation, location: str) -> list[dict[str, Any]]:
    return [
        parameter
        for parameter in operation.raw.get("parameters") or []
        if isinstance(parameter, dict) and parameter.get("in") == location and parameter.get("name")
    ]


def _required_parameters(operation: Operation) -> list[dict[str, Any]]:
    return [
        parameter
        for parameter in operation.raw.get("parameters") or []
        if isinstance(parameter, dict) and parameter.get("required")
    ]


def _request_body_type(operation: Operation) -> str | None:
    request_body = operation.raw.get("requestBody")
    if not isinstance(request_body, dict):
        return None

    content = request_body.get("content") or {}
    if not isinstance(content, dict) or not content:
        return "body:*" if request_body.get("required") else "body"

    body_type = _content_type_label(content)
    suffix = "*" if request_body.get("required") else ""
    return f"body:{body_type}{suffix}"


def _request_body_parts(
    openapi: dict[str, Any], operation: Operation, *, include_optional: bool
) -> list[str]:
    content = _request_body_content(operation)
    if not content:
        return []
    if "multipart/form-data" in content:
        return _multipart_body_parts(openapi, content["multipart/form-data"], include_optional=include_optional)
    if "application/x-www-form-urlencoded" in content:
        return _form_body_parts(openapi, content["application/x-www-form-urlencoded"], include_optional=include_optional)
    if "application/json" in content:
        sample = _json_sample(openapi, content["application/json"], include_optional=include_optional)
        return ["-d", json.dumps(sample, ensure_ascii=False, separators=(",", ":"))]
    return []


def _request_body_content(operation: Operation) -> dict[str, Any]:
    request_body = operation.raw.get("requestBody")
    if not isinstance(request_body, dict):
        return {}
    content = request_body.get("content")
    return content if isinstance(content, dict) else {}


def _multipart_body_parts(
    openapi: dict[str, Any], media: dict[str, Any], *, include_optional: bool
) -> list[str]:
    schema = _resolve_schema(openapi, media.get("schema") if isinstance(media, dict) else None)
    fields = _schema_fields(schema, include_optional=include_optional)
    if not fields:
        return ["-F", "file=./file"]
    return _field_parts(fields)


def _form_body_parts(openapi: dict[str, Any], media: dict[str, Any], *, include_optional: bool) -> list[str]:
    schema = _resolve_schema(openapi, media.get("schema") if isinstance(media, dict) else None)
    return [part for name in _schema_fields(schema, include_optional=include_optional) for part in ("-f", f"{name}=<{name}>")]


def _field_parts(fields: list[tuple[str, dict[str, Any]]]) -> list[str]:
    parts: list[str] = []
    for name, schema in fields:
        if _is_file_field(name, schema):
            parts.extend(["-F", f"{name}=./{name}"])
        else:
            parts.extend(["-f", f"{name}=<{name}>"])
    return parts


def _is_file_field(name: str, schema: dict[str, Any]) -> bool:
    field_name = name.lower()
    return (
        schema.get("format") == "binary"
        or bool(schema.get("contentMediaType"))
        or field_name in {"file", "image", "avatar", "upload"}
    )


def _json_sample(openapi: dict[str, Any], media: dict[str, Any], *, include_optional: bool) -> Any:
    schema = _resolve_schema(openapi, media.get("schema") if isinstance(media, dict) else None)
    return _schema_sample(openapi, schema, include_optional=include_optional)


def _schema_sample(openapi: dict[str, Any], schema: Any, *, include_optional: bool) -> Any:
    schema = _resolve_schema(openapi, schema)
    if not isinstance(schema, dict):
        return {}
    if "anyOf" in schema or "oneOf" in schema:
        choices = schema.get("anyOf") or schema.get("oneOf") or []
        return _schema_sample(openapi, choices[0] if choices else {}, include_optional=include_optional)
    if schema.get("type") == "array":
        return []
    if schema.get("type") == "object" or "properties" in schema:
        return _object_sample(openapi, schema, include_optional=include_optional)
    return _scalar_sample(schema)


def _object_sample(openapi: dict[str, Any], schema: dict[str, Any], *, include_optional: bool) -> dict[str, Any]:
    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        return {}
    required = set(schema.get("required") or [])
    selected = [name for name in properties if include_optional or name in required or not required]
    return {
        name: _schema_sample(openapi, properties[name], include_optional=include_optional)
        for name in selected
    }


def _scalar_sample(schema: dict[str, Any]) -> Any:
    if "default" in schema:
        return schema["default"]
    schema_type = schema.get("type")
    if schema_type in {"integer", "number"}:
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None
    return "<value>"


def _schema_fields(schema: dict[str, Any], *, include_optional: bool) -> list[tuple[str, dict[str, Any]]]:
    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        return []
    required = set(schema.get("required") or [])
    return [
        (name, prop if isinstance(prop, dict) else {})
        for name, prop in properties.items()
        if include_optional or name in required or not required
    ]


def _resolve_schema(openapi: dict[str, Any], schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        resolved = _resolve_ref(openapi, ref)
        return resolved if isinstance(resolved, dict) else {}
    return schema


def _resolve_ref(openapi: dict[str, Any], ref: str) -> Any:
    current: Any = openapi
    for part in ref.removeprefix("#/").split("/"):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _content_type_label(content: dict[str, Any]) -> str:
    types = set(content)
    if "multipart/form-data" in types:
        return "multipart"
    if "application/json" in types:
        return "json"
    if "application/x-www-form-urlencoded" in types:
        return "form"
    return ",".join(sorted(types))


def _operation_returns_json(operation: Operation) -> bool:
    responses = operation.raw.get("responses")
    if not isinstance(responses, dict):
        return True
    for response in responses.values():
        if not isinstance(response, dict):
            continue
        content = response.get("content")
        if not isinstance(content, dict) or not content:
            continue
        return any("json" in content_type for content_type in content)
    return True


def group_operations_by_feature(openapi: dict[str, Any]) -> dict[str, list[Operation]]:
    grouped: dict[str, list[Operation]] = {}
    for operation in list_operations(openapi):
        grouped.setdefault(feature_key(operation.path), []).append(operation)
    return dict(sorted(grouped.items()))


def find_feature_operation(openapi: dict[str, Any], feature: str, slug: str) -> Operation:
    operations = group_operations_by_feature(openapi).get(feature)
    if not operations:
        raise CliError(f"未找到功能模块：{feature}")

    matches = [operation for operation in operations if operation_slug(operation) == slug]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        choices = ", ".join(operation.operation_id for operation in matches)
        raise CliError(f"操作名不唯一：{slug}。可用 routes call 调用 operationId：{choices}")
    raise CliError(f"模块 {feature} 下未找到操作：{slug}")


def fill_path(path: str, values: dict[str, str]) -> tuple[str, dict[str, str]]:
    remaining = dict(values)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in remaining:
            raise CliError(f"缺少路径参数：{key}。用 -p {key}=... 传入。")
        return remaining.pop(key)

    return re.sub(r"\{([^}]+)\}", replace, path), remaining
