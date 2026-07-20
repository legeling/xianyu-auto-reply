"""
在线聊天(新) WebSocket 路由

功能：
1. 前端通过 WebSocket 连接后端，订阅指定账号的 IM 实时消息推送
2. 当 IM 服务器推送新消息时，后端解密后实时转发给前端
3. 支持心跳保活（ping/pong）

与 chat_new.py 的 HTTP 接口配合使用：
- 前端先通过 HTTP 接口首次加载会话列表和消息
- 然后通过此 WebSocket 接收后续的实时更新
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from loguru import logger
from sqlalchemy import select

from app.core.security import decode_token
from app.services.chat_new import get_im_session_manager
from common.db.session import async_session_maker
from common.models import User, UserRole, UserStatus
from common.models.xy_account import XYAccount
from common.schemas.auth import TokenPayload

router = APIRouter(prefix="/chat-new")

# WebSocket 自定义关闭码
WS_CLOSE_UNAUTHORIZED = 4401  # 未认证（token 缺失/无效/用户失效）
WS_CLOSE_FORBIDDEN = 4403  # 已认证但无权访问该账号


async def _authenticate_ws_user(token: str | None) -> User | None:
    """
    校验 WebSocket 连接携带的 token，返回对应的活跃用户。

    校验失败（token 缺失/无效、用户不存在或非活跃）时返回 None。
    """
    if not token:
        return None
    try:
        raw_payload = decode_token(token)
        # 安全：与 get_current_user 一致的令牌类型校验（拒绝 refresh token 混淆使用；
        # 无 type 字段的旧令牌按 access 兼容处理）
        if raw_payload.get("type", "access") != "access":
            return None
        payload = TokenPayload(**raw_payload)
        if payload.sub is None:
            return None
        user_id = int(payload.sub)
    except (JWTError, ValueError, TypeError):
        return None

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if not user or user.status != UserStatus.ACTIVE:
        return None
    return user


async def _user_can_access_account(user: User, account_id: str) -> bool:
    """
    校验用户是否有权订阅指定账号的实时消息。

    管理员可访问全部；普通用户只能访问自己名下的账号（owner_id 匹配）。
    """
    if user.role == UserRole.ADMIN:
        return True

    async with async_session_maker() as session:
        result = await session.execute(
            select(XYAccount).where(XYAccount.account_id == account_id)
        )
        account = result.scalar_one_or_none()

    return account is not None and account.owner_id == user.id


# 通过 Sec-WebSocket-Protocol 传递令牌的子协议标记：
# 前端 new WebSocket(url, ["bearer", "<token>"])，服务端选回 "bearer" 完成协商。
WS_TOKEN_SUBPROTOCOL = "bearer"


def _extract_ws_token(websocket: WebSocket, query_token: str | None) -> tuple[str | None, str | None]:
    """从 WebSocket 握手提取登录令牌。

    安全：查询参数中的 token 会进入访问日志/浏览器历史，属于敏感信息泄露面。
    按优先级支持三种传递方式：
    1. Authorization: Bearer <token> 请求头（非浏览器客户端可用）；
    2. Sec-WebSocket-Protocol 子协议（浏览器推荐新用法）：
       new WebSocket(url, ["bearer", "<token>"])；
    3. 查询参数 token（旧用法，保留兼容，已标记废弃，前端应尽快迁移到方式 2）。

    Returns:
        (token, 需要协商回应的子协议或 None)
    """
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip(), None

    protocols = websocket.headers.get("sec-websocket-protocol")
    if protocols:
        parts = [p.strip() for p in protocols.split(",") if p.strip()]
        if len(parts) >= 2 and parts[0].lower() == WS_TOKEN_SUBPROTOCOL:
            # JWT 字符集（base64url + '.'）均为合法的 subprotocol token 字符
            return parts[1], WS_TOKEN_SUBPROTOCOL

    # 废弃兼容：查询参数 token
    return query_token, None


@router.websocket("/ws/{account_id}")
async def chat_new_websocket(
    websocket: WebSocket,
    account_id: str,
    token: str | None = Query(default=None, description="登录令牌（已废弃，请改用 Sec-WebSocket-Protocol 或 Authorization 头）"),
):
    """
    在线聊天(新) WebSocket 连接

    前端连接后，会自动将此 WebSocket 注册到 ImSessionManager，
    当 IM 推送消息到达时，会实时转发给前端。

    鉴权说明（按优先级）：
    - Authorization: Bearer <token> 请求头（非浏览器客户端）；
    - Sec-WebSocket-Protocol：new WebSocket(url, ["bearer", "<token>"])（浏览器推荐）；
    - 查询参数 `token`（旧用法，保留兼容、已废弃：token 会进入访问日志）。
    token 无效返回关闭码 4401；无权访问该账号返回关闭码 4403。

    推送消息格式示例：
    {
        "event": "new_message",
        "cid": "会话ID",
        "message": {
            "senderId": "发送者ID",
            "senderName": "发送者名称",
            "isSelf": false,
            "type": "text",
            "text": "消息内容",
            "images": [],
            "time": 1234567890000
        }
    }

    前端可发送的消息：
    - {"type": "ping"} 心跳检测

    Args:
        websocket: WebSocket 连接
        account_id: 账号ID
        token: 登录令牌（查询参数，已废弃的兼容方式）
    """
    # 从握手信息提取令牌（Header > Sec-WebSocket-Protocol > 查询参数）
    ws_token, negotiated_subprotocol = _extract_ws_token(websocket, token)

    # 鉴权：先 accept 再校验，确保自定义关闭码（4401/4403）能通过 WebSocket 关闭帧
    # 可靠送达浏览器（若在 accept 前 close，握手会被以 HTTP 拒绝，客户端只会收到 1006）。
    # 校验未通过时立即关闭，全程不注册到消息管理器、不下发任何数据，无信息泄露。
    # 若客户端通过子协议传 token，accept 时需选回该子协议完成协商。
    await websocket.accept(subprotocol=negotiated_subprotocol)

    user = await _authenticate_ws_user(ws_token)
    if user is None:
        logger.warning(f"【{account_id}】在线聊天 WebSocket 鉴权失败：token 无效或缺失，拒绝连接")
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    if not await _user_can_access_account(user, account_id):
        logger.warning(
            f"【{account_id}】用户 {user.id} 无权订阅该账号实时消息，拒绝连接"
        )
        await websocket.close(code=WS_CLOSE_FORBIDDEN)
        return

    logger.info(f"【{account_id}】在线聊天 WebSocket 已连接（用户 {user.id}）")

    manager = get_im_session_manager()

    try:
        # 注册到管理器，开始接收推送
        await manager.register_ws_client(account_id, websocket)

        # 发送连接成功消息
        await websocket.send_text(json.dumps({
            "event": "connected",
            "account_id": account_id,
            "message": "WebSocket 已连接，等待实时消息推送",
        }, ensure_ascii=False))

        # 持续接收前端消息（心跳等）
        await _receive_loop(websocket, account_id)

    except WebSocketDisconnect:
        logger.info(f"【{account_id}】在线聊天 WebSocket 已断开")
    except Exception as e:
        logger.error(f"【{account_id}】在线聊天 WebSocket 异常: {e}")
    finally:
        await manager.unregister_ws_client(account_id, websocket)
        logger.info(f"【{account_id}】在线聊天 WebSocket 已清理")


async def _receive_loop(websocket: WebSocket, account_id: str):
    """
    接收前端 WebSocket 消息的循环

    目前支持：
    - ping: 心跳，回复 pong
    - 其他: 忽略

    Args:
        websocket: WebSocket 连接
        account_id: 账号ID（用于日志）
    """
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_text(
                    json.dumps({"event": "pong"}, ensure_ascii=False)
                )
            else:
                logger.info(
                    f"【{account_id}】收到前端未知消息类型: {msg_type}"
                )
    except WebSocketDisconnect:
        raise
    except Exception as e:
        logger.error(f"【{account_id}】接收前端消息异常: {e}")
        raise
