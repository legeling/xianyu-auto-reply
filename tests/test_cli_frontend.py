from __future__ import annotations

from xianyu_cli.frontend import audit_frontend_endpoints, scan_frontend_api_functions, scan_frontend_endpoints


def test_scan_frontend_endpoints_resolves_prefixes_templates_and_fetch_methods(tmp_path) -> None:
    source = tmp_path / "api.ts"
    source.write_text(
        """
import { get, put } from '@/utils/request'

const PREFIX = '/api/v1/cookies'

export const options = () => get(`${PREFIX}/options`)
export const status = (accountId: string) =>
  put<{ success: boolean }>(`${PREFIX}/${accountId}/status`, { enabled: true })
export const exported = () =>
  fetch(`${PREFIX}/export`, { method: 'POST' })
export const refresh = async () => {
  const response = await axios.post('/api/v1/auth/refresh', {})
  return response
}
export async function profile(accountId: string): Promise<unknown> {
  return get(`${PREFIX}/${accountId}/profile`)
}
""",
        encoding="utf-8",
    )

    endpoints = {(item.method, item.path) for item in scan_frontend_endpoints(tmp_path)}
    functions = {
        (item.module, item.name, item.method, item.path)
        for item in scan_frontend_api_functions(tmp_path)
    }

    assert endpoints == {
        ("GET", "/api/v1/cookies/options"),
        ("PUT", "/api/v1/cookies/{accountId}/status"),
        ("POST", "/api/v1/cookies/export"),
        ("POST", "/api/v1/auth/refresh"),
        ("GET", "/api/v1/cookies/{accountId}/profile"),
    }
    assert functions == {
        ("api", "options", "GET", "/api/v1/cookies/options"),
        ("api", "status", "PUT", "/api/v1/cookies/{accountId}/status"),
        ("api", "exported", "POST", "/api/v1/cookies/export"),
        ("api", "refresh", "POST", "/api/v1/auth/refresh"),
        ("api", "profile", "GET", "/api/v1/cookies/{accountId}/profile"),
    }


def test_scan_frontend_endpoints_expands_batch_log_factory_paths(tmp_path) -> None:
    source = tmp_path / "polishLogs.ts"
    source.write_text(
        """
import { createBatchLogApi } from './batchLogFactory'

const api = createBatchLogApi({
  batches: 'polish-batches',
  clearLogs: 'polish-logs/clear',
})

export const getPolishBatches = api.getBatches
export const getPolishBatchDetail = api.getBatchDetail
export const clearPolishLogs = api.clearLogs
""",
        encoding="utf-8",
    )

    endpoints = {(item.method, item.path) for item in scan_frontend_endpoints(tmp_path)}
    functions = {
        (item.module, item.name, item.method, item.path)
        for item in scan_frontend_api_functions(tmp_path)
    }

    assert endpoints == {
        ("GET", "/api/v1/admin/polish-batches"),
        ("GET", "/api/v1/admin/polish-batches/{batch_id}"),
        ("DELETE", "/api/v1/admin/polish-logs/clear"),
    }
    assert functions == {
        ("polishLogs", "getPolishBatches", "GET", "/api/v1/admin/polish-batches"),
        ("polishLogs", "getPolishBatchDetail", "GET", "/api/v1/admin/polish-batches/{batch_id}"),
        ("polishLogs", "clearPolishLogs", "DELETE", "/api/v1/admin/polish-logs/clear"),
    }


def test_scan_frontend_api_functions_resolves_request_aliases_and_local_helpers(tmp_path) -> None:
    source = tmp_path / "blacklist.ts"
    source.write_text(
        """
import { get, post, del as httpDel } from '@/utils/request'

const PREFIX = '/api/v1/blacklist'

const listPersonal = () => get(`${PREFIX}/personal`)
const savePersonal = (items: unknown[]) => post(`${PREFIX}/personal/batch`, { items })

export const deletePersonalBlacklist = (id: number) => {
  return httpDel(`${PREFIX}/personal/${id}`)
}

export const replacePersonalBlacklist = async (items: unknown[]) => {
  await listPersonal()
  return savePersonal(items)
}
""",
        encoding="utf-8",
    )

    endpoints = {(item.method, item.path) for item in scan_frontend_endpoints(tmp_path)}
    functions = {
        (item.name, item.method, item.path)
        for item in scan_frontend_api_functions(tmp_path)
    }

    assert ("DELETE", "/api/v1/blacklist/personal/{id}") in endpoints
    assert functions == {
        ("deletePersonalBlacklist", "DELETE", "/api/v1/blacklist/personal/{id}"),
        ("replacePersonalBlacklist", "GET", "/api/v1/blacklist/personal"),
        ("replacePersonalBlacklist", "POST", "/api/v1/blacklist/personal/batch"),
    }


def test_audit_frontend_endpoints_matches_openapi_shape_and_reports_missing(tmp_path) -> None:
    source = tmp_path / "api.ts"
    source.write_text(
        """
import { get, put } from '@/utils/request'

const PREFIX = '/api/v1/cookies'

export const status = (id: string) => put(`${PREFIX}/${id}/status`, { enabled: true })
export const missing = () => get('/api/v1/cookies/not-in-openapi')
""",
        encoding="utf-8",
    )
    openapi = {
        "paths": {
            "/api/v1/cookies/{account_id}/status": {
                "put": {"operationId": "update_cookie_status", "tags": ["cookies"]}
            }
        }
    }

    rows = {(row["method"], row["path"]): row for row in audit_frontend_endpoints(openapi, tmp_path)}

    assert rows[("PUT", "/api/v1/cookies/{id}/status")]["status"] == "ok"
    assert rows[("PUT", "/api/v1/cookies/{id}/status")]["operation_id"] == "update_cookie_status"
    assert rows[("GET", "/api/v1/cookies/not-in-openapi")]["status"] == "missing_openapi"
