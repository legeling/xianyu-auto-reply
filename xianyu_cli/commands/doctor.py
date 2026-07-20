"""CLI environment diagnostics."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client, load_openapi
from xianyu_cli.config import load_config
from xianyu_cli.exceptions import CliError
from xianyu_cli.openapi import list_operations
from xianyu_cli.output import print_output


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("doctor", help="诊断 CLI 配置、后端连接、OpenAPI 和 token")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    config = load_config()
    client = build_client(args, require_token=False)
    checks = []

    checks.append({"name": "base_url", "ok": True, "detail": client.base_url})
    checks.append(_check_health(client))
    checks.append(_check_openapi(args, client))
    checks.append(_check_token(args, bool(config.get("token"))))

    print_output(checks, json_output=args.json, columns=["name", "ok", "detail"])


def _check_health(client) -> dict[str, object]:
    try:
        response = client.request("GET", "/api/v1/health/ping", auth=False)
        ok = isinstance(response, dict) and bool(response.get("success"))
        return {"name": "health", "ok": ok, "detail": response.get("message") if isinstance(response, dict) else response}
    except CliError as exc:
        return {"name": "health", "ok": False, "detail": str(exc)}


def _check_openapi(args: argparse.Namespace, client) -> dict[str, object]:
    try:
        openapi = load_openapi(args, client)
        count = len(list_operations(openapi))
        return {"name": "openapi", "ok": count > 0, "detail": f"{count} operations"}
    except CliError as exc:
        return {"name": "openapi", "ok": False, "detail": str(exc)}


def _check_token(args: argparse.Namespace, has_saved_token: bool) -> dict[str, object]:
    if not has_saved_token:
        return {"name": "token", "ok": False, "detail": "未保存 token；需要认证接口时先执行 auth login 或 auth token set"}

    try:
        response = build_client(args).request("GET", "/api/v1/auth/verify")
        ok = isinstance(response, dict) and bool(response.get("authenticated"))
        detail = response.get("username") if ok else "token 无效或已过期"
        return {"name": "token", "ok": ok, "detail": detail}
    except CliError as exc:
        return {"name": "token", "ok": False, "detail": str(exc)}
