"""Local CLI config storage."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from xianyu_cli.exceptions import CliError

CONFIG_PATH = Path(os.environ.get("XIANYU_CLI_CONFIG", "~/.xianyu-auto-reply-cli.json")).expanduser()


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"配置文件格式错误：{CONFIG_PATH}") from exc


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass
