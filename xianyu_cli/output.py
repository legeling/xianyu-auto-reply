"""Output formatting helpers."""
from __future__ import annotations

import json
from typing import Any

from xianyu_cli.constants import SENSITIVE_FIELDS


def print_output(
    data: Any,
    *,
    json_output: bool = False,
    columns: list[str] | None = None,
    max_width: int = 40,
) -> None:
    if json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    rows = extract_rows(data)
    if rows is not None and rows:
        print_table(rows, columns=columns, max_width=max_width)
        return

    print(json.dumps(mask_sensitive(data), ensure_ascii=False, indent=2))


def extract_rows(data: Any) -> list[dict[str, Any]] | None:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]

    if not isinstance(data, dict):
        return None

    for key in ("data", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = extract_rows(value)
            if nested is not None:
                return nested
    return None


def print_table(rows: list[dict[str, Any]], *, columns: list[str] | None = None, max_width: int = 40) -> None:
    if not rows:
        print("无数据")
        return

    selected = [col for col in (columns or list(rows[0].keys())) if any(col in row for row in rows)]
    if not selected:
        print(json.dumps(mask_sensitive(rows), ensure_ascii=False, indent=2))
        return

    display_rows = [{col: format_cell(row.get(col)) for col in selected} for row in rows]
    widths = {
        col: min(max_width, max(len(col), *(len(row[col]) for row in display_rows)))
        for col in selected
    }
    header = "  ".join(col.ljust(widths[col]) for col in selected)
    print(header)
    print("  ".join("-" * widths[col] for col in selected))
    for row in display_rows:
        print("  ".join(row[col][: widths[col]].ljust(widths[col]) for col in selected))


def print_command_examples(rows: list[dict[str, Any]], *, json_output: bool = False) -> None:
    if json_output:
        print_output(rows, json_output=True)
        return

    if not rows:
        print("无数据")
        return

    for index, row in enumerate(rows, start=1):
        print(f"{index}. {row.get('operation', '')}")
        summary = row.get("summary")
        if summary:
            print(f"   {summary}")
        print(f"   {row.get('command', '')}")


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(mask_sensitive(value), ensure_ascii=False)
    return str(value)


def mask_sensitive(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            key: (_mask_secret(str(value)) if key in SENSITIVE_FIELDS and value else mask_sensitive(value))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [mask_sensitive(item) for item in data]
    return data


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"
