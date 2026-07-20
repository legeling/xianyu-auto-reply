"""Auth commands."""
from __future__ import annotations

import argparse
import getpass
import os
from typing import Any

from xianyu_cli.client import ApiClient, build_client
from xianyu_cli.config import load_config, save_config
from xianyu_cli.constants import DEFAULT_BASE_URL
from xianyu_cli.exceptions import CliError
from xianyu_cli.output import print_output


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("auth", help="登录和 token 管理")
    auth_sub = parser.add_subparsers(dest="auth_action", required=True)

    login_parser = auth_sub.add_parser("login", help="用户名密码登录")
    login_parser.add_argument("-u", "--username", required=True)
    login_parser.add_argument("-p", "--password")
    login_parser.add_argument("--geetest-challenge")
    login_parser.add_argument("--geetest-validate")
    login_parser.add_argument("--geetest-seccode")

    token_parser = auth_sub.add_parser("token", help="手动管理 token")
    token_sub = token_parser.add_subparsers(dest="token_action", required=True)
    token_set_parser = token_sub.add_parser("set", help="保存已有 access token")
    token_set_parser.add_argument("token")
    token_sub.add_parser("clear", help="清除本地 token")

    auth_sub.add_parser("whoami", help="验证当前 token")
    auth_sub.add_parser("logout", help="清除本地登录态")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    config = load_config()
    base_url = args.base_url or os.environ.get("XIANYU_API_URL") or config.get("base_url") or DEFAULT_BASE_URL

    if args.auth_action == "login":
        password = args.password or getpass.getpass("Password: ")
        payload: dict[str, Any] = {"username": args.username, "password": password}
        for key in ("geetest_challenge", "geetest_validate", "geetest_seccode"):
            value = getattr(args, key)
            if value:
                payload[key] = value

        response = ApiClient(str(base_url)).request("POST", "/api/v1/auth/login", data=payload, auth=False)
        if not response.get("success"):
            raise CliError(response.get("message") or "登录失败")

        config.update(
            {
                "base_url": str(base_url).rstrip("/"),
                "token": response.get("token"),
                "refresh_token": response.get("refresh_token"),
                "user": {
                    "user_id": response.get("user_id"),
                    "username": response.get("username"),
                    "is_admin": response.get("is_admin"),
                    "account_limit": response.get("account_limit"),
                },
            }
        )
        save_config(config)
        print(f"登录成功：{response.get('username') or args.username}")
        return

    if args.auth_action == "token":
        handle_token(args, config, str(base_url))
        return

    if args.auth_action == "whoami":
        response = build_client(args).request("GET", "/api/v1/auth/verify")
        print_output(response, json_output=args.json)
        return

    if args.auth_action == "logout":
        config.pop("token", None)
        config.pop("refresh_token", None)
        save_config(config)
        print("已退出本地 CLI 登录态")
        return

    raise CliError("未知 auth 操作")


def handle_token(args: argparse.Namespace, config: dict[str, Any], base_url: str) -> None:
    if args.token_action == "set":
        config["base_url"] = base_url.rstrip("/")
        config["token"] = args.token.strip()
        save_config(config)
        print("token 已保存")
        return
    if args.token_action == "clear":
        config.pop("token", None)
        config.pop("refresh_token", None)
        save_config(config)
        print("token 已清除")
        return
    raise CliError("未知 token 操作")
