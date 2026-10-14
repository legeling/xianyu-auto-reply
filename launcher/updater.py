"""独立分支采用部署发布，禁止用上游安装包覆盖本地定制。"""
from common.version import get_update_info


def check_update() -> dict:
    return {**get_update_info(), "sha256": "", "error": ""}


def download_update(filename: str, progress_callback=None, expected_sha256: str = "") -> dict:
    return {"success": False, "file_path": "", "error": "本分支通过本仓库部署更新，不下载上游发布包"}


def apply_update(zip_path: str) -> dict:
    return {"success": False, "error": "本分支通过本仓库部署更新，不安装上游发布包"}
