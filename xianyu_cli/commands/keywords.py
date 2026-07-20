"""Keyword shortcut commands."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client
from xianyu_cli.output import print_output


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("keywords", help="关键词列表快捷命令")
    parser.add_argument("--account-id")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    path = f"/api/v1/keywords-with-item-id/{args.account_id}" if args.account_id else "/api/v1/keywords-with-item-id"
    response = build_client(args).request("GET", path)
    print_output(response, json_output=args.json, columns=["account_id", "keyword", "reply", "item_id"])
