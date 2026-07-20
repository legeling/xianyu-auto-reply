"""Feature-oriented OpenAPI commands."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client, load_openapi
from xianyu_cli.openapi import (
    fill_path,
    find_feature_operation,
    group_operations_by_feature,
    operation_command_template,
    operation_inputs,
    operation_slug,
)
from xianyu_cli.output import print_command_examples, print_output
from xianyu_cli.parsing import parse_key_value_args
from xianyu_cli.request_args import add_payload_options, parse_payload_args


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("features", help="按网页版功能模块浏览和调用 API")
    features_sub = parser.add_subparsers(dest="features_action", required=True)

    list_parser = features_sub.add_parser("list", help="列出功能模块")
    list_parser.add_argument("--search", help="按模块名或 tag 搜索")

    ops_parser = features_sub.add_parser("ops", help="列出某个功能模块的操作")
    ops_parser.add_argument("feature")
    ops_parser.add_argument("--search", help="按路径、summary 或操作名搜索")

    examples_parser = features_sub.add_parser("examples", help="生成某个功能模块的 CLI 调用示例")
    examples_parser.add_argument("feature")
    examples_parser.add_argument("--search", help="按路径、summary 或操作名搜索")
    examples_parser.add_argument("--include-optional", action="store_true", help="同时生成可选参数占位符")

    call_parser = features_sub.add_parser("call", help="按功能模块和操作名调用接口")
    call_parser.add_argument("feature")
    call_parser.add_argument("operation")
    call_parser.add_argument("-p", "--path-param", action="append", help="路径参数 key=value，可重复")
    call_parser.add_argument("-q", "--query", action="append", help="查询参数 key=value，可重复")
    add_payload_options(call_parser)
    call_parser.add_argument("--no-auth", action="store_true", help="不附带 Authorization")

    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    require_token = args.features_action == "call" and not args.no_auth
    client = build_client(args, require_token=require_token)
    openapi = load_openapi(args, client)

    if args.features_action == "list":
        rows = []
        for feature, operations in group_operations_by_feature(openapi).items():
            tags = sorted({tag for operation in operations for tag in operation.tags})
            row = {
                "feature": feature,
                "operations": len(operations),
                "tags": ",".join(tags),
            }
            if _matches_feature(row, args.search):
                rows.append(row)
        print_output(rows, json_output=args.json, columns=["feature", "operations", "tags"])
        return

    if args.features_action == "ops":
        operations = group_operations_by_feature(openapi).get(args.feature, [])
        rows = []
        for operation in operations:
            row = {
                "operation": operation_slug(operation),
                "method": operation.method,
                "path": operation.path,
                "summary": operation.summary,
                "inputs": operation_inputs(operation),
                "operation_id": operation.operation_id,
            }
            if _matches_operation(row, args.search):
                rows.append(row)
        print_output(rows, json_output=args.json, columns=["operation", "method", "path", "summary", "inputs"])
        return

    if args.features_action == "examples":
        operations = group_operations_by_feature(openapi).get(args.feature, [])
        rows = []
        for operation in operations:
            operation_name = operation_slug(operation)
            row = {
                "operation": operation_name,
                "method": operation.method,
                "path": operation.path,
                "summary": operation.summary,
                "inputs": operation_inputs(operation),
                "operation_id": operation.operation_id,
                "command": operation_command_template(
                    openapi,
                    operation,
                    ["xianyu-cli", "features", "call", args.feature, operation_name],
                    include_optional=args.include_optional,
                ),
            }
            if _matches_operation(row, args.search):
                rows.append(row)
        print_command_examples(rows, json_output=args.json)
        return

    if args.features_action == "call":
        operation = find_feature_operation(openapi, args.feature, args.operation)
        path, leftover_path_values = fill_path(operation.path, parse_key_value_args(args.path_param))
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


def _matches_feature(row: dict[str, object], search: str | None) -> bool:
    if not search:
        return True
    haystack = f"{row['feature']} {row['tags']}".lower()
    return search.lower() in haystack


def _matches_operation(row: dict[str, object], search: str | None) -> bool:
    if not search:
        return True
    haystack = " ".join(str(value) for value in row.values()).lower()
    return search.lower() in haystack
