from __future__ import annotations

import ast
import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def service():
    path = Path(__file__).resolve().parents[1] / "scheduler/app/services/scheduler/polish_task.py"
    tree = ast.parse(path.read_text())
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in {"POLISH_API", "POLISH_API_VERSION"}
            for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "PolishTaskService":
            node.body = [method for method in node.body if isinstance(method, ast.AsyncFunctionDef)
                         and method.name in {"_polish_item", "_process_account"}]
            selected.append(node)
    namespace = {
        "json": json, "time": time,
        "asyncio": SimpleNamespace(sleep=AsyncMock()),
        "logger": SimpleNamespace(info=Mock(), warning=Mock(), error=Mock()),
        "trans_cookies": lambda cookie: {"_m_h5_tk": "fixture-token_timestamp"},
        "generate_sign": lambda *args: "fixture-sign",
    }
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                             *selected], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)  # noqa: S102
    instance = namespace["PolishTaskService"]()
    instance.task_name = "test"
    instance._handle_polish_response_cookies = lambda response, cookie: cookie
    return instance, namespace


@pytest.mark.parametrize("payload,completed,already", [
    ({"ret": ["SUCCESS::调用成功"], "data": {"itemDO": {"id": "100", "canPolish": False}}}, True, False),
    ({"ret": ["SUCCESS::调用成功"], "data": {"itemDO": {"id": "100", "canPolish": True}}}, False, False),
    ({"ret": ["SUCCESS::调用成功"], "data": {}}, False, False),
    ({"ret": ["SUCCESS::调用成功"], "data": {"itemDO": {"id": "200", "canPolish": False}}}, False, False),
    ({"ret": ["FAIL_BIZ_IDLEITEM_POLISH_AGAIN::宝贝已经擦亮过了，请刷新一下~"]}, True, True),
    ({"ret": ["POLISH_DUPLICATE::频率限制"]}, False, False),
])
def test_polish_version_and_platform_completion(service, payload, completed, already):
    instance, namespace = service
    response = SimpleNamespace(json=AsyncMock(return_value=payload))

    class Context:
        def __init__(self, value):
            self.value = value

        async def __aenter__(self):
            return self.value

        async def __aexit__(self, *args):
            return False

    post = Mock(return_value=Context(response))
    namespace["aiohttp"] = SimpleNamespace(
        ClientSession=lambda: Context(SimpleNamespace(post=post)),
        ClientTimeout=lambda **kwargs: kwargs,
        ClientError=type("FixtureClientError", (Exception,), {}),
    )
    result = asyncio.run(instance._polish_item("session", "100"))
    assert result["success"] is completed
    assert bool(result.get("already_polished")) is already
    assert result["cookie_str"] == "session"
    assert post.call_args.args == ("https://h5api.m.goofish.com/h5/mtop.taobao.idle.item.polish/1.0/",)
    assert post.call_args.kwargs["params"]["v"] == "1.0"
    assert json.loads(post.call_args.kwargs["data"]["data"]) == {"itemId": "100"}


@pytest.mark.parametrize("response,expected_counts,marked,log_message", [
    ({"success": False, "message": "POLISH_DUPLICATE::一天只能擦亮一次"}, (0, 1), False,
     "POLISH_DUPLICATE::一天只能擦亮一次"),
    ({"success": True, "already_polished": True, "message": "平台确认今日已擦亮（本次未重复擦亮）"},
     (1, 0), True, "平台确认今日已擦亮（本次未重复擦亮）"),
])
def test_process_preserves_confirmation_and_reason(service, response, expected_counts, marked, log_message):
    instance, _ = service
    item = SimpleNamespace(item_id="100", is_polished=False)
    account = SimpleNamespace(id=1, account_id="account", cookie="session")
    instance._get_unpolished_items = AsyncMock(return_value=[item])
    instance._polish_item = AsyncMock(return_value=response)
    instance._log_execution = AsyncMock()
    session = SimpleNamespace(add=Mock(), commit=AsyncMock())
    counts = asyncio.run(instance._process_account(session, account, "batch"))
    assert counts == expected_counts
    assert item.is_polished is marked
    assert instance._log_execution.await_args.kwargs["error_message"] == log_message
