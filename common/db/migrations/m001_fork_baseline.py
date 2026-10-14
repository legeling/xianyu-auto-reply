"""迁移 001：升级已部署的上游 1.0.7 数据到本分支首个独立发布基线。"""
from sqlalchemy import text

from common.db.auto_relist_schema import AUTO_RELIST_COLUMNS, AUTO_RELIST_TABLE_DDL
from common.db.session import async_engine


async def upgrade() -> None:
    from common.db.init_database import DatabaseInitializer

    initializer = DatabaseInitializer()
    await initializer.init_all()
    # 旧初始化器会记录部分 DDL 错误后继续；核验实际结构才允许记为迁移成功。
    async with async_engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
        """))).all()
    columns: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        columns.setdefault(table_name, set()).add(column_name)
    missing_tables = (set(initializer.TABLES_DDL) | set(AUTO_RELIST_TABLE_DDL)) - columns.keys()
    expected_columns = {
        table_name: {entry[0] for entry in entries}
        for table_name, entries in initializer.COLUMN_MIGRATIONS.items()
    }
    for table_name, definitions in AUTO_RELIST_COLUMNS.items():
        expected_columns.setdefault(table_name, set()).update(definitions)
    missing_columns = {
        table_name: sorted(expected - columns.get(table_name, set()))
        for table_name, expected in expected_columns.items()
        if expected - columns.get(table_name, set())
    }
    if missing_tables or missing_columns:
        raise RuntimeError(
            f"数据库迁移结构不完整：tables={sorted(missing_tables)}, columns={missing_columns}"
        )
