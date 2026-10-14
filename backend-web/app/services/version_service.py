"""本分支版本信息；发布由本仓库构建、部署完成。"""
from __future__ import annotations

from common.version import CURRENT_VERSION, get_update_info


def get_current_version() -> str:
    return CURRENT_VERSION


async def check_update() -> dict:
    return {**get_update_info(), "error": ""}
