"""
消息发送路由
外部系统发送消息接口
"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from loguru import logger

router = APIRouter(tags=["消息"])


# ==================== 请求/响应模型 ====================

class SendMessageRequest(BaseModel):
    """发送消息请求"""
    api_key: str
    cookie_id: str
    chat_id: str
    to_user_id: str
    message: str


class SendMessageResponse(BaseModel):
    """发送消息响应"""
    success: bool
    message: str


# ==================== 工具函数 ====================

# API秘钥（从配置读取）
def get_api_secret_key() -> str | None:
    """获取API密钥（仅来自配置/环境变量 API_SECRET_KEY）。

    安全（H3 修复）：不再回退到源码内置的硬编码默认密钥；
    未配置时返回 None，由调用方 fail-closed 拒绝服务（503）。
    """
    from app.core.config import get_settings
    settings = get_settings()
    return (settings.api_secret_key or "").strip() or None


def verify_api_key(api_key: str) -> bool:
    """验证API秘钥（hmac.compare_digest 常量时间比较，防时序侧信道）"""
    expected = get_api_secret_key()
    if not expected:
        return False
    return hmac.compare_digest(api_key, expected)


def clean_param(param_str: str) -> str:
    """清理参数中的换行符"""
    if isinstance(param_str, str):
        return param_str.replace("\\n", "").replace("\n", "")
    return param_str


# ==================== 路由 ====================

@router.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """
    发送消息API接口（使用秘钥验证）
    
    用于外部系统（如QQ机器人）向闲鱼发送消息
    """
    try:
        # 清理参数
        cleaned_api_key = clean_param(request.api_key)
        cleaned_cookie_id = clean_param(request.cookie_id)
        cleaned_chat_id = clean_param(request.chat_id)
        cleaned_to_user_id = clean_param(request.to_user_id)
        cleaned_message = clean_param(request.message)
        
        # 验证API秘钥
        if not cleaned_api_key:
            logger.warning("API秘钥为空")
            return SendMessageResponse(
                success=False,
                message="API秘钥不能为空"
            )

        # 安全（H3 修复）：服务端未配置 API_SECRET_KEY 时 fail-closed，
        # 返回 503 而非使用任何默认密钥
        if get_api_secret_key() is None:
            logger.error("消息发送接口被拒绝：服务端未配置 API_SECRET_KEY（fail-closed）")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="消息接口未配置，请联系管理员配置 API_SECRET_KEY",
            )

        # 验证秘钥
        if not verify_api_key(cleaned_api_key):
            logger.warning("API秘钥验证失败")  # 安全：日志不再记录传入的密钥内容
            return SendMessageResponse(
                success=False,
                message="API秘钥验证失败"
            )
        
        # 验证必需参数
        required_params = {
            "cookie_id": cleaned_cookie_id,
            "chat_id": cleaned_chat_id,
            "to_user_id": cleaned_to_user_id,
            "message": cleaned_message,
        }
        
        for param_name, param_value in required_params.items():
            if not param_value:
                logger.warning(f"必需参数 {param_name} 为空")
                return SendMessageResponse(
                    success=False,
                    message=f"参数 {param_name} 不能为空"
                )
        
        # 通过WebSocket服务发送消息
        from app.services.websocket_client import websocket_client
        
        result = await websocket_client.send_message(
            account_id=cleaned_cookie_id,
            chat_id=cleaned_chat_id,
            content=cleaned_message,
            message_type="text"
        )
        
        if result.get('success'):
            logger.info(f"消息发送成功: {cleaned_cookie_id} -> {cleaned_to_user_id}")
            return SendMessageResponse(
                success=True,
                message="消息发送成功"
            )
        else:
            error_msg = result.get('message', '发送失败')
            logger.error(f"发送消息失败: {error_msg}")
            return SendMessageResponse(
                success=False,
                message=error_msg
            )
        
    except Exception as e:
        logger.error(f"发送消息异常: {e}")
        return SendMessageResponse(
            success=False,
            message=f"发送消息失败: {str(e)}"
        )
