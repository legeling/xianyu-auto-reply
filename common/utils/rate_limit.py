"""
登录接口限流（防暴力破解 / 防用户枚举）

安全意图：
- 登录接口此前仅按"账号维度"记录失败次数（数据库 login_fail_count），
  攻击者可以换着账号名从同一 IP 持续爆破，或枚举有效用户名；
- 这里补充一层基于客户端 IP 的进程内存限流：连续失败 N 次后锁定 M 秒，
  实现简单、无外部依赖（Redis 非必配环境下也能生效）。
- 进程内存实现意味着多实例部署时各实例独立计数，属于已知局限，
  但作为纵深防御的一层已足够抬高暴力破解成本。
"""
from __future__ import annotations

import threading
import time

from loguru import logger


class LoginRateLimiter:
    """基于客户端 IP 的内存登录限流器：连续失败 max_failures 次后锁定 lock_seconds 秒。"""

    def __init__(self, max_failures: int = 5, lock_seconds: int = 300):
        self.max_failures = max_failures
        self.lock_seconds = lock_seconds
        # {ip: {"fail_count": int, "locked_until": float}}
        self._records: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    def check_locked(self, ip: str) -> tuple[bool, int]:
        """检查 IP 是否处于锁定期。

        Returns:
            (是否锁定, 剩余锁定秒数)
        """
        now = time.time()
        with self._lock:
            record = self._records.get(ip)
            if not record:
                return False, 0
            locked_until = record.get("locked_until", 0.0)
            if locked_until > now:
                return True, int(locked_until - now) + 1
            return False, 0

    def record_failure(self, ip: str) -> None:
        """记录一次登录失败；达到阈值后进入锁定期。"""
        now = time.time()
        with self._lock:
            record = self._records.setdefault(ip, {"fail_count": 0, "locked_until": 0.0})
            # 锁定期内的失败不再累加，保持既有锁定窗口即可
            if record.get("locked_until", 0.0) > now:
                return
            record["fail_count"] = int(record.get("fail_count", 0)) + 1
            if record["fail_count"] >= self.max_failures:
                record["locked_until"] = now + self.lock_seconds
                record["fail_count"] = 0
                logger.warning(
                    f"【登录限流】IP {ip} 连续登录失败达到 {self.max_failures} 次，"
                    f"锁定 {self.lock_seconds} 秒"
                )

    def record_success(self, ip: str) -> None:
        """登录成功后清除该 IP 的失败计数。"""
        with self._lock:
            self._records.pop(ip, None)

    def cleanup(self, max_idle_seconds: int = 3600) -> None:
        """清理过期记录（锁定期已过且无失败计数的条目），避免内存无限增长。"""
        now = time.time()
        with self._lock:
            expired = [
                ip
                for ip, record in self._records.items()
                if record.get("locked_until", 0.0) < now - max_idle_seconds
            ]
            for ip in expired:
                self._records.pop(ip, None)


# 全局共享实例：登录失败 5 次锁定 5 分钟
login_rate_limiter = LoginRateLimiter(max_failures=5, lock_seconds=300)


def get_client_ip(request) -> str:
    """获取客户端 IP（兼容反向代理 X-Forwarded-For，取第一个地址）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "-"
