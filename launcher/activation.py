"""
激活码验证模块（Ed25519 非对称签名版）

功能：
1. 根据机器码 + 到期时间生成带有效期的激活码（需私钥，仅 keygen 使用）
2. 验证激活码是否匹配当前机器码且未过期（嵌入公钥验签，客户端无私钥）
3. 保存/读取激活验证文件（含到期时间与续期链）
4. 提供到期时间查询接口供GUI显示

安全说明：
- 签名算法为 Ed25519，公钥嵌入本文件，私钥由运营方离线保管（绝不入库）。
- 旧的「机器码:时间戳:盐」SHA256 方案因盐随源码泄露已废弃，
  旧格式激活码/续期码/license.dat 一律视为无效，需用新码重新激活。
- license.dat 的 check_hash 仅为防误改/防随手篡改的完整性校验，
  其材料全部随客户端分发，不能抵御有源码阅读能力的攻击者，
  真正的信任锚是激活码/续期码本身的 Ed25519 签名。
"""
import base64
import binascii
import hashlib
import json
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# 激活码验签公钥（Ed25519，base64 编码的 32 字节原始公钥）
# 私钥由运营方离线保管，绝不提交到仓库；轮换密钥需同步替换此处公钥
_PUBLIC_KEY_B64 = "Vk++PSqvJrNfUlzHSqUdSEMSTXGytx2W0Zk69UWi/YU="

# 验证文件名
_LICENSE_FILE = "license.dat"

# 北京时间时区
_BJ_TZ = timezone(timedelta(hours=8))


def _b64url_encode(data: bytes) -> str:
    """base64url 编码（去填充），用于激活码中的签名部分"""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    """base64url 解码（自动补填充），非法输入抛 ValueError"""
    pad = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + pad)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"base64 解码失败: {e}")


def _load_public_key() -> Ed25519PublicKey:
    """加载嵌入的 Ed25519 公钥"""
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(_PUBLIC_KEY_B64))


def sign_payload(payload: str, private_key_b64: str) -> str:
    """
    用 Ed25519 私钥对载荷签名（仅 keygen 等离线工具使用）

    Args:
        payload: 待签名字符串（UTF-8）
        private_key_b64: base64 编码的 32 字节私钥种子
    Returns:
        base64url（去填充）编码的 64 字节签名
    """
    seed = base64.b64decode(private_key_b64)
    sk = Ed25519PrivateKey.from_private_bytes(seed)
    return _b64url_encode(sk.sign(payload.encode("utf-8")))


def _verify_payload(payload: str, signature_b64url: str) -> bool:
    """
    用嵌入公钥验证载荷签名

    Returns:
        True 签名有效，False 签名无效或格式错误
    """
    try:
        sig = _b64url_decode(signature_b64url)
        _load_public_key().verify(sig, payload.encode("utf-8"))
        return True
    except Exception:
        return False


def _get_license_path() -> Path:
    """
    获取验证文件路径

    验证文件保存在exe同级目录，或项目根目录下的data文件夹中

    Returns:
        验证文件的完整路径
    """
    from launcher.frozen_detect import get_project_root
    base_dir = get_project_root()
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / _LICENSE_FILE


def _now_bj() -> datetime:
    """获取当前北京时间"""
    return datetime.now(_BJ_TZ)


def calc_expire_time(unit: str, amount: int) -> int:
    """
    根据维度和数量计算到期时间戳（北京时间）

    Args:
        unit: 时间维度，h=小时 d=天 m=月 y=年
        amount: 数量，必须为正整数
    Returns:
        到期时间的Unix时间戳（秒）
    """
    now = _now_bj()
    if unit == "h":
        expire = now + timedelta(hours=amount)
    elif unit == "d":
        expire = now + timedelta(days=amount)
    elif unit == "m":
        # 月份简单处理：每月按30天
        expire = now + timedelta(days=amount * 30)
    elif unit == "y":
        expire = now + timedelta(days=amount * 365)
    else:
        raise ValueError(f"不支持的时间维度: {unit}，可选: h/d/m/y")
    return int(expire.timestamp())


def generate_activation_code(machine_id: str, expire_ts: int,
                             private_key_b64: str) -> str:
    """
    根据机器码和到期时间戳生成激活码（Ed25519 签名，需私钥，仅 keygen 使用）

    激活码格式: {到期时间戳hex大写}-{base64url签名}
    签名载荷: "{机器码}:{到期时间戳}"

    Args:
        machine_id: 32位大写机器码
        expire_ts: 到期时间的Unix时间戳（秒）
        private_key_b64: base64 编码的 Ed25519 私钥种子
    Returns:
        激活码字符串
    """
    expire_hex = format(expire_ts, "X")
    sig = sign_payload(f"{machine_id}:{expire_ts}", private_key_b64)
    return f"{expire_hex}-{sig}"


def _canonical_activation_code(activation_code: str) -> str:
    """
    规范化激活码：到期时间戳 hex 统一大写，签名部分保持原始大小写
    （base64url 签名大小写敏感，整体 upper() 会破坏签名）
    """
    code = activation_code.strip()
    parts = code.split("-", 1)
    if len(parts) != 2:
        return code
    return f"{parts[0].upper()}-{parts[1]}"


def verify_activation_code(machine_id: str, activation_code: str) -> dict:
    """
    验证激活码是否匹配机器码，并提取到期时间（Ed25519 公钥验签）

    Args:
        machine_id: 32位大写机器码
        activation_code: 激活码字符串
    Returns:
        字典包含:
        - valid: bool 签名是否有效
        - expire_ts: int 到期时间戳（签名无效时为0）
        - expired: bool 是否已过期
    """
    code = _canonical_activation_code(activation_code)
    # base64url 签名本身可能含 '-'，只按第一个分隔符切分（前缀为纯 hex，不含 '-'）
    parts = code.split("-", 1)
    if len(parts) != 2:
        return {"valid": False, "expire_ts": 0, "expired": True}

    try:
        expire_ts = int(parts[0], 16)
    except ValueError:
        return {"valid": False, "expire_ts": 0, "expired": True}

    # base64url 签名大小写敏感，必须使用原始大小写的签名部分
    if not _verify_payload(f"{machine_id}:{expire_ts}", parts[1]):
        return {"valid": False, "expire_ts": 0, "expired": True}

    now_ts = int(_now_bj().timestamp())
    return {
        "valid": True,
        "expire_ts": expire_ts,
        "expired": now_ts > expire_ts,
    }


def _calc_check_hash(machine_id: str, activation_code: str, expire_ts: int,
                     renewals: list, used_renew_codes: list,
                     last_renew_ts: int) -> str:
    """
    计算 license.dat 完整性校验哈希

    注意：材料全部随客户端分发（含公钥），仅防误改/低强度篡改，
    不能替代激活码/续期码本身的 Ed25519 签名校验。
    """
    payload = json.dumps({
        "machine_id": machine_id,
        "activation_code": activation_code.strip(),
        "expire_ts": expire_ts,
        "renewals": renewals,
        "used_renew_codes": used_renew_codes,
        "last_renew_ts": last_renew_ts,
        "pk": _PUBLIC_KEY_B64,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()


def save_license(machine_id: str, activation_code: str,
                 expire_ts: int, used_renew_codes: list = None,
                 last_renew_ts: int = 0, renewals: list = None) -> bool:
    """
    保存激活信息到验证文件

    Args:
        machine_id: 32位大写机器码
        activation_code: 激活码
        expire_ts: 当前生效的到期时间戳（含续期叠加结果）
        used_renew_codes: 已使用的续期码列表（可选）
        last_renew_ts: 上次续期时间戳（可选，用于一天只能续期一次的校验）
        renewals: 续期记录链（可选，每条含 code/duration_seconds/applied_ts/expire_ts）
    Returns:
        True保存成功，False保存失败
    """
    try:
        renewals = renewals or []
        used_renew_codes = used_renew_codes or []
        check_hash = _calc_check_hash(
            machine_id, activation_code, expire_ts,
            renewals, used_renew_codes, last_renew_ts,
        )

        data = {
            "machine_id": machine_id,
            "activation_code": activation_code.strip(),
            "expire_ts": expire_ts,
            "check_hash": check_hash,
            "used_renew_codes": used_renew_codes,
            "last_renew_ts": last_renew_ts,
            "renewals": renewals,
        }
        license_path = _get_license_path()
        license_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        return True
    except Exception:
        return False


def load_and_verify_license(current_machine_id: str) -> dict:
    """
    加载验证文件并校验激活状态

    检查内容：文件存在性、完整性哈希、机器码匹配、
    激活码 Ed25519 签名、续期链签名与叠加结果、是否已过期。

    Args:
        current_machine_id: 当前机器的机器码
    Returns:
        字典包含:
        - valid: bool 是否激活有效（签名正确且未过期）
        - message: str 状态说明
        - machine_changed: bool 机器码是否发生变化
        - expire_ts: int 到期时间戳（0表示未知）
        - expired: bool 是否已过期
    """
    license_path = _get_license_path()
    _fail = {"valid": False, "machine_changed": False,
             "expire_ts": 0, "expired": False}

    if not license_path.exists():
        return {**_fail, "message": "未找到激活文件，请输入激活码"}

    try:
        data = json.loads(license_path.read_text(encoding="utf-8"))
    except Exception:
        return {**_fail, "message": "激活文件损坏，请重新激活"}

    stored_mid = data.get("machine_id", "")
    stored_code = data.get("activation_code", "")
    stored_expire = data.get("expire_ts", 0)
    stored_hash = data.get("check_hash", "")
    stored_renewals = data.get("renewals", [])
    stored_used = data.get("used_renew_codes", [])
    stored_last_renew = data.get("last_renew_ts", 0)

    # 校验文件完整性（防误改/低强度篡改；信任锚仍是各码的 Ed25519 签名）
    expected_hash = _calc_check_hash(
        stored_mid, stored_code, stored_expire,
        stored_renewals, stored_used, stored_last_renew,
    )

    if stored_hash != expected_hash:
        return {**_fail, "message": "激活文件已被篡改，请重新激活"}

    # 检查机器码（同机兼容：允许不同生成方式下得到的候选机器码）
    try:
        from launcher.hardware_id import generate_machine_id_candidates
        candidates = set(generate_machine_id_candidates())
        candidates.add(current_machine_id)
    except Exception:
        candidates = {current_machine_id}

    if stored_mid not in candidates:
        return {**_fail, "message": "检测到硬件变更，机器码已变化，请重新激活",
                "machine_changed": True}

    # 验证激活码签名：必须用 license 中存储的 machine_id（激活码签名与之绑定）
    result = verify_activation_code(stored_mid, stored_code)
    if not result["valid"]:
        return {**_fail, "message": "激活码无效，请重新输入"}

    # 重放续期链：逐条验证续期码签名并重算到期时间，防止手改 expire_ts
    effective_expire = result["expire_ts"]
    for renewal in stored_renewals:
        renew_code = renewal.get("code", "")
        applied_ts = renewal.get("applied_ts", 0)
        verify_result = verify_renew_code(stored_mid, renew_code)
        if not verify_result["valid"]:
            return {**_fail, "message": "续期记录签名无效，激活文件已被篡改，请重新激活"}
        base_ts = effective_expire if effective_expire > applied_ts else applied_ts
        effective_expire = base_ts + verify_result["duration_seconds"]

    if effective_expire != stored_expire:
        return {**_fail, "message": "激活文件已被篡改，请重新激活"}

    # 检查是否过期
    now_ts = int(_now_bj().timestamp())
    if now_ts > effective_expire:
        expire_str = format_expire_time(effective_expire)
        return {**_fail, "message": f"激活码已过期（{expire_str}），可输入续期码继续进入系统",
                "expire_ts": effective_expire, "expired": True}

    return {
        "valid": True,
        "message": "激活验证通过",
        "machine_changed": False,
        "expire_ts": effective_expire,
        "expired": False,
    }


def calc_duration_seconds(unit: str, amount: int) -> int:
    """
    根据维度和数量计算时长（秒数）

    Args:
        unit: 时间维度，h=小时 d=天 m=月 y=年
        amount: 数量，必须为正整数
    Returns:
        时长秒数
    """
    if unit == "h":
        return amount * 3600
    elif unit == "d":
        return amount * 86400
    elif unit == "m":
        return amount * 30 * 86400
    elif unit == "y":
        return amount * 365 * 86400
    else:
        raise ValueError(f"不支持的时间维度: {unit}，可选: h/d/m/y")


def generate_renew_code(machine_id: str, duration_seconds: int,
                        private_key_b64: str) -> str:
    """
    生成续期激活码（以R开头，区别于普通激活码，需私钥，仅 keygen 使用）

    续期码格式: R{时长秒数hex大写}-{签发标记}-{base64url签名}
    签名载荷: "{机器码}:R:{时长秒数}:{签发标记}"

    Args:
        machine_id: 32位大写机器码
        duration_seconds: 要续期的时长（秒）
        private_key_b64: base64 编码的 Ed25519 私钥种子
    Returns:
        续期码字符串
    """
    issue_marker = secrets.token_hex(8).upper()
    dur_hex = format(duration_seconds, "X")
    sig = sign_payload(f"{machine_id}:R:{duration_seconds}:{issue_marker}",
                       private_key_b64)
    return f"R{dur_hex}-{issue_marker}-{sig}"


def _canonical_renew_code(renew_code: str) -> str:
    """
    规范化续期码：R 前缀、时长 hex、签发标记统一大写，签名部分保持原始大小写
    （base64url 签名大小写敏感，整体 upper() 会破坏签名）
    """
    code = renew_code.strip()
    if not code.upper().startswith("R"):
        return code
    body = code[1:]
    parts = body.split("-", 2)
    if len(parts) != 3:
        return code
    return f"R{parts[0].upper()}-{parts[1].upper()}-{parts[2]}"


def verify_renew_code(machine_id: str, renew_code: str) -> dict:
    """
    验证续期激活码是否匹配机器码，并提取续期时长（Ed25519 公钥验签）

    Args:
        machine_id: 32位大写机器码
        renew_code: 续期码字符串（以R开头）
    Returns:
        字典包含:
        - valid: bool 签名是否有效
        - duration_seconds: int 续期时长秒数（无效时为0）
    """
    code = _canonical_renew_code(renew_code)
    if not code.startswith("R"):
        return {"valid": False, "duration_seconds": 0}

    # 去掉R前缀（base64url 签名本身可能含 '-'，只按前两个分隔符切分）
    body = code[1:]
    parts = body.split("-", 2)
    if len(parts) != 3:
        return {"valid": False, "duration_seconds": 0}

    try:
        duration_seconds = int(parts[0], 16)
    except ValueError:
        return {"valid": False, "duration_seconds": 0}

    issue_marker = parts[1]
    if not issue_marker:
        return {"valid": False, "duration_seconds": 0}
    try:
        int(issue_marker, 16)
    except ValueError:
        return {"valid": False, "duration_seconds": 0}

    if not _verify_payload(
            f"{machine_id}:R:{duration_seconds}:{issue_marker}", parts[2]):
        return {"valid": False, "duration_seconds": 0}

    return {"valid": True, "duration_seconds": duration_seconds}


def _load_license_data() -> dict:
    """
    读取验证文件原始数据

    Returns:
        解析后的字典，文件不存在或解析失败返回空字典
    """
    license_path = _get_license_path()
    if not license_path.exists():
        return {}
    try:
        return json.loads(license_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_used_renew_codes() -> list:
    """
    从验证文件中加载已使用的续期码列表

    Returns:
        已使用续期码的字符串列表，文件不存在或解析失败返回空列表
    """
    return _load_license_data().get("used_renew_codes", [])


def _load_last_renew_ts() -> int:
    """
    从验证文件中加载上次续期时间戳

    Returns:
        上次续期的Unix时间戳，文件不存在或无记录返回0
    """
    return _load_license_data().get("last_renew_ts", 0)


def renew_license(machine_id: str, renew_code: str) -> dict:
    """
    使用续期码对现有激活进行续期（时长叠加到原到期时间）

    Args:
        machine_id: 32位大写机器码
        renew_code: 续期码字符串
    Returns:
        字典包含:
        - success: bool 续期是否成功
        - message: str 结果说明
        - new_expire_ts: int 新的到期时间戳（失败时为0）
    """
    # 验证续期码（code_canonical 保留签名原始大小写，可安全存储与重放验签）
    code_canonical = _canonical_renew_code(renew_code)
    verify_result = verify_renew_code(machine_id, code_canonical)
    if not verify_result["valid"]:
        return {"success": False, "message": "续期码无效，请检查是否输入正确",
                "new_expire_ts": 0}

    duration = verify_result["duration_seconds"]

    # 加载当前激活信息
    license_result = load_and_verify_license(machine_id)
    old_expire_ts = license_result.get("expire_ts", 0)

    # 检查续期码是否已经使用过
    used_codes = _load_used_renew_codes()
    if code_canonical in used_codes:
        return {"success": False, "message": "该续期码已使用过，不能重复使用",
                "new_expire_ts": 0}

    # 检查一天只能续期一次
    last_renew = _load_last_renew_ts()
    if last_renew > 0:
        now_ts = int(_now_bj().timestamp())
        elapsed = now_ts - last_renew
        if elapsed < 86400:
            remaining_hours = (86400 - elapsed) // 3600
            remaining_mins = ((86400 - elapsed) % 3600) // 60
            return {"success": False,
                    "message": f"每天只能续期一次，请{remaining_hours}小时{remaining_mins}分钟后再试",
                    "new_expire_ts": 0}

    current_ts = int(_now_bj().timestamp())
    if old_expire_ts <= 0:
        # 没有有效激活记录，从当前时间开始计算
        base_ts = current_ts
    elif license_result.get("expired", False):
        # 已过期，从当前时间开始计算
        base_ts = current_ts
    else:
        # 未过期，叠加到原到期时间
        base_ts = old_expire_ts

    new_expire_ts = base_ts + duration

    # 保留原激活码与续期链，追加本次续期记录（客户端无私钥，不能重签激活码，
    # 到期时间由续期链重放得出，见 load_and_verify_license）
    license_data = _load_license_data()
    original_code = license_data.get("activation_code", "")
    renewals = license_data.get("renewals", [])
    renewals.append({
        "code": code_canonical,
        "duration_seconds": duration,
        "applied_ts": current_ts,
        "expire_ts": new_expire_ts,
    })

    # 记录已使用的续期码和本次续期时间并保存
    used_codes.append(code_canonical)
    if not save_license(machine_id, original_code, new_expire_ts, used_codes,
                        last_renew_ts=current_ts, renewals=renewals):
        return {"success": False, "message": "保存激活信息失败",
                "new_expire_ts": 0}

    expire_str = format_expire_time(new_expire_ts)
    return {"success": True,
            "message": f"续期成功，新到期时间: {expire_str}",
            "new_expire_ts": new_expire_ts}


def revoke_license() -> dict:
    """
    注销激活状态，删除激活验证文件

    Returns:
        字典包含:
        - success: bool 注销是否成功
        - message: str 结果说明
    """
    license_path = _get_license_path()
    if not license_path.exists():
        return {"success": False, "message": "当前没有激活记录"}
    try:
        license_path.unlink()
        return {"success": True, "message": "激活已注销，请重新激活"}
    except Exception as e:
        return {"success": False, "message": f"注销失败: {e}"}


def format_expire_time(expire_ts: int) -> str:
    """
    将到期时间戳格式化为北京时间字符串

    Args:
        expire_ts: Unix时间戳
    Returns:
        格式化字符串，如 "2026-03-30 18:00:00"
    """
    if expire_ts <= 0:
        return "未知"
    dt = datetime.fromtimestamp(expire_ts, tz=_BJ_TZ)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def get_remaining_text(expire_ts: int) -> str:
    """
    计算剩余时间并返回可读文本

    Args:
        expire_ts: Unix时间戳
    Returns:
        剩余时间文本，如 "剩余 3天12小时" 或 "已过期"
    """
    if expire_ts <= 0:
        return "未知"
    now_ts = int(_now_bj().timestamp())
    diff = expire_ts - now_ts
    if diff <= 0:
        return "已过期"

    days = diff // 86400
    hours = (diff % 86400) // 3600
    minutes = (diff % 3600) // 60

    if days > 0:
        return f"剩余 {days}天{hours}小时"
    elif hours > 0:
        return f"剩余 {hours}小时{minutes}分钟"
    else:
        return f"剩余 {minutes}分钟"
