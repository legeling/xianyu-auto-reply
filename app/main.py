"""项目启动模块

职责：
1. 创建 CookieManager，按配置 / 环境变量初始化账号任务
2. 在后台线程启动 FastAPI (`app.api.reply_server`) 提供管理与自动回复接口
3. 保持主协程运行
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from app.bootstrap.database import migrate_database_files_early

try:
    migrate_database_files_early()
except Exception as exc:  # noqa: BLE001
    print(f"⚠ 数据库迁移检查失败: {exc}")

from app.core.config import AUTO_REPLY, COOKIES_LIST  # noqa: E402
from app.repositories.db_manager import db_manager  # noqa: E402
from app.services import cookie_manager as cm  # noqa: E402
from app.services.file_log_collector import setup_file_logging  # noqa: E402
from app.services.usage_stats import report_user_count  # noqa: E402


def _configure_event_loop():
    """设置事件循环策略（Linux 平台优化）。"""
    if sys.platform.startswith("linux"):
        try:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            logger.debug("已设置事件循环策略以支持子进程")
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"设置事件循环策略失败: {exc}")


def _start_api_server():
    """后台线程启动 FastAPI 服务。"""
    api_conf = AUTO_REPLY.get("api", {})

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))

    if "host" in api_conf:
        host = api_conf["host"]
    if "port" in api_conf:
        port = api_conf["port"]

    if "url" in api_conf and "host" not in api_conf and "port" not in api_conf:
        url = api_conf.get("url", "http://0.0.0.0:8080/xianyu/reply")
        parsed = urlparse(url)
        if parsed.hostname and parsed.hostname != "localhost":
            host = parsed.hostname
        port = parsed.port or 8080

    logger.info(f"启动Web服务器: http://{host}:{port}")

    import uvicorn

    try:
        config = uvicorn.Config("app.api.reply_server:app", host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())
    except Exception as exc:  # noqa: BLE001
        logger.error(f"uvicorn服务器启动失败: {exc}")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except Exception:  # noqa: BLE001
            pass


def load_keywords_file(path: str):
    """从文件读取关键字 -> [(keyword, reply)]"""
    kw_list = []
    p = Path(path)
    if not p.exists():
        return kw_list
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                k, r = line.split("\t", 1)
            elif " " in line:
                k, r = line.split(" ", 1)
            elif ":" in line:
                k, r = line.split(":", 1)
            else:
                continue
            kw_list.append((k.strip(), r.strip()))
    return kw_list


async def startup():
    """应用主入口协程。"""
    print("开始启动主程序...")

    print("初始化文件日志收集器...")
    setup_file_logging()
    logger.info("文件日志收集器已启动，开始收集实时日志")

    loop = asyncio.get_running_loop()

    print("创建 CookieManager...")
    cm.manager = cm.CookieManager(loop)
    manager = cm.manager
    print("CookieManager 创建完成")

    for cid, val in manager.cookies.items():
        if not manager.get_cookie_status(cid):
            logger.info(f"跳过禁用的 Cookie: {cid}")
            continue

        try:
            logger.info(f"正在获取Cookie详细信息: {cid}")
            cookie_info = db_manager.get_cookie_details(cid)
            user_id = cookie_info.get("user_id") if cookie_info else None
            logger.info(f"Cookie详细信息获取成功: {cid}, user_id: {user_id}")

            logger.info(f"正在创建异步任务: {cid}")
            task = loop.create_task(manager._run_xianyu(cid, val, user_id))
            manager.tasks[cid] = task
            logger.info(f"启动数据库中的 Cookie 任务: {cid} (用户ID: {user_id})")
            logger.info(f"任务已添加到管理器，当前任务数: {len(manager.tasks)}")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"启动 Cookie 任务失败: {cid}, {exc}")
            import traceback

            logger.error(f"详细错误信息: {traceback.format_exc()}")

    for entry in COOKIES_LIST:
        cid = entry.get("id")
        val = entry.get("value")
        if not cid or not val or cid in manager.cookies:
            continue

        kw_file = entry.get("keywords_file")
        kw_list = load_keywords_file(kw_file) if kw_file else None
        manager.add_cookie(cid, val, kw_list)
        logger.info(f"从配置文件加载 Cookie: {cid}")

    env_cookie = os.getenv("COOKIES_STR")
    if env_cookie and "default" not in manager.list_cookies():
        manager.add_cookie("default", env_cookie)
        logger.info("从环境变量加载 default Cookie")

    print("启动 API 服务线程...")
    threading.Thread(target=_start_api_server, daemon=True).start()
    print("API 服务线程已启动")

    try:
        await report_user_count()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"上报用户统计失败: {exc}")

    print("主程序启动完成，保持运行...")
    await asyncio.Event().wait()


def main():
    """同步入口。"""
    _configure_event_loop()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(startup())
        else:
            loop.run_until_complete(startup())
    except RuntimeError:
        asyncio.run(startup())


if __name__ == "__main__":
    main()

