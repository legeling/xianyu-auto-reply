"""按顺序执行本分支迁移，成功后记录版本，失败保留可重复执行的状态。"""
from sqlalchemy import text

from common.db.session import async_engine
from common.db.migrations.m001_fork_baseline import upgrade as upgrade_baseline

MIGRATIONS = ((1, "fork_baseline", upgrade_baseline),)


async def upgrade_database() -> None:
    async with async_engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS xy_schema_migrations (
                version INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        applied = set((await conn.execute(text("SELECT version FROM xy_schema_migrations"))).scalars())
    if applied - {version for version, _, _ in MIGRATIONS}:
        raise RuntimeError("数据库包含当前代码不支持的迁移版本，请使用对应发布版")
    for version, name, upgrade in MIGRATIONS:
        if version in applied:
            continue
        await upgrade()
        async with async_engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO xy_schema_migrations (version, name) VALUES (:version, :name)"),
                {"version": version, "name": name},
            )
