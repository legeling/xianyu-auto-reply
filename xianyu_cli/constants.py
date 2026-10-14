"""Shared constants for the CLI."""
from __future__ import annotations

DEFAULT_BASE_URL = "http://127.0.0.1:8089"
SENSITIVE_FIELDS = {
    "value", "cookie", "login_password", "password", "token", "refresh_token",
    "access_token", "api_key", "apikey", "authorization", "headers", "data_content", "text_content", "delivery_content",
}
