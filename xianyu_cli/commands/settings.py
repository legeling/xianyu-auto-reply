"""System setting shortcut commands."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client
from xianyu_cli.exceptions import CliError
from xianyu_cli.output import print_output


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("settings", help="系统设置快捷命令")
    settings_sub = parser.add_subparsers(dest="settings_action", required=True)
    settings_sub.add_parser("list", help="列出系统设置")
    get_parser = settings_sub.add_parser("get", help="读取单个设置")
    get_parser.add_argument("key")
    set_parser = settings_sub.add_parser("set", help="更新单个设置")
    set_parser.add_argument("key")
    set_parser.add_argument("value")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args)
    if args.settings_action == "list":
        print_output(client.request("GET", "/api/v1/system-settings"), json_output=args.json)
        return

    if args.settings_action == "get":
        response = client.request("GET", "/api/v1/system-settings")
        print_output({args.key: response.get(args.key)}, json_output=args.json)
        return

    if args.settings_action == "set":
        response = client.request("PUT", f"/api/v1/system-settings/{args.key}", data={"value": args.value})
        print_output(response, json_output=args.json)
        return

    raise CliError("未知 settings 操作")
