"""Shared request argument helpers for generic API calls."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

from xianyu_cli.client import FilePart
from xianyu_cli.parsing import parse_file_args, parse_json_arg, parse_key_value_args


@dataclass(frozen=True)
class RequestPayload:
    data: Any | None
    form: dict[str, str]
    files: list[FilePart]
    output_path: str | None


def add_payload_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-d", "--data", help="JSON 请求体")
    parser.add_argument("-f", "--form", action="append", help="multipart 表单字段 key=value，可重复")
    parser.add_argument("-F", "--file", action="append", help="multipart 文件字段 field=path，可重复")
    parser.add_argument("-o", "--output", help="把响应原样保存到文件，适合导出/下载接口")


def parse_payload_args(args: argparse.Namespace) -> RequestPayload:
    data = parse_json_arg(args.data) if getattr(args, "data", None) else None
    return RequestPayload(
        data=data,
        form=parse_key_value_args(getattr(args, "form", None)),
        files=parse_file_args(getattr(args, "file", None)),
        output_path=getattr(args, "output", None),
    )
