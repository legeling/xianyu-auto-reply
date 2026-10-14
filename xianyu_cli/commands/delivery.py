"""Account shipping policy, product bindings and delivery evidence."""
from __future__ import annotations

import argparse
from urllib.parse import quote

from xianyu_cli.client import build_client
from xianyu_cli.commands.accounts import get_account
from xianyu_cli.exceptions import ensure_success
from xianyu_cli.output import extract_rows, print_output
from xianyu_cli.parsing import parse_bool
from xianyu_cli.request_args import add_json_options, add_pagination_options, parse_payload_args

SWITCH_FIELDS = ("auto_confirm", "scheduled_redelivery", "confirm_before_send", "send_before_confirm", "only_send_card")
ACCOUNT_FIELDS = ("id", "enabled", "online", *SWITCH_FIELDS, "delivery_disabled",
                  "delivery_disabled_reason", "delivery_disabled_excluded_item_ids")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("delivery", help="自动发货开关、拦截规则、同意后发货与日志")
    actions = parser.add_subparsers(dest="delivery_action", required=True)
    config = actions.add_parser("config", help="查看账号发货开关，不输出Cookie")
    config.add_argument("account_id")
    switch = actions.add_parser("switch", help="更新一个账号发货开关，字段采用后端规范名")
    switch.add_argument("account_id")
    switch.add_argument("field", choices=SWITCH_FIELDS)
    switch.add_argument("enabled", type=parse_bool)
    for group, title in (("block-rules", "禁止发货规则"), ("agree", "同意后发货配置"), ("refund", "退款注销配置")):
        parent = actions.add_parser(group, help=title)
        leaves = parent.add_subparsers(dest="config_action", required=True)
        for action in ("get", "set"):
            leaf = leaves.add_parser(action, help="查看" if action == "get" else "保存完整配置")
            leaf.add_argument("account_id")
            if action == "set":
                add_json_options(leaf, required=True)
    actions.add_parser("block-rule-types", help="查询后端支持的禁止发货规则")
    actions.add_parser("pickup-url", help="查询本系统提货页地址建议")
    inspect = actions.add_parser("inspect", help="检查账号、商品与发货内容配置；不触发发货")
    inspect.add_argument("account_id")
    inspect.add_argument("item_id")
    logs = actions.add_parser("logs", help="查询实际自动发货消息的发送结果")
    add_pagination_options(logs)
    for flag in ("account-id", "item-id", "start-date", "end-date", "send-status", "matched-rule-type"):
        logs.add_argument(f"--{flag}")
    batches = actions.add_parser("redelivery-logs", help="定时补发货批次（管理员接口）")
    leaves = batches.add_subparsers(dest="log_action", required=True)
    listing = leaves.add_parser("list")
    add_pagination_options(listing)
    listing.add_argument("--start-date")
    listing.add_argument("--end-date")
    detail = leaves.add_parser("get")
    detail.add_argument("batch_id")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args)
    action = args.delivery_action
    kwargs = {}
    method = "GET"
    if action in {"config", "inspect"}:
        account = get_account(client, args.account_id)
        response = {key: account.get(key) for key in ACCOUNT_FIELDS}
        if action == "inspect":
            account_id, item_id = quote(args.account_id, safe=""), quote(args.item_id, safe="")
            item = client.request("GET", f"/api/v1/items/{account_id}/{item_id}")
            cards = client.request("GET", f"/api/v1/cards/item/{item_id}")
            card_rows = extract_rows(cards) or []
            ensure_success(item)
            ensure_success(cards)
            response = {"account": response, "item": item,
                        "cards": [{key: card.get(key) for key in
                                   ("id", "name", "type", "enabled", "delay_seconds")}
                                  for card in card_rows],
                        "block_rules": client.request("GET", f"/api/v1/cookies/{account_id}/delivery-block-rules"),
                        "agree": client.request("GET", f"/api/v1/agree-deliver/{account_id}")}
            ensure_success(response["block_rules"])
            ensure_success(response["agree"])
            response["verification_note"] = "配置检查不触发发货；实际结果请结合订单和 delivery logs 核对。"
        print_output(response, json_output=args.json)
        return
    if action == "switch":
        method = "PUT"
        path = f"/api/v1/cookies/{quote(args.account_id, safe='')}/{args.field.replace('_', '-')}"
        kwargs["data"] = {args.field: args.enabled}
    elif action in {"block-rules", "agree", "refund"}:
        account_id = quote(args.account_id, safe="")
        path = {"block-rules": f"/api/v1/cookies/{account_id}/delivery-block-rules",
                "agree": f"/api/v1/agree-deliver/{account_id}",
                "refund": f"/api/v1/refund-cancel/{account_id}"}[action]
        if args.config_action == "set":
            method = "PUT"
            kwargs["data"] = parse_payload_args(args).data
    elif action == "block-rule-types":
        path = "/api/v1/cookies/delivery-block-rules/available"
    elif action == "pickup-url":
        path = "/api/v1/agree-deliver/pickup-url/suggestion"
    elif action == "logs":
        path = "/api/v1/auto-reply-logs"
        kwargs["params"] = {key: getattr(args, key) for key in
                            ("account_id", "item_id", "start_date", "end_date", "send_status",
                             "matched_rule_type", "page", "page_size")}
        kwargs["params"]["message_type"] = "auto_delivery"
    else:
        path = "/api/v1/admin/redelivery-batches"
        if args.log_action == "get":
            path += f"/{quote(args.batch_id, safe='')}"
        else:
            kwargs["params"] = {key: getattr(args, key) for key in ("page", "page_size", "start_date", "end_date")}
    print_output(client.request(method, path, **kwargs), json_output=args.json)
