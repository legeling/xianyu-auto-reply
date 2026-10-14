"""Text/image reply management with the backend's replace and update semantics."""
from __future__ import annotations

import argparse
from urllib.parse import quote

from xianyu_cli.client import FilePart, build_client
from xianyu_cli.output import print_output
from xianyu_cli.request_args import add_json_options, parse_payload_args

PREFIX = "/api/v1/keywords-with-item-id"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("keywords", help="关键词回复查询、替换、修改、删除与导入导出")
    parser.add_argument("--account-id")
    actions = parser.add_subparsers(dest="keywords_action")
    listing = actions.add_parser("list")
    listing.add_argument("--account-id", default=argparse.SUPPRESS)
    for action in ("replace", "update", "delete", "import", "export", "image"):
        leaf = actions.add_parser(action, help={"replace": "替换账号的全部文本/位置回复；不是追加",
                                              "update": "更新单条关键词", "delete": "删除单条关键词",
                                              "import": "导入Excel", "export": "导出Excel", "image": "添加图片回复"}[action])
        leaf.add_argument("account")
        if action in {"replace", "update"}:
            add_json_options(leaf, required=True)
        if action in {"update", "delete", "image"}:
            leaf.add_argument("keyword")
        if action == "update":
            leaf.add_argument("--old-item-id", default="")
        if action in {"delete", "image"}:
            leaf.add_argument("--item-id", default="")
        if action == "delete":
            leaf.add_argument("--rule-id", type=int)
        if action in {"import", "image"}:
            leaf.add_argument("path")
        if action == "export":
            leaf.add_argument("--output", required=True)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    action, method, path, kwargs = args.keywords_action or "list", "GET", PREFIX, {}
    if action == "list":
        if args.account_id:
            path += f"/{quote(args.account_id, safe='')}"
    else:
        path += f"/{quote(args.account, safe='')}"
        if action == "replace":
            method, kwargs["data"] = "POST", parse_payload_args(args).data
        elif action in {"update", "delete"}:
            path += f"/{quote(args.keyword, safe='')}"
            method = "PUT" if action == "update" else "DELETE"
            if action == "update":
                kwargs.update(data=parse_payload_args(args).data, params={"old_item_id": args.old_item_id})
            else:
                kwargs["params"] = {"item_id": args.item_id, "rule_id": args.rule_id}
        elif action == "export":
            path += "/export"
            kwargs["output_path"] = args.output
        elif action == "import":
            method, path = "POST", path + "/import"
            kwargs["files"] = [FilePart("file", args.path)]
        else:
            method, path = "POST", path + "/image"
            kwargs["form"] = {"keyword": args.keyword, "item_id": args.item_id}
            kwargs["files"] = [FilePart("image", args.path)]
    print_output(build_client(args).request(method, path, **kwargs), json_output=args.json,
                 columns=["account_id", "keyword", "reply", "item_id"] if action == "list" else None)
