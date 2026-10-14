"""Account shortcut commands."""
from __future__ import annotations

import argparse
import sys
from urllib.parse import quote

from xianyu_cli.client import build_client
from xianyu_cli.exceptions import CliError, ensure_success
from xianyu_cli.output import extract_rows, print_output
from xianyu_cli.parsing import parse_bool


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("accounts", help="账号管理快捷命令")
    accounts_sub = parser.add_subparsers(dest="accounts_action", required=True)

    list_parser = accounts_sub.add_parser("list", help="账号列表")
    list_parser.add_argument("--page", type=int, default=1)
    list_parser.add_argument("--page-size", type=int, default=20)
    list_parser.add_argument("--status", choices=["active", "inactive"])
    list_parser.add_argument("--online", type=parse_bool)
    list_parser.add_argument("--search")

    for action in ("get", "delete"):
        leaf = accounts_sub.add_parser(action, help="账号详情" if action == "get" else "删除账号")
        leaf.add_argument("account_id")

    create_parser = accounts_sub.add_parser("create", help="添加账号，cookie 可从 stdin 输入")
    create_parser.add_argument("account_id")
    create_parser.add_argument("--cookie")

    cookie_parser = accounts_sub.add_parser("cookie", help="更新账号 Cookie，cookie 可从 stdin 输入")
    cookie_parser.add_argument("account_id")
    cookie_parser.add_argument("--cookie")

    for action in ("enable", "disable"):
        action_parser = accounts_sub.add_parser(action, help=f"{'启用' if action == 'enable' else '禁用'}账号")
        action_parser.add_argument("account_id")

    remark_parser = accounts_sub.add_parser("remark", help="更新账号备注")
    remark_parser.add_argument("account_id")
    remark_parser.add_argument("remark")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args)

    if args.accounts_action == "get":
        print_output(get_account(client, args.account_id), json_output=args.json)
        return
    if args.accounts_action == "delete":
        print_output(client.request("DELETE", f"/api/v1/cookies/{quote(args.account_id, safe='')}"),
                     json_output=args.json)
        return

    if args.accounts_action == "list":
        response = client.request(
            "GET",
            "/api/v1/cookies/details/paginated",
            params={
                "page": args.page,
                "page_size": args.page_size,
                "status": args.status,
                "online": args.online,
                "account_id": args.search,
            },
        )
        print_output(response, json_output=args.json, columns=["id", "enabled", "online", "remark", "owner_username"])
        return

    if args.accounts_action == "create":
        response = client.request("POST", "/api/v1/cookies", data={"id": args.account_id, "value": read_cookie(args)})
        print_output(response, json_output=args.json)
        return

    if args.accounts_action == "cookie":
        response = client.request("PUT", f"/api/v1/cookies/{quote(args.account_id, safe='')}", data={"value": read_cookie(args)})
        print_output(response, json_output=args.json)
        return

    if args.accounts_action in {"enable", "disable"}:
        enabled = args.accounts_action == "enable"
        response = client.request("PUT", f"/api/v1/cookies/{quote(args.account_id, safe='')}/status", data={"enabled": enabled})
        print_output(response, json_output=args.json)
        return

    if args.accounts_action == "remark":
        response = client.request("PUT", f"/api/v1/cookies/{quote(args.account_id, safe='')}/remark", data={"remark": args.remark})
        print_output(response, json_output=args.json)
        return


def read_cookie(args: argparse.Namespace) -> str:
    cookie = args.cookie if args.cookie is not None else sys.stdin.read().strip()
    if not cookie:
        raise CliError("Cookie 不能为空。可用 --cookie 传入，或通过 stdin 输入。")
    return cookie


def get_account(client, account_id: str) -> dict:
    """Search is fuzzy on the server; select the exact identifier without loading all accounts."""
    page = 1
    while True:
        response = client.request("GET", "/api/v1/cookies/details/paginated",
                                  params={"account_id": account_id, "page": page})
        ensure_success(response)
        for account in extract_rows(response) or []:
            if account.get("id") == account_id:
                return account
        if page >= response.get("total_pages", 1):
            raise CliError("账号不存在或无权查看")
        page += 1
