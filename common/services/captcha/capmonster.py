"""CapMonster Alibaba punishUrl 任务；不上传账号完整 Cookie，不重复创建付费任务。"""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import parse_qs, urlsplit, urlunsplit

import requests

from common.services.captcha.provider_config import CAPMONSTER_API_URL, CAPMONSTER_USER_AGENT_URL
from common.services.captcha.remote_timeout import get_remote_solve_timeout

# 官方 getTaskResult 每个任务最多 120 次查询；查询间隔由现有求解预算均分。
MAX_RESULT_REQUESTS = 120
CONNECTION_TIMEOUT_SECONDS = 8
BALANCE_TIMEOUT_SECONDS = 10
logger = logging.getLogger(__name__)


class CapMonsterError(Exception):
    pass


def _post(session: requests.Session, method: str, payload: dict, timeout: float) -> dict:
    response = session.post(
        f"{CAPMONSTER_API_URL}/{method}", json=payload,
        timeout=(min(CONNECTION_TIMEOUT_SECONDS, timeout), timeout),
    )
    if response.status_code != 200:
        raise CapMonsterError(f"CapMonster {method} HTTP {response.status_code}")
    body = response.json()
    if not isinstance(body, dict) or type(body.get("errorId")) is not int:
        raise CapMonsterError("CapMonster 响应格式错误")
    if body["errorId"] != 0:
        code = body.get("errorCode")
        # 不回显供应商 errorDescription，避免错误中包含请求密钥或验证链接。
        safe_code = code if isinstance(code, str) and re.fullmatch(r"ERROR_[A-Z_]+", code) else "服务错误"
        raise CapMonsterError(f"CapMonster {method} {safe_code}")
    return body


def test_connection(api_key: str) -> dict:
    """只查询余额，不创建收费验证码任务。"""
    if not api_key.strip():
        raise CapMonsterError("请先填写 CapMonster API Key")
    try:
        with requests.Session() as session:
            body = _post(session, "getBalance", {"clientKey": api_key}, BALANCE_TIMEOUT_SECONDS)
        balance = body.get("balance")
        if type(balance) not in (int, float) or balance < 0:
            raise CapMonsterError("CapMonster 余额响应格式错误")
        return {"balance": balance, "currency": "USD"}
    except (requests.RequestException, ValueError) as exc:
        raise CapMonsterError("CapMonster 连接或响应失败") from exc


def _solution_cookies(solution: object, host: str) -> dict[str, str]:
    domains = solution.get("domains") if isinstance(solution, dict) else None
    if not isinstance(domains, dict):
        raise CapMonsterError("CapMonster 未返回验证 Cookie")
    cookies: dict[str, str] = {}
    # 父域先写，具体域覆盖；只接收当前验证主机适用的域，避免跨域 Cookie 污染。
    for domain in sorted((key for key in domains if isinstance(key, str)), key=len):
        normalized = domain.lstrip(".").lower()
        if not normalized or (host != normalized and not host.endswith("." + normalized)):
            continue
        item = domains[domain]
        values = item.get("cookies") if isinstance(item, dict) else None
        if isinstance(values, dict):
            cookies.update({name: value for name, value in values.items()
                            if isinstance(name, str) and isinstance(value, str) and value
                            and not any(c in name + value for c in "\r\n;")})
    if not cookies.get("x5sec"):
        raise CapMonsterError("CapMonster 已完成任务，但未返回适用的 x5sec，不能视为闲鱼验证成功")
    return cookies


def solve(api_key: str, punish_url: str, browser_timeout: int) -> tuple[str, dict | None, str | None]:
    try:
        parsed = urlsplit(punish_url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
        query = parse_qs(parsed.query, keep_blank_values=True)
        valid = (parsed.scheme == "https" and host and "_____tmd_____/punish" in parsed.path
                 and not parsed.username and all(query.get(key, [""])[0] for key in ("x5secdata", "x5step", "action"))
                 and "pureCaptcha" in query)
    except ValueError:
        valid = False
    if not valid:
        return "fail", None, "CapMonster 需要有效的 HTTPS punish 验证链接"
    if port is None:
        punish_url = urlunsplit(parsed._replace(netloc=f"{parsed.netloc}:443"))
    if not api_key.strip():
        return "fail", None, "请先配置 CapMonster API Key"
    budget = get_remote_solve_timeout(browser_timeout)
    deadline = time.monotonic() + budget
    interval = budget / MAX_RESULT_REQUESTS
    task_id = None
    phase = "userAgent"
    try:
        with requests.Session() as session:
            response = session.get(CAPMONSTER_USER_AGENT_URL,
                                   timeout=(CONNECTION_TIMEOUT_SECONDS, budget))
            if response.status_code != 200:
                raise CapMonsterError(f"CapMonster userAgent HTTP {response.status_code}")
            user_agent = response.text.strip()
            if not user_agent.startswith("Mozilla/") or any(c in user_agent for c in "\r\n"):
                raise CapMonsterError("CapMonster User-Agent 响应格式错误")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CapMonsterError("CapMonster User-Agent 查询超时")
            phase = "createTask"
            created = _post(session, "createTask", {
                "clientKey": api_key,
                "task": {
                    "type": "CustomTask", "class": "alibaba",
                    "websiteURL": f"{parsed.scheme}://{parsed.netloc}",
                    "userAgent": user_agent,
                    "metadata": {"punishUrl": punish_url, "cookieRequired": True},
                },
            }, remaining)
            task_id = created.get("taskId")
            if type(task_id) is not int or task_id <= 0:
                task_id = None
                raise CapMonsterError("CapMonster 未返回有效任务编号")
            logger.info("CapMonster createTask accepted taskId=%s class=alibaba userAgent_set=true", task_id)
            phase = "getTaskResult"
            for _ in range(MAX_RESULT_REQUESTS):
                remaining = deadline - time.monotonic()
                if remaining <= interval:
                    break
                time.sleep(interval)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                body = _post(session, "getTaskResult", {"clientKey": api_key, "taskId": task_id}, remaining)
                if body.get("status") == "ready":
                    logger.info("CapMonster getTaskResult ready taskId=%s", task_id)
                    return "ok", _solution_cookies(body.get("solution"), host), None
                if body.get("status") != "processing":
                    raise CapMonsterError("CapMonster 任务状态错误")
        raise CapMonsterError("CapMonster 求解超时；未重复创建收费任务")
    except CapMonsterError as exc:
        reason = str(exc)
    except (requests.RequestException, ValueError):
        reason = "CapMonster 连接或响应失败；未重复创建收费任务"
    detail = f"{reason}（阶段={phase}" + (f"，taskId={task_id}" if task_id is not None else "") + "）"
    logger.warning("%s", detail)
    return "fail", None, detail
