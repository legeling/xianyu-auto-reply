"""Product materials, media, addresses, publication and automatic relisting."""
from __future__ import annotations

import argparse
from urllib.parse import quote

from xianyu_cli.client import FilePart, build_client
from xianyu_cli.exceptions import CliError
from xianyu_cli.output import print_output
from xianyu_cli.parsing import parse_bool
from xianyu_cli.request_args import add_json_options, add_pagination_options, parse_payload_args

PREFIX = "/api/v1/product-publish"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("publish", help="商品素材、图片、地址、单品/批量上架和自动续售")
    actions = parser.add_subparsers(dest="publish_action", required=True)
    materials = actions.add_parser("materials", help="商品素材增删改查")
    leaves = materials.add_subparsers(dest="material_action", required=True)
    listing = leaves.add_parser("list")
    add_pagination_options(listing)
    for flag in ("title", "category", "condition", "platform-category-id"):
        listing.add_argument(f"--{flag}")
    for action in ("create", "get", "update", "delete"):
        leaf = leaves.add_parser(action)
        if action != "create":
            leaf.add_argument("material_id", type=int)
        if action in {"create", "update"}:
            add_json_options(leaf, required=True)
    bulk = leaves.add_parser("batch-delete")
    bulk.add_argument("ids", nargs="+", type=int)
    capability = actions.add_parser("check-account", help="检查账号Cookie和发布能力")
    capability.add_argument("account_id")
    for action in ("single", "recommend-category"):
        leaf = actions.add_parser(action, help="发布一件商品" if action == "single" else "推荐分类与属性")
        add_json_options(leaf, required=True)
    batch = actions.add_parser("batch", help="按账号与素材组合提交批量发布任务")
    batch.add_argument("--account-id", action="append", required=True)
    batch.add_argument("--material-id", action="append", type=int, required=True)
    status = actions.add_parser("status", help="查询批量结果；完成但有失败时返回非零")
    status.add_argument("batch_id")
    logs = actions.add_parser("logs", help="发布日志")
    add_pagination_options(logs)
    logs.add_argument("--account-id")
    logs.add_argument("--status")
    actions.add_parser("clear-logs", help="清理后端规定保留期外的发布日志")
    for action in ("upload-images", "upload-videos"):
        leaf = actions.add_parser(action, help="上传发布素材，返回可用于商品JSON的路径")
        leaf.add_argument("paths", nargs="+")
    for group in ("addresses", "personal-addresses"):
        parent = actions.add_parser(group, help="随机地址库" if group == "addresses" else "个人发布地址库")
        leaves = parent.add_subparsers(dest="address_action", required=True)
        listing = leaves.add_parser("list")
        add_pagination_options(listing)
        listing.add_argument("--keyword")
        if group == "addresses":
            listing.add_argument("--account-id")
            listing.add_argument("--is-enabled", type=parse_bool)
        for action in ("create", "update"):
            leaf = leaves.add_parser(action)
            if action == "update":
                leaf.add_argument("address_id", type=int)
            add_json_options(leaf, required=True)
        delete = leaves.add_parser("delete", help="删除指定地址ID")
        delete.add_argument("ids", nargs="+", type=int)
        if group == "addresses":
            switch = leaves.add_parser("set-enabled")
            switch.add_argument("address_id", type=int)
            switch.add_argument("enabled", type=parse_bool)
        else:
            upload = leaves.add_parser("import")
            upload.add_argument("path")
            export = leaves.add_parser("export")
            export.add_argument("--output", required=True)
    relist = actions.add_parser("relist", help="自动续售配置、事件和人工对账")
    leaves = relist.add_subparsers(dest="relist_action", required=True)
    for action in ("get", "set", "events", "reconcile", "mark-failed"):
        leaf = leaves.add_parser(action)
        leaf.add_argument("material_id", type=int)
        if action in {"reconcile", "mark-failed"}:
            leaf.add_argument("event_id", type=int)
        if action in {"set", "reconcile"}:
            add_json_options(leaf, required=True)
        if action == "events":
            add_pagination_options(leaf)
    events = leaves.add_parser("all-events")
    add_pagination_options(events)
    events.add_argument("--status")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args)
    action = args.publish_action
    method, path, kwargs = "GET", PREFIX, {}
    if action == "materials":
        path += "/materials"
        leaf = args.material_action
        if leaf == "list":
            kwargs["params"] = {key: getattr(args, key) for key in
                                ("page", "page_size", "title", "category", "condition", "platform_category_id")}
        elif leaf == "batch-delete":
            method, path = "POST", path + "/batch-delete"
            kwargs["data"] = {"ids": args.ids}
        else:
            if leaf != "create":
                path += f"/{args.material_id}"
            method = {"create": "POST", "get": "GET", "update": "PUT", "delete": "DELETE"}[leaf]
            if leaf in {"create", "update"}:
                kwargs["data"] = parse_payload_args(args).data
    elif action == "check-account":
        path += f"/accounts/{quote(args.account_id, safe='')}/capability"
    elif action in {"single", "recommend-category"}:
        method, path = "POST", path + ("/publish/single" if action == "single" else "/category/recommend")
        kwargs["data"] = parse_payload_args(args).data
    elif action == "batch":
        method, path = "POST", path + "/publish/batch"
        kwargs["data"] = {"account_ids": args.account_id, "material_ids": args.material_id}
    elif action == "status":
        path += f"/publish/batch/{quote(args.batch_id, safe='')}/status"
    elif action == "logs":
        path += "/logs"
        kwargs["params"] = {key: getattr(args, key) for key in ("page", "page_size", "account_id", "status")}
    elif action == "clear-logs":
        method, path = "DELETE", path + "/logs/clear"
    elif action in {"upload-images", "upload-videos"}:
        method, path = "POST", path + ("/upload/images" if action == "upload-images" else "/upload/videos")
        kwargs["files"] = [FilePart("files", p) for p in args.paths]
    elif action in {"addresses", "personal-addresses"}:
        path += f"/{action}"
        leaf = args.address_action
        if leaf == "list":
            kwargs["params"] = {key: getattr(args, key) for key in ("page", "page_size", "keyword")}
            if action == "addresses":
                kwargs["params"].update(account_id=args.account_id, is_enabled=args.is_enabled)
        elif leaf in {"create", "update"}:
            method = "POST" if leaf == "create" else "PUT"
            if leaf == "update":
                path += f"/{args.address_id}"
            kwargs["data"] = parse_payload_args(args).data
        elif leaf == "delete":
            method, path = "POST", path + "/batch-delete"
            kwargs["data"] = {"ids": args.ids}
        elif leaf == "set-enabled":
            method, path = "PUT", path + f"/{args.address_id}/status"
            kwargs["data"] = {"is_enabled": args.enabled}
        elif leaf == "import":
            method, path = "POST", path + "/import"
            kwargs["files"] = [FilePart("file", args.path)]
        else:
            path += "/export"
            kwargs["output_path"] = args.output
    else:
        leaf = args.relist_action
        if leaf == "all-events":
            path += "/auto-relist/events"
            kwargs["params"] = {key: getattr(args, key) for key in ("page", "page_size", "status")}
        else:
            path += f"/materials/{args.material_id}/auto-relist"
            if leaf == "set":
                method, kwargs["data"] = "PUT", parse_payload_args(args).data
            elif leaf == "events":
                path += "/events"
                kwargs["params"] = {"page": args.page, "page_size": args.page_size}
            elif leaf in {"reconcile", "mark-failed"}:
                method, path = "POST", path + f"/events/{args.event_id}/{leaf}"
                if leaf == "reconcile":
                    kwargs["data"] = parse_payload_args(args).data
    response = client.request(method, path, **kwargs)
    if "output_path" not in kwargs and (not isinstance(response, dict) or response.get("success") is not True):
        message = response.get("message") if isinstance(response, dict) else None
        raise CliError(message or "商品发布接口未返回成功结果")
    print_output(response, json_output=args.json)
    if action == "status":
        data = response.get("data") or {}
        if data.get("finished") and data.get("failed", 0):
            raise CliError("批量发布已结束但有失败商品，请查看发布日志；未自动重复提交")
