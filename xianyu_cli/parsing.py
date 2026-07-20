"""Argument and payload parsing helpers."""
from __future__ import annotations

import argparse
import json
from typing import Any

from xianyu_cli.client import FilePart
from xianyu_cli.exceptions import CliError


def parse_json_arg(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(f"JSON 格式错误：{exc}") from exc


def parse_key_value_args(items: list[str] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise CliError(f"参数格式应为 key=value：{item}")
        key, value = item.split("=", 1)
        if not key:
            raise CliError(f"参数 key 不能为空：{item}")
        values[key] = value
    return values


def parse_file_args(items: list[str] | None) -> list[FilePart]:
    files: list[FilePart] = []
    for item in items or []:
        if "=" not in item:
            raise CliError(f"文件参数格式应为 field=path：{item}")
        field, path = item.split("=", 1)
        if not field:
            raise CliError(f"文件字段名不能为空：{item}")
        clean_path = path[1:] if path.startswith("@") else path
        if not clean_path:
            raise CliError(f"文件路径不能为空：{item}")
        files.append(FilePart(field=field, path=clean_path))
    return files


def parse_bool(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError("布尔值必须是 true/false")
