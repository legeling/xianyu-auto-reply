from __future__ import annotations

import json

from xianyu_cli.commands.web import (
    _coverage_rows,
    _frontend_function_rows,
    _page_example_rows,
    _resolve_page_operation,
    _smoke_failure_count,
    _unmapped_feature_rows,
    _verification_failure_count,
    _verification_rows,
)
from xianyu_cli.main import main
from xianyu_cli.openapi import Operation, operation_command_template, operation_inputs, operation_is_smoke_safe
from xianyu_cli.smoke import run_smoke_candidates, web_smoke_candidates
from xianyu_cli.websocket_client import build_chat_new_ws_url
from xianyu_cli.webmap import find_page


def make_operation(method: str, path: str, operation_id: str = "operation") -> Operation:
    return Operation(
        method=method,
        path=path,
        operation_id=operation_id,
        summary="",
        tags=["test"],
        raw={},
    )


def test_find_page_accepts_key_path_and_label() -> None:
    assert find_page("accounts").key == "accounts"
    assert find_page("/accounts").key == "accounts"
    assert find_page("账号管理").key == "accounts"


def test_coverage_reports_missing_and_static_pages() -> None:
    grouped = {"cookies": [make_operation("GET", "/api/v1/cookies/details/paginated")]}
    rows = {str(row["page"]): row for row in _coverage_rows(grouped, search=None, only="all")}

    assert rows["accounts"]["status"] == "missing"
    assert "qr-login" in str(rows["accounts"]["missing_features"])
    assert rows["tutorial"]["status"] == "static"


def test_unmapped_feature_rows_excludes_mapped_features() -> None:
    grouped = {
        "cookies": [make_operation("GET", "/api/v1/cookies")],
        "internal-only": [make_operation("GET", "/api/v1/internal-only")],
    }

    rows = _unmapped_feature_rows(grouped, search=None)

    assert rows == [{"feature": "internal-only", "operations": 1, "tags": "test"}]


def test_verification_rows_reports_page_coverage_failure_without_frontend_scan() -> None:
    page = find_page("accounts")

    assert page is not None
    rows = _verification_rows(
        {"paths": {}},
        {"cookies": [make_operation("GET", "/api/v1/cookies")]},
        raw_page="accounts",
        frontend_root="frontend/src",
        skip_frontend=True,
    )

    assert rows[0]["check"] == "page_coverage"
    assert rows[0]["status"] == "failed"
    assert rows[1]["status"] == "skipped"
    assert rows[2]["status"] == "skipped"
    assert _verification_failure_count(rows) == 1


def test_resolve_page_operation_accepts_slug_and_operation_id() -> None:
    operation = make_operation(
        "GET",
        "/api/v1/cookies/details/paginated",
        "list_cookie_details_paginated_api_v1_cookies_details_paginated_get",
    )
    grouped = {"cookies": [operation]}
    page = find_page("accounts")

    assert page is not None
    assert _resolve_page_operation(grouped, page, "get-details-paginated") == operation
    assert _resolve_page_operation(grouped, page, operation.operation_id) == operation


def test_operation_inputs_summarizes_parameters_and_body() -> None:
    operation = Operation(
        method="POST",
        path="/api/v1/cookies/{account_id}/import",
        operation_id="import",
        summary="",
        tags=[],
        raw={
            "parameters": [
                {"name": "account_id", "in": "path", "required": True},
                {"name": "page", "in": "query", "required": False},
            ],
            "requestBody": {
                "required": True,
                "content": {"multipart/form-data": {}},
            },
        },
    )

    assert operation_inputs(operation) == "path:account_id* query:page body:multipart*"


def test_operation_command_template_builds_path_query_and_json_body() -> None:
    openapi = {
        "components": {
            "schemas": {
                "StatusUpdate": {
                    "type": "object",
                    "required": ["enabled"],
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "remark": {"type": "string"},
                    },
                }
            }
        }
    }
    operation = Operation(
        method="PUT",
        path="/api/v1/cookies/{account_id}/status",
        operation_id="update_status",
        summary="",
        tags=[],
        raw={
            "parameters": [
                {"name": "account_id", "in": "path", "required": True},
                {"name": "sync", "in": "query", "required": True},
                {"name": "trace_id", "in": "query", "required": False},
            ],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/StatusUpdate"}}},
            },
        },
    )

    command = operation_command_template(openapi, operation, ["xianyu-cli", "routes", "call", "update_status"])

    assert command == (
        "xianyu-cli routes call update_status -p 'account_id=<account_id>' "
        "-q 'sync=<sync>' -d '{\"enabled\":false}'"
    )


def test_operation_command_template_can_include_optional_multipart_fields() -> None:
    operation = Operation(
        method="POST",
        path="/api/v1/cookies/import",
        operation_id="import_cookies",
        summary="",
        tags=[],
        raw={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {
                                "file": {"type": "string", "contentMediaType": "application/octet-stream"},
                                "enable_all": {"type": "boolean"},
                            },
                        }
                    }
                },
            },
        },
    )

    command = operation_command_template(
        {},
        operation,
        ["xianyu-cli", "routes", "call", "import_cookies"],
        include_optional=True,
    )

    assert command == "xianyu-cli routes call import_cookies -F file=./file -f 'enable_all=<enable_all>'"


def test_page_example_rows_builds_web_call_commands() -> None:
    operation = make_operation(
        "GET",
        "/api/v1/cookies/details/paginated",
        "list_cookie_details_paginated_api_v1_cookies_details_paginated_get",
    )
    page = find_page("accounts")

    assert page is not None
    rows = _page_example_rows({}, page, {"cookies": [operation]}, search=None, include_optional=False)

    assert rows == [
        {
            "operation": "cookies.get-details-paginated",
            "method": "GET",
            "path": "/api/v1/cookies/details/paginated",
            "summary": "",
            "inputs": "",
            "operation_id": "list_cookie_details_paginated_api_v1_cookies_details_paginated_get",
            "command": "xianyu-cli web call accounts cookies.get-details-paginated",
        }
    ]


def test_frontend_function_rows_build_web_call_commands(tmp_path) -> None:
    source = tmp_path / "accounts.ts"
    source.write_text(
        """
import { get } from '@/utils/request'

export const getAccountDetails = async () => get('/api/v1/cookies/options')
""",
        encoding="utf-8",
    )
    openapi = {
        "paths": {
            "/api/v1/cookies/options": {
                "get": {
                    "operationId": "list_cookie_options",
                    "summary": "Cookie Options",
                    "tags": ["cookies"],
                }
            }
        }
    }

    rows = _frontend_function_rows(openapi, str(tmp_path), search=None, only="all", include_optional=False)

    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["function"] == "accounts.getAccountDetails"
    assert rows[0]["method"] == "GET"
    assert rows[0]["path"] == "/api/v1/cookies/options"
    assert rows[0]["page"] == "accounts"
    assert str(rows[0]["pages"]).startswith("accounts,")
    assert rows[0]["operation"] == "cookies.get-options"
    assert rows[0]["operation_id"] == "list_cookie_options"
    assert str(rows[0]["source"]).startswith(f"{source}:")
    assert rows[0]["command"] == "xianyu-cli web call accounts cookies.get-options"


def test_web_function_call_invokes_operation_from_frontend_function(tmp_path, capsys, monkeypatch) -> None:
    source = tmp_path / "accounts.ts"
    source.write_text(
        "import { get } from '@/utils/request'\nexport const getAccountDetails = () => get('/api/v1/cookies/options')\n",
        encoding="utf-8",
    )
    openapi_file = tmp_path / "openapi.json"
    openapi_file.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "paths": {
                    "/api/v1/cookies/options": {
                        "get": {"operationId": "list_cookie_options", "tags": ["cookies"]}
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeClient:
        def request(
            self,
            method,
            path,
            *,
            params=None,
            data=None,
            form=None,
            files=None,
            output_path=None,
            auth=True,
        ):
            return {"method": method, "path": path, "auth": auth}

    monkeypatch.setattr("xianyu_cli.commands.web.build_client", lambda args, require_token: FakeClient())

    code = main(
        [
            "--openapi-file",
            str(openapi_file),
            "--json",
            "web",
            "function-call",
            "accounts.getAccountDetails",
            "--frontend-root",
            str(tmp_path),
            "--no-auth",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert json.loads(captured.out) == {"method": "GET", "path": "/api/v1/cookies/options", "auth": False}


def test_web_function_call_reports_composite_frontend_function(tmp_path, capsys, monkeypatch) -> None:
    source = tmp_path / "keywords.ts"
    source.write_text(
        """
import { get, post } from '@/utils/request'

const PREFIX = '/api/v1/keywords-with-item-id'
const listKeywords = () => get(`${PREFIX}/account`)
const saveKeywords = () => post(`${PREFIX}/account`, {})

export const addKeyword = async () => {
  await listKeywords()
  return saveKeywords()
}
""",
        encoding="utf-8",
    )
    openapi_file = tmp_path / "openapi.json"
    openapi_file.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "paths": {
                    "/api/v1/keywords-with-item-id/account": {
                        "get": {"operationId": "list_keywords", "tags": ["keywords-with-item-id"]},
                        "post": {"operationId": "save_keywords", "tags": ["keywords-with-item-id"]},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeClient:
        def request(self, *args, **kwargs):
            return {"success": True}

    monkeypatch.setattr("xianyu_cli.commands.web.build_client", lambda args, require_token: FakeClient())

    code = main(
        [
            "--openapi-file",
            str(openapi_file),
            "web",
            "function-call",
            "keywords.addKeyword",
            "--frontend-root",
            str(tmp_path),
            "--no-auth",
        ]
    )
    captured = capsys.readouterr()

    assert code == 1
    assert "对应多个后端接口" in captured.err


def test_web_function_command_shows_exact_frontend_function(tmp_path, capsys) -> None:
    source = tmp_path / "keywords.ts"
    source.write_text(
        """
import { get, post } from '@/utils/request'

const PREFIX = '/api/v1/keywords-with-item-id'
const getKeywords = () => get(`${PREFIX}/account`)
const saveKeywords = () => post(`${PREFIX}/account`, {})

export const addKeyword = async () => {
  await getKeywords()
  return saveKeywords()
}

export const batchAddKeywords = async () => {
  return saveKeywords()
}
""",
        encoding="utf-8",
    )
    openapi_file = tmp_path / "openapi.json"
    openapi_file.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "paths": {
                    "/api/v1/keywords-with-item-id/account": {
                        "get": {"operationId": "list_keywords", "tags": ["keywords-with-item-id"]},
                        "post": {"operationId": "save_keywords", "tags": ["keywords-with-item-id"]},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--openapi-file",
            str(openapi_file),
            "--json",
            "web",
            "function",
            "addKeyword",
            "--frontend-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    rows = json.loads(captured.out)

    assert code == 0
    assert len(rows) == 2
    assert {row["function"] for row in rows} == {"keywords.addKeyword"}
    assert {row["method"] for row in rows} == {"GET", "POST"}


def test_operation_is_smoke_safe_only_allows_parameterless_gets() -> None:
    assert operation_is_smoke_safe(make_operation("GET", "/api/v1/cookies/options"))
    assert not operation_is_smoke_safe(make_operation("GET", "/api/v1/cookies/{account_id}"))
    assert not operation_is_smoke_safe(make_operation("POST", "/api/v1/cookies"))
    assert not operation_is_smoke_safe(
        Operation(
            method="GET",
            path="/api/v1/cookies/details/paginated",
            operation_id="paginated",
            summary="",
            tags=[],
            raw={"parameters": [{"name": "page", "in": "query", "required": True}]},
        )
    )


def test_web_smoke_candidates_dedupes_and_filters_by_page_feature() -> None:
    page = find_page("accounts")
    safe = make_operation("GET", "/api/v1/cookies/options", "cookie_options")
    unsafe = make_operation("GET", "/api/v1/cookies/{account_id}", "cookie_detail")

    assert page is not None
    candidates = web_smoke_candidates([page], {"cookies": [safe, unsafe]}, search=None)

    assert len(candidates) == 1
    assert candidates[0].page == "accounts"
    assert candidates[0].operation_name == "cookies.get-options"
    assert candidates[0].operation == safe


def test_run_smoke_candidates_supports_dry_run_and_fail_fast() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.paths: list[str] = []

        def request(self, method, path, *, auth=True):
            self.paths.append(path)
            if path.endswith("/bad"):
                return {"success": False, "message": "boom"}
            return {"success": True}

    page = find_page("accounts")
    good = make_operation("GET", "/api/v1/cookies/options", "good")
    bad = make_operation("GET", "/api/v1/cookies/bad", "bad")

    assert page is not None
    candidates = web_smoke_candidates([page], {"cookies": [bad, good]}, search=None)
    dry_run_rows = run_smoke_candidates(FakeClient(), candidates, auth=True, dry_run=True, limit=10, fail_fast=False)
    run_rows = run_smoke_candidates(FakeClient(), candidates, auth=True, dry_run=False, limit=10, fail_fast=True)

    assert [row["status"] for row in dry_run_rows] == ["planned", "planned"]
    assert [row["status"] for row in run_rows] == ["failed"]
    assert _smoke_failure_count(run_rows) == 1


def test_web_smoke_command_dry_run_uses_local_openapi(tmp_path, capsys) -> None:
    openapi_file = tmp_path / "openapi.json"
    openapi_file.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "paths": {
                    "/api/v1/cookies/options": {
                        "get": {
                            "operationId": "list_cookie_options",
                            "summary": "Cookie Options",
                            "tags": ["cookies"],
                            "responses": {"200": {"content": {"application/json": {}}}},
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(["--openapi-file", str(openapi_file), "--json", "web", "smoke", "accounts", "--dry-run"])
    captured = capsys.readouterr()

    assert code == 0
    rows = json.loads(captured.out)
    assert rows[0]["status"] == "planned"
    assert rows[0]["operation"] == "cookies.get-options"


def test_chat_new_ws_url_uses_api_base_url_scheme_and_account_id() -> None:
    assert (
        build_chat_new_ws_url("http://127.0.0.1:8089", "acct/1")
        == "ws://127.0.0.1:8089/api/v1/chat-new/ws/acct%2F1"
    )
    assert (
        build_chat_new_ws_url("https://example.com/backend", "account-1")
        == "wss://example.com/backend/api/v1/chat-new/ws/account-1"
    )


def test_web_ws_command_uses_configured_base_url_without_openapi(capsys, monkeypatch) -> None:
    calls = {}

    class FakeClient:
        base_url = "http://backend.test:8089"

    def fail_load_openapi(*args, **kwargs):
        raise AssertionError("web ws should not load OpenAPI")

    def fake_run_chat_new_ws(base_url, account_id, **kwargs):
        calls.update({"base_url": base_url, "account_id": account_id, **kwargs})

    monkeypatch.setattr("xianyu_cli.commands.web.build_client", lambda args, require_token: FakeClient())
    monkeypatch.setattr("xianyu_cli.commands.web.load_openapi", fail_load_openapi)
    monkeypatch.setattr("xianyu_cli.commands.web.run_chat_new_ws", fake_run_chat_new_ws)

    code = main(["--json", "web", "ws", "account-1", "--limit", "2", "--timeout", "1.5", "--ping-interval", "0", "--raw"])
    captured = capsys.readouterr()

    assert code == 0
    assert captured.err == ""
    assert calls == {
        "base_url": "http://backend.test:8089",
        "account_id": "account-1",
        "limit": 2,
        "timeout": 1.5,
        "ping_interval": 0.0,
        "raw": True,
        "json_output": True,
    }


def test_web_smoke_command_fails_by_default_and_can_allow_failures(tmp_path, capsys, monkeypatch) -> None:
    class FakeClient:
        def request(self, method, path, *, auth=True):
            return {"success": False, "message": "boom"}

    openapi_file = tmp_path / "openapi.json"
    openapi_file.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "paths": {
                    "/api/v1/cookies/options": {
                        "get": {
                            "operationId": "list_cookie_options",
                            "tags": ["cookies"],
                            "responses": {"200": {"content": {"application/json": {}}}},
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("xianyu_cli.commands.web.build_client", lambda args, require_token: FakeClient())

    failed_code = main(["--openapi-file", str(openapi_file), "--json", "web", "smoke", "accounts", "--no-auth"])
    failed_output = capsys.readouterr()
    allowed_code = main(
        [
            "--openapi-file",
            str(openapi_file),
            "--json",
            "web",
            "smoke",
            "accounts",
            "--no-auth",
            "--allow-failures",
        ]
    )
    allowed_output = capsys.readouterr()

    assert failed_code == 1
    assert "smoke 检查失败" in failed_output.err
    assert json.loads(failed_output.out)[0]["status"] == "failed"
    assert allowed_code == 0
    assert json.loads(allowed_output.out)[0]["status"] == "failed"


def test_web_verify_command_fails_by_default_and_can_allow_failures(tmp_path, capsys) -> None:
    openapi_file = tmp_path / "openapi.json"
    openapi_file.write_text('{"openapi":"3.1.0","paths":{}}', encoding="utf-8")

    failed_code = main(
        [
            "--openapi-file",
            str(openapi_file),
            "--json",
            "web",
            "verify",
            "accounts",
            "--skip-frontend",
        ]
    )
    failed_output = capsys.readouterr()
    allowed_code = main(
        [
            "--openapi-file",
            str(openapi_file),
            "--json",
            "web",
            "verify",
            "accounts",
            "--skip-frontend",
            "--allow-failures",
        ]
    )
    allowed_output = capsys.readouterr()

    assert failed_code == 1
    assert "verify 检查失败" in failed_output.err
    assert json.loads(failed_output.out)[0]["status"] == "failed"
    assert allowed_code == 0
    assert json.loads(allowed_output.out)[0]["status"] == "failed"
