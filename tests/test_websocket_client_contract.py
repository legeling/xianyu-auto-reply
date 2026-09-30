from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock


def test_send_message_uses_current_receiver_and_message_contract(monkeypatch) -> None:
    services = ModuleType("common.services")
    services.__path__ = [str(Path(__file__).resolve().parents[1] / "common/services")]
    monkeypatch.setitem(sys.modules, "common.services", services)
    captcha = ModuleType("common.services.captcha")
    captcha.__path__ = [str(Path(__file__).resolve().parents[1] / "common/services/captcha")]
    monkeypatch.setitem(sys.modules, "common.services.captcha", captcha)
    settings = SimpleNamespace(websocket_service_url="http://websocket:8090")
    http_client = SimpleNamespace(post=AsyncMock(return_value={"success": True}))
    config = ModuleType("app.core.config")
    config.get_settings = lambda: settings
    http = ModuleType("app.core.http_client")
    http.get_http_client = lambda: http_client
    monkeypatch.setitem(sys.modules, "app.core.config", config)
    monkeypatch.setitem(sys.modules, "app.core.http_client", http)
    source = Path(__file__).resolve().parents[1] / "backend-web/app/services/websocket_client.py"
    spec = importlib.util.spec_from_file_location("websocket_client_contract", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = module.WebSocketServiceClient()

    result = asyncio.run(client.send_message("seller", "chat", "你好", to_user_id="buyer"))

    assert result == {"success": True}
    http_client.post.assert_awaited_once_with(
        "http://websocket:8090/internal/accounts/seller/send-message",
        json={"chat_id": "chat", "message": "你好", "to_user_id": "buyer", "wait_result": True},
    )
