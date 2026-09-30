from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common.models.system_setting import SystemSetting
from common.utils.internal_auth import MIN_INTERNAL_TOKEN_LENGTH


@pytest_asyncio.fixture
async def token_store(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'settings.sqlite'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(SystemSetting.__table__.create)
    # Import without creating production engines or accessing the owner's configured database.
    session_module = ModuleType("common.db.session")
    session_module.async_session_maker = sessions
    monkeypatch.setitem(sys.modules, "common.db.session", session_module)
    module = importlib.import_module("common.utils.internal_token_service")
    common_settings = SimpleNamespace(internal_api_token="")
    monkeypatch.setattr(module, "async_session_maker", sessions)
    monkeypatch.setattr(module, "get_common_settings", lambda: common_settings)
    try:
        yield module, sessions, common_settings
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_preserves_existing_settings_and_deployment_token(token_store) -> None:
    module, sessions, common_settings = token_store
    old_settings = {"login.system_name": "我的闲鱼系统", "smtp_password": "test-only-password"}
    async with sessions() as session:
        session.add_all([SystemSetting(key=key, value=value) for key, value in old_settings.items()])
        await session.commit()

    deployment_token = "existing-random-token-123"
    settings = SimpleNamespace(internal_api_token=deployment_token)
    assert await module.ensure_internal_api_token(settings) == deployment_token
    assert await module.ensure_internal_api_token(settings) == deployment_token
    worker_settings = SimpleNamespace(internal_api_token="other-configured-token-123")
    assert await module.load_internal_api_token(worker_settings) == deployment_token
    assert worker_settings.internal_api_token == common_settings.internal_api_token == deployment_token

    async with sessions() as session:
        records = (await session.execute(select(SystemSetting))).scalars().all()
        actual = {record.key: record.value for record in records}
    assert actual == {**old_settings, module.INTERNAL_TOKEN_SETTING_KEY: deployment_token}
    assert len(records) == len(old_settings) + 1


@pytest.mark.asyncio
async def test_missing_worker_token_does_not_write_database(token_store) -> None:
    module, sessions, _ = token_store
    with pytest.raises(RuntimeError, match="请先启动 backend"):
        await module.load_internal_api_token(SimpleNamespace(internal_api_token=""))
    async with sessions() as session:
        assert (await session.execute(select(SystemSetting))).scalars().all() == []


@pytest.mark.asyncio
async def test_new_token_is_persisted_once_and_loaded_by_workers(token_store) -> None:
    module, sessions, _ = token_store
    initialized = await module.ensure_internal_api_token(SimpleNamespace(internal_api_token=""))
    assert len(initialized) >= MIN_INTERNAL_TOKEN_LENGTH
    assert await module.ensure_internal_api_token(SimpleNamespace(internal_api_token="")) == initialized
    assert await module.load_internal_api_token(SimpleNamespace(internal_api_token="")) == initialized
    async with sessions() as session:
        records = (await session.execute(select(SystemSetting))).scalars().all()
    assert len(records) == 1


@pytest.mark.asyncio
async def test_invalid_config_does_not_partially_initialize_database(token_store) -> None:
    module, sessions, _ = token_store
    invalid_token = "x" * (MIN_INTERNAL_TOKEN_LENGTH - 1)
    with pytest.raises(ValueError):
        await module.ensure_internal_api_token(SimpleNamespace(internal_api_token=invalid_token))
    async with sessions() as session:
        assert (await session.execute(select(SystemSetting))).scalars().all() == []


@pytest.mark.asyncio
async def test_settings_protect_internal_tokens_and_preserve_masked_secrets(token_store, monkeypatch) -> None:
    _, sessions, _ = token_store
    services = ModuleType("common.services")
    services.__path__ = [str(Path(__file__).resolve().parents[1] / "common/services")]
    monkeypatch.setitem(sys.modules, "common.services", services)
    compat = ModuleType("common.db.compat")
    compat.db_manager = None
    monkeypatch.setitem(sys.modules, "common.db.compat", compat)
    source = Path(__file__).resolve().parents[1] / "backend-web/app/services/system_setting_service.py"
    spec = importlib.util.spec_from_file_location("settings_service_contract", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    token_key = "security.internal_api_token"
    secret_key = module.TOKEN_REMOTE_SECRET_KEY_SETTING_KEY
    saved_secret = "test-only-remote-secret"
    async with sessions() as session:
        session.add_all([
            SystemSetting(key=token_key, value="test-only-internal-token"),
            SystemSetting(key=secret_key, value=saved_secret),
        ])
        await session.commit()
        service = module.SystemSettingService(session)
        public = await service.list_settings()
        internal = await service.list_settings(include_sensitive=True)
        assert token_key not in public and token_key not in internal
        assert public[secret_key] == module.SENSITIVE_MASK
        assert internal[secret_key] == saved_secret
        await service.set_setting(secret_key, module.SENSITIVE_MASK)
        assert await service.resolve_sensitive_value(secret_key, module.SENSITIVE_MASK) == saved_secret
        assert await service.resolve_sensitive_value(secret_key, "replacement") == "replacement"
        with pytest.raises(ValueError):
            await service.set_setting(token_key, "replacement")
        with pytest.raises(ValueError):
            await service.set_settings({token_key: ("replacement", None)})
