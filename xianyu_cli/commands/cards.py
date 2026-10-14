"""Delivery content and product relations using the existing cards API."""
from __future__ import annotations

import argparse
from io import StringIO
from urllib.parse import quote

from xianyu_cli.client import FilePart, build_client
from xianyu_cli.exceptions import CliError, ensure_success
from xianyu_cli.output import print_output
from xianyu_cli.request_args import add_json_options, add_pagination_options, parse_payload_args

PREFIX = "/api/v1/cards"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("cards", help="发货内容、卡密库存与商品关联管理")
    actions = parser.add_subparsers(dest="cards_action", required=True)
    listing = actions.add_parser("list", help="分页查询轻量卡券，不下载整批卡密")
    add_pagination_options(listing)
    listing.add_argument("--search")
    listing.add_argument("--type")
    create = actions.add_parser("create", help="创建文本、卡密、图片或API发货内容")
    add_json_options(create, required=True)
    for action in ("get", "stock", "update", "delete", "enable", "disable", "items"):
        leaf = actions.add_parser(action, help={
            "get": "查询详情（发货内容脱敏）", "stock": "查询数据卡券剩余非空行数，不输出卡密",
            "update": "替换指定内容或库存字段", "delete": "删除卡券",
            "enable": "启用卡券", "disable": "停用卡券", "items": "查询卡券关联商品",
        }[action])
        leaf.add_argument("card_id", type=int)
        if action == "update":
            add_json_options(leaf, required=True)
    for action in ("batch-delete", "batch-save", "set-items", "bind", "set-item-cards", "clear-item-cards"):
        leaf = actions.add_parser(action, help={
            "batch-delete": "批量删除卡券", "batch-save": "给多个商品保存发货内容",
            "set-items": "替换卡券的完整商品关联", "bind": "增加卡券与商品的批量关联",
            "set-item-cards": "替换商品的完整卡券关联（支持对接卡券）",
            "clear-item-cards": "清空指定商品的关联，保留卡券",
        }[action])
        if action == "set-items":
            leaf.add_argument("card_id", type=int)
        if action == "set-item-cards":
            leaf.add_argument("item_id")
        add_json_options(leaf, required=True)
    by_item = actions.add_parser("for-item", help="查询一个商品的发货内容")
    by_item.add_argument("item_id")
    unbind = actions.add_parser("unbind", help="移除一条卡券商品关联")
    unbind.add_argument("card_id", type=int)
    unbind.add_argument("item_id")
    upload = actions.add_parser("upload-image", help="上传发货图片")
    upload.add_argument("path")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args)
    action = args.cards_action
    kwargs = {}
    if action == "list":
        method, path = "GET", PREFIX
        kwargs["params"] = {"page": args.page, "page_size": args.page_size, "search": args.search,
                            "type": args.type, "lite": True}
    elif action == "create":
        method, path = "POST", PREFIX
        kwargs["data"] = parse_payload_args(args).data
    elif action in {"get", "stock", "update", "delete", "enable", "disable", "items", "set-items"}:
        path = f"{PREFIX}/{args.card_id}"
        method = {"get": "GET", "stock": "GET", "update": "PUT", "delete": "DELETE", "enable": "PUT",
                  "disable": "PUT", "items": "GET", "set-items": "PUT"}[action]
        if action in {"items", "set-items"}:
            path += "/items"
        if action in {"update", "set-items"}:
            kwargs["data"] = parse_payload_args(args).data
        elif action in {"enable", "disable"}:
            kwargs["data"] = {"enabled": action == "enable"}
    elif action in {"batch-delete", "batch-save", "bind", "clear-item-cards"}:
        suffix = {"bind": "batch-bind", "clear-item-cards": "batch-clear-item-relations"}.get(action, action)
        method, path = "POST", f"{PREFIX}/{suffix}"
        kwargs["data"] = parse_payload_args(args).data
    elif action == "set-item-cards":
        method, path = "PUT", f"{PREFIX}/item/{quote(args.item_id, safe='')}/cards"
        kwargs["data"] = parse_payload_args(args).data
    elif action == "for-item":
        method, path = "GET", f"{PREFIX}/item/{quote(args.item_id, safe='')}"
    elif action == "unbind":
        method, path = "DELETE", f"{PREFIX}/relation/{args.card_id}/{quote(args.item_id, safe='')}"
    else:
        method, path = "POST", f"{PREFIX}/upload-image"
        kwargs["files"] = [FilePart("image", args.path)]
    response = client.request(method, path, **kwargs)
    ensure_success(response)
    if action == "stock":
        if not isinstance(response, dict) or response.get("type") != "data":
            raise CliError("该卡券不是按行消费的数据类型，没有卡密行库存")
        response = {"id": response.get("id"), "enabled": response.get("enabled"),
                    "remaining_line_count": sum(bool(line.strip()) for line in StringIO(response.get("data_content") or ""))}
    columns = ["id", "name", "type", "enabled", "delivery_count", "delay_seconds"]
    print_output(response, json_output=args.json, columns=columns if action in {"list", "for-item"} else None)
    if action in {"bind", "batch-save"} and isinstance(response, dict):
        result = response.get("data") or {}
        incomplete_save = action == "batch-save" and result.get("bind_count", 0) < len(set(kwargs["data"].get("item_ids", [])))
        if result.get("fail_count", 0) or incomplete_save:
            raise CliError("部分商品关联或保存失败，请核对已输出的结果；未自动重复提交")
