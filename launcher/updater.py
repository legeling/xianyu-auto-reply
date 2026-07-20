"""
在线更新模块（带签名校验版）

功能：
1. 从服务器获取最新版本信息（version.json）
2. 对比本地版本号，判断是否需要更新
3. 下载新版本压缩包到临时目录，强制校验 SHA256 与 Ed25519 签名
4. 生成更新脚本（bat），等待当前进程退出后覆盖并重启

服务器端需要提供：
- {UPDATE_URL}/version.json  版本信息文件（必须 https）
- {UPDATE_URL}/app-vX.X.X.zip  完整程序压缩包

version.json 格式示例：
{
    "version": "1.1.0",
    "description": "1. 修复xxx\\n2. 新增xxx",
    "filename": "app-v1.1.0.zip",
    "sha256": "压缩包的SHA256十六进制（小写）",
    "signature": "对 sha256 字符串的 Ed25519 签名（base64url，去填充）"
}

安全说明：
- sha256 与 signature 由发布流水线用 launcher/update_signing.py 生成，
  签名私钥由运营方离线保管（绝不入库），公钥嵌入本文件。
- 供应链局限：SHA256 只能防传输损坏/防镜像被替换（前提是清单本身可信）；
  Ed25519 签名才是信任锚。若更新服务器与私钥同时失陷，客户端无法自救。
"""
import base64
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from launcher.version import CURRENT_VERSION

# 更新服务器地址（从 data/update_config.json 读取）
_DEFAULT_UPDATE_URL = "https://xy-update.zhinianboke.com"

# 更新清单验签公钥（Ed25519，base64 编码的 32 字节原始公钥）
# 私钥由运营方离线保管，绝不提交到仓库；轮换密钥需同步替换此处公钥
_UPDATE_PUBLIC_KEY_B64 = "fgOfn/thujsROVJ5TRLRf+EjsMgRWLpkh41htMgnGO4="

# 是否强制要求清单携带有效 Ed25519 签名
# True：发布时必须用 launcher/update_signing.py 对清单签名（推荐，防清单被篡改）
# False：仅兼容过渡期（仅 SHA256 校验，清单被篡改则哈希不可信，不建议长期使用）
_REQUIRE_MANIFEST_SIGNATURE = True


def _get_update_url() -> str:
    """
    获取更新服务器地址

    优先从 data/update_config.json 读取，否则使用默认值。
    安全要求：必须是 https（仅允许 localhost/127.0.0.1 用 http 便于本地调试），
    否则拒绝更新，防止明文 HTTP 被中间人篡改清单与安装包。
    Returns:
        更新服务器基础URL（不含尾部斜杠）
    """
    url = _DEFAULT_UPDATE_URL
    try:
        from launcher.frozen_detect import get_project_root
        base_dir = get_project_root()
        config_path = base_dir / "data" / "update_config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            custom = data.get("update_url", "").rstrip("/")
            if custom:
                url = custom
    except Exception:
        pass

    # 强制 https：非 https 地址直接回退默认 https 地址（防止配置文件被改成 http）
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme != "https":
        host = (parsed.hostname or "").lower()
        if parsed.scheme == "http" and host in ("localhost", "127.0.0.1"):
            # 本地调试放行 http
            return url
        return _DEFAULT_UPDATE_URL
    return url


def _verify_manifest_signature(sha256_hex: str, signature_b64url: str) -> bool:
    """
    用嵌入公钥验证清单签名（签名载荷为 sha256 十六进制字符串）

    Returns:
        True 签名有效，False 签名无效或格式错误
    """
    try:
        pad = "=" * (-len(signature_b64url) % 4)
        sig = base64.urlsafe_b64decode(signature_b64url + pad)
        pub = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(_UPDATE_PUBLIC_KEY_B64))
        pub.verify(sig, sha256_hex.encode("utf-8"))
        return True
    except Exception:
        return False


def _compare_versions(local: str, remote: str) -> bool:
    """
    比较版本号，判断远程版本是否比本地新

    Args:
        local: 本地版本号，如 "1.0.0"
        remote: 远程版本号，如 "1.1.0"
    Returns:
        True表示远程版本更新，需要升级
    """
    try:
        local_parts = [int(x) for x in local.split(".")]
        remote_parts = [int(x) for x in remote.split(".")]
        return remote_parts > local_parts
    except (ValueError, AttributeError):
        return False


def check_update() -> dict:
    """
    检查是否有新版本可用

    从服务器获取 version.json 并与本地版本对比。

    Returns:
        字典包含:
        - has_update: bool 是否有新版本
        - current_version: str 当前版本号
        - remote_version: str 远程版本号（无更新时为空）
        - description: str 更新说明
        - filename: str 下载文件名
        - sha256: str 文件SHA256校验值（十六进制小写）
        - error: str 错误信息（正常时为空）
    """
    result = {
        "has_update": False,
        "current_version": CURRENT_VERSION,
        "remote_version": "",
        "description": "",
        "filename": "",
        "sha256": "",
        "error": "",
    }

    update_url = _get_update_url()
    version_url = f"{update_url}/version.json"

    try:
        req = urllib.request.Request(version_url, method="GET")
        req.add_header("User-Agent", "XianyuAutoReply-Updater")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        result["error"] = f"无法连接更新服务器: {e.reason}"
        return result
    except Exception as e:
        result["error"] = f"检查更新失败: {str(e)}"
        return result

    remote_ver = data.get("version", "")
    if not remote_ver:
        result["error"] = "服务器返回的版本信息无效"
        return result

    result["remote_version"] = remote_ver
    result["description"] = data.get("description", "无更新说明")
    result["filename"] = data.get("filename", "")

    if _compare_versions(CURRENT_VERSION, remote_ver):
        # 有新版本时强制校验清单完整性字段
        sha256_hex = str(data.get("sha256", "")).strip().lower()
        if (len(sha256_hex) != 64
                or any(c not in "0123456789abcdef" for c in sha256_hex)):
            result["error"] = ("更新清单缺少有效的 sha256 字段，已中止更新"
                               "（发布流水线需使用 launcher/update_signing.py 生成清单）")
            return result

        signature = str(data.get("signature", "")).strip()
        if _REQUIRE_MANIFEST_SIGNATURE:
            if not signature or not _verify_manifest_signature(sha256_hex, signature):
                result["error"] = ("更新清单签名校验失败，已中止更新"
                                   "（可能遭遇篡改，请勿继续）")
                return result
        elif signature and not _verify_manifest_signature(sha256_hex, signature):
            # 过渡期：携带签名但验签失败同样拒绝（宁可误杀不可放行）
            result["error"] = "更新清单签名校验失败，已中止更新（可能遭遇篡改，请勿继续）"
            return result

        result["sha256"] = sha256_hex
        result["has_update"] = True

    return result


def _sha256_file(file_path: Path) -> str:
    """计算文件的 SHA256（分块读取，避免大包占内存）"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def download_update(filename: str,
                    progress_callback=None,
                    expected_sha256: str = "") -> dict:
    """
    下载新版本压缩包到临时目录，并强制校验 SHA256

    Args:
        filename: 下载文件名（如 app-v1.1.0.zip）
        progress_callback: 进度回调函数，参数为(已下载字节, 总字节)
        expected_sha256: 清单中给出的 SHA256（十六进制小写），必填；
                         为空或校验不匹配则中止更新并删除已下载文件
    Returns:
        字典包含:
        - success: bool 是否下载成功
        - file_path: str 下载文件的本地路径
        - error: str 错误信息
    """
    result = {"success": False, "file_path": "", "error": ""}

    # 强制要求携带预期哈希，防止调用方绕过校验
    expected_sha256 = (expected_sha256 or "").strip().lower()
    if len(expected_sha256) != 64:
        result["error"] = "缺少预期的 SHA256 校验值，已中止更新"
        return result

    # 文件名安全校验：仅允许纯文件名，防止路径穿越写到临时目录之外
    if not filename or Path(filename).name != filename:
        result["error"] = "非法的下载文件名，已中止更新"
        return result

    update_url = _get_update_url()
    download_url = f"{update_url}/{filename}"

    # 临时目录用于存放下载文件
    temp_dir = Path(tempfile.gettempdir()) / "xianyu_update"
    temp_dir.mkdir(parents=True, exist_ok=True)
    local_path = temp_dir / filename

    try:
        req = urllib.request.Request(download_url, method="GET")
        req.add_header("User-Agent", "XianyuAutoReply-Updater")
        with urllib.request.urlopen(req, timeout=90) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(local_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)
    except Exception as e:
        result["error"] = f"下载失败: {str(e)}"
        return result

    # 强制 SHA256 校验：不匹配则删除文件并告警，绝不进入安装流程
    actual_sha256 = _sha256_file(local_path)
    if actual_sha256 != expected_sha256:
        try:
            local_path.unlink()
        except OSError:
            pass
        result["error"] = ("安装包 SHA256 校验失败，已中止更新并删除安装包"
                           "（可能遭遇篡改或下载损坏，请勿继续）")
        return result

    result["success"] = True
    result["file_path"] = str(local_path)
    return result


def apply_update(zip_path: str) -> dict:
    """
    生成更新脚本并启动，当前程序随后退出

    更新脚本（bat）会：
    1. 等待当前exe进程退出
    2. 解压新版本覆盖到当前目录
    3. 删除临时文件
    4. 启动新版本exe

    Args:
        zip_path: 下载的zip文件路径
    Returns:
        字典包含:
        - success: bool 是否成功生成并启动更新脚本
        - error: str 错误信息
    """
    result = {"success": False, "error": ""}

    # 确定当前程序目录
    from launcher.frozen_detect import is_frozen, get_project_root
    if is_frozen():
        app_dir = Path(sys.executable).parent
        exe_name = Path(sys.executable).name
    else:
        # 开发模式：用项目根目录模拟
        app_dir = get_project_root()
        exe_name = "main.exe"

    # 生成更新bat脚本
    bat_path = Path(tempfile.gettempdir()) / "xianyu_update" / "do_update.bat"

    # data目录路径（包含激活码、配置、数据库等用户数据）
    data_dir = app_dir / "data"
    backup_dir = Path(tempfile.gettempdir()) / "xianyu_update" / "data_backup"

    # bat脚本内容：停止所有服务 → 备份data → 解压覆盖 → 恢复data → 重启
    bat_content = f"""@echo off
chcp 65001 >nul
echo 正在更新，请稍候...

echo 停止主程序...
taskkill /F /IM "{exe_name}" >nul 2>nul

echo 停止后台服务...
REM 杀掉4个服务端口（backend-web:8089, websocket:8090, scheduler:8091, frontend:9000）
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8089 "') do taskkill /F /PID %%a >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8090 "') do taskkill /F /PID %%a >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8091 "') do taskkill /F /PID %%a >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9000 "') do taskkill /F /PID %%a >nul 2>nul

timeout /t 2 /nobreak >nul

REM 备份data目录（激活码、配置、数据库等用户数据）
if exist "{data_dir}" (
    echo 备份用户数据...
    if exist "{backup_dir}" rmdir /s /q "{backup_dir}"
    xcopy "{data_dir}" "{backup_dir}\\" /E /I /Q /Y >nul 2>nul
)

REM 解压覆盖到程序目录
echo 正在解压新版本...
powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{app_dir}' -Force"

if %errorlevel% neq 0 (
    echo 更新失败！请手动解压 {zip_path} 到 {app_dir}
    REM 恢复备份
    if exist "{backup_dir}" (
        xcopy "{backup_dir}" "{data_dir}\\" /E /I /Q /Y >nul 2>nul
    )
    pause
    exit /b 1
)

REM 恢复data目录（覆盖回来，保证用户数据不丢失）
if exist "{backup_dir}" (
    echo 恢复用户数据...
    xcopy "{backup_dir}" "{data_dir}\\" /E /I /Q /Y >nul 2>nul
    rmdir /s /q "{backup_dir}" 2>nul
)

echo 更新完成，正在启动新版本...
REM 清理临时文件
del /q "{zip_path}" 2>nul

REM 启动新版本
cd /d "{app_dir}"
start "" "{app_dir}\\{exe_name}"

REM 删除自身
del /q "%~f0" 2>nul
exit
"""
    try:
        bat_path.parent.mkdir(parents=True, exist_ok=True)
        bat_path.write_text(bat_content, encoding="utf-8")
    except Exception as e:
        result["error"] = f"生成更新脚本失败: {str(e)}"
        return result

    # 启动更新脚本
    try:
        os.startfile(str(bat_path))
        result["success"] = True
    except Exception as e:
        result["error"] = f"启动更新脚本失败: {str(e)}"

    return result
