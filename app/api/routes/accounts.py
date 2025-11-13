"""账号与 Cookie 管理相关路由。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.api.dependencies import get_current_user, log_with_user
from app.repositories.db_manager import db_manager
from app.services import cookie_manager

router = APIRouter()


class CookieIn(BaseModel):
    id: str
    value: str


class CookieStatusIn(BaseModel):
    enabled: bool


class DefaultReplyIn(BaseModel):
    enabled: bool
    reply_content: Optional[str] = None
    reply_once: bool = False


class CookieAccountInfo(BaseModel):
    value: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    show_browser: Optional[bool] = None


@router.get("/cookies")
def get_all_cookies(current_user: Dict[str, Any] = Depends(get_current_user)):
    if cookie_manager.manager is None:
        return []

    user_id = current_user["user_id"]
    user_cookies = db_manager.get_all_cookies(user_id)
    return list(user_cookies.keys())


@router.get("/cookies/details")
def get_cookies_details(current_user: Dict[str, Any] = Depends(get_current_user)):
    if cookie_manager.manager is None:
        return []

    user_id = current_user["user_id"]
    user_cookies = db_manager.get_all_cookies(user_id)

    result = []
    for cookie_id, cookie_value in user_cookies.items():
        cookie_enabled = cookie_manager.manager.get_cookie_status(cookie_id)
        auto_confirm = db_manager.get_auto_confirm(cookie_id)
        cookie_details = db_manager.get_cookie_details(cookie_id)
        remark = cookie_details.get("remark", "") if cookie_details else ""

        result.append(
            {
                "id": cookie_id,
                "value": cookie_value,
                "enabled": cookie_enabled,
                "auto_confirm": auto_confirm,
                "remark": remark,
                "pause_duration": cookie_details.get("pause_duration", 10) if cookie_details else 10,
            }
        )
    return result


@router.post("/cookies")
def add_cookie(item: CookieIn, current_user: Dict[str, Any] = Depends(get_current_user)):
    if cookie_manager.manager is None:
        raise HTTPException(status_code=500, detail="CookieManager 未就绪")
    try:
        user_id = current_user["user_id"]
        log_with_user(
            "info",
            f"尝试添加Cookie: {item.id}, 当前用户ID: {user_id}, 用户名: {current_user.get('username', 'unknown')}",
            current_user,
        )

        existing_cookies = db_manager.get_all_cookies()
        if item.id in existing_cookies:
            user_cookies = db_manager.get_all_cookies(user_id)
            if item.id not in user_cookies:
                log_with_user("warning", f"Cookie ID冲突: {item.id} 已被其他用户使用", current_user)
                raise HTTPException(status_code=400, detail="该Cookie ID已被其他用户使用")

        db_manager.save_cookie(item.id, item.value, user_id)
        cookie_manager.manager.add_cookie(item.id, item.value, user_id=user_id)
        log_with_user("info", f"Cookie添加成功: {item.id}", current_user)
        return {"msg": "success"}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log_with_user("error", f"添加Cookie失败: {item.id} - {exc}", current_user)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/cookies/{cid}")
def update_cookie(cid: str, item: CookieIn, current_user: Dict[str, Any] = Depends(get_current_user)):
    if cookie_manager.manager is None:
        raise HTTPException(status_code=500, detail="CookieManager 未就绪")
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)

        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作该Cookie")

        old_cookie_details = db_manager.get_cookie_details(cid)
        old_cookie_value = old_cookie_details.get("value") if old_cookie_details else None

        success = db_manager.update_cookie_account_info(cid, cookie_value=item.value)
        if not success:
            raise HTTPException(status_code=400, detail="更新Cookie失败")

        if item.value != old_cookie_value:
            logger.info(f"Cookie值已变化，重启任务: {cid}")
            cookie_manager.manager.update_cookie(cid, item.value, save_to_db=False)
        else:
            logger.info(f"Cookie值未变化，无需重启任务: {cid}")

        return {"msg": "updated"}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cookie/{cid}/account-info")
def update_cookie_account_info(
    cid: str, info: CookieAccountInfo, current_user: Dict[str, Any] = Depends(get_current_user)
):
    if cookie_manager.manager is None:
        raise HTTPException(status_code=500, detail="CookieManager 未就绪")
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)

        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作该Cookie")

        old_cookie_details = db_manager.get_cookie_details(cid)
        old_cookie_value = old_cookie_details.get("value") if old_cookie_details else None

        success = db_manager.update_cookie_account_info(
            cid,
            cookie_value=info.value,
            username=info.username,
            password=info.password,
            show_browser=info.show_browser,
        )

        if not success:
            raise HTTPException(status_code=400, detail="更新账号信息失败")

        if info.value is not None and info.value != old_cookie_value:
            logger.info(f"Cookie值已变化，重启任务: {cid}")
            cookie_manager.manager.update_cookie(cid, info.value, save_to_db=False)
        else:
            logger.info(f"Cookie值未变化，无需重启任务: {cid}")

        return {"msg": "updated", "success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"更新账号信息失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/cookie/{cid}/details")
def get_cookie_account_details(cid: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)

        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作该Cookie")

        details = db_manager.get_cookie_details(cid)
        if not details:
            raise HTTPException(status_code=404, detail="账号不存在")

        return details
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"获取账号详情失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/cookies/{cid}/status")
def update_cookie_status(cid: str, status_data: CookieStatusIn, current_user: Dict[str, Any] = Depends(get_current_user)):
    if cookie_manager.manager is None:
        raise HTTPException(status_code=500, detail="CookieManager 未就绪")

    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作该Cookie")

        cookie_manager.manager.update_cookie_status(cid, status_data.enabled)
        db_manager.update_cookie_status(cid, status_data.enabled)
        log_with_user("info", f"更新Cookie状态: {cid} -> {status_data.enabled}", current_user)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/default-replies/{cid}")
def get_default_reply(cid: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限访问")

        return db_manager.get_default_reply(cid) or {"enabled": False, "reply_content": "", "reply_once": False}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"获取默认回复失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/default-replies/{cid}")
def update_default_reply(cid: str, data: DefaultReplyIn, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限访问")

        db_manager.set_default_reply(cid, data.enabled, data.reply_content, data.reply_once)
        log_with_user("info", f"更新默认回复: {cid} -> {data.dict()}", current_user)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"更新默认回复失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/default-replies")
def get_all_default_replies(current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = current_user["user_id"]
    user_cookies = db_manager.get_all_cookies(user_id)
    result = {}
    for cid in user_cookies.keys():
        result[cid] = db_manager.get_default_reply(cid)
    return result


@router.delete("/default-replies/{cid}")
def delete_default_reply(cid: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限访问")

        db_manager.delete_default_reply(cid)
        log_with_user("info", f"删除默认回复: {cid}", current_user)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"删除默认回复失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/default-replies/{cid}/clear-records")
def clear_default_reply_records(cid: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限访问")

        db_manager.clear_default_reply_records(cid)
        log_with_user("info", f"清理默认回复记录: {cid}", current_user)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"清理默认回复记录失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/cookies/{cid}/auto-confirm")
def update_auto_confirm_setting(cid: str, data: Dict[str, bool], current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作")

        db_manager.set_auto_confirm(cid, data.get("auto_confirm", True))
        log_with_user("info", f"更新自动确认设置: {cid} -> {data}", current_user)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/cookies/{cid}/auto-confirm")
def get_auto_confirm_setting(cid: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作")

        return {"auto_confirm": db_manager.get_auto_confirm(cid)}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/cookies/{cid}/remark")
def update_cookie_remark(cid: str, data: Dict[str, str], current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作")

        remark = data.get("remark", "")
        db_manager.update_cookie_remark(cid, remark)
        log_with_user("info", f"更新Cookie备注: {cid} -> {remark}", current_user)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/cookies/{cid}/remark")
def get_cookie_remark(cid: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作")

        remark = db_manager.get_cookie_remark(cid)
        return {"remark": remark}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/cookies/{cid}/pause-duration")
def update_cookie_pause_duration(cid: str, data: Dict[str, int], current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作")

        pause_duration = data.get("pause_duration", 10)
        db_manager.update_cookie_pause_duration(cid, pause_duration)
        log_with_user("info", f"更新Cookie暂停时长: {cid} -> {pause_duration}", current_user)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/cookies/{cid}/pause-duration")
def get_cookie_pause_duration(cid: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作")

        pause_duration = db_manager.get_cookie_pause_duration(cid)
        return {"pause_duration": pause_duration}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/cookies/{cid}")
def delete_cookie(cid: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user["user_id"]
        user_cookies = db_manager.get_all_cookies(user_id)
        if cid not in user_cookies:
            raise HTTPException(status_code=403, detail="无权限操作")

        if cookie_manager.manager:
            cookie_manager.manager.remove_cookie(cid)
        db_manager.delete_cookie(cid)
        log_with_user("info", f"删除Cookie: {cid}", current_user)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

