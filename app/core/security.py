"""
Security utilities and dependencies for API authentication.

Currently implements simple API key authentication via the `X-API-Key` HTTP
header. Valid keys are provided through the `Settings.api_keys` list which can
be overridden using the `API_KEYS` environment variable (comma-separated or
JSON list).
"""
from typing import List
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

from app.core.config import settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_valid_api_keys() -> List[str]:
    """Return list of valid API keys from settings (case-sensitive)."""
    return settings.api_keys or []


async def get_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Dependency that validates the provided API key.

    Raises
    ------
    HTTPException
        If the API key is missing or invalid.
    """
    valid_keys = get_valid_api_keys()

    if api_key is None or api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
        )

    return api_key
