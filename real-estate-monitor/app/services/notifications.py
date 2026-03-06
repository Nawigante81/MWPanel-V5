"""
Multi-channel notification service.
Supports: WhatsApp, Email, Slack, Telegram, Discord, Webhooks
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import httpx
from datetime import datetime

from app.logging_config import get_logger
from app.models import NotificationChannel
from app.schemas import OfferNormalized
from app.settings import settings

logger = get_logger("notifications")


class BaseNotifier(ABC):
    """Base class for all notification channels."""
    
    channel: NotificationChannel
    
    @abstractmethod
    async def send(self, offer: OfferNormalized, recipient: str) -> dict:
        """Send notification and return response data."""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this notifier is properly configured."""
        pass


class WhatsAppNotifier(BaseNotifier):
    """WhatsApp Cloud API notifier."""
    
    channel = NotificationChannel.WHATSAPP
    
    def __init__(self):
        self.token = settings.wa_token
        self.phone_number_id = settings.wa_phone_number_id
        self.default_recipient = settings.wa_to
    
    def is_configured(self) -> bool:
        return all([self.token, self.phone_number_id, self.default_recipient])
    
    async def send(self, offer: OfferNormalized, recipient: Optional[str] = None) -> dict:
        """Send WhatsApp message."""
        to = recipient or self.default_recipient
        
        # Build message (5 lines format)
        lines = [
            offer.title[:100] if offer.title else "New Property",
        ]
        
        details = []
        if offer.price:
            currency = offer.currency or "PLN"
            details.append(f"{offer.price:,.0f} {currency}".replace(",", " "))
        if offer.area_m2:
            details.append(f"{offer.area_m2:.0f} m²")
        if offer.rooms:
            details.append(f"{offer.rooms} pok")
        lines.append(" | ".join(details) if details else "Details not available")
        
        location_parts = []
        if offer.city:
            location_parts.append(offer.city)
        if offer.region:
            location_parts.append(offer.region)
        lines.append(", ".join(location_parts) if location_parts else "Location not specified")
        
        lines.append(offer.url or "")
        lines.append(f"via {offer.source}")
        
        message_text = "\n".join(lines)
        
        api_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "body": message_text,
                "preview_url": True,
            },
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()


class EmailNotifier(BaseNotifier):
    """Email notifier using SMTP."""
    
    channel = NotificationChannel.EMAIL
    
    def __init__(self):
        self.smtp_host = getattr(settings, 'SMTP_HOST', None)
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_user = getattr(settings, 'SMTP_USER', None)
        self.smtp_pass = getattr(settings, 'SMTP_PASS', None)
        self.from_email = getattr(settings, 'FROM_EMAIL', None)
    
    def is_configured(self) -> bool:
        return all([self.smtp_host, self.smtp_user, self.smtp_pass])
    
    async def send(self, offer: OfferNormalized, recipient: str) -> dict:
        """Send email notification."""
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart()
        msg['From'] = self.from_email or self.smtp_user
        msg['To'] = recipient
        msg['Subject'] = f"[{offer.source}] {offer.title[:80]}"
        
        body = f"""
        <html>
        <body>
            <h2>{offer.title}</h2>
            <p><strong>Price:</strong> {offer.price} {offer.currency or 'PLN'}</p>
            <p><strong>Area:</strong> {offer.area_m2} m²</p>
            <p><strong>Rooms:</strong> {offer.rooms}</p>
            <p><strong>Location:</strong> {offer.city}, {offer.region}</p>
            <p><a href="{offer.url}">View Offer</a></p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        await aiosmtplib.send(
            msg,
            hostname=self.smtp_host,
            port=self.smtp_port,
            username=self.smtp_user,
            password=self.smtp_pass,
            start_tls=True,
        )
        
        return {"status": "sent", "recipient": recipient}


class SlackNotifier(BaseNotifier):
    """Slack webhook notifier."""
    
    channel = NotificationChannel.SLACK
    
    def __init__(self):
        self.webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
    
    def is_configured(self) -> bool:
        return self.webhook_url is not None
    
    async def send(self, offer: OfferNormalized, recipient: str) -> dict:
        """Send Slack notification."""
        payload = {
            "text": f"New property from {offer.source}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": offer.title[:100]
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Price:*\n{offer.price} {offer.currency or 'PLN'}"},
                        {"type": "mrkdwn", "text": f"*Area:*\n{offer.area_m2} m²"},
                        {"type": "mrkdwn", "text": f"*Rooms:*\n{offer.rooms}"},
                        {"type": "mrkdwn", "text": f"*Location:*\n{offer.city}, {offer.region}"},
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Offer"},
                            "url": offer.url
                        }
                    ]
                }
            ]
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()
            return {"status": "sent"}


class TelegramNotifier(BaseNotifier):
    """Telegram Bot API notifier."""
    
    channel = NotificationChannel.TELEGRAM
    
    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.default_chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
    
    def is_configured(self) -> bool:
        return self.bot_token is not None
    
    async def send(self, offer: OfferNormalized, recipient: str) -> dict:
        """Send Telegram message."""
        chat_id = recipient or self.default_chat_id
        
        message = f"""
🏠 <b>{offer.title}</b>

💰 Price: {offer.price} {offer.currency or 'PLN'}
📐 Area: {offer.area_m2} m²
🚪 Rooms: {offer.rooms}
📍 Location: {offer.city}, {offer.region}

🔗 <a href="{offer.url}">View Offer</a>
📱 Source: {offer.source}
        """.strip()
        
        api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            return response.json()


class DiscordNotifier(BaseNotifier):
    """Discord webhook notifier."""
    
    channel = NotificationChannel.DISCORD
    
    def __init__(self):
        self.webhook_url = getattr(settings, 'DISCORD_WEBHOOK_URL', None)
    
    def is_configured(self) -> bool:
        return self.webhook_url is not None
    
    async def send(self, offer: OfferNormalized, recipient: str) -> dict:
        """Send Discord notification."""
        payload = {
            "embeds": [{
                "title": offer.title[:256],
                "url": offer.url,
                "color": 3447003,
                "fields": [
                    {"name": "Price", "value": f"{offer.price} {offer.currency or 'PLN'}", "inline": True},
                    {"name": "Area", "value": f"{offer.area_m2} m²", "inline": True},
                    {"name": "Rooms", "value": str(offer.rooms), "inline": True},
                    {"name": "Location", "value": f"{offer.city}, {offer.region}", "inline": False},
                    {"name": "Source", "value": offer.source, "inline": True},
                ],
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()
            return {"status": "sent"}


class NotificationManager:
    """Manager for all notification channels."""
    
    def __init__(self):
        self.notifiers: Dict[NotificationChannel, BaseNotifier] = {
            NotificationChannel.WHATSAPP: WhatsAppNotifier(),
            NotificationChannel.EMAIL: EmailNotifier(),
            NotificationChannel.SLACK: SlackNotifier(),
            NotificationChannel.TELEGRAM: TelegramNotifier(),
            NotificationChannel.DISCORD: DiscordNotifier(),
        }
    
    def get_available_channels(self) -> List[NotificationChannel]:
        """Get list of configured channels."""
        return [
            channel for channel, notifier in self.notifiers.items()
            if notifier.is_configured()
        ]
    
    async def send_to_channel(
        self,
        channel: NotificationChannel,
        offer: OfferNormalized,
        recipient: str
    ) -> dict:
        """Send notification to specific channel."""
        notifier = self.notifiers.get(channel)
        
        if not notifier:
            raise ValueError(f"Unknown channel: {channel}")
        
        if not notifier.is_configured():
            raise RuntimeError(f"Channel not configured: {channel}")
        
        return await notifier.send(offer, recipient)
    
    async def send_to_all(
        self,
        offer: OfferNormalized,
        recipients: Dict[NotificationChannel, str]
    ) -> Dict[NotificationChannel, dict]:
        """Send notification to all configured channels."""
        results = {}
        
        for channel, recipient in recipients.items():
            try:
                result = await self.send_to_channel(channel, offer, recipient)
                results[channel] = {"success": True, "data": result}
            except Exception as e:
                logger.error(f"Failed to send to {channel}: {e}")
                results[channel] = {"success": False, "error": str(e)}
        
        return results


# Global instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get or create notification manager."""
    global _notification_manager
    
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    
    return _notification_manager
