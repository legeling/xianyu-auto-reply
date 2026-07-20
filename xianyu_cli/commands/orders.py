"""Order shortcut commands."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client
from xianyu_cli.output import print_output


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("orders", help="订单列表快捷命令")
    parser.add_argument("--account-id")
    parser.add_argument("--status")
    parser.add_argument("--search")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=20)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    response = build_client(args).request(
        "GET",
        "/api/v1/orders",
        params={
            "cookie_id": args.account_id,
            "status": args.status,
            "search": args.search,
            "page": args.page,
            "page_size": args.page_size,
        },
    )
    print_output(response, json_output=args.json, columns=["order_no", "account_id", "item_id", "status", "price"])
