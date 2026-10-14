import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.routes import captcha
from common.services.captcha.provider_config import CAPMONSTER_API_URL, REMOTE_PROVIDER_KEY, REMOTE_SECRET_KEY, REMOTE_PASS_COOKIES_KEY, REMOTE_URL_KEY


def database_results(*values):
    return SimpleNamespace(execute=AsyncMock(side_effect=[SimpleNamespace(scalar_one_or_none=lambda v=value: v) for value in values]))


def test_saved_masked_key_is_resolved_only_for_same_provider():
    db = database_results("capmonster", "saved-private-key")
    with patch.object(captcha, "test_connection", return_value={"balance": 1, "currency": "USD"}) as connection:
        result = asyncio.run(captcha.test_remote_slider_solve(
            captcha.TestRemoteSolveRequest(provider="capmonster", secret_key="***"), current_user=None, db=db,
        ))
    assert result.success and result.data["balance"] == 1
    connection.assert_called_once_with("saved-private-key")
    assert "saved-private-key" not in str(result.model_dump())

    with patch.object(captcha, "test_connection") as connection:
        result = asyncio.run(captcha.test_remote_slider_solve(
            captcha.TestRemoteSolveRequest(provider="capmonster", secret_key="***"), current_user=None,
            db=database_results("remote"),
        ))
    assert not result.success
    connection.assert_not_called()


def test_save_uses_fixed_endpoint_preserves_masked_key_and_disables_cookie_upload():
    with patch.object(captcha.SystemSettingService, "set_settings", new_callable=AsyncMock) as save:
        result = asyncio.run(captcha.update_remote_config(
            captcha.RemoteConfigUpdate(provider="capmonster", url="https://wrong.test", secret_key="***", pass_cookies=True),
            current_user=None, db=database_results("capmonster"),
        ))
    assert result.success
    saved = save.await_args.args[0]
    assert saved[REMOTE_PROVIDER_KEY][0] == "capmonster"
    assert saved[REMOTE_URL_KEY][0] == CAPMONSTER_API_URL
    assert saved[REMOTE_PASS_COOKIES_KEY][0] == "false"
    assert REMOTE_SECRET_KEY not in saved
