"""认证与注册相关 API 路由。"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger
from pydantic import BaseModel

from app.api.dependencies import (
    ADMIN_USERNAME,
    SESSION_TOKENS,
    generate_token,
    security,
    verify_admin_token,
    verify_token,
)
from app.repositories.db_manager import db_manager

router = APIRouter()


class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    verification_code: Optional[str] = None


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    is_admin: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    verification_code: str


class RegisterResponse(BaseModel):
    success: bool
    message: str


class SendCodeRequest(BaseModel):
    email: str
    session_id: Optional[str] = None
    type: Optional[str] = "register"


class SendCodeResponse(BaseModel):
    success: bool
    message: str


class CaptchaRequest(BaseModel):
    session_id: str


class CaptchaResponse(BaseModel):
    success: bool
    captcha_image: str
    session_id: str
    message: str


class VerifyCaptchaRequest(BaseModel):
    session_id: str
    captcha_code: str


class VerifyCaptchaResponse(BaseModel):
    success: bool
    message: str


@router.post("/login")
async def login(request: LoginRequest) -> LoginResponse:
    if request.username and request.password:
        logger.info(f"【{request.username}】尝试账号密码登录")

        user = db_manager.get_user_by_username(request.username)
        if user and db_manager.verify_user_password(request.username, request.password):
            token = generate_token()
            SESSION_TOKENS[token] = {
                "user_id": user["id"],
                "username": user["username"],
                "timestamp": time.time(),
            }

            logger.info(f"【{user['username']}#{user['id']}】账号密码登录成功")

            return LoginResponse(
                success=True,
                token=token,
                message="登录成功",
                user_id=user["id"],
                username=user["username"],
                is_admin=(user["username"] == ADMIN_USERNAME),
            )

        logger.warning(f"【{request.username}】登录失败：用户名或密码错误")
        return LoginResponse(success=False, message="用户名或密码错误")

    if request.email and request.password:
        logger.info(f"【{request.email}】尝试邮箱密码登录")

        user = db_manager.get_user_by_email(request.email)
        if user and db_manager.verify_user_password(user["username"], request.password):
            token = generate_token()
            SESSION_TOKENS[token] = {
                "user_id": user["id"],
                "username": user["username"],
                "timestamp": time.time(),
            }

            logger.info(f"【{user['username']}#{user['id']}】邮箱登录成功")

            return LoginResponse(
                success=True,
                token=token,
                message="登录成功",
                user_id=user["id"],
                username=user["username"],
                is_admin=(user["username"] == ADMIN_USERNAME),
            )

        logger.warning(f"【{request.email}】邮箱登录失败：邮箱或密码错误")
        return LoginResponse(success=False, message="邮箱或密码错误")

    if request.email and request.verification_code:
        logger.info(f"【{request.email}】尝试邮箱验证码登录")

        if not db_manager.verify_email_code(request.email, request.verification_code, "login"):
            logger.warning(f"【{request.email}】验证码登录失败：验证码错误或已过期")
            return LoginResponse(success=False, message="验证码错误或已过期")

        user = db_manager.get_user_by_email(request.email)
        if not user:
            logger.warning(f"【{request.email}】验证码登录失败：用户不存在")
            return LoginResponse(success=False, message="用户不存在")

        token = generate_token()
        SESSION_TOKENS[token] = {
            "user_id": user["id"],
            "username": user["username"],
            "timestamp": time.time(),
        }

        logger.info(f"【{user['username']}#{user['id']}】验证码登录成功")

        return LoginResponse(
            success=True,
            token=token,
            message="登录成功",
            user_id=user["id"],
            username=user["username"],
            is_admin=(user["username"] == ADMIN_USERNAME),
        )

    return LoginResponse(success=False, message="请提供有效的登录信息")


@router.get("/verify")
async def verify(user_info: Optional[Dict[str, Any]] = Depends(verify_token)):
    if user_info:
        return {
            "authenticated": True,
            "user_id": user_info["user_id"],
            "username": user_info["username"],
            "is_admin": user_info["username"] == ADMIN_USERNAME,
        }
    return {"authenticated": False}


@router.post("/logout")
async def logout(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if credentials and credentials.credentials in SESSION_TOKENS:
        del SESSION_TOKENS[credentials.credentials]
    return {"message": "已登出"}


@router.post("/change-admin-password")
async def change_admin_password(
    request: ChangePasswordRequest, admin_user: Dict[str, Any] = Depends(verify_admin_token)
):
    try:
        if not db_manager.verify_user_password("admin", request.current_password):
            return {"success": False, "message": "当前密码错误"}

        success = db_manager.update_user_password("admin", request.new_password)

        if success:
            logger.info(f"【admin#{admin_user['user_id']}】管理员密码修改成功")
            return {"success": True, "message": "密码修改成功"}
        return {"success": False, "message": "密码修改失败"}

    except Exception as exc:  # noqa: BLE001
        logger.error(f"修改管理员密码异常: {exc}")
        return {"success": False, "message": "系统错误"}


@router.post("/generate-captcha")
async def generate_captcha(request: CaptchaRequest) -> CaptchaResponse:
    try:
        captcha_text, captcha_image = db_manager.generate_captcha()

        if not captcha_image:
            return CaptchaResponse(
                success=False,
                captcha_image="",
                session_id=request.session_id,
                message="图形验证码生成失败",
            )

        if db_manager.save_captcha(request.session_id, captcha_text):
            return CaptchaResponse(
                success=True,
                captcha_image=captcha_image,
                session_id=request.session_id,
                message="图形验证码生成成功",
            )
        return CaptchaResponse(
            success=False,
            captcha_image="",
            session_id=request.session_id,
            message="图形验证码保存失败",
        )

    except Exception as exc:  # noqa: BLE001
        logger.error(f"生成图形验证码失败: {exc}")
        return CaptchaResponse(
            success=False,
            captcha_image="",
            session_id=request.session_id,
            message="图形验证码生成失败",
        )


@router.post("/verify-captcha")
async def verify_captcha(request: VerifyCaptchaRequest) -> VerifyCaptchaResponse:
    try:
        if db_manager.verify_captcha(request.session_id, request.captcha_code):
            return VerifyCaptchaResponse(success=True, message="图形验证码验证成功")
        return VerifyCaptchaResponse(success=False, message="图形验证码错误或已过期")

    except Exception as exc:  # noqa: BLE001
        logger.error(f"验证图形验证码失败: {exc}")
        return VerifyCaptchaResponse(success=False, message="图形验证码验证失败")


@router.post("/send-verification-code")
async def send_verification_code(request: SendCodeRequest) -> SendCodeResponse:
    try:
        with db_manager.lock:
            _ = db_manager.conn.cursor()  # 保留原有逻辑结构，即便当前未使用

        if request.type == "register":
            existing_user = db_manager.get_user_by_email(request.email)
            if existing_user:
                return SendCodeResponse(success=False, message="该邮箱已被注册")
        elif request.type == "login":
            existing_user = db_manager.get_user_by_email(request.email)
            if not existing_user:
                return SendCodeResponse(success=False, message="该邮箱未注册")

        code = db_manager.generate_verification_code()

        if not db_manager.save_verification_code(request.email, code, request.type):
            return SendCodeResponse(success=False, message="验证码保存失败，请稍后重试")

        if await db_manager.send_verification_email(request.email, code):
            return SendCodeResponse(success=True, message="验证码已发送到您的邮箱，请查收")
        return SendCodeResponse(
            success=False,
            message="验证码发送失败，请检查邮箱地址或稍后重试",
        )

    except Exception as exc:  # noqa: BLE001
        logger.error(f"发送验证码失败: {exc}")
        return SendCodeResponse(success=False, message="发送验证码失败，请稍后重试")


@router.post("/register")
async def register(request: RegisterRequest) -> RegisterResponse:
    registration_enabled = db_manager.get_system_setting("registration_enabled")
    if registration_enabled != "true":
        logger.warning(f"【{request.username}】注册失败: 注册功能已关闭")
        return RegisterResponse(success=False, message="注册功能已关闭，请联系管理员")

    try:
        logger.info(f"【{request.username}】尝试注册，邮箱: {request.email}")

        if not db_manager.verify_email_code(request.email, request.verification_code):
            logger.warning(f"【{request.username}】注册失败: 验证码错误或已过期")
            return RegisterResponse(success=False, message="验证码错误或已过期")

        existing_user = db_manager.get_user_by_username(request.username)
        if existing_user:
            logger.warning(f"【{request.username}】注册失败: 用户名已存在")
            return RegisterResponse(success=False, message="用户名已存在")

        existing_email = db_manager.get_user_by_email(request.email)
        if existing_email:
            logger.warning(f"【{request.username}】注册失败: 邮箱已被注册")
            return RegisterResponse(success=False, message="该邮箱已被注册")

        if db_manager.create_user(request.username, request.email, request.password):
            logger.info(f"【{request.username}】注册成功")
            return RegisterResponse(success=True, message="注册成功，请登录")

        logger.error(f"【{request.username}】注册失败: 数据库操作失败")
        return RegisterResponse(success=False, message="注册失败，请稍后重试")

    except Exception as exc:  # noqa: BLE001
        logger.error(f"【{request.username}】注册异常: {exc}")
        return RegisterResponse(success=False, message="注册失败，请稍后重试")

