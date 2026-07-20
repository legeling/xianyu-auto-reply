from __future__ import annotations

from types import SimpleNamespace

import pytest

from xianyu_cli.client import ApiClient, FilePart, _build_request_body, load_openapi
from xianyu_cli.exceptions import CliError
from xianyu_cli.parsing import parse_file_args


def test_parse_file_args_accepts_at_prefix() -> None:
    files = parse_file_args(["image=@/tmp/a.png"])

    assert files == [FilePart(field="image", path="/tmp/a.png")]


def test_build_request_body_rejects_json_with_file(tmp_path) -> None:
    upload = tmp_path / "a.txt"
    upload.write_text("hello", encoding="utf-8")

    with pytest.raises(CliError, match="JSON 请求体不能和 --form/--file 同时使用"):
        _build_request_body(data={"x": 1}, form=None, files=[FilePart("file", str(upload))])


def test_build_request_body_encodes_multipart(tmp_path) -> None:
    upload = tmp_path / "a.txt"
    upload.write_text("hello", encoding="utf-8")

    body, content_type = _build_request_body(
        data=None,
        form={"description": "测试"},
        files=[FilePart("file", str(upload))],
    )

    assert body is not None
    assert content_type is not None
    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="description"' in body
    assert "测试".encode("utf-8") in body
    assert b'name="file"; filename="a.txt"' in body
    assert b"hello" in body


def test_load_openapi_reads_local_file(tmp_path) -> None:
    openapi_file = tmp_path / "openapi.json"
    openapi_file.write_text('{"openapi":"3.1.0","paths":{}}', encoding="utf-8")
    args = SimpleNamespace(openapi_file=str(openapi_file))

    assert load_openapi(args, ApiClient("http://127.0.0.1:9"))["paths"] == {}
