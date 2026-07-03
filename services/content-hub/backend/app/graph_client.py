from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


async def get_app_access_token(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not settings.graph_publish_configured:
        raise HTTPException(status_code=400, detail="graph_publish_unavailable")

    token_url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": settings.azure_client_id,
        "client_secret": settings.azure_client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            logger.error("Graph token request failed: %s", response.text)
            raise HTTPException(status_code=502, detail="graph_token_failed")
        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="graph_token_failed")
        return access_token
