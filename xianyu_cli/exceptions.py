"""CLI exception types."""
from __future__ import annotations


class CliError(Exception):
    """Expected command line failure with a user-facing message."""
