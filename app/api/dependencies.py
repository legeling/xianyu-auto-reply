"""API 层通用依赖与工具函数。"""

from __future__ import annotations

import secrets
import time
import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from app.services import cookie_manager

# 关键字文件路径
KEYWORDS_FILE = Path(__file__).resolve().parent / "回复关键字.txt"


def load_keywords() -> List[Tuple[str, str]]:
    """读取关键字→回复映射表。"""
    mapping: List[Tuple[str, str]] = []
    if not KEYWORDS_FILE.exists():
        return mapping

    with KEYWORDS_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                key, reply = line.split("\t", 1)
            elif " " in line:
                key, reply = line.split(" ", 1)
            elif ":" in line:
                key, reply = line.split(":", 1)
            else:
                continue
            mapping.append((key.strip(), reply.strip()))
    return mapping


KEYWORDS_MAPPING = load_keywords()

# 简单的用户认证配置
ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
SESSION_TOKENS: Dict[str, Dict[str, Any]] = {}
TOKEN_EXPIRE_TIME = 24 * 60 * 60  # 24小时

# HTTP Bearer 认证
security = HTTPBearer(auto_error=False)

# 扫码登录检查锁 - 防止并发处理同一个 session
qr_check_locks = defaultdict(lambda: asyncio.Lock())
qr_check_processed: Dict[str, Dict[str, Any]] = {}


def cleanup_qr_check_records() -> None:
    """清理过期的扫码检查记录。"""
    current_time = time.time()
    expired_sessions: List[str] = []

    for session_id, record in list(qr_check_processed.items()):
        if current_time - record["timestamp"] > 3600:
            expired_sessions.append(session_id)

    for session_id in expired_sessions:
        qr_check_processed.pop(session_id, None)
        qr_check_locks.pop(session_id, None)


def generate_token() -> str:
    """生成随机 token。"""
    return secrets.token_urlsafe(32)


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """验证 token 并返回用户信息。"""
    if not credentials:
        return None

    token = credentials.credentials
    token_data = SESSION_TOKENS.get(token)
    if not token_data:
        return None

    if time.time() - token_data["timestamp"] > TOKEN_EXPIRE_TIME:
        SESSION_TOKENS.pop(token, None)
        return None

    return token_data


def verify_admin_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """验证管理员 token。"""
    user_info = verify_token(credentials)
    if not user_info:
        raise HTTPException(status_code=401, detail="未授权访问")
    if user_info["username"] != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user_info


def require_auth(user_info: Optional[Dict[str, Any]] = Depends(verify_token)):
    """需要认证的依赖，返回用户信息。"""
    if not user_info:
        raise HTTPException(status_code=401, detail="未授权访问")
    return user_info


def get_current_user(user_info: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
    """获取当前登录用户信息。"""
    return user_info


def get_current_user_optional(user_info: Optional[Dict[str, Any]] = Depends(verify_token)) -> Optional[Dict[str, Any]]:
    """获取当前用户信息（可选，不强制要求登录）。"""
    return user_info


def get_user_log_prefix(user_info: Optional[Dict[str, Any]] = None) -> str:
    """获取用户日志前缀。"""
    if user_info:
        return f"【{user_info['username']}#{user_info['user_id']}】"
    return "【系统】"


def log_with_user(level: str, message: str, user_info: Optional[Dict[str, Any]] = None) -> None:
    """带用户信息的日志记录。"""
    prefix = get_user_log_prefix(user_info)
    full_message = f"{prefix} {message}"

    level_lower = level.lower()
    if level_lower == "info":
        logger.info(full_message)
    elif level_lower == "error":
        logger.error(full_message)
    elif level_lower == "warning":
        logger.warning(full_message)
    elif level_lower == "debug":
        logger.debug(full_message)
    else:
        logger.info(full_message)


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """要求管理员权限。"""
    if current_user["username"] != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def match_reply(cookie_id: str, message: str) -> Optional[str]:
    """根据 cookie_id 及消息内容匹配回复。只有启用的账号才会匹配关键字回复。"""
    manager = cookie_manager.manager
    if manager is None:
        return None

    if not manager.get_cookie_status(cookie_id):
        return None

    keywords = manager.get_keywords(cookie_id)
    if keywords:
        for keyword, reply in keywords:
            if keyword in message:
                return reply

    for keyword, reply in KEYWORDS_MAPPING:
        if keyword in message:
            return reply
    return None

