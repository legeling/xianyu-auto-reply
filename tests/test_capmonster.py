from types import SimpleNamespace

import pytest
import requests

from common.services.captcha import capmonster
from common.services.captcha.provider_config import (
    CAPMONSTER_API_URL, REMOTE_PROVIDER_KEY, REMOTE_SECRET_KEY,
    REMOTE_URL_KEY, REMOTE_PASS_COOKIES_KEY, remote_config_from_settings,
)
from xianyu_cli.commands import captcha
from xianyu_cli.main import main

PUNISH_URL = "https://h5api.m.goofish.com:443/_____tmd_____/punish?x5secdata=challenge&x5step=2&action=captcha&pureCaptcha="
USER_AGENT = "Mozilla/5.0 CapMonster-supported-browser"


@pytest.fixture
def service(monkeypatch):
    calls, responses = [], []
    clock = [0.0]

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            calls.append((url, kwargs["json"]))
            body = responses.pop(0)
            if isinstance(body, Exception):
                raise body
            return SimpleNamespace(status_code=200, json=lambda: body)

        def get(self, url, **kwargs):
            assert url == capmonster.CAPMONSTER_USER_AGENT_URL
            return SimpleNamespace(status_code=200, text=USER_AGENT)

    monkeypatch.setattr(capmonster.requests, "Session", Session)
    monkeypatch.setattr(capmonster.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(capmonster.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    return calls, responses


def test_alibaba_task_polls_once_created_and_filters_cookie_domains(service):
    calls, responses = service
    responses.extend([
        {"errorId": 0, "taskId": 42},
        {"errorId": 0, "status": "processing"},
        {"errorId": 0, "status": "ready", "solution": {"domains": {
            "goofish.com": {"cookies": {"x5sec": "parent"}},
            "h5api.m.goofish.com": {"cookies": {"x5sec": "specific", "tfstk": "valid"}},
            "goofish.com.evil.test": {"cookies": {"x5sec": "wrong", "auth": "poison"}},
        }}},
    ])
    assert capmonster.solve("private-key", PUNISH_URL, 40) == ("ok", {"x5sec": "specific", "tfstk": "valid"}, None)
    task = calls[0][1]["task"]
    assert task == {"type": "CustomTask", "class": "alibaba", "websiteURL": "https://h5api.m.goofish.com:443",
                    "userAgent": USER_AGENT,
                    "metadata": {"punishUrl": PUNISH_URL, "cookieRequired": True}}
    assert [url.rsplit("/", 1)[1] for url, _ in calls] == ["createTask", "getTaskResult", "getTaskResult"]


def test_ready_tokens_without_x5sec_do_not_mean_success(service):
    _, responses = service
    responses.extend([{"errorId": 0, "taskId": 42}, {"errorId": 0, "status": "ready", "solution": {"data": {"tokens": "token"}}}])
    assert capmonster.solve("key", PUNISH_URL, 40)[0] == "fail"


def test_service_errors_do_not_leak_keys_or_recreate_paid_task(service):
    calls, responses = service
    responses.append({"errorId": 1, "errorCode": "ERROR_KEY_DOES_NOT_EXIST", "errorDescription": "private-key"})
    status, _, message = capmonster.solve("private-key", PUNISH_URL, 40)
    assert status == "fail" and "private-key" not in message
    assert len(calls) == 1


def test_network_failure_is_not_a_second_paid_task(service):
    calls, responses = service
    responses.append(requests.Timeout("private-key"))
    result = capmonster.solve("private-key", PUNISH_URL, 40)
    assert result[0] == "fail" and "private-key" not in result[2]
    assert len(calls) == 1


def test_polling_is_bounded_by_budget_and_supplier_limit(service):
    calls, responses = service
    responses.extend([{"errorId": 0, "taskId": 42}] + [{"errorId": 0, "status": "processing"}] * capmonster.MAX_RESULT_REQUESTS)
    assert capmonster.solve("key", PUNISH_URL, 40)[0] == "fail"
    assert 0 < len(calls) - 1 <= capmonster.MAX_RESULT_REQUESTS
    assert sum(url.endswith("/createTask") for url, _ in calls) == 1


def test_balance_check_does_not_create_paid_task(service):
    calls, responses = service
    responses.append({"errorId": 0, "balance": 0})
    assert capmonster.test_connection("key") == {"balance": 0, "currency": "USD"}
    assert calls == [(CAPMONSTER_API_URL + "/getBalance", {"clientKey": "key"})]


def test_solver_failure_records_method_and_task_id_without_credentials(service, caplog):
    calls, responses = service
    responses.extend([{"errorId": 0, "taskId": 42},
                      {"errorId": 1, "errorCode": "ERROR_CAPTCHA_UNSOLVABLE", "errorDescription": PUNISH_URL + " private-key"}])
    status, _, reason = capmonster.solve("private-key", PUNISH_URL, 40)
    assert status == "fail" and "getTaskResult" in reason and "taskId=42" in reason
    assert "ERROR_CAPTCHA_UNSOLVABLE" in caplog.text
    assert "private-key" not in caplog.text + reason and PUNISH_URL not in caplog.text + reason
    assert sum(url.endswith("/createTask") for url, _ in calls) == 1


def test_incomplete_link_does_not_create_paid_task(service):
    calls, _ = service
    assert capmonster.solve("key", PUNISH_URL.replace("&action=captcha", ""), 40)[0] == "fail"
    assert not calls


def test_https_port_added_without_reencoding_challenge(service):
    calls, responses = service
    responses.append({"errorId": 1, "errorCode": "ERROR_CAPTCHA_UNSOLVABLE"})
    url = PUNISH_URL.replace(":443", "").replace("challenge", "challenge%2Bvalue%3D")
    capmonster.solve("key", url, 40)
    assert calls[0][1]["task"]["metadata"]["punishUrl"] == url.replace("goofish.com/", "goofish.com:443/")


def test_user_agent_failure_does_not_submit_or_leak(service, monkeypatch):
    calls, _ = service
    def get(self, *args, **kwargs):
        raise requests.Timeout("private-key")
    monkeypatch.setattr(capmonster.requests.Session, "get", get)
    status, _, reason = capmonster.solve("private-key", PUNISH_URL, 40)
    assert status == "fail" and "userAgent" in reason and "private-key" not in reason
    assert not calls


def test_capmonster_fixed_endpoint_and_no_account_cookie():
    result = remote_config_from_settings({REMOTE_PROVIDER_KEY: "capmonster", REMOTE_SECRET_KEY: "key",
                                         REMOTE_URL_KEY: "https://wrong.test", REMOTE_PASS_COOKIES_KEY: "true"})
    assert result == {"provider": "capmonster", "url": CAPMONSTER_API_URL, "secret": "key", "pass_cookies": False}
    assert remote_config_from_settings({REMOTE_PROVIDER_KEY: "capmonster"}) is None
    with pytest.raises(ValueError):
        remote_config_from_settings({REMOTE_PROVIDER_KEY: "unknown"})


def test_cli_preserves_other_config_and_tests_masked_key(monkeypatch, tmp_path):
    calls = []
    config = {"provider": "capmonster", "url": CAPMONSTER_API_URL, "secret_key": "***", "pass_cookies": False,
              "block_remote_calls": True, "local_weight": 1, "remote_weight": 1,
              "remote_processing_max": 0, "remote_cooldown_seconds": 0}

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"success": True, "data": dict(config)}

    monkeypatch.setattr(captcha, "build_client", lambda args: SimpleNamespace(request=request))
    secret_file = tmp_path / "config.json"
    secret_file.write_text('{"secret_key":"new-key"}')
    assert main(["captcha", "set", "--data-file", str(secret_file)]) == 0
    assert calls[-1][2]["data"] == {**config, "secret_key": "new-key"}
    assert main(["captcha", "test"]) == 0
    assert calls[-1] == ("POST", "/api/v1/captcha/slider-solve/test", {"data": {
        "provider": "capmonster", "url": CAPMONSTER_API_URL, "secret_key": "***"}})
