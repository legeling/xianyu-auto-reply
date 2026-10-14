"""Product queries, synchronization, shipping flags and platform operations."""
from __future__ import annotations

import argparse
from urllib.parse import quote

from xianyu_cli.client import build_client
from xianyu_cli.exceptions import CliError
from xianyu_cli.output import print_output
from xianyu_cli.parsing import parse_bool
from xianyu_cli.request_args import add_json_options, parse_payload_args

PREFIX = "/api/v1/items"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("items", help="商品查询、同步、发货设置、下架及鱼小铺编辑")
    actions = parser.add_subparsers(dest="items_action", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--account-id")
    listing.add_argument("--keyword")
    listing.add_argument("--page", type=int, default=1)
    listing.add_argument("--page-size", type=int, default=20)
    for flag in ("is-polished", "is-multi-spec", "multi-quantity-delivery"):
        listing.add_argument(f"--{flag}", type=parse_bool)
    sync = actions.add_parser("sync", help="实时获取闲鱼商品的一页并入库")
    sync.add_argument("account_id")
    sync.add_argument("--page", type=int)
    sync.add_argument("--page-size", type=int)
    for action in ("get", "update-local", "delete-local", "seller-detail", "edit", "price", "multi-spec", "multi-quantity"):
        leaf = actions.add_parser(action, help={
            "get": "本地商品详情", "update-local": "只更新本地配置，不修改闲鱼商品",
            "delete-local": "只删除本地记录", "seller-detail": "鱼小铺平台编辑详情",
            "edit": "提交鱼小铺平台编辑（普通卖家暂不支持）", "price": "鱼小铺改价/库存",
            "multi-spec": "本地多规格发货开关", "multi-quantity": "本地多数量发货开关",
        }[action])
        leaf.add_argument("account_id")
        leaf.add_argument("item_id")
        if action in {"update-local", "edit", "price"}:
            add_json_options(leaf, required=True)
        if action in {"multi-spec", "multi-quantity"}:
            leaf.add_argument("enabled", type=parse_bool)
    for action in ("offline", "delete-platform"):
        leaf = actions.add_parser(action, help="从闲鱼下架商品" if action == "offline" else "从闲鱼删除商品并清理本地记录")
        leaf.add_argument("account_id")
        leaf.add_argument("--item-id", action="append", required=True)
    reply = actions.add_parser("default-reply", help="商品默认回复配置")
    leaves = reply.add_subparsers(dest="reply_action", required=True)
    for action in ("get", "set", "delete"):
        leaf = leaves.add_parser(action)
        leaf.add_argument("account_id")
        leaf.add_argument("item_id")
        if action == "set":
            add_json_options(leaf, required=True)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args)
    action, method, path, kwargs = args.items_action, "GET", PREFIX, {}
    if action == "list":
        path += "/paginated"
        kwargs["params"] = {"cookie_id": args.account_id, "keyword": args.keyword, "page": args.page,
                            "page_size": args.page_size, "is_polished": args.is_polished,
                            "is_multi_spec": args.is_multi_spec, "multi_quantity_delivery": args.multi_quantity_delivery}
    elif action == "sync":
        method, path = "POST", path + "/get-by-page"
        kwargs["data"] = {"cookie_id": args.account_id}
        kwargs["data"].update({key: getattr(args, key) for key in ("page", "page_size") if getattr(args, key) is not None})
    elif action in {"offline", "delete-platform"}:
        method, path = "POST", path + ("/batch-offline" if action == "offline" else "/batch-delete-xianyu")
        kwargs["data"] = {"cookie_id": args.account_id, "item_ids": args.item_id}
    else:
        path += f"/{quote(args.account_id, safe='')}/{quote(args.item_id, safe='')}"
        if action == "default-reply":
            path += "/default-reply"
            method = {"get": "GET", "set": "PUT", "delete": "DELETE"}[args.reply_action]
            if args.reply_action == "set":
                kwargs["data"] = parse_payload_args(args).data
        elif action == "delete-local":
            method = "DELETE"
        elif action == "seller-detail":
            path += "/seller-detail"
        elif action in {"update-local", "edit", "price"}:
            method = "PUT"
            path += {"update-local": "", "edit": "/seller-edit", "price": "/price"}[action]
            kwargs["data"] = parse_payload_args(args).data
        elif action in {"multi-spec", "multi-quantity"}:
            method = "PUT"
            field = "is_multi_spec" if action == "multi-spec" else "multi_quantity_delivery"
            path += "/multi-spec" if action == "multi-spec" else "/multi-quantity-delivery"
            kwargs["data"] = {field: args.enabled}
    columns = ["item_id", "title", "cookie_id", "item_price", "has_card", "multi_quantity_delivery"]
    response = client.request(method, path, **kwargs)
    print_output(response, json_output=args.json,
                 columns=columns if action == "list" else None)
    if action in {"offline", "delete-platform"}:
        result = response.get("data") or {}
        if result.get("fail_count", 0) or result.get("local_failed_ids"):
            raise CliError("部分商品操作失败，请核对结果；未自动重复提交")
