"""Health command."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client
from xianyu_cli.output import print_output


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("health", help="检查 backend-web 健康状态")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args, require_token=False)
    response = client.request("GET", "/api/v1/health/ping", auth=False)
    print_output(response, json_output=args.json)
