"""Order management, synchronization and explicit shipping operations."""
from __future__ import annotations

import argparse
from urllib.parse import quote

from xianyu_cli.client import build_client
from xianyu_cli.exceptions import CliError
from xianyu_cli.output import print_output
from xianyu_cli.parsing import parse_bool

PREFIX = "/api/v1/orders"


def _filters(parser: argparse.ArgumentParser, *, defaults: bool) -> None:
    for name in ("account-id", "status", "search", "delivery-method", "start-date", "end-date", "delivery-send-status"):
        parser.add_argument(f"--{name}", default=None if defaults else argparse.SUPPRESS)
    for name in ("is-bargain", "is-rated"):
        parser.add_argument(f"--{name}", type=parse_bool, default=None if defaults else argparse.SUPPRESS)
    parser.add_argument("--page", type=int, default=1 if defaults else argparse.SUPPRESS)
    parser.add_argument("--page-size", type=int, default=20 if defaults else argparse.SUPPRESS)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("orders", help="订单查询、同步、手动发货、无物流发货及关闭订单")
    _filters(parser, defaults=True)
    actions = parser.add_subparsers(dest="orders_action")
    listing = actions.add_parser("list")
    _filters(listing, defaults=False)
    for action in ("get", "deliver", "no-logistics", "cancel"):
        leaf = actions.add_parser(action, help={"get": "订单详情", "deliver": "实际发送关联卡券并发货",
                                              "no-logistics": "仅提交无需物流发货", "cancel": "关闭闲鱼订单"}[action])
        leaf.add_argument("order_no")
    sync = actions.add_parser("sync", help="从闲鱼同步订单")
    sync.add_argument("--account-id", default=argparse.SUPPRESS)
    delete = actions.add_parser("delete", help="删除本地订单记录")
    delete.add_argument("order_id", type=int)
    batch = actions.add_parser("batch-delete", help="批量删除本地订单记录")
    batch.add_argument("ids", nargs="+", type=int)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    action = args.orders_action or "list"
    method, path, kwargs = "GET", PREFIX, {}
    if action == "list":
        kwargs["params"] = {"cookie_id": args.account_id}
        kwargs["params"].update({key: getattr(args, key) for key in
                                 ("status", "search", "delivery_method", "start_date", "end_date",
                                  "delivery_send_status", "is_bargain", "is_rated", "page", "page_size")})
    elif action == "get":
        path += f"/{quote(args.order_no, safe='')}"
    elif action == "sync":
        method, path = "POST", path + "/fetch-xianyu"
        kwargs["data"] = {"cookie_id": args.account_id}
    elif action in {"deliver", "no-logistics", "cancel"}:
        method, path = "POST", path + {"deliver": "/manual-delivery", "no-logistics": "/no-logistics-delivery",
                                       "cancel": "/cancel"}[action]
        kwargs["data"] = {"order_no": args.order_no}
    elif action == "delete":
        method, path = "DELETE", path + f"/{args.order_id}"
    else:
        method, path = "POST", path + "/batch-delete"
        kwargs["data"] = {"ids": args.ids}
    response = build_client(args).request(method, path, **kwargs)
    print_output(response, json_output=args.json,
                 columns=["order_id", "cookie_id", "item_id", "status", "amount", "delivery_method", "delivery_send_status"]
                 if action == "list" else None)
    if action == "batch-delete" and (response.get("data") or {}).get("failed", 0):
        raise CliError("部分本地订单未删除，请核对结果；未自动重复提交")
