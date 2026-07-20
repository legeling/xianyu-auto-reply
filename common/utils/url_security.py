"""
外发 URL 安全校验（SSRF 防护）

安全意图：
- 系统中存在多处"用户可配置 URL、服务端代为发起请求"的功能
  （API 卡券取数、AI base_url 连通性测试、Webhook 测试等），
  未校验时会形成认证后 SSRF：攻击者可让服务端访问内网服务、
  云元数据接口（169.254.169.254）等并回显内容。
- 本模块在发起请求前统一校验：仅允许 http/https，解析目标主机并做 DNS 解析，
  拒绝所有内网/保留地址段（10/8、172.16/12、192.168/16、127/8、169.254/16、
  ::1、fc00::/7 等，由 ipaddress 的 is_private/is_loopback/is_link_local 等判定）。

已知残余风险（注释说明）：
- DNS rebinding（校验后到实际连接之间 DNS 记录被换成内网地址）属于 TOCTOU，
  彻底缓解需要在连接层固定解析结果，超出本次修复范围；
- 校验通过仅表示"目标是公网地址"，不代表目标内容可信。
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from loguru import logger

# 允许的外发协议
_ALLOWED_SCHEMES = {"http", "https"}


def _is_forbidden_ip(ip: ipaddress._BaseAddress) -> bool:
    """判断 IP 是否属于禁止外发访问的地址段（内网/环回/链路本地/保留/组播/未指定）。"""
    # IPv4-mapped IPv6（如 ::ffff:127.0.0.1）按映射后的 IPv4 判定，防止绕过
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (
        ip.is_private          # 10/8、172.16/12、192.168/16、fc00::/7 等
        or ip.is_loopback      # 127/8、::1
        or ip.is_link_local    # 169.254/16（含云元数据 169.254.169.254）、fe80::/10
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified   # 0.0.0.0、::
    )


async def resolve_host_ips(hostname: str) -> list[ipaddress._BaseAddress]:
    """解析主机名得到全部 IP（主机名为 IP 字面量时直接返回）。"""
    try:
        return [ipaddress.ip_address(hostname.strip("[]"))]
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    ips: list[ipaddress._BaseAddress] = []
    for info in infos:
        sockaddr = info[4]
        try:
            ips.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    return ips


async def validate_public_url(url: str, *, allow_private: bool = False) -> str | None:
    """校验外发 URL 是否安全（SSRF 防护）。

    Args:
        url: 待校验的目标 URL。
        allow_private: 为 True 时放行内网地址（仅用于管理员显式允许的
            内网部署场景，如内网开源模型 base_url）。

    Returns:
        None 表示校验通过；否则返回中文错误信息（可直接展示给调用方）。
    """
    raw = (url or "").strip()
    if not raw:
        return "URL 不能为空"

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return f"仅允许 http/https 协议的 URL（当前: {scheme or '无协议'}）"

    hostname = parsed.hostname
    if not hostname:
        return "URL 缺少有效的主机名"

    try:
        ips = await resolve_host_ips(hostname)
    except (socket.gaierror, UnicodeError) as e:
        logger.warning(f"【SSRF防护】主机名解析失败: {hostname}: {e}")
        return f"目标主机名无法解析: {hostname}"
    except Exception as e:
        logger.warning(f"【SSRF防护】主机名解析异常: {hostname}: {e}")
        return f"目标主机名解析异常: {hostname}"

    if not ips:
        return f"目标主机名未解析到任何 IP: {hostname}"

    # 任一解析结果落入禁止段即整体拒绝（防止多 A 记录夹带内网地址）
    forbidden = [str(ip) for ip in ips if _is_forbidden_ip(ip)]
    if forbidden and not allow_private:
        logger.warning(
            f"【SSRF防护】拒绝访问内网/保留地址: host={hostname}, ips={forbidden}, url={raw[:120]}"
        )
        return "目标地址指向内网或保留地址段，已按安全策略拒绝"

    return None
