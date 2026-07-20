"""Raw API command."""
from __future__ import annotations

import argparse

from xianyu_cli.client import build_client
from xianyu_cli.output import print_output
from xianyu_cli.parsing import parse_key_value_args
from xianyu_cli.request_args import add_payload_options, parse_payload_args


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("api", help="直接调用任意 API")
    parser.add_argument(
        "method",
        choices=["GET", "POST", "PUT", "DELETE", "PATCH", "get", "post", "put", "delete", "patch"],
    )
    parser.add_argument("path", help="例如 /api/v1/cookies/details")
    parser.add_argument("-q", "--query", action="append", help="查询参数 key=value，可重复")
    add_payload_options(parser)
    parser.add_argument("--no-auth", action="store_true", help="不附带 Authorization")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> None:
    client = build_client(args, require_token=not args.no_auth)
    params = parse_key_value_args(args.query)
    payload = parse_payload_args(args)
    response = client.request(
        args.method,
        args.path,
        params=params,
        data=payload.data,
        form=payload.form,
        files=payload.files,
        output_path=payload.output_path,
        auth=not args.no_auth,
    )
    print_output(response, json_output=args.json)
