from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class PublicationProvider(ABC):
    @abstractmethod
    async def create_listing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def update_listing(self, external_listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def deactivate_listing(self, external_listing_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def upload_images(self, external_listing_id: str, images: List[Dict[str, Any]]) -> Dict[str, Any]:
        raise NotImplementedError
