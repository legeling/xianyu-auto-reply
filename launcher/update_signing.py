"""
更新清单签名工具（发布流水线用）

功能：
1. 计算更新安装包（zip）的 SHA256
2. 用 Ed25519 私钥对 SHA256 字符串签名
3. 将 sha256 / signature 写入 version.json 更新清单

用法：
    python launcher/update_signing.py \
        --private-key-file <私钥文件路径> \
        --zip <安装包路径> \
        --manifest <version.json路径>

安全说明：
- 私钥文件为「不入库的本地文件」，内容为 base64 编码的 32 字节 Ed25519
  私钥种子（单行），由运营方离线保管，绝不提交到仓库（.gitignore 已排除
  *.pem / *.key / launcher/private_key*）。
- 也可用环境变量 XIANYU_UPDATE_PRIVATE_KEY 代替 --private-key-file。
- 签名对应的验签公钥嵌入 launcher/updater.py（_UPDATE_PUBLIC_KEY_B64）。
"""
import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

# 确保项目根目录在搜索路径中，支持直接运行本文件
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# 私钥环境变量名
_PRIVATE_KEY_ENV = "XIANYU_UPDATE_PRIVATE_KEY"


def _sha256_file(file_path: Path) -> str:
    """计算文件的 SHA256（分块读取）"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_private_key(key_file: str) -> str:
    """从私钥文件或环境变量读取 base64 私钥"""
    if key_file:
        try:
            key = Path(key_file).read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"错误: 无法读取私钥文件 {key_file}: {e}")
            sys.exit(1)
        if key:
            return key
        print(f"错误: 私钥文件 {key_file} 内容为空")
        sys.exit(1)

    key = os.environ.get(_PRIVATE_KEY_ENV, "").strip()
    if key:
        return key

    print("错误: 未提供签名私钥。请通过以下任一方式提供：")
    print(f"  1. --private-key-file <私钥文件路径>（不入库的本地文件）")
    print(f"  2. 环境变量 {_PRIVATE_KEY_ENV}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="更新清单签名工具")
    parser.add_argument("--private-key-file", default="",
                        help="Ed25519 私钥文件路径（base64 单行，不入库）")
    parser.add_argument("--zip", required=True, dest="zip_path",
                        help="更新安装包（zip）路径")
    parser.add_argument("--manifest", required=True,
                        help="version.json 清单路径（原地更新 sha256/signature）")
    args = parser.parse_args()

    zip_path = Path(args.zip_path)
    if not zip_path.is_file():
        print(f"错误: 安装包不存在: {zip_path}")
        sys.exit(1)

    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        print(f"错误: 清单文件不存在: {manifest_path}")
        sys.exit(1)

    private_key_b64 = _load_private_key(args.private_key_file)
    try:
        seed = base64.b64decode(private_key_b64)
        sk = Ed25519PrivateKey.from_private_bytes(seed)
    except Exception as e:
        print(f"错误: 私钥格式无效（应为 base64 编码的 32 字节种子）: {e}")
        sys.exit(1)

    # 计算安装包 SHA256 并签名
    sha256_hex = _sha256_file(zip_path)
    signature = base64.urlsafe_b64encode(
        sk.sign(sha256_hex.encode("utf-8"))).decode("ascii").rstrip("=")

    # 更新清单
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"错误: 清单文件解析失败: {e}")
        sys.exit(1)

    manifest["sha256"] = sha256_hex
    manifest["signature"] = signature
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    print("✓ 清单已签名：")
    print(f"  文件:      {zip_path.name}")
    print(f"  SHA256:    {sha256_hex}")
    print(f"  签名:      {signature}")
    print(f"  清单:      {manifest_path}")


if __name__ == "__main__":
    main()
