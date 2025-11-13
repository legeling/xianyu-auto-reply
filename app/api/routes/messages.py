"""消息发送与自动回复相关路由。"""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.api.dependencies import match_reply
from app.repositories.db_manager import db_manager
from app.services.xianyu_async import XianyuLive

router = APIRouter()

API_SECRET_KEY = "xianyu_api_secret_2024"


class SendMessageRequest(BaseModel):
    api_key: str
    cookie_id: str
    chat_id: str
    to_user_id: str
    message: str


class SendMessageResponse(BaseModel):
    success: bool
    message: str


class RequestModel(BaseModel):
    cookie_id: str
    msg_time: str
    user_url: str
    send_user_id: str
    send_user_name: str
    item_id: str
    send_message: str
    chat_id: str


class ResponseData(BaseModel):
    send_msg: str


class ResponseModel(BaseModel):
    code: int
    data: ResponseData


def verify_api_key(api_key: str) -> bool:
    """验证 API 秘钥。"""
    try:
        qq_secret_key = db_manager.get_system_setting("qq_reply_secret_key")
        if not qq_secret_key:
            qq_secret_key = API_SECRET_KEY
        return api_key == qq_secret_key
    except Exception as exc:  # noqa: BLE001
        logger.error(f"验证API秘钥时发生异常: {exc}")
        return api_key == API_SECRET_KEY


@router.post("/send-message", response_model=SendMessageResponse)
async def send_message_api(request: SendMessageRequest):
    """发送消息 API 接口（使用秘钥验证）。"""
    try:
        def clean_param(param_str):
            if isinstance(param_str, str):
                return param_str.replace("\\n", "").replace("\n", "")
            return param_str

        cleaned_api_key = clean_param(request.api_key)
        cleaned_cookie_id = clean_param(request.cookie_id)
        cleaned_chat_id = clean_param(request.chat_id)
        cleaned_to_user_id = clean_param(request.to_user_id)
        cleaned_message = clean_param(request.message)

        if not cleaned_api_key:
            logger.warning("API秘钥为空")
            return SendMessageResponse(success=False, message="API秘钥不能为空")

        if cleaned_api_key == "zhinina_test_key":
            logger.info("使用测试秘钥，直接返回成功")
            return SendMessageResponse(success=True, message="接口验证成功")

        if not verify_api_key(cleaned_api_key):
            logger.warning(f"API秘钥验证失败: {cleaned_api_key}")
            return SendMessageResponse(success=False, message="API秘钥验证失败")

        required_params = {
            "cookie_id": cleaned_cookie_id,
            "chat_id": cleaned_chat_id,
            "to_user_id": cleaned_to_user_id,
            "message": cleaned_message,
        }

        for param_name, param_value in required_params.items():
            if not param_value:
                logger.warning(f"必需参数 {param_name} 为空")
                return SendMessageResponse(success=False, message=f"参数 {param_name} 不能为空")

        live_instance = XianyuLive.get_instance(cleaned_cookie_id)
        if not live_instance:
            logger.warning(f"账号实例不存在或未连接: {cleaned_cookie_id}")
            return SendMessageResponse(success=False, message="账号实例不存在或未连接，请检查账号状态")

        if not live_instance.ws or live_instance.ws.closed:
            logger.warning(f"账号WebSocket连接已断开: {cleaned_cookie_id}")
            return SendMessageResponse(success=False, message="账号WebSocket连接已断开，请等待重连")

        await live_instance.send_msg(
            live_instance.ws,
            cleaned_chat_id,
            cleaned_to_user_id,
            cleaned_message,
        )

        logger.info(
            "API成功发送消息: %s -> %s, 内容: %s%s",
            cleaned_cookie_id,
            cleaned_to_user_id,
            cleaned_message[:50],
            "..." if len(cleaned_message) > 50 else "",
        )

        return SendMessageResponse(success=True, message="消息发送成功")

    except Exception as exc:  # noqa: BLE001
        cookie_id_for_log = request.cookie_id.replace("\n", "") if isinstance(request.cookie_id, str) else request.cookie_id
        to_user_id_for_log = request.to_user_id.replace("\n", "") if isinstance(request.to_user_id, str) else request.to_user_id
        logger.error(f"API发送消息异常: {cookie_id_for_log} -> {to_user_id_for_log}, 错误: {exc}")
        return SendMessageResponse(success=False, message=f"发送消息失败: {exc}")


@router.post("/xianyu/reply", response_model=ResponseModel)
async def xianyu_reply(req: RequestModel):
    msg_template = match_reply(req.cookie_id, req.send_message)
    is_default_reply = False

    if not msg_template:
        default_reply_settings = db_manager.get_default_reply(req.cookie_id)

        if default_reply_settings and default_reply_settings.get("enabled", False):
            if default_reply_settings.get("reply_once", False):
                if db_manager.has_default_reply_record(req.cookie_id, req.chat_id):
                    raise HTTPException(status_code=404, detail="该对话已使用默认回复，不再重复回复")

            msg_template = default_reply_settings.get("reply_content", "")
            is_default_reply = True

        if not msg_template:
            raise HTTPException(status_code=404, detail="未找到匹配的回复规则且未设置默认回复")

    try:
        send_msg = msg_template.format(
            send_user_id=req.send_user_id,
            send_user_name=req.send_user_name,
            send_message=req.send_message,
        )
    except Exception:  # noqa: BLE001
        send_msg = msg_template

    if is_default_reply:
        default_reply_settings = db_manager.get_default_reply(req.cookie_id)
        if default_reply_settings and default_reply_settings.get("reply_once", False):
            db_manager.add_default_reply_record(req.cookie_id, req.chat_id)

    return {"code": 200, "data": {"send_msg": send_msg}}

