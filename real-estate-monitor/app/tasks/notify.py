"""
Celery tasks for sending notifications via WhatsApp Cloud API.
"""
from datetime import datetime
from typing import Optional

import httpx
from celery import Task
from sqlalchemy import select
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.db import get_sync_session
from app.logging_config import get_logger
from app.models import Notification, NotificationStatus, Offer
from app.settings import settings
from app.tasks.celery_app import celery_app

logger = get_logger("tasks.notify")


class NotifyTask(Task):
    """Base class for notification tasks."""
    
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True
    max_retries = settings.notification_max_retries


@celery_app.task(bind=True, base=NotifyTask)
def notify_whatsapp(self, offer_id: str) -> dict:
    """
    Send WhatsApp notification for a new offer.
    
    This task:
    - Creates a notification record
    - Sends message via WhatsApp Cloud API
    - Retries on failure with exponential backoff
    - Updates notification status
    """
    logger.info(
        "Sending WhatsApp notification",
        extra={"offer_id": offer_id, "task_id": self.request.id},
    )
    
    # Check if WhatsApp is configured
    if not settings.whatsapp_enabled:
        logger.warning("WhatsApp not configured, skipping notification")
        return {"status": "skipped", "reason": "not_configured"}
    
    # Get offer details
    with get_sync_session() as session:
        offer = session.get(Offer, offer_id)
        
        if not offer:
            logger.error(f"Offer not found: {offer_id}")
            return {"status": "failed", "reason": "offer_not_found"}
        
        # Create notification record
        notification = Notification(
            offer_id=offer.id,
            channel="whatsapp",
            status=NotificationStatus.PENDING,
        )
        session.add(notification)
        session.flush()
        notification_id = notification.id
    
    try:
        # Send message
        result = _send_whatsapp_message(offer)
        
        # Update notification record
        with get_sync_session() as session:
            notification = session.get(Notification, notification_id)
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            notification.tries = notification.tries + 1
        
        logger.info(
            "WhatsApp notification sent successfully",
            extra={"offer_id": offer_id, "notification_id": str(notification_id)},
        )
        
        return {
            "status": "sent",
            "notification_id": str(notification_id),
            "whatsapp_message_id": result.get("messages", [{}])[0].get("id"),
        }
        
    except Exception as e:
        # Update notification record with error
        with get_sync_session() as session:
            notification = session.get(Notification, notification_id)
            notification.tries = notification.tries + 1
            notification.last_error = str(e)[:500]
            
            # Mark as failed if max retries reached
            if notification.tries >= settings.notification_max_retries:
                notification.status = NotificationStatus.FAILED
        
        logger.error(
            "Failed to send WhatsApp notification",
            extra={
                "offer_id": offer_id,
                "error": str(e),
                "tries": notification.tries,
            },
        )
        
        raise self.retry(exc=e)


def _send_whatsapp_message(offer: Offer) -> dict:
    """
    Send WhatsApp message via Cloud API.
    
    Message format (5 lines):
    1. Title
    2. Price + area + rooms (compact)
    3. City / Region
    4. Link
    5. Source
    """
    # Build message
    lines = []
    
    # Line 1: Title
    title = offer.title[:100] if offer.title else "New Property"
    lines.append(title)
    
    # Line 2: Price + area + rooms
    details = []
    if offer.price:
        currency = offer.currency or "PLN"
        price_str = f"{offer.price:,.0f} {currency}".replace(",", " ")
        details.append(price_str)
    
    if offer.area_m2:
        details.append(f"{offer.area_m2:.0f} m²")
    
    if offer.rooms:
        rooms_str = f"{offer.rooms} pok{'oje' if offer.rooms > 1 else 'ój'}"
        details.append(rooms_str)
    
    lines.append(" | ".join(details) if details else "Details not available")
    
    # Line 3: City / Region
    location_parts = []
    if offer.city:
        location_parts.append(offer.city)
    if offer.region:
        location_parts.append(offer.region)
    
    lines.append(", ".join(location_parts) if location_parts else "Location not specified")
    
    # Line 4: Link
    lines.append(offer.url or "")
    
    # Line 5: Source
    source_name = offer.source.name if offer.source else "Unknown"
    lines.append(f"via {source_name}")
    
    message_text = "\n".join(lines)
    
    # Send via WhatsApp Cloud API
    api_url = (
        f"https://graph.facebook.com/v18.0/{settings.wa_phone_number_id}/messages"
    )
    
    headers = {
        "Authorization": f"Bearer {settings.wa_token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": settings.wa_to,
        "type": "text",
        "text": {
            "body": message_text,
            "preview_url": True,
        },
    }
    
    logger.debug(
        "Sending WhatsApp API request",
        extra={
            "url": api_url,
            "recipient": settings.wa_to,
        },
    )
    
    response = httpx.post(
        api_url,
        headers=headers,
        json=payload,
        timeout=30.0,
    )
    
    response.raise_for_status()
    
    result = response.json()
    
    if "error" in result:
        raise Exception(f"WhatsApp API error: {result['error']}")
    
    return result


@celery_app.task
def retry_failed_notifications():
    """
    Periodic task to retry failed notifications.
    """
    with get_sync_session() as session:
        # Find pending or failed notifications with retries left
        notifications = session.execute(
            select(Notification)
            .where(Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.FAILED]))
            .where(Notification.tries < settings.notification_max_retries)
        ).scalars().all()
        
        for notification in notifications:
            logger.info(
                "Retrying notification",
                extra={
                    "notification_id": str(notification.id),
                    "tries": notification.tries,
                },
            )
            
            # Re-enqueue
            notify_whatsapp.delay(str(notification.offer_id))
        
        return {
            "status": "completed",
            "retried": len(notifications),
        }
