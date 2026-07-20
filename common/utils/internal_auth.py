"""
服务间内部接口共享密钥鉴权（X-Internal-Token）

安全意图：
- websocket / scheduler 的 /internal/* 与 /password-login 等内部接口此前完全无鉴权，
  任何能访问服务端口的人都可以直接调用（启动/停止账号、订单发货、过滑块等高危操作）。
- 采用共享密钥 + hmac.compare_digest 常量时间比较，防止时序侧信道。
- fail-closed：服务端未配置 INTERNAL_API_TOKEN 时拒绝所有内部请求（503 并告警），
  避免"忘了配置 = 内部接口裸奔"；配置后令牌缺失/不匹配返回 401。

使用方式：
- 服务端（被调用方）：在内部路由上挂载 make_internal_token_dependency(get_settings) 依赖；
- 调用方：请求时携带 build_internal_headers(settings) 生成的请求头。
  所有服务共用 common.core.config.BaseConfig 中的 internal_api_token 字段
  （环境变量 INTERNAL_API_TOKEN），docker 部署时对各服务注入同一个值即可。
"""
from __future__ import annotations

import hmac
from typing import Callable

from fastapi import HTTPException, Request, status
from loguru import logger

# 内部接口鉴权请求头名称
INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def get_internal_api_token(settings) -> str:
    """从配置实例读取内部接口共享密钥（去除首尾空白）。"""
    return (getattr(settings, "internal_api_token", None) or "").strip()


def build_internal_headers(settings=None) -> dict[str, str]:
    """构造调用内部接口所需的鉴权请求头。

    Args:
        settings: 调用方服务的配置实例；不传时使用 common 基础配置
            （所有服务读取同一个 INTERNAL_API_TOKEN 环境变量，取值一致）。

    Returns:
        包含 X-Internal-Token 的请求头字典；未配置时返回空字典并告警
        （对端 fail-closed 会拒绝该请求，此处告警便于定位配置缺失）。
    """
    if settings is None:
        from common.core.config import get_settings

        settings = get_settings()
    token = get_internal_api_token(settings)
    if not token:
        logger.warning(
            "INTERNAL_API_TOKEN 未配置，本次内部接口调用将被对端拒绝（fail-closed），"
            "请为所有服务配置相同的 INTERNAL_API_TOKEN"
        )
        return {}
    return {INTERNAL_TOKEN_HEADER: token}


def make_internal_token_dependency(settings_getter: Callable[[], object]):
    """生成内部接口鉴权依赖（注入被调用方自己的配置实例）。

    Args:
        settings_getter: 返回配置实例的可调用对象（通常为各服务的 get_settings）。

    Returns:
        FastAPI 依赖：校验 X-Internal-Token 请求头。
    """

    async def _verify_internal_token(request: Request) -> None:
        expected = get_internal_api_token(settings_getter())
        if not expected:
            # fail-closed：宁可内部接口全部不可用，也不允许无鉴权暴露
            logger.error(
                f"内部接口 {request.url.path} 被拒绝：服务端未配置 INTERNAL_API_TOKEN（fail-closed）"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="内部接口未配置访问令牌，服务不可用",
            )
        provided = (request.headers.get(INTERNAL_TOKEN_HEADER) or "").strip()
        # 常量时间比较，防止时序侧信道逐字节探测密钥
        if not provided or not hmac.compare_digest(provided, expected):
            client_host = request.client.host if request.client else "-"
            logger.warning(
                f"内部接口 {request.url.path} 鉴权失败：X-Internal-Token 缺失或不匹配，"
                f"client={client_host}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="内部接口令牌无效",
            )

    return _verify_internal_token
