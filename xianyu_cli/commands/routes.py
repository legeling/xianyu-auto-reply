"""OpenAPI route catalog commands."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client, load_openapi
from xianyu_cli.openapi import (
    fill_path,
    find_operation,
    list_operations,
    operation_command_template,
    operation_inputs,
)
from xianyu_cli.output import print_output
from xianyu_cli.parsing import parse_key_value_args
from xianyu_cli.request_args import add_payload_options, parse_payload_args


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("routes", help="查看并调用 OpenAPI 路由，覆盖网页版后端接口")
    routes_sub = parser.add_subparsers(dest="routes_action", required=True)

    list_parser = routes_sub.add_parser("list", help="列出后端全部 API")
    list_parser.add_argument("--tag", help="按 tag 过滤，例如 账号管理")
    list_parser.add_argument("--search", help="按路径、summary、operationId 搜索")

    show_parser = routes_sub.add_parser("show", help="查看单个 operationId 的接口定义")
    show_parser.add_argument("operation_id")

    template_parser = routes_sub.add_parser("template", help="生成单个 operationId 的 CLI 调用模板")
    template_parser.add_argument("operation_id")
    template_parser.add_argument("--include-optional", action="store_true", help="同时生成可选参数占位符")

    call_parser = routes_sub.add_parser("call", help="按 operationId 调用接口")
    call_parser.add_argument("operation_id")
    call_parser.add_argument("-p", "--path-param", action="append", help="路径参数 key=value，可重复")
    call_parser.add_argument("-q", "--query", action="append", help="查询参数 key=value，可重复")
    add_payload_options(call_parser)
    call_parser.add_argument("--no-auth", action="store_true", help="不附带 Authorization")

    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    read_only_actions = {"list", "show", "template"}
    require_token = args.routes_action not in read_only_actions and not args.no_auth
    client = build_client(args, require_token=require_token)
    openapi = load_openapi(args, client)

    if args.routes_action == "list":
        rows = [
            {
                "method": operation.method,
                "path": operation.path,
                "operation_id": operation.operation_id,
                "summary": operation.summary,
                "inputs": operation_inputs(operation),
                "tags": ",".join(operation.tags),
            }
            for operation in list_operations(openapi)
            if _matches(operation, tag=args.tag, search=args.search)
        ]
        print_output(rows, json_output=args.json, columns=["method", "path", "operation_id", "summary", "inputs", "tags"])
        return

    if args.routes_action == "show":
        operation = find_operation(openapi, args.operation_id)
        print_output(
            {
                "method": operation.method,
                "path": operation.path,
                "operation_id": operation.operation_id,
                "summary": operation.summary,
                "tags": operation.tags,
                "definition": operation.raw,
            },
            json_output=True,
        )
        return

    if args.routes_action == "template":
        operation = find_operation(openapi, args.operation_id)
        command = operation_command_template(
            openapi,
            operation,
            ["xianyu-cli", "routes", "call", operation.operation_id],
            include_optional=args.include_optional,
        )
        if args.json:
            print_output(
                {
                    "operation_id": operation.operation_id,
                    "method": operation.method,
                    "path": operation.path,
                    "summary": operation.summary,
                    "command": command,
                },
                json_output=True,
            )
            return
        print(command)
        return

    if args.routes_action == "call":
        operation = find_operation(openapi, args.operation_id)
        path_values = parse_key_value_args(args.path_param)
        path, leftover_path_values = fill_path(operation.path, path_values)
        params = parse_key_value_args(args.query)
        params.update(leftover_path_values)
        payload = parse_payload_args(args)
        response = client.request(
            operation.method,
            path,
            params=params,
            data=payload.data,
            form=payload.form,
            files=payload.files,
            output_path=payload.output_path,
            auth=not args.no_auth,
        )
        print_output(response, json_output=args.json)
        return


def _matches(operation, *, tag: str | None, search: str | None) -> bool:
    if tag and tag not in operation.tags:
        return False
    if not search:
        return True
    haystack = " ".join([operation.path, operation.operation_id, operation.summary, *operation.tags]).lower()
    return search.lower() in haystack
