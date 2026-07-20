"""Frontend page oriented API commands."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client, load_openapi
from xianyu_cli.exceptions import CliError
from xianyu_cli.frontend import (
    FrontendApiFunction,
    audit_frontend_endpoints,
    match_operation,
    scan_frontend_api_functions,
)
from xianyu_cli.openapi import (
    Operation,
    feature_key,
    fill_path,
    group_operations_by_feature,
    list_operations,
    operation_command_template,
    operation_inputs,
    operation_slug,
)
from xianyu_cli.output import print_command_examples, print_output
from xianyu_cli.parsing import parse_key_value_args
from xianyu_cli.request_args import add_payload_options, parse_payload_args
from xianyu_cli.smoke import run_smoke_candidates, web_smoke_candidates
from xianyu_cli.webmap import WEB_PAGES, WebPage, find_page
from xianyu_cli.websocket_client import run_chat_new_ws


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("web", help="按网页版页面浏览和调用对应 API")
    web_sub = parser.add_subparsers(dest="web_action", required=True)

    pages_parser = web_sub.add_parser("pages", help="列出网页版页面和对应 API 功能模块")
    pages_parser.add_argument("--search", help="按页面 key、标题、路径或 feature 搜索")

    coverage_parser = web_sub.add_parser("coverage", help="检查网页版页面到后端 OpenAPI 的覆盖情况")
    coverage_parser.add_argument("--search", help="按页面 key、标题、路径或 feature 搜索")
    coverage_parser.add_argument("--only", choices=["all", "ok", "missing", "static"], default="all")
    coverage_parser.add_argument("--unmapped-features", action="store_true", help="改为列出未映射到页面的后端模块")

    audit_parser = web_sub.add_parser("audit", help="审计前端实际 API 调用是否已被 OpenAPI 和页面映射覆盖")
    audit_parser.add_argument("--frontend-root", default="frontend/src", help="前端源码目录，默认 frontend/src")
    audit_parser.add_argument(
        "--only",
        choices=["all", "ok", "missing_openapi", "unmapped_feature"],
        default="all",
        help="只显示指定状态",
    )
    audit_parser.add_argument("--search", help="按路径、feature、operationId 或源码位置搜索")

    functions_parser = web_sub.add_parser("functions", help="列出前端 API 导出函数及对应 CLI 调用")
    functions_parser.add_argument("--frontend-root", default="frontend/src", help="前端源码目录，默认 frontend/src")
    functions_parser.add_argument("--search", help="按函数名、路径、feature、operationId 或源码位置搜索")
    functions_parser.add_argument(
        "--only",
        choices=["all", "ok", "missing_openapi", "unmapped_feature"],
        default="all",
        help="只显示指定状态",
    )
    functions_parser.add_argument("--include-optional", action="store_true", help="模板中包含可选参数占位符")

    function_parser = web_sub.add_parser("function", help="精确查看某个前端 API 函数对应的后端接口")
    function_parser.add_argument("function", help="函数名或 module.function，例如 accounts.getAccountDetails")
    function_parser.add_argument("--frontend-root", default="frontend/src", help="前端源码目录，默认 frontend/src")
    function_parser.add_argument("--include-optional", action="store_true", help="模板中包含可选参数占位符")

    verify_parser = web_sub.add_parser("verify", help="聚合验证网页版 API、OpenAPI 和 CLI 页面映射是否对齐")
    verify_parser.add_argument("page", nargs="?", help="页面 key、路径或中文标题；不传则验证全部页面")
    verify_parser.add_argument("--frontend-root", default="frontend/src", help="前端源码目录，默认 frontend/src")
    verify_parser.add_argument("--skip-frontend", action="store_true", help="跳过前端源码 API 静态审计")
    verify_parser.add_argument("--allow-failures", action="store_true", help="即使发现对齐问题也返回 0")

    smoke_parser = web_sub.add_parser("smoke", help="运行网页版 API 只读 smoke 测试")
    smoke_parser.add_argument("page", nargs="?", help="页面 key、路径或中文标题；不传则从全部页面挑选")
    smoke_parser.add_argument("--search", help="按页面、操作名、路径、summary 搜索")
    smoke_parser.add_argument("--limit", type=int, default=20, help="最多执行或预览多少个接口，默认 20")
    smoke_parser.add_argument("--dry-run", action="store_true", help="只列出将要测试的接口，不发送请求")
    smoke_parser.add_argument("--fail-fast", action="store_true", help="遇到第一个失败后停止")
    smoke_parser.add_argument("--allow-failures", action="store_true", help="即使有接口失败也返回 0")
    smoke_parser.add_argument("--no-auth", action="store_true", help="不附带 Authorization，只测试公开接口")

    ws_parser = web_sub.add_parser("ws", help="监听在线聊天 WebSocket 实时推送")
    ws_parser.add_argument("account_id", help="账号ID")
    ws_parser.add_argument("--limit", type=int, default=0, help="收到多少条事件后退出，0 表示持续监听")
    ws_parser.add_argument("--timeout", type=float, help="等待单条事件的超时时间秒")
    ws_parser.add_argument("--ping-interval", type=float, default=25.0, help="发送应用层 ping 心跳的间隔秒，0 表示关闭")
    ws_parser.add_argument("--raw", action="store_true", help="原样输出服务端文本消息")

    ops_parser = web_sub.add_parser("ops", help="列出某个页面对应的 API 操作")
    ops_parser.add_argument("page", help="页面 key、路径或中文标题")
    ops_parser.add_argument("--search", help="按操作名、路径、summary 搜索")

    examples_parser = web_sub.add_parser("examples", help="生成某个页面对应 API 的 CLI 调用示例")
    examples_parser.add_argument("page", help="页面 key、路径或中文标题")
    examples_parser.add_argument("--search", help="按操作名、路径、summary 搜索")
    examples_parser.add_argument("--include-optional", action="store_true", help="同时生成可选参数占位符")

    call_parser = web_sub.add_parser("call", help="按页面和操作名调用接口")
    call_parser.add_argument("page", help="页面 key、路径或中文标题")
    call_parser.add_argument("operation", help="来自 web ops 的 feature.operation，也可传页面内唯一操作名或 operationId")
    call_parser.add_argument("-p", "--path-param", action="append", help="路径参数 key=value，可重复")
    call_parser.add_argument("-q", "--query", action="append", help="查询参数 key=value，可重复")
    add_payload_options(call_parser)
    call_parser.add_argument("--no-auth", action="store_true", help="不附带 Authorization")

    function_call_parser = web_sub.add_parser("function-call", help="按前端 API 导出函数名调用接口")
    function_call_parser.add_argument("function", help="函数名或 module.function，例如 accounts.getAccountDetails")
    function_call_parser.add_argument("--frontend-root", default="frontend/src", help="前端源码目录，默认 frontend/src")
    function_call_parser.add_argument("-p", "--path-param", action="append", help="路径参数 key=value，可重复")
    function_call_parser.add_argument("-q", "--query", action="append", help="查询参数 key=value，可重复")
    add_payload_options(function_call_parser)
    function_call_parser.add_argument("--no-auth", action="store_true", help="不附带 Authorization")

    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    if args.web_action == "pages":
        rows = [
            {
                "page": page.key,
                "label": page.label,
                "path": page.path,
                "features": ",".join(page.features),
            }
            for page in WEB_PAGES
            if _matches_page(page, args.search)
        ]
        print_output(rows, json_output=args.json, columns=["page", "label", "path", "features"])
        return

    if args.web_action == "ws":
        client = build_client(args, require_token=False)
        run_chat_new_ws(
            client.base_url,
            args.account_id,
            limit=args.limit,
            timeout=args.timeout,
            ping_interval=args.ping_interval,
            raw=args.raw,
            json_output=args.json,
        )
        return

    require_token = (
        args.web_action in {"call", "function-call", "smoke"}
        and not getattr(args, "no_auth", False)
        and not getattr(args, "dry_run", False)
    )
    client = build_client(args, require_token=require_token)
    openapi = load_openapi(args, client)
    grouped = group_operations_by_feature(openapi)

    if args.web_action == "coverage":
        if args.unmapped_features:
            rows = _unmapped_feature_rows(grouped, args.search)
            print_output(rows, json_output=args.json, columns=["feature", "operations", "tags"])
            return
        rows = _coverage_rows(grouped, search=args.search, only=args.only)
        print_output(
            rows,
            json_output=args.json,
            columns=["status", "page", "label", "path", "operations", "missing_features"],
        )
        return

    if args.web_action == "audit":
        rows = [
            row
            for row in audit_frontend_endpoints(openapi, args.frontend_root)
            if (args.only == "all" or row["status"] == args.only) and _matches_coverage(row, args.search)
        ]
        print_output(
            rows,
            json_output=args.json,
            columns=["status", "method", "path", "feature", "operation_id", "sources"],
            max_width=80,
        )
        return

    if args.web_action == "functions":
        rows = _frontend_function_rows(
            openapi,
            args.frontend_root,
            search=args.search,
            only=args.only,
            include_optional=args.include_optional,
        )
        print_output(
            rows,
            json_output=args.json,
            columns=["status", "function", "method", "path", "page", "operation", "inputs", "source", "command"],
            max_width=100,
        )
        return

    if args.web_action == "function":
        rows = _frontend_function_detail_rows(
            openapi,
            args.frontend_root,
            args.function,
            include_optional=args.include_optional,
        )
        print_output(
            rows,
            json_output=args.json,
            columns=["status", "function", "method", "path", "page", "operation", "inputs", "source", "command"],
            max_width=100,
        )
        return

    if args.web_action == "verify":
        rows = _verification_rows(
            openapi,
            grouped,
            raw_page=args.page,
            frontend_root=args.frontend_root,
            skip_frontend=args.skip_frontend,
        )
        print_output(rows, json_output=args.json, columns=["check", "status", "count", "detail"], max_width=100)
        failures = _verification_failure_count(rows)
        if failures and not args.allow_failures:
            raise CliError(f"verify 检查失败：{failures} 项未通过。可加 --allow-failures 只输出报告。")
        return

    if args.web_action == "smoke":
        pages = _resolve_smoke_pages(args.page)
        candidates = web_smoke_candidates(pages, grouped, search=args.search)
        rows = run_smoke_candidates(
            client,
            candidates,
            auth=not args.no_auth,
            dry_run=args.dry_run,
            limit=max(args.limit, 0),
            fail_fast=args.fail_fast,
        )
        print_output(
            rows,
            json_output=args.json,
            columns=["status", "page", "operation", "method", "path", "detail"],
            max_width=80,
        )
        failures = _smoke_failure_count(rows)
        if failures and not args.dry_run and not args.allow_failures:
            raise CliError(f"smoke 检查失败：{failures} 个接口失败。可加 --allow-failures 只输出报告。")
        return

    if args.web_action == "function-call":
        _, operation = _resolve_frontend_api_function(openapi, args.frontend_root, args.function)
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

    page = find_page(args.page)
    if not page:
        raise CliError(f"未找到页面：{args.page}。可用 web pages 查看。")

    if args.web_action == "ops":
        rows = _page_operation_rows(page, grouped, args.search)
        print_output(rows, json_output=args.json, columns=["operation", "method", "path", "summary", "inputs"])
        return

    if args.web_action == "examples":
        rows = _page_example_rows(openapi, page, grouped, args.search, include_optional=args.include_optional)
        print_command_examples(rows, json_output=args.json)
        return

    if args.web_action == "call":
        operation = _resolve_page_operation(grouped, page, args.operation)
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


def _coverage_rows(
    grouped: dict[str, list[Operation]],
    *,
    search: str | None,
    only: str,
    pages: list[WebPage] | None = None,
) -> list[dict[str, object]]:
    rows = []
    for page in pages or list(WEB_PAGES):
        missing = [feature for feature in page.features if feature not in grouped]
        status = _coverage_status(page, missing)
        row = {
            "status": status,
            "page": page.key,
            "label": page.label,
            "path": page.path,
            "features": ",".join(page.features),
            "operations": sum(len(grouped.get(feature, [])) for feature in page.features),
            "missing_features": ",".join(missing),
        }
        if (only == "all" or status == only) and _matches_coverage(row, search):
            rows.append(row)
    return rows


def _unmapped_feature_rows(grouped: dict[str, list[Operation]], search: str | None) -> list[dict[str, object]]:
    mapped_features = {feature for page in WEB_PAGES for feature in page.features}
    rows = []
    for feature, operations in grouped.items():
        if feature in mapped_features:
            continue
        tags = sorted({tag for operation in operations for tag in operation.tags})
        row = {"feature": feature, "operations": len(operations), "tags": ",".join(tags)}
        if _matches_coverage(row, search):
            rows.append(row)
    return rows


def _coverage_status(page: WebPage, missing: list[str]) -> str:
    if not page.features:
        return "static"
    return "missing" if missing else "ok"


def _verification_rows(
    openapi: dict[str, object],
    grouped: dict[str, list[Operation]],
    *,
    raw_page: str | None,
    frontend_root: str,
    skip_frontend: bool,
) -> list[dict[str, object]]:
    pages = _resolve_smoke_pages(raw_page) if raw_page else list(WEB_PAGES)
    coverage_issues = _coverage_rows(grouped, search=None, only="missing", pages=pages)
    rows = [
        _verification_row(
            "page_coverage",
            coverage_issues,
            "页面声明的 feature 都能在 OpenAPI 中找到",
        )
    ]

    if raw_page:
        rows.append(
            {
                "check": "backend_feature_mapping",
                "status": "skipped",
                "count": 0,
                "detail": "页面级验证不检查全局后端 feature 映射",
            }
        )
    else:
        rows.append(
            _verification_row(
                "backend_feature_mapping",
                _unmapped_feature_rows(grouped, search=None),
                "后端 OpenAPI feature 都映射到了至少一个网页版页面",
            )
        )

    if skip_frontend:
        rows.append(
            {
                "check": "frontend_openapi_audit",
                "status": "skipped",
                "count": 0,
                "detail": "已跳过前端源码 API 审计",
            }
        )
    else:
        frontend_issues = [
            row for row in audit_frontend_endpoints(openapi, frontend_root) if row.get("status") != "ok"
        ]
        rows.append(
            _verification_row(
                "frontend_openapi_audit",
                frontend_issues,
                "前端源码实际调用的 API 都存在于 OpenAPI 且 feature 已映射",
            )
        )
    return rows


def _verification_row(check: str, issues: list[dict[str, object]], success_detail: str) -> dict[str, object]:
    return {
        "check": check,
        "status": "failed" if issues else "ok",
        "count": len(issues),
        "detail": _issue_detail(issues) if issues else success_detail,
    }


def _issue_detail(issues: list[dict[str, object]]) -> str:
    preview = []
    for issue in issues[:3]:
        label = issue.get("page") or issue.get("feature") or issue.get("path") or issue.get("operation_id")
        if label:
            preview.append(str(label))
    suffix = "" if len(issues) <= 3 else f" 等 {len(issues)} 项"
    return ", ".join(preview) + suffix if preview else f"{len(issues)} 项问题"


def _verification_failure_count(rows: list[dict[str, object]]) -> int:
    return sum(1 for row in rows if row.get("status") == "failed")


def _resolve_smoke_pages(raw_page: str | None) -> list[WebPage]:
    if not raw_page:
        return list(WEB_PAGES)
    page = find_page(raw_page)
    if not page:
        raise CliError(f"未找到页面：{raw_page}。可用 web pages 查看。")
    return [page]


def _smoke_failure_count(rows: list[dict[str, object]]) -> int:
    return sum(1 for row in rows if row.get("status") == "failed")


def _frontend_function_rows(
    openapi: dict[str, object],
    frontend_root: str,
    *,
    search: str | None,
    only: str,
    include_optional: bool,
) -> list[dict[str, object]]:
    operations = list_operations(openapi)
    mapped_features = {feature for page in WEB_PAGES for feature in page.features}
    rows = [
        _frontend_function_row(openapi, function, operations, mapped_features, include_optional)
        for function in scan_frontend_api_functions(frontend_root)
    ]
    return [
        row
        for row in rows
        if (only == "all" or row["status"] == only) and _matches_operation(row, search)
    ]


def _frontend_function_detail_rows(
    openapi: dict[str, object],
    frontend_root: str,
    raw: str,
    *,
    include_optional: bool,
) -> list[dict[str, object]]:
    functions = scan_frontend_api_functions(frontend_root)
    matches = _matching_frontend_functions(functions, raw)
    _ensure_unambiguous_frontend_identity(matches, raw)
    operations = list_operations(openapi)
    mapped_features = {feature for page in WEB_PAGES for feature in page.features}
    return [
        _frontend_function_row(openapi, function, operations, mapped_features, include_optional)
        for function in matches
    ]


def _frontend_function_row(
    openapi: dict[str, object],
    function: FrontendApiFunction,
    operations: list[Operation],
    mapped_features: set[str],
    include_optional: bool,
) -> dict[str, object]:
    operation = match_operation(function, operations)
    feature = feature_key(function.path)
    pages = _pages_for_function(function, feature)
    status = _frontend_function_status(operation, feature, mapped_features)
    operation_name = f"{feature}.{operation_slug(operation)}" if operation else ""
    return {
        "status": status,
        "function": _function_key(function),
        "method": function.method,
        "path": function.path,
        "feature": feature,
        "page": pages[0].key if pages else "",
        "pages": ",".join(page.key for page in pages),
        "operation": operation_name,
        "inputs": operation_inputs(operation) if operation else "",
        "operation_id": operation.operation_id if operation else "",
        "source": function.source,
        "command": _frontend_function_command(openapi, operation, feature, pages, include_optional),
    }


def _frontend_function_status(operation: Operation | None, feature: str, mapped_features: set[str]) -> str:
    if not operation:
        return "missing_openapi"
    return "ok" if feature in mapped_features else "unmapped_feature"


def _frontend_function_command(
    openapi: dict[str, object],
    operation: Operation | None,
    feature: str,
    pages: list[WebPage],
    include_optional: bool,
) -> str:
    if not operation:
        return ""
    if pages:
        operation_name = f"{feature}.{operation_slug(operation)}"
        command_parts = ["xianyu-cli", "web", "call", pages[0].key, operation_name]
    else:
        command_parts = ["xianyu-cli", "features", "call", feature, operation_slug(operation)]
    return operation_command_template(openapi, operation, command_parts, include_optional=include_optional)


def _resolve_frontend_api_function(
    openapi: dict[str, object], frontend_root: str, raw: str
) -> tuple[FrontendApiFunction, Operation]:
    matches = _matching_frontend_functions(scan_frontend_api_functions(frontend_root), raw)
    if not matches:
        raise CliError(f"未找到前端 API 函数：{raw}。可用 web functions --search {raw} 查看。")
    _ensure_unambiguous_frontend_identity(matches, raw)
    if len(matches) > 1:
        identities = {_function_key(function) for function in matches}
        choices = ", ".join(f"{_function_key(function)} {function.method} {function.path}" for function in matches[:8])
        if len(identities) == 1:
            identity = next(iter(identities))
            raise CliError(f"前端 API 函数 {identity} 对应多个后端接口。请用 web function {identity} 查看具体调用模板：{choices}")
    operation = match_operation(matches[0], list_operations(openapi))
    if not operation:
        raise CliError(f"前端 API 函数未匹配到 OpenAPI：{_function_key(matches[0])} {matches[0].path}")
    return matches[0], operation


def _matching_frontend_functions(functions: list[FrontendApiFunction], raw: str) -> list[FrontendApiFunction]:
    if "." in raw:
        return [function for function in functions if _function_key(function) == raw]
    return [function for function in functions if function.name == raw]


def _ensure_unambiguous_frontend_identity(functions: list[FrontendApiFunction], raw: str) -> None:
    identities = sorted({_function_key(function) for function in functions})
    if len(identities) > 1:
        raise CliError(f"前端 API 函数不唯一：{raw}。请使用 module.function。可选：{', '.join(identities[:8])}")


def _function_key(function: FrontendApiFunction) -> str:
    return f"{function.module}.{function.name}"


def _pages_for_function(function: FrontendApiFunction, feature: str) -> list[WebPage]:
    pages = [page for page in WEB_PAGES if feature in page.features]
    return sorted(pages, key=lambda page: _page_preference(page, function.module))


def _page_preference(page: WebPage, module: str) -> tuple[int, str]:
    normalized_module = module.replace("_", "-").lower()
    if page.key == normalized_module or page.key.startswith(f"{normalized_module}-"):
        return 0, page.key
    return 1, page.key


def _page_operation_rows(
    page: WebPage, grouped: dict[str, list[Operation]], search: str | None
) -> list[dict[str, object]]:
    rows = []
    for feature in page.features:
        for operation in grouped.get(feature, []):
            row = {
                "operation": f"{feature}.{operation_slug(operation)}",
                "method": operation.method,
                "path": operation.path,
                "summary": operation.summary,
                "inputs": operation_inputs(operation),
                "operation_id": operation.operation_id,
            }
            if _matches_operation(row, search):
                rows.append(row)
    return rows


def _page_example_rows(
    openapi: dict[str, object],
    page: WebPage,
    grouped: dict[str, list[Operation]],
    search: str | None,
    *,
    include_optional: bool,
) -> list[dict[str, object]]:
    rows = []
    for feature in page.features:
        for operation in grouped.get(feature, []):
            operation_name = f"{feature}.{operation_slug(operation)}"
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
                    ["xianyu-cli", "web", "call", page.key, operation_name],
                    include_optional=include_optional,
                ),
            }
            if _matches_operation(row, search):
                rows.append(row)
    return rows


def _resolve_page_operation(grouped: dict[str, list[Operation]], page: WebPage, raw: str) -> Operation:
    if "." in raw:
        feature, operation_name = _split_operation_name(raw)
        if feature not in page.features:
            raise CliError(f"页面 {page.key} 不包含 feature：{feature}。可用 web ops {page.key} 查看。")
        return _find_page_operation(grouped, feature, operation_name)

    matches = [
        operation
        for feature in page.features
        for operation in grouped.get(feature, [])
        if operation_slug(operation) == raw or operation.operation_id == raw
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        choices = ", ".join(_page_operation_choices(page, grouped))
        raise CliError(f"操作名不唯一：{raw}。请改用 feature.operation。可用选项：{choices}")
    raise CliError(f"页面 {page.key} 下未找到操作：{raw}。可用 web ops {page.key} 查看。")


def _page_operation_choices(page: WebPage, grouped: dict[str, list[Operation]]) -> list[str]:
    return [
        f"{feature}.{operation_slug(operation)}"
        for feature in page.features
        for operation in grouped.get(feature, [])
    ]


def _find_page_operation(grouped: dict[str, list[Operation]], feature: str, operation_name: str) -> Operation:
    matches = [operation for operation in grouped.get(feature, []) if operation_slug(operation) == operation_name]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        ids = ", ".join(operation.operation_id for operation in matches)
        raise CliError(f"操作名不唯一：{feature}.{operation_name}。可用 routes call 调用 operationId：{ids}")
    raise CliError(f"未找到操作：{feature}.{operation_name}")


def _split_operation_name(raw: str) -> tuple[str, str]:
    if "." not in raw:
        raise CliError("操作名格式应为 feature.operation，可用 web ops <page> 查看。")
    feature, operation = raw.split(".", 1)
    if not feature or not operation:
        raise CliError("操作名格式应为 feature.operation，可用 web ops <page> 查看。")
    return feature, operation


def _matches_page(page, search: str | None) -> bool:
    if not search:
        return True
    haystack = " ".join([page.key, page.label, page.path, *page.features]).lower()
    return search.lower() in haystack


def _matches_operation(row: dict[str, object], search: str | None) -> bool:
    if not search:
        return True
    haystack = " ".join(str(value) for value in row.values()).lower()
    return search.lower() in haystack


def _matches_coverage(row: dict[str, object], search: str | None) -> bool:
    if not search:
        return True
    haystack = " ".join(str(value) for value in row.values()).lower()
    return search.lower() in haystack
