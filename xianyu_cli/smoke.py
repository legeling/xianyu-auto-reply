"""Runtime smoke checks for OpenAPI operations."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from xianyu_cli.client import ApiClient
from xianyu_cli.exceptions import CliError
from xianyu_cli.openapi import Operation, operation_is_smoke_safe, operation_slug
from xianyu_cli.webmap import WebPage


@dataclass(frozen=True)
class SmokeCandidate:
    page: str
    operation_name: str
    operation: Operation


def web_smoke_candidates(
    pages: list[WebPage],
    grouped: dict[str, list[Operation]],
    *,
    search: str | None,
) -> list[SmokeCandidate]:
    candidates = []
    seen_operation_ids: set[str] = set()
    for page in pages:
        for feature in page.features:
            for operation in grouped.get(feature, []):
                if operation.operation_id in seen_operation_ids or not operation_is_smoke_safe(operation):
                    continue
                candidate = SmokeCandidate(page.key, f"{feature}.{operation_slug(operation)}", operation)
                if _matches_candidate(candidate, search):
                    candidates.append(candidate)
                    seen_operation_ids.add(operation.operation_id)
    return candidates


def run_smoke_candidates(
    client: ApiClient,
    candidates: list[SmokeCandidate],
    *,
    auth: bool,
    dry_run: bool,
    limit: int,
    fail_fast: bool,
) -> list[dict[str, object]]:
    rows = []
    for candidate in candidates[:limit]:
        if dry_run:
            rows.append(_candidate_row(candidate, status="planned", detail="dry-run"))
            continue

        try:
            response = client.request(candidate.operation.method, candidate.operation.path, auth=auth)
            status, detail = _response_status(response)
        except CliError as exc:
            status, detail = "failed", str(exc)
        rows.append(_candidate_row(candidate, status=status, detail=detail))
        if fail_fast and status == "failed":
            break
    return rows


def _candidate_row(candidate: SmokeCandidate, *, status: str, detail: str) -> dict[str, object]:
    return {
        "status": status,
        "page": candidate.page,
        "operation": candidate.operation_name,
        "method": candidate.operation.method,
        "path": candidate.operation.path,
        "operation_id": candidate.operation.operation_id,
        "detail": detail,
    }


def _response_status(response: Any) -> tuple[str, str]:
    if isinstance(response, dict) and response.get("success") is False:
        return "failed", _compact_json(response)
    return "ok", _summarize_response(response)


def _summarize_response(response: Any) -> str:
    if response is None:
        return "empty"
    if isinstance(response, dict):
        if "success" in response:
            return f"success={response.get('success')}"
        return "keys=" + ",".join(str(key) for key in list(response)[:6])
    if isinstance(response, list):
        return f"items={len(response)}"
    return str(response)[:120]


def _compact_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))[:240]


def _matches_candidate(candidate: SmokeCandidate, search: str | None) -> bool:
    if not search:
        return True
    haystack = " ".join(
        [
            candidate.page,
            candidate.operation_name,
            candidate.operation.path,
            candidate.operation.operation_id,
            candidate.operation.summary,
            *candidate.operation.tags,
        ]
    ).lower()
    return search.lower() in haystack
