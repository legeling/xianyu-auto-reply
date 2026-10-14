"""远程验证码配置的唯一键名与供应商标识。"""
from typing import Literal

RemoteProvider = Literal["remote", "capmonster"]
REMOTE_PROVIDER_KEY = "captcha.remote_provider"
REMOTE_URL_KEY = "captcha.remote_service_url"
REMOTE_SECRET_KEY = "captcha.remote_secret_key"
REMOTE_PASS_COOKIES_KEY = "captcha.remote_pass_cookies"
DEFAULT_REMOTE_PROVIDER: RemoteProvider = "remote"
CAPMONSTER_API_URL = "https://api.capmonster.cloud"
CAPMONSTER_USER_AGENT_URL = "https://capmonster.cloud/api/useragent/actual"


def remote_config_from_settings(values: dict[str, str]) -> dict | None:
    provider = values.get(REMOTE_PROVIDER_KEY, DEFAULT_REMOTE_PROVIDER)
    if provider not in ("remote", "capmonster"):
        raise ValueError("未知远程验证码服务")
    url = CAPMONSTER_API_URL if provider == "capmonster" else values.get(REMOTE_URL_KEY, "").strip()
    secret = values.get(REMOTE_SECRET_KEY, "").strip()
    if not url or not secret:
        return None
    return {
        "provider": provider,
        "url": url,
        "secret": secret,
        "pass_cookies": provider == "remote" and values.get(REMOTE_PASS_COOKIES_KEY, "").strip().lower() == "true",
    }
