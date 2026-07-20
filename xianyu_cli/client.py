"""HTTP API client used by all commands."""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from xianyu_cli.config import load_config
from xianyu_cli.constants import DEFAULT_BASE_URL
from xianyu_cli.exceptions import CliError


@dataclass(frozen=True)
class FilePart:
    field: str
    path: str


class ApiClient:
    """Small stdlib HTTP client for backend-web API requests."""

    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: Any | None = None,
        form: dict[str, Any] | None = None,
        files: list[FilePart] | None = None,
        output_path: str | None = None,
        auth: bool = True,
    ) -> Any:
        url = self._build_url(path, params)
        body = None
        headers = {"Accept": "application/json"}

        body, content_type = _build_request_body(data=data, form=form, files=files or [])
        if content_type:
            headers["Content-Type"] = content_type

        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = Request(url, data=body, headers=headers, method=method.upper())
        try:
            with urlopen(req, timeout=30) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
        except HTTPError as exc:
            raw = exc.read()
            message = _extract_error_message(raw) or f"HTTP {exc.code}"
            raise CliError(message) from exc
        except URLError as exc:
            raise CliError(f"请求失败：{exc.reason}") from exc

        if output_path:
            return _save_response(raw, output_path, content_type)
        if not raw:
            return None

        text = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def get_openapi(self) -> dict[str, Any]:
        response = self.request("GET", "/openapi.json", auth=False)
        if not isinstance(response, dict):
            raise CliError(
                "OpenAPI 响应格式异常。当前地址可能是前端地址，请把 base-url 设置为 backend-web 地址，例如 http://127.0.0.1:8089。"
            )
        return response

    def _build_url(self, path: str, params: dict[str, Any] | None) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{normalized_path}"
        clean_params = _clean_params(params or {})
        if clean_params:
            url = f"{url}?{urlencode(clean_params, doseq=True)}"
        return url


def build_client(args: argparse.Namespace, *, require_token: bool = True) -> ApiClient:
    config = load_config()
    base_url = args.base_url or os.environ.get("XIANYU_API_URL") or config.get("base_url") or DEFAULT_BASE_URL
    token = os.environ.get("XIANYU_TOKEN") or config.get("token")
    if require_token and not token:
        raise CliError("未登录。先执行 auth login，或用 auth token set 写入已有 token。")
    return ApiClient(str(base_url), str(token) if token else None)


def load_openapi(args: argparse.Namespace, client: ApiClient) -> dict[str, Any]:
    openapi_file = getattr(args, "openapi_file", None)
    if not openapi_file:
        return client.get_openapi()

    path = Path(str(openapi_file)).expanduser()
    if not path.is_file():
        raise CliError(f"OpenAPI 文件不存在：{openapi_file}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"OpenAPI 文件不是合法 JSON：{exc}") from exc

    if not isinstance(parsed, dict) or not isinstance(parsed.get("paths"), dict):
        raise CliError("OpenAPI 文件格式异常：缺少 paths 对象。")
    return parsed


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            clean[key] = "true" if value else "false"
        else:
            clean[key] = value
    return clean


def _build_request_body(
    *, data: Any | None, form: dict[str, Any] | None, files: list[FilePart]
) -> tuple[bytes | None, str | None]:
    if data is not None and (form or files):
        raise CliError("JSON 请求体不能和 --form/--file 同时使用。文件上传请用 --form 传普通字段。")
    if files or form:
        return _encode_multipart(form or {}, files)
    if data is None:
        return None, None
    return json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json"


def _encode_multipart(form: dict[str, Any], files: list[FilePart]) -> tuple[bytes, str]:
    boundary = f"----xianyu-cli-{uuid.uuid4().hex}"
    body = bytearray()

    for key, value in form.items():
        _append_form_field(body, boundary, key, value)
    for file_part in files:
        _append_file_field(body, boundary, file_part)

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _append_form_field(body: bytearray, boundary: str, key: str, value: Any) -> None:
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
    body.extend(_format_form_value(value).encode("utf-8"))
    body.extend(b"\r\n")


def _append_file_field(body: bytearray, boundary: str, file_part: FilePart) -> None:
    file_path = Path(file_part.path).expanduser()
    if not file_path.is_file():
        raise CliError(f"文件不存在或不是普通文件：{file_part.path}")

    filename = file_path.name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="{file_part.field}"; filename="{filename}"\r\n'.encode("utf-8")
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_path.read_bytes())
    body.extend(b"\r\n")


def _format_form_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _save_response(raw: bytes, output_path: str, content_type: str) -> dict[str, Any]:
    target = Path(output_path).expanduser()
    if target.parent != Path(""):
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {
        "saved_to": str(target.resolve()),
        "bytes": len(raw),
        "content_type": content_type,
    }


def _extract_error_message(raw: bytes) -> str | None:
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text.strip() or None
    detail = parsed.get("detail") if isinstance(parsed, dict) else None
    if isinstance(detail, str):
        return detail
    if detail:
        return json.dumps(detail, ensure_ascii=False)
    return None
