"""Shared request argument helpers for generic API calls."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xianyu_cli.client import FilePart
from xianyu_cli.exceptions import CliError
from xianyu_cli.parsing import parse_file_args, parse_json_arg, parse_key_value_args


@dataclass(frozen=True)
class RequestPayload:
    data: Any | None
    form: dict[str, str]
    files: list[FilePart]
    output_path: str | None


def add_json_options(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    json_options = parser.add_mutually_exclusive_group(required=required)
    json_options.add_argument("-d", "--data", help="JSON 请求体")
    json_options.add_argument("--data-file", help="从 UTF-8 JSON 文件读取请求体")


def add_pagination_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page", type=int)
    parser.add_argument("--page-size", type=int)


def add_payload_options(parser: argparse.ArgumentParser) -> None:
    add_json_options(parser)
    parser.add_argument("-f", "--form", action="append", help="multipart 表单字段 key=value，可重复")
    parser.add_argument("-F", "--file", action="append", help="multipart 文件字段 field=path，可重复")
    parser.add_argument("-o", "--output", help="把响应原样保存到文件，适合导出/下载接口")


def parse_payload_args(args: argparse.Namespace) -> RequestPayload:
    raw_data = getattr(args, "data", None)
    data_file = getattr(args, "data_file", None)
    if data_file:
        try:
            raw_data = Path(data_file).expanduser().read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CliError(f"无法读取 JSON 文件：{data_file}") from exc
    data = parse_json_arg(raw_data) if raw_data is not None else None
    return RequestPayload(
        data=data,
        form=parse_key_value_args(getattr(args, "form", None)),
        files=parse_file_args(getattr(args, "file", None)),
        output_path=getattr(args, "output", None),
    )
