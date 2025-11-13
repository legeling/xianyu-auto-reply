"""扫码登录相关路由。"""

from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, Depends
from loguru import logger

from app.api.dependencies import (
    cleanup_qr_check_records,
    get_current_user,
    log_with_user,
    qr_check_locks,
    qr_check_processed,
)
from app.repositories.db_manager import db_manager
from app.services import cookie_manager
from app.utils.qr_login import qr_login_manager
from app.utils.xianyu_utils import trans_cookies

router = APIRouter()


@router.post("/qr-login/generate")
async def generate_qr_code(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        log_with_user("info", "请求生成扫码登录二维码", current_user)

        result = await qr_login_manager.generate_qr_code()

        if result["success"]:
            log_with_user("info", f"扫码登录二维码生成成功: {result['session_id']}", current_user)
        else:
            log_with_user("warning", f"扫码登录二维码生成失败: {result.get('message', '未知错误')}", current_user)

        return result

    except Exception as exc:  # noqa: BLE001
        log_with_user("error", f"生成扫码登录二维码异常: {exc}", current_user)
        return {"success": False, "message": f"生成二维码失败: {exc}"}


@router.get("/qr-login/check/{session_id}")
async def check_qr_code_status(session_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        cleanup_qr_check_records()

        if session_id in qr_check_processed:
            record = qr_check_processed[session_id]
            if record["processed"]:
                log_with_user("debug", f"扫码登录session {session_id} 已处理过，直接返回", current_user)
                return {"status": "already_processed", "message": "该会话已处理完成"}

        session_lock = qr_check_locks[session_id]

        if session_lock.locked():
            log_with_user("debug", f"扫码登录session {session_id} 正在被其他请求处理，跳过", current_user)
            return {"status": "processing", "message": "正在处理中，请稍候..."}

        async with session_lock:
            if session_id in qr_check_processed and qr_check_processed[session_id]["processed"]:
                log_with_user("debug", f"扫码登录session {session_id} 在获取锁后发现已处理，直接返回", current_user)
                return {"status": "already_processed", "message": "该会话已处理完成"}

            qr_login_manager.cleanup_expired_sessions()

            status_info = qr_login_manager.get_session_status(session_id)

            if status_info["status"] == "success":
                cookies_info = qr_login_manager.get_session_cookies(session_id)
                if cookies_info:
                    account_info = await process_qr_login_cookies(
                        cookies_info["cookies"],
                        cookies_info["unb"],
                        current_user,
                    )
                    status_info["account_info"] = account_info

                    log_with_user(
                        "info",
                        f"扫码登录处理完成: {session_id}, 账号: {account_info.get('account_id', 'unknown')}",
                        current_user,
                    )

                    qr_check_processed[session_id] = {
                        "processed": True,
                        "timestamp": time.time(),
                    }

            return status_info

    except Exception as exc:  # noqa: BLE001
        log_with_user("error", f"检查扫码登录状态异常: {exc}", current_user)
        return {"status": "error", "message": str(exc)}


async def process_qr_login_cookies(cookies: str, unb: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
    try:
        user_id = current_user["user_id"]

        existing_cookies = db_manager.get_all_cookies(user_id)
        existing_account_id = None

        for account_id, cookie_value in existing_cookies.items():
            try:
                existing_cookie_dict = trans_cookies(cookie_value)
                if existing_cookie_dict.get("unb") == unb:
                    existing_account_id = account_id
                    break
            except Exception:
                continue

        if existing_account_id:
            account_id = existing_account_id
            is_new_account = False
            log_with_user("info", f"扫码登录找到现有账号: {account_id}, UNB: {unb}", current_user)
        else:
            account_id = unb
            counter = 1
            original_account_id = account_id
            while account_id in existing_cookies:
                account_id = f"{original_account_id}_{counter}"
                counter += 1

            is_new_account = True
            log_with_user("info", f"扫码登录准备创建新账号: {account_id}, UNB: {unb}", current_user)

        log_with_user("info", f"开始使用扫码cookie获取真实cookie: {account_id}", current_user)

        try:
            from app.services.xianyu_async import XianyuLive

            temp_instance = XianyuLive(
                cookies_str=cookies,
                cookie_id=account_id,
                user_id=user_id,
            )

            refresh_success = await temp_instance.refresh_cookies_from_qr_login(
                qr_cookies_str=cookies,
                cookie_id=account_id,
                user_id=user_id,
            )

            if refresh_success:
                log_with_user("info", f"扫码登录真实cookie获取成功: {account_id}", current_user)

                updated_cookie_info = db_manager.get_cookie_by_id(account_id)
                if updated_cookie_info:
                    real_cookies = updated_cookie_info["cookies_str"]
                    log_with_user("info", f"已获取真实cookie，长度: {len(real_cookies)}", current_user)

                    if cookie_manager.manager:
                        if is_new_account:
                            cookie_manager.manager.add_cookie(account_id, real_cookies)
                            log_with_user("info", f"已将真实cookie添加到cookie_manager: {account_id}", current_user)
                        else:
                            cookie_manager.manager.update_cookie(account_id, real_cookies, save_to_db=False)
                            log_with_user("info", f"已更新cookie_manager中的真实cookie: {account_id}", current_user)

                    return {
                        "account_id": account_id,
                        "is_new_account": is_new_account,
                        "real_cookie_refreshed": True,
                        "cookie_length": len(real_cookies),
                    }
                log_with_user("error", f"无法从数据库获取真实cookie: {account_id}", current_user)
                return await _fallback_save_qr_cookie(
                    account_id, cookies, user_id, is_new_account, current_user, "无法从数据库获取真实cookie"
                )
            log_with_user("warning", f"扫码登录真实cookie获取失败: {account_id}", current_user)
            return await _fallback_save_qr_cookie(
                account_id, cookies, user_id, is_new_account, current_user, "真实cookie获取失败"
            )

        except Exception as refresh_exc:  # noqa: BLE001
            log_with_user("error", f"扫码登录真实cookie获取异常: {refresh_exc}", current_user)
            return await _fallback_save_qr_cookie(
                account_id,
                cookies,
                user_id,
                is_new_account,
                current_user,
                f"获取真实cookie异常: {refresh_exc}",
            )

    except Exception as exc:  # noqa: BLE001
        log_with_user("error", f"处理扫码登录Cookie失败: {exc}", current_user)
        raise


async def _fallback_save_qr_cookie(
    account_id: str,
    cookies: str,
    user_id: int,
    is_new_account: bool,
    current_user: Dict[str, Any],
    error_reason: str,
) -> Dict[str, Any]:
    try:
        log_with_user("warning", f"降级处理 - 保存原始扫码cookie: {account_id}, 原因: {error_reason}", current_user)

        if is_new_account:
            db_manager.save_cookie(account_id, cookies, user_id)
            log_with_user("info", f"降级处理 - 新账号原始cookie已保存: {account_id}", current_user)
        else:
            db_manager.update_cookie_account_info(account_id, cookie_value=cookies)
            log_with_user("info", f"降级处理 - 现有账号原始cookie已更新: {account_id}", current_user)

        if cookie_manager.manager:
            if is_new_account:
                cookie_manager.manager.add_cookie(account_id, cookies)
                log_with_user("info", f"降级处理 - 已将原始cookie添加到cookie_manager: {account_id}", current_user)
            else:
                cookie_manager.manager.update_cookie(account_id, cookies, save_to_db=False)
                log_with_user("info", f"降级处理 - 已更新cookie_manager中的原始cookie: {account_id}", current_user)

        return {
            "account_id": account_id,
            "is_new_account": is_new_account,
            "real_cookie_refreshed": False,
            "fallback_reason": error_reason,
            "cookie_length": len(cookies),
        }

    except Exception as fallback_exc:  # noqa: BLE001
        log_with_user("error", f"降级处理失败: {fallback_exc}", current_user)
        raise


@router.post("/qr-login/refresh-cookies")
async def refresh_cookies_from_qr_login(
    request: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        qr_cookies = request.get("qr_cookies")
        cookie_id = request.get("cookie_id")

        if not qr_cookies:
            return {"success": False, "message": "缺少扫码登录cookie"}
        if not cookie_id:
            return {"success": False, "message": "缺少cookie_id"}

        log_with_user("info", f"开始使用扫码cookie刷新真实cookie: {cookie_id}", current_user)

        from app.services.xianyu_async import XianyuLive

        temp_instance = XianyuLive(
            cookies_str=qr_cookies,
            cookie_id=cookie_id,
            user_id=current_user["user_id"],
        )

        success = await temp_instance.refresh_cookies_from_qr_login(
            qr_cookies_str=qr_cookies,
            cookie_id=cookie_id,
            user_id=current_user["user_id"],
        )

        if success:
            log_with_user("info", f"扫码cookie刷新成功: {cookie_id}", current_user)

            if cookie_manager.manager:
                updated_cookie_info = db_manager.get_cookie_by_id(cookie_id)
                if updated_cookie_info:
                    cookie_manager.manager.update_cookie(
                        cookie_id, updated_cookie_info["cookies_str"], save_to_db=False
                    )
                    log_with_user("info", f"已更新cookie_manager中的cookie: {cookie_id}", current_user)

            return {
                "success": True,
                "message": "真实cookie获取并保存成功",
                "cookie_id": cookie_id,
            }
        log_with_user("error", f"扫码cookie刷新失败: {cookie_id}", current_user)
        return {"success": False, "message": "获取真实cookie失败"}

    except Exception as exc:  # noqa: BLE001
        log_with_user("error", f"扫码cookie刷新异常: {exc}", current_user)
        return {"success": False, "message": f"刷新cookie失败: {exc}"}


@router.post("/qr-login/reset-cooldown/{cookie_id}")
async def reset_qr_cookie_refresh_cooldown(
    cookie_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        log_with_user("info", f"重置扫码登录Cookie刷新冷却时间: {cookie_id}", current_user)

        cookie_info = db_manager.get_cookie_by_id(cookie_id)
        if not cookie_info:
            return {"success": False, "message": "账号不存在"}

        if cookie_manager.manager and cookie_id in cookie_manager.manager.instances:
            instance = cookie_manager.manager.instances[cookie_id]
            remaining_time_before = instance.get_qr_cookie_refresh_remaining_time()
            instance.reset_qr_cookie_refresh_flag()

            log_with_user(
                "info",
                f"已重置账号 {cookie_id} 的扫码登录冷却时间，原剩余时间: {remaining_time_before}秒",
                current_user,
            )

            return {
                "success": True,
                "message": "扫码登录Cookie刷新冷却时间已重置",
                "cookie_id": cookie_id,
                "previous_remaining_time": remaining_time_before,
            }

        log_with_user("info", f"账号 {cookie_id} 没有活跃实例，无需重置冷却时间", current_user)
        return {
            "success": True,
            "message": "账号没有活跃实例，无需重置冷却时间",
            "cookie_id": cookie_id,
        }

    except Exception as exc:  # noqa: BLE001
        log_with_user("error", f"重置扫码登录冷却时间异常: {exc}", current_user)
        return {"success": False, "message": f"重置冷却时间失败: {exc}"}


@router.get("/qr-login/cooldown-status/{cookie_id}")
async def get_qr_cookie_refresh_cooldown_status(
    cookie_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        cookie_info = db_manager.get_cookie_by_id(cookie_id)
        if not cookie_info:
            return {"success": False, "message": "账号不存在"}

        if cookie_manager.manager and cookie_id in cookie_manager.manager.instances:
            instance = cookie_manager.manager.instances[cookie_id]
            remaining_time = instance.get_qr_cookie_refresh_remaining_time()
            cooldown_duration = instance.qr_cookie_refresh_cooldown
            last_refresh_time = instance.last_qr_cookie_refresh_time

            return {
                "success": True,
                "cookie_id": cookie_id,
                "remaining_time": remaining_time,
                "cooldown_duration": cooldown_duration,
                "last_refresh_time": last_refresh_time,
                "is_in_cooldown": remaining_time > 0,
                "remaining_minutes": remaining_time // 60,
                "remaining_seconds": remaining_time % 60,
            }

        return {
            "success": True,
            "cookie_id": cookie_id,
            "remaining_time": 0,
            "cooldown_duration": 600,
            "last_refresh_time": 0,
            "is_in_cooldown": False,
            "remaining_minutes": 0,
            "remaining_seconds": 0,
        }

    except Exception as exc:  # noqa: BLE001
        log_with_user("error", f"获取扫码登录冷却状态异常: {exc}", current_user)
        return {"success": False, "message": f"获取冷却状态失败: {exc}"}

