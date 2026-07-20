"""Item shortcut commands."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client
from xianyu_cli.output import print_output


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("items", help="商品管理快捷命令")
    items_sub = parser.add_subparsers(dest="items_action", required=True)

    list_parser = items_sub.add_parser("list", help="商品列表")
    list_parser.add_argument("--account-id")
    list_parser.add_argument("--keyword")
    list_parser.add_argument("--page", type=int, default=1)
    list_parser.add_argument("--page-size", type=int, default=20)

    get_parser = items_sub.add_parser("get", help="商品详情")
    get_parser.add_argument("account_id")
    get_parser.add_argument("item_id")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args)
    if args.items_action == "list":
        response = client.request(
            "GET",
            "/api/v1/items/paginated",
            params={
                "cookie_id": args.account_id,
                "keyword": args.keyword,
                "page": args.page,
                "page_size": args.page_size,
            },
        )
        print_output(response, json_output=args.json, columns=["item_id", "title", "account_id", "price", "is_polished"])
        return

    if args.items_action == "get":
        response = client.request("GET", f"/api/v1/items/{args.account_id}/{args.item_id}")
        print_output(response, json_output=args.json)
