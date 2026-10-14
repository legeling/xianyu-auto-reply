"""CLI exception types."""
from __future__ import annotations


class CliError(Exception):
    """Expected command line failure with a user-facing message."""


def ensure_success(response: object) -> None:
    """HTTP success does not imply success of the requested business operation."""
    if isinstance(response, dict) and response.get("success") is False:
        raise CliError(str(response.get("message") or "后端操作失败"))
