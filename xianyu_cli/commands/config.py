"""Config commands."""
from __future__ import annotations

import argparse

from xianyu_cli.config import load_config, save_config
from xianyu_cli.exceptions import CliError
from xianyu_cli.output import print_output


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("config", help="管理 CLI 配置")
    config_sub = parser.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("show", help="显示当前配置")
    set_url_parser = config_sub.add_parser("set-url", help="设置 Backend-Web 地址")
    set_url_parser.add_argument("url")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    config = load_config()
    if args.config_action == "show":
        print_output(config, json_output=args.json)
        return

    if args.config_action == "set-url":
        config["base_url"] = args.url.rstrip("/")
        save_config(config)
        print(f"已保存 API 地址：{config['base_url']}")
        return

    raise CliError("未知 config 操作")
