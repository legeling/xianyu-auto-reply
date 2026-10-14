from __future__ import annotations

import ast
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest


@pytest.fixture
def offline_service(monkeypatch):
    client = ModuleType("common.services.xianyu_mtop")
    client.mtop_call = AsyncMock()
    monkeypatch.setitem(sys.modules, client.__name__, client)
    path = Path(__file__).resolve().parents[1] / "common/services/item_offline_service.py"
    spec = importlib.util.spec_from_file_location("item_offline_contract", path)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    return service, client.mtop_call


def test_offline_uses_owner_api_and_preserves_partial_results(offline_service):
    service, request = offline_service
    request.side_effect = [
        {"success": True, "cookies_str": "rotated-session"},
        {"success": False, "error": "非本账号商品", "cookies_str": "rotated-session"},
    ]
    result = asyncio.run(service.batch_offline_items_from_xianyu(
        "account", "initial-session", [" 100 ", "100", "", "200"], owner_id=4,
    ))
    assert request.await_args_list == [
        call("account", "initial-session", "mtop.taobao.idle.item.downshelf", "2.0", {"itemId": "100"},
             owner_id=4, referer="https://www.goofish.com/item?id=100"),
        call("account", "rotated-session", "mtop.taobao.idle.item.downshelf", "2.0", {"itemId": "200"},
             owner_id=4, referer="https://www.goofish.com/item?id=200"),
    ]
    assert result["success"] is True
    assert (result["suc_count"], result["fail_count"]) == (1, 1)
    assert result["results"] == [{"item_id": "100", "success": True}, {"item_id": "200", "success": False}]
    assert result["cookies_str"] == "rotated-session"


def test_invalid_account_stops_remaining_requests(offline_service):
    service, request = offline_service
    request.return_value = {"success": False, "account_invalid": True, "error": "Session过期"}
    result = asyncio.run(service.batch_offline_items_from_xianyu("account", "session", ["100", "200"]))
    assert request.await_count == 1
    assert result["success"] is False
    assert result["message"] == "Session过期"
    assert (result["suc_count"], result["fail_count"]) == (0, 2)
    assert result["results"] == [{"item_id": "100", "success": False}, {"item_id": "200", "success": False}]


def test_empty_items_do_not_call_platform(offline_service):
    service, request = offline_service
    result = asyncio.run(service.batch_offline_items_from_xianyu("account", "session", ["", "  "]))
    request.assert_not_awaited()
    assert result["success"] is False
    assert (result["suc_count"], result["fail_count"]) == (0, 0)
    assert result["results"] == []


def test_route_forwards_resolved_account_owner():
    path = Path(__file__).resolve().parents[1] / "backend-web/app/api/routes/items.py"
    source = ast.parse(path.read_text())
    handler = next(node for node in source.body if isinstance(node, ast.AsyncFunctionDef)
                   and node.name == "batch_offline_items")
    handler.decorator_list = []
    handler.args.defaults = [ast.Constant(None) for _ in handler.args.defaults]
    request = AsyncMock(return_value={"suc_count": 1, "fail_count": 0, "results": []})
    namespace = {
        "ApiResponse": lambda **kwargs: kwargs,
        "resolve_owner_scope": lambda user: (None, True),
        "batch_offline_items_from_xianyu": request,
        "logger": SimpleNamespace(info=lambda message: None),
    }
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                             handler], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)  # noqa: S102
    account = SimpleNamespace(account_id="account", cookie="session", owner_id=4)
    accounts = SimpleNamespace(get_account_for_user=AsyncMock(return_value=account))
    result = asyncio.run(namespace["batch_offline_items"](
        SimpleNamespace(cookie_id="account", item_ids=["100"]), SimpleNamespace(id=1), accounts,
    ))
    accounts.get_account_for_user.assert_awaited_once_with(None, "account")
    request.assert_awaited_once_with("account", "session", ["100"], owner_id=4)
    assert result["success"] is True
