from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import patch

from common.version import CURRENT_VERSION, UPSTREAM_VERSION, get_release_info, get_update_info
from launcher import updater, version


def test_web_and_launcher_use_fork_version_without_network() -> None:
    source = Path(__file__).resolve().parents[1] / "backend-web/app/services/version_service.py"
    spec = importlib.util.spec_from_file_location("fork_version_service", source)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    with patch("urllib.request.urlopen", side_effect=AssertionError("上游更新请求不应发生")):
        assert version.CURRENT_VERSION == service.get_current_version() == CURRENT_VERSION
        assert asyncio.run(service.check_update())["description"] == get_update_info()["description"]
        assert updater.check_update()["has_update"] is False
        assert updater.download_update("upstream.zip", expected_sha256="a" * 64)["success"] is False
        assert updater.apply_update("upstream.zip")["success"] is False
    assert get_release_info()["upstream_version"] == UPSTREAM_VERSION
    assert get_update_info()["remote_version"] == get_update_info()["download_url"] == ""
