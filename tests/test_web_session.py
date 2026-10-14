import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common.core.config import BaseConfig
from common.utils import security


def test_backend_inherits_thirty_day_refresh_default():
    source = Path(__file__).resolve().parents[1] / "backend-web/app/core/config.py"
    spec = importlib.util.spec_from_file_location("web_session_config", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expiry = module.BackendWebConfig.model_fields["refresh_token_expire_minutes"].default
    assert expiry == BaseConfig.model_fields["refresh_token_expire_minutes"].default
    assert timedelta(minutes=expiry) == timedelta(days=30)


def test_each_renewal_gets_full_refresh_window(monkeypatch):
    settings = BaseConfig(_env_file=None, jwt_secret_key="test-session-signing-key-never-used-in-production")
    instant = [datetime.now(timezone.utc)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant[0]

    monkeypatch.setattr(security, "datetime", Clock)
    first = security.decode_token(security.create_refresh_token("4", settings=settings), settings=settings)
    elapsed = timedelta(hours=1)
    instant[0] += elapsed
    second = security.decode_token(security.create_refresh_token("4", settings=settings), settings=settings)
    assert first["type"] == second["type"] == "refresh"
    assert second["exp"] - first["exp"] == elapsed.total_seconds()
    assert abs(second["exp"] - instant[0].timestamp() - timedelta(minutes=settings.refresh_token_expire_minutes).total_seconds()) < 1
