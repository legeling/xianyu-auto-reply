from __future__ import annotations

from types import SimpleNamespace

import pytest

from xianyu_cli.commands import auth, publish
from xianyu_cli.main import build_parser, main
from xianyu_cli.request_args import parse_payload_args


def test_json_file_payload_preserves_backend_fields(tmp_path):
    path = tmp_path / "material.json"
    path.write_text('{"title":"商品", "platform_attributes":[{"property_id":"a"}]}', encoding="utf-8")

    payload = parse_payload_args(SimpleNamespace(data_file=str(path)))

    assert payload.data == {"title": "商品", "platform_attributes": [{"property_id": "a"}]}


@pytest.mark.parametrize("content", ["", "{broken json"])
def test_invalid_json_file_does_not_submit_publication(monkeypatch, tmp_path, content):
    path = tmp_path / "invalid.json"
    path.write_text(content, encoding="utf-8")
    calls = []
    client = SimpleNamespace(request=lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(publish, "build_client", lambda args: client)

    assert main(["publish", "single", "--data-file", str(path)]) == 1
    assert calls == []


def test_inline_json_and_json_file_are_mutually_exclusive():
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args([
            "api", "POST", "/api/v1/product-publish/materials", "-d", "{}", "--data-file", "material.json",
        ])

    assert error.value.code == 2


@pytest.mark.parametrize("arguments,method,path,body", [
    (["publish", "batch", "--account-id", "one", "--account-id", "two", "--material-id", "7"],
     "POST", "/api/v1/product-publish/publish/batch", {"account_ids": ["one", "two"], "material_ids": [7]}),
    (["publish", "status", "batch-1"], "GET", "/api/v1/product-publish/publish/batch/batch-1/status", None),
    (["publish", "check-account", "account/name"],
     "GET", "/api/v1/product-publish/accounts/account%2Fname/capability", None),
])
def test_publish_shortcuts_use_canonical_api(monkeypatch, arguments, method, path, body):
    calls = []

    def request(actual_method, actual_path, **kwargs):
        calls.append((actual_method, actual_path, kwargs.get("data")))
        return {"success": True, "data": {"batch_id": "batch-1"}}

    monkeypatch.setattr(publish, "build_client", lambda args: SimpleNamespace(request=request))

    assert main(arguments) == 0
    assert calls == [(method, path, body)]


@pytest.mark.parametrize("action,path", [
    (["publish", "single"], "/api/v1/product-publish/publish/single"),
    (["publish", "materials", "create"], "/api/v1/product-publish/materials"),
])
def test_publish_json_file_reaches_backend_unchanged(monkeypatch, tmp_path, action, path):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text('{"title":"商品", "images":["/static/a.png"]}', encoding="utf-8")
    calls = []

    def request(method, actual_path, **kwargs):
        calls.append((method, actual_path, kwargs["data"]))
        return {"success": True}

    monkeypatch.setattr(publish, "build_client", lambda args: SimpleNamespace(request=request))

    assert main([*action, "--data-file", str(payload_path)]) == 0
    assert calls == [("POST", path, {"title": "商品", "images": ["/static/a.png"]})]


def test_rejected_batch_returns_nonzero_without_resubmitting(monkeypatch, capsys):
    calls = []

    def request(*args, **kwargs):
        calls.append(args)
        return {"success": False, "message": "没有找到有效的素材"}

    monkeypatch.setattr(publish, "build_client", lambda args: SimpleNamespace(request=request))

    assert main(["publish", "batch", "--account-id", "one", "--material-id", "7"]) == 1
    assert len(calls) == 1
    assert "没有找到有效的素材" in capsys.readouterr().err


def test_refresh_replaces_saved_session_without_printing_tokens(monkeypatch, capsys):
    config = {"base_url": "https://service.example", "token": "expired-access", "refresh_token": "valid-refresh"}
    calls = []
    saved = []

    class Client:
        def __init__(self, base_url, token):
            calls.append((base_url, token))

        def request(self, method, path):
            calls.append((method, path))
            return {"success": True, "token": "fresh-access", "refresh_token": "fresh-refresh", "user_id": 2}

    monkeypatch.setattr(auth, "load_config", lambda: config.copy())
    monkeypatch.setattr(auth, "save_config", saved.append)
    monkeypatch.setattr(auth, "ApiClient", Client)

    assert main(["auth", "refresh"]) == 0
    assert calls == [("https://service.example", "valid-refresh"), ("POST", "/api/v1/auth/refresh")]
    assert saved[0]["token"] == "fresh-access"
    assert saved[0]["refresh_token"] == "fresh-refresh"
    assert "fresh-access" not in capsys.readouterr().out


def test_failed_refresh_preserves_saved_session(monkeypatch):
    config = {"refresh_token": "expired-refresh"}
    saved = []
    client = SimpleNamespace(request=lambda *args, **kwargs: {"success": False, "message": "刷新令牌无效"})
    monkeypatch.setattr(auth, "load_config", lambda: config.copy())
    monkeypatch.setattr(auth, "save_config", saved.append)
    monkeypatch.setattr(auth, "ApiClient", lambda *args: client)

    assert main(["auth", "refresh"]) == 1
    assert saved == []


def test_invalid_whoami_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(auth, "load_config", lambda: {})
    client = SimpleNamespace(request=lambda *args: {"authenticated": False})
    monkeypatch.setattr(auth, "build_client", lambda args: client)

    assert main(["auth", "whoami"]) == 1
