"""CLI entrypoint."""
from __future__ import annotations

import argparse
import sys

from xianyu_cli import __version__
from xianyu_cli.commands import accounts, api, auth, config, doctor, features, health, items, keywords, orders, routes, settings, web
from xianyu_cli.constants import DEFAULT_BASE_URL
from xianyu_cli.exceptions import CliError


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", help=f"Backend-Web 地址，默认 {DEFAULT_BASE_URL}")
    parser.add_argument("--openapi-file", help="从本地 OpenAPI JSON 文件读取接口定义，用于离线审计")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON")
    parser.add_argument("--version", action="version", version=f"xianyu-cli {__version__}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xianyu-cli", description="闲鱼自动回复系统命令行客户端")
    add_common_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for module in (
        config,
        auth,
        doctor,
        health,
        accounts,
        items,
        orders,
        keywords,
        settings,
        api,
        routes,
        features,
        web,
    ):
        module.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except CliError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
