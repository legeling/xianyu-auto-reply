from __future__ import annotations

import pytest
from fastapi import HTTPException

from common.utils.internal_auth import (
    INTERNAL_AUTH_HEADER,
    MIN_INTERNAL_TOKEN_LENGTH,
    build_internal_auth_headers,
    is_internal_api_url,
    merge_internal_auth_headers,
    require_valid_internal_token,
)


def test_existing_deployment_token_remains_valid() -> None:
    # The deployment scripts already generated tokens of this length before this merge.
    deployment_token = "existing-random-token-123"
    assert len(deployment_token) >= MIN_INTERNAL_TOKEN_LENGTH
    headers = build_internal_auth_headers(deployment_token)
    require_valid_internal_token(headers[INTERNAL_AUTH_HEADER], deployment_token)


@pytest.mark.parametrize("provided", [None, "", "different-random-token-123"])
def test_invalid_token_is_rejected(provided: str | None) -> None:
    configured_token = "configured-token-123456789"
    with pytest.raises(HTTPException) as error:
        require_valid_internal_token(provided, configured_token)
    assert error.value.status_code == 401


def test_missing_server_token_fails_closed() -> None:
    with pytest.raises(HTTPException) as error:
        require_valid_internal_token("request-token-123456789012", None)
    assert error.value.status_code == 503
    with pytest.raises(RuntimeError):
        build_internal_auth_headers(None)


def test_internal_header_replaces_case_variants_without_losing_other_headers() -> None:
    token = "configured-token-123456789"
    original = {"x-internal-token": "obsolete", "Accept": "application/json"}
    assert merge_internal_auth_headers(original, token) == {
        "Accept": "application/json",
        INTERNAL_AUTH_HEADER: token,
    }
    assert original["x-internal-token"] == "obsolete"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://websocket:8090/internal/accounts/demo/start", True),
        ("http://websocket:8090/internality", False),
        ("http://external.example/internal/accounts/demo/start", False),
        ("http://websocket:8090@external.example/internal/accounts/demo/start", False),
        ("http://websocket:8090/password-login/start", False),
    ],
)
def test_credentials_only_attach_to_configured_internal_origin(url: str, expected: bool) -> None:
    assert is_internal_api_url(url, ("http://websocket:8090",)) is expected
