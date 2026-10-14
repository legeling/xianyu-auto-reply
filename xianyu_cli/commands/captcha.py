"""验证码供应商配置与免费连接检查。"""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client
from xianyu_cli.exceptions import CliError, ensure_success
from xianyu_cli.output import print_output
from xianyu_cli.request_args import add_json_options, parse_payload_args

CONFIG_PATH = "/api/v1/captcha/remote-config"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("captcha", help="远程验证码配置（管理员），支持 CapMonster")
    actions = parser.add_subparsers(dest="captcha_action", required=True)
    actions.add_parser("get", help="读取配置，密钥脱敏")
    setting = actions.add_parser("set", help="更新配置；推荐 --data-file，避免密钥进入命令历史")
    add_json_options(setting, required=True)
    actions.add_parser("test", help="测试已保存配置；CapMonster 只查询余额，不创建收费任务")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args)
    if args.captcha_action == "get":
        response = client.request("GET", CONFIG_PATH)
    else:
        current = client.request("GET", CONFIG_PATH)
        ensure_success(current)
        data = current["data"]
        if args.captcha_action == "set":
            updates = parse_payload_args(args).data
            if not isinstance(updates, dict):
                raise CliError("验证码配置必须是 JSON 对象")
            allowed = set(data)
            if set(updates) - allowed:
                raise CliError("验证码配置含未知字段")
            previous_provider = data["provider"]
            data = {**data, **updates}
            if data["provider"] != previous_provider and data.get("secret_key") == "***":
                raise CliError("更换供应商时请同时填写新 secret_key，或传空字符串清空")
            response = client.request("PUT", CONFIG_PATH, data=data)
        else:
            response = client.request("POST", "/api/v1/captcha/slider-solve/test", data={
                "provider": data["provider"], "url": data["url"], "secret_key": data["secret_key"],
            })
    ensure_success(response)
    print_output(response, json_output=args.json)
