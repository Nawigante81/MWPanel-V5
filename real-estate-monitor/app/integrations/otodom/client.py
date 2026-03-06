from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from .logger import logger, mask_secret


class OtodomClient:
    def __init__(self):
        self.base_url = os.getenv("OTODOM_API_BASE_URL", "").rstrip("/")
        self.client_id = os.getenv("OTODOM_CLIENT_ID")
        self.client_secret = os.getenv("OTODOM_CLIENT_SECRET")
        self.access_token = os.getenv("OTODOM_ACCESS_TOKEN")
        self.refresh_token = os.getenv("OTODOM_REFRESH_TOKEN")
        self.account_id = os.getenv("OTODOM_ACCOUNT_ID")
        self.timeout_ms = int(os.getenv("OTODOM_REQUEST_TIMEOUT", "30000"))

        if not self.base_url:
            raise RuntimeError("OTODOM_API_BASE_URL is not configured")

    def _headers(self) -> Dict[str, str]:
        if not self.access_token:
            raise RuntimeError("OTODOM_ACCESS_TOKEN is not configured")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            resp = await client.request(method, url, headers=self._headers(), json=json_body)

        if resp.status_code == 401 and self.refresh_token and self.client_id and self.client_secret:
            await self.refresh_access_token()
            async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
                resp = await client.request(method, url, headers=self._headers(), json=json_body)

        if resp.status_code >= 400:
            txt = resp.text[:1000]
            logger.error(f"Otodom API error {resp.status_code} {method} {path}: {txt}")
            raise RuntimeError(f"Otodom API {resp.status_code}: {txt}")

        return resp.json() if resp.text else {}

    async def refresh_access_token(self) -> Dict[str, Any]:
        token_url = f"{self.base_url}/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            resp = await client.post(token_url, data=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Otodom token refresh failed: {resp.status_code} {resp.text[:500]}")
        data = resp.json()
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        logger.info(
            f"Otodom token refreshed. access={mask_secret(self.access_token)} refresh={mask_secret(self.refresh_token)}"
        )
        return data

    async def create_listing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", f"/accounts/{self.account_id}/listings", payload)

    async def update_listing(self, listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/accounts/{self.account_id}/listings/{listing_id}", payload)

    async def deactivate_listing(self, listing_id: str) -> Dict[str, Any]:
        return await self._request("POST", f"/accounts/{self.account_id}/listings/{listing_id}/deactivate", {})

    async def upload_image(self, listing_id: str, image_url: str, is_cover: bool = False, sort_order: int = 0) -> Dict[str, Any]:
        payload = {"url": image_url, "isCover": is_cover, "position": sort_order}
        return await self._request("POST", f"/accounts/{self.account_id}/listings/{listing_id}/images", payload)
