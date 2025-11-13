"""启动前的数据库迁移辅助函数。"""

from __future__ import annotations

import shutil
from pathlib import Path


def migrate_database_files_early() -> bool:
    """在启动前检查并迁移数据库文件到data目录（使用print，因为logger还未初始化）"""
    print("检查数据库文件位置...")

    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        print("✓ 创建 data 目录")

    files_to_migrate = [
        ("xianyu_data.db", "data/xianyu_data.db", "主数据库"),
        ("user_stats.db", "data/user_stats.db", "统计数据库"),
    ]

    migrated_files = []

    for old_path, new_path, description in files_to_migrate:
        old_file = Path(old_path)
        new_file = Path(new_path)

        if old_file.exists():
            if not new_file.exists():
                try:
                    shutil.move(str(old_file), str(new_file))
                    print(f"✓ 迁移{description}: {old_path} -> {new_path}")
                    migrated_files.append(description)
                except Exception as exc:
                    print(f"⚠ 无法迁移{description}: {exc}")
                    print("  尝试复制文件...")
                    try:
                        shutil.copy2(str(old_file), str(new_file))
                        print(f"✓ 已复制{description}到新位置")
                        print(f"  请在确认数据正常后手动删除: {old_path}")
                        migrated_files.append(f"{description}(已复制)")
                    except Exception as copy_exc:
                        print(f"✗ 复制{description}失败: {copy_exc}")
            else:
                try:
                    if old_file.stat().st_size > 0:
                        print(f"⚠ 发现旧{description}文件: {old_path}")
                        print(f"  新数据库位于: {new_path}")
                        print("  建议备份后删除旧文件")
                except Exception:
                    pass

    backup_files = list(Path(".").glob("xianyu_data_backup_*.db"))
    if backup_files:
        print(f"发现 {len(backup_files)} 个备份文件")
        backup_migrated = 0
        for backup_file in backup_files:
            new_backup_path = data_dir / backup_file.name
            if not new_backup_path.exists():
                try:
                    shutil.move(str(backup_file), str(new_backup_path))
                    print(f"✓ 迁移备份文件: {backup_file.name}")
                    backup_migrated += 1
                except Exception as exc:
                    print(f"⚠ 无法迁移备份文件 {backup_file.name}: {exc}")

        if backup_migrated > 0:
            migrated_files.append(f"{backup_migrated}个备份文件")

    if migrated_files:
        print(f"✓ 数据库迁移完成，已迁移: {', '.join(migrated_files)}")
    else:
        print("✓ 数据库文件检查完成")

    return True

