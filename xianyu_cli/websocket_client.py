"""WebSocket helpers for realtime backend features."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable
from urllib.parse import quote, urlsplit, urlunsplit

from xianyu_cli.exceptions import CliError
from xianyu_cli.output import print_output


def build_chat_new_ws_url(base_url: str, account_id: str) -> str:
    """Build the online-chat WebSocket URL from the configured HTTP API base URL."""
    parsed = urlsplit(base_url.rstrip("/"))
    scheme = _ws_scheme(parsed.scheme)
    if not parsed.netloc:
        raise CliError(f"WebSocket 地址无效：{base_url}")

    prefix = parsed.path.rstrip("/")
    path = f"{prefix}/api/v1/chat-new/ws/{quote(account_id, safe='')}"
    return urlunsplit((scheme, parsed.netloc, path, "", ""))


def run_chat_new_ws(
    base_url: str,
    account_id: str,
    *,
    limit: int,
    timeout: float | None,
    ping_interval: float,
    raw: bool,
    json_output: bool,
) -> None:
    """Connect to the online-chat WebSocket and print received events."""
    _validate_ws_options(limit=limit, timeout=timeout, ping_interval=ping_interval)
    url = build_chat_new_ws_url(base_url, account_id)
    asyncio.run(
        _listen_chat_new_ws(
            url,
            limit=limit,
            timeout=timeout,
            ping_interval=ping_interval,
            raw=raw,
            json_output=json_output,
            output=print,
        )
    )


async def _listen_chat_new_ws(
    url: str,
    *,
    limit: int,
    timeout: float | None,
    ping_interval: float,
    raw: bool,
    json_output: bool,
    output: Callable[[str], None],
) -> list[Any]:
    try:
        import websockets
    except ImportError as exc:  # pragma: no cover - dependency is declared by the project.
        raise CliError("缺少 websockets 依赖，请先安装项目依赖。") from exc

    messages: list[Any] = []
    try:
        async with websockets.connect(url) as websocket:
            ping_task = _create_ping_task(websocket, ping_interval)
            try:
                while limit == 0 or len(messages) < limit:
                    raw_message = await _receive_text(websocket, timeout)
                    message = raw_message if raw else _parse_ws_message(raw_message)
                    messages.append(message)
                    _emit_ws_message(message, raw=raw, json_output=json_output, streaming=limit == 0, output=output)
            finally:
                await _cancel_ping_task(ping_task)
    except CliError:
        raise
    except OSError as exc:
        raise CliError(f"WebSocket 连接失败：{exc}") from exc
    except Exception as exc:
        raise CliError(f"WebSocket 异常：{exc}") from exc

    if json_output and limit > 0:
        print_output(messages, json_output=True)
    return messages


def _ws_scheme(scheme: str) -> str:
    if scheme in {"http", "ws"}:
        return "ws"
    if scheme in {"https", "wss"}:
        return "wss"
    raise CliError(f"WebSocket 地址协议不支持：{scheme or '<empty>'}")


def _validate_ws_options(*, limit: int, timeout: float | None, ping_interval: float) -> None:
    if limit < 0:
        raise CliError("--limit 不能小于 0。")
    if timeout is not None and timeout <= 0:
        raise CliError("--timeout 必须大于 0。")
    if ping_interval < 0:
        raise CliError("--ping-interval 不能小于 0。")


def _create_ping_task(websocket: Any, ping_interval: float) -> asyncio.Task[None] | None:
    if ping_interval == 0:
        return None
    return asyncio.create_task(_send_ping_loop(websocket, ping_interval))


async def _send_ping_loop(websocket: Any, ping_interval: float) -> None:
    while True:
        await asyncio.sleep(ping_interval)
        await websocket.send(json.dumps({"type": "ping"}, ensure_ascii=False))


async def _cancel_ping_task(task: asyncio.Task[None] | None) -> None:
    if not task:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return


async def _receive_text(websocket: Any, timeout: float | None) -> str:
    try:
        if timeout is None:
            message = await websocket.recv()
        else:
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise CliError(f"WebSocket 等待消息超时：{timeout} 秒") from exc

    if isinstance(message, bytes):
        return message.decode("utf-8", errors="replace")
    return str(message)


def _parse_ws_message(raw_message: str) -> Any:
    try:
        return json.loads(raw_message)
    except json.JSONDecodeError:
        return {"event": "message", "data": raw_message}


def _emit_ws_message(
    message: Any,
    *,
    raw: bool,
    json_output: bool,
    streaming: bool,
    output: Callable[[str], None],
) -> None:
    if raw:
        output(str(message))
        return
    if json_output and streaming:
        output(json.dumps(message, ensure_ascii=False))
        return
    if not json_output:
        output(_format_ws_message(message))


def _format_ws_message(message: Any) -> str:
    if not isinstance(message, dict):
        return json.dumps(message, ensure_ascii=False)

    event = str(message.get("event") or "message")
    if event == "connected":
        account_id = message.get("account_id", "")
        detail = message.get("message", "")
        return f"[connected] account={account_id} {detail}".strip()
    if event == "pong":
        return "[pong]"
    if event == "new_message":
        return _format_new_message(message)
    return json.dumps(message, ensure_ascii=False)


def _format_new_message(message: dict[str, Any]) -> str:
    chat_message = message.get("message") if isinstance(message.get("message"), dict) else {}
    sender = chat_message.get("senderName") or chat_message.get("senderId") or ""
    text = chat_message.get("text") or ""
    images = chat_message.get("images")
    image_count = len(images) if isinstance(images, list) else 0
    image_detail = f" images={image_count}" if image_count else ""
    return f"[new_message] cid={message.get('cid', '')} sender={sender} text={text}{image_detail}".strip()
