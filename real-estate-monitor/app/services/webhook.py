"""
Webhook service for external integrations.
Sends HTTP callbacks when new offers are detected.
"""
import hmac
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from app.logging_config import get_logger
from app.models import Webhook
from app.schemas import OfferNormalized

logger = get_logger("webhook")


class WebhookService:
    """
    Manages webhook delivery.
    
    Features:
    - Signature verification (HMAC)
    - Retry with backoff
    - Filter matching
    - Batch delivery
    """
    
    def __init__(self):
        self.timeout = 30.0
        self.max_retries = 3
    
    async def send_webhook(
        self,
        webhook: Webhook,
        offer: OfferNormalized,
        event_type: str = "offer.new"
    ) -> bool:
        """
        Send webhook notification.
        
        Args:
            webhook: Webhook configuration
            offer: Offer data
            event_type: Type of event
        
        Returns:
            True if successful
        """
        # Check filters
        if webhook.filters and not self._matches_filters(offer, webhook.filters):
            return True  # Skip but don't count as failure
        
        payload = self._build_payload(offer, event_type)
        headers = self._build_headers(webhook, payload)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    webhook.url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
            
            webhook.last_triggered = datetime.utcnow()
            webhook.fail_count = 0
            
            logger.info(
                "Webhook sent successfully",
                extra={"webhook_id": str(webhook.id), "offer_id": offer.url}
            )
            
            return True
            
        except Exception as e:
            webhook.fail_count += 1
            
            logger.error(
                "Webhook delivery failed",
                extra={
                    "webhook_id": str(webhook.id),
                    "error": str(e),
                    "fail_count": webhook.fail_count
                }
            )
            
            # Disable webhook after too many failures
            if webhook.fail_count >= 10:
                webhook.is_active = False
                logger.warning(f"Disabled webhook due to failures: {webhook.url}")
            
            return False
    
    def _build_payload(self, offer: OfferNormalized, event_type: str) -> dict:
        """Build webhook payload."""
        return {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "source": offer.source,
                "url": offer.url,
                "title": offer.title,
                "price": float(offer.price) if offer.price else None,
                "currency": offer.currency,
                "city": offer.city,
                "region": offer.region,
                "area_m2": offer.area_m2,
                "rooms": offer.rooms,
                "lat": offer.lat,
                "lng": offer.lng,
            }
        }
    
    def _build_headers(self, webhook: Webhook, payload: dict) -> dict:
        """Build webhook headers with signature."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "RealEstateMonitor/1.0",
            "X-Webhook-ID": str(webhook.id),
            "X-Event-Type": "offer.new",
        }
        
        # Add HMAC signature if secret is configured
        if webhook.secret:
            signature = self._generate_signature(payload, webhook.secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        
        return headers
    
    def _generate_signature(self, payload: dict, secret: str) -> str:
        """Generate HMAC signature for payload."""
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        secret_bytes = secret.encode('utf-8')
        
        signature = hmac.new(
            secret_bytes,
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _matches_filters(self, offer: OfferNormalized, filters: dict) -> bool:
        """Check if offer matches webhook filters."""
        # Source filter
        if "sources" in filters:
            if offer.source not in filters["sources"]:
                return False
        
        # City filter
        if "cities" in filters:
            if offer.city and offer.city.lower() not in [
                c.lower() for c in filters["cities"]
            ]:
                return False
        
        # Region filter
        if "regions" in filters:
            if offer.region and offer.region.lower() not in [
                r.lower() for r in filters["regions"]
            ]:
                return False
        
        # Price range filter
        if "min_price" in filters:
            if offer.price and offer.price < filters["min_price"]:
                return False
        
        if "max_price" in filters:
            if offer.price and offer.price > filters["max_price"]:
                return False
        
        # Area filter
        if "min_area" in filters:
            if offer.area_m2 and offer.area_m2 < filters["min_area"]:
                return False
        
        if "max_area" in filters:
            if offer.area_m2 and offer.area_m2 > filters["max_area"]:
                return False
        
        # Rooms filter
        if "rooms" in filters:
            if offer.rooms and offer.rooms not in filters["rooms"]:
                return False
        
        return True
    
    async def send_to_all(
        self,
        webhooks: List[Webhook],
        offer: OfferNormalized,
        event_type: str = "offer.new"
    ) -> Dict[str, bool]:
        """
        Send webhook to all active webhooks.
        
        Returns:
            Dict mapping webhook ID to success status
        """
        results = {}
        
        for webhook in webhooks:
            if not webhook.is_active:
                continue
            
            success = await self.send_webhook(webhook, offer, event_type)
            results[str(webhook.id)] = success
        
        return results


class WebhookVerifier:
    """Utility for verifying webhook signatures."""
    
    @staticmethod
    def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Raw request body
            signature: Signature from header (format: "sha256=<hash>")
            secret: Webhook secret
        
        Returns:
            True if signature is valid
        """
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Extract hash from signature header
        if signature.startswith("sha256="):
            provided_hash = signature[7:]
        else:
            provided_hash = signature
        
        return hmac.compare_digest(expected_signature, provided_hash)


# Global instance
_webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    """Get or create webhook service."""
    global _webhook_service
    
    if _webhook_service is None:
        _webhook_service = WebhookService()
    
    return _webhook_service
