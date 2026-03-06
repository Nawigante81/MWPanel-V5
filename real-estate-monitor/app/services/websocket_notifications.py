"""
WebSocket Notifications Service - Powiadomienia na Żywo

Real-time notifications via WebSocket for instant updates to connected clients.
Supports user-specific channels, broadcast, and notification history.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
import asyncio

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class NotificationType(str, Enum):
    """Typ powiadomienia"""
    NEW_OFFER = "new_offer"                    # Nowa oferta
    PRICE_CHANGE = "price_change"              # Zmiana ceny
    PRICE_DROP = "price_drop"                  # Obniżka ceny
    STATUS_CHANGE = "status_change"            # Zmiana statusu
    TASK_ASSIGNED = "task_assigned"            # Nowe zadanie
    TASK_DUE = "task_due"                      # Zadanie do wykonania
    VIEWING_REMINDER = "viewing_reminder"      # Przypomnienie o prezentacji
    COMPETITOR_ALERT = "competitor_alert"      # Alert konkurencji
    COMMISSION_EARNED = "commission_earned"    # Zarobiona prowizja
    SYSTEM = "system"                          # Systemowe


class NotificationPriority(str, Enum):
    """Priorytet powiadomienia"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationMessage:
    """Wiadomość powiadomienia"""
    id: str
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority
    
    # Odbiorcy
    user_id: Optional[str]           # None = broadcast
    organization_id: Optional[str]
    
    # Dane
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Czas
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Status
    read: bool = False
    read_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type.value,
            'title': self.title,
            'message': self.message,
            'priority': self.priority.value,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'read': self.read,
        }
    
    def to_websocket_message(self) -> str:
        """Konwertuj do JSON dla WebSocket"""
        return json.dumps({
            'event': 'notification',
            'payload': self.to_dict(),
        })


@dataclass
class Connection:
    """Połączenie WebSocket"""
    id: str
    websocket: WebSocket
    user_id: Optional[str]
    organization_id: Optional[str]
    connected_at: datetime
    subscriptions: Set[str] = field(default_factory=set)
    
    async def send(self, message: str):
        """Wyślij wiadomość"""
        try:
            await self.websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending to connection {self.id}: {e}")
    
    async def send_notification(self, notification: NotificationMessage):
        """Wyślij powiadomienie"""
        await self.send(notification.to_websocket_message())


class WebSocketManager:
    """
    Manager połączeń WebSocket.
    
    Zarządza połączeniami, subskrypcjami i dystrybucją powiadomień.
    """
    
    def __init__(self):
        self.connections: Dict[str, Connection] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.org_connections: Dict[str, Set[str]] = {}   # org_id -> connection_ids
        self.notification_history: List[NotificationMessage] = []
        self.max_history = 1000
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Connection:
        """
        Akceptuj nowe połączenie WebSocket.
        
        Args:
            websocket: Obiekt WebSocket
            user_id: ID użytkownika (opcjonalne)
            organization_id: ID organizacji (opcjonalne)
        
        Returns:
            Obiekt Connection
        """
        await websocket.accept()
        
        connection = Connection(
            id=str(uuid.uuid4()),
            websocket=websocket,
            user_id=user_id,
            organization_id=organization_id,
            connected_at=datetime.utcnow(),
        )
        
        self.connections[connection.id] = connection
        
        # Indeksuj po użytkowniku
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection.id)
        
        # Indeksuj po organizacji
        if organization_id:
            if organization_id not in self.org_connections:
                self.org_connections[organization_id] = set()
            self.org_connections[organization_id].add(connection.id)
        
        logger.info(f"WebSocket connected: {connection.id} (user: {user_id})")
        
        # Wyślij potwierdzenie połączenia
        await connection.send(json.dumps({
            'event': 'connected',
            'payload': {
                'connection_id': connection.id,
                'user_id': user_id,
                'organization_id': organization_id,
            }
        }))
        
        return connection
    
    async def disconnect(self, connection_id: str):
        """Rozłącz klienta"""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        # Usuń z indeksów
        if connection.user_id and connection.user_id in self.user_connections:
            self.user_connections[connection.user_id].discard(connection_id)
            if not self.user_connections[connection.user_id]:
                del self.user_connections[connection.user_id]
        
        if connection.organization_id and connection.organization_id in self.org_connections:
            self.org_connections[connection.organization_id].discard(connection_id)
            if not self.org_connections[connection.organization_id]:
                del self.org_connections[connection.organization_id]
        
        # Usuń połączenie
        del self.connections[connection_id]
        
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def handle_message(self, connection_id: str, message: str):
        """
        Obsługa wiadomości od klienta.
        
        Obsługiwane komendy:
        - subscribe: Subskrybuj kanał
        - unsubscribe: Anuluj subskrypcję
        - ping: Keepalive
        - mark_read: Oznacz powiadomienie jako przeczytane
        """
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        try:
            data = json.loads(message)
            event = data.get('event')
            payload = data.get('payload', {})
            
            if event == 'subscribe':
                channel = payload.get('channel')
                if channel:
                    connection.subscriptions.add(channel)
                    await connection.send(json.dumps({
                        'event': 'subscribed',
                        'payload': {'channel': channel}
                    }))
            
            elif event == 'unsubscribe':
                channel = payload.get('channel')
                if channel and channel in connection.subscriptions:
                    connection.subscriptions.discard(channel)
                    await connection.send(json.dumps({
                        'event': 'unsubscribed',
                        'payload': {'channel': channel}
                    }))
            
            elif event == 'ping':
                await connection.send(json.dumps({
                    'event': 'pong',
                    'payload': {'timestamp': datetime.utcnow().isoformat()}
                }))
            
            elif event == 'mark_read':
                notification_id = payload.get('notification_id')
                if notification_id:
                    await self._mark_notification_read(notification_id, connection.user_id)
            
            elif event == 'get_history':
                # Pobierz historię powiadomień dla użytkownika
                history = self._get_user_history(connection.user_id, limit=50)
                await connection.send(json.dumps({
                    'event': 'history',
                    'payload': {'notifications': [n.to_dict() for n in history]}
                }))
            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from connection {connection_id}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def send_to_user(
        self,
        user_id: str,
        notification: NotificationMessage,
    ) -> int:
        """
        Wyślij powiadomienie do wszystkich połączeń użytkownika.
        
        Returns:
            Liczba dostarczonych powiadomień
        """
        connection_ids = self.user_connections.get(user_id, set())
        delivered = 0
        
        for conn_id in connection_ids:
            connection = self.connections.get(conn_id)
            if connection:
                await connection.send_notification(notification)
                delivered += 1
        
        return delivered
    
    async def send_to_organization(
        self,
        organization_id: str,
        notification: NotificationMessage,
        exclude_user_id: Optional[str] = None,
    ) -> int:
        """
        Wyślij powiadomienie do wszystkich w organizacji.
        
        Args:
            organization_id: ID organizacji
            notification: Powiadomienie do wysłania
            exclude_user_id: Wyklucz tego użytkownika
        
        Returns:
            Liczba dostarczonych powiadomień
        """
        connection_ids = self.org_connections.get(organization_id, set())
        delivered = 0
        
        for conn_id in connection_ids:
            connection = self.connections.get(conn_id)
            if connection:
                if exclude_user_id and connection.user_id == exclude_user_id:
                    continue
                await connection.send_notification(notification)
                delivered += 1
        
        return delivered
    
    async def broadcast(self, notification: NotificationMessage) -> int:
        """
        Wyślij powiadomienie do wszystkich połączonych klientów.
        
        Returns:
            Liczba dostarczonych powiadomień
        """
        delivered = 0
        
        for connection in self.connections.values():
            await connection.send_notification(notification)
            delivered += 1
        
        return delivered
    
    async def notify_new_offer(
        self,
        offer_id: str,
        title: str,
        price: float,
        city: str,
        user_ids: Optional[List[str]] = None,
    ):
        """Powiadom o nowej ofercie"""
        notification = NotificationMessage(
            id=str(uuid.uuid4()),
            type=NotificationType.NEW_OFFER,
            title="Nowa oferta",
            message=f"{title} - {price:,.0f} zł w {city}",
            priority=NotificationPriority.NORMAL,
            user_id=None,  # Broadcast lub do konkretnych użytkowników
            data={
                'offer_id': offer_id,
                'title': title,
                'price': price,
                'city': city,
            }
        )
        
        if user_ids:
            for user_id in user_ids:
                notification.user_id = user_id
                await self.send_to_user(user_id, notification)
        else:
            await self.broadcast(notification)
        
        self._add_to_history(notification)
    
    async def notify_price_change(
        self,
        offer_id: str,
        title: str,
        old_price: float,
        new_price: float,
        user_ids: List[str],
    ):
        """Powiadom o zmianie ceny"""
        change_percent = ((new_price - old_price) / old_price) * 100
        is_drop = new_price < old_price
        
        notification = NotificationMessage(
            id=str(uuid.uuid4()),
            type=NotificationType.PRICE_DROP if is_drop else NotificationType.PRICE_CHANGE,
            title="Obniżka ceny!" if is_drop else "Zmiana ceny",
            message=f"{title}: {old_price:,.0f} → {new_price:,.0f} zł ({change_percent:+.1f}%)",
            priority=NotificationPriority.HIGH if is_drop else NotificationPriority.NORMAL,
            data={
                'offer_id': offer_id,
                'title': title,
                'old_price': old_price,
                'new_price': new_price,
                'change_percent': round(change_percent, 2),
            }
        )
        
        for user_id in user_ids:
            notification.user_id = user_id
            await self.send_to_user(user_id, notification)
        
        self._add_to_history(notification)
    
    async def notify_task_assigned(
        self,
        task_id: str,
        title: str,
        assigned_to: str,
        due_date: Optional[datetime] = None,
    ):
        """Powiadom o nowym zadaniu"""
        message = f"Przydzielono zadanie: {title}"
        if due_date:
            message += f" (termin: {due_date.strftime('%Y-%m-%d')})"
        
        notification = NotificationMessage(
            id=str(uuid.uuid4()),
            type=NotificationType.TASK_ASSIGNED,
            title="Nowe zadanie",
            message=message,
            priority=NotificationPriority.NORMAL,
            user_id=assigned_to,
            data={
                'task_id': task_id,
                'title': title,
                'due_date': due_date.isoformat() if due_date else None,
            }
        )
        
        await self.send_to_user(assigned_to, notification)
        self._add_to_history(notification)
    
    async def notify_viewing_reminder(
        self,
        viewing_id: str,
        address: str,
        datetime_str: str,
        user_ids: List[str],
    ):
        """Przypomnienie o prezentacji"""
        notification = NotificationMessage(
            id=str(uuid.uuid4()),
            type=NotificationType.VIEWING_REMINDER,
            title="Przypomnienie o prezentacji",
            message=f"Prezentacja {address} o {datetime_str}",
            priority=NotificationPriority.HIGH,
            data={
                'viewing_id': viewing_id,
                'address': address,
                'datetime': datetime_str,
            }
        )
        
        for user_id in user_ids:
            notification.user_id = user_id
            await self.send_to_user(user_id, notification)
        
        self._add_to_history(notification)
    
    async def notify_competitor_alert(
        self,
        listing_title: str,
        change_type: str,
        change_percent: float,
        organization_id: str,
    ):
        """Alert o zmianie u konkurencji"""
        notification = NotificationMessage(
            id=str(uuid.uuid4()),
            type=NotificationType.COMPETITOR_ALERT,
            title="Zmiana u konkurencji",
            message=f"{listing_title}: {change_type} {change_percent:.1f}%",
            priority=NotificationPriority.HIGH,
            organization_id=organization_id,
            data={
                'listing_title': listing_title,
                'change_type': change_type,
                'change_percent': change_percent,
            }
        )
        
        await self.send_to_organization(organization_id, notification)
        self._add_to_history(notification)
    
    async def notify_commission_earned(
        self,
        user_id: str,
        amount: float,
        deal_address: str,
    ):
        """Powiadom o zarobionej prowizji"""
        notification = NotificationMessage(
            id=str(uuid.uuid4()),
            type=NotificationType.COMMISSION_EARNED,
            title="Gratulacje! Nowa prowizja",
            message=f"Zarobiłeś {amount:,.2f} zł za {deal_address}",
            priority=NotificationPriority.NORMAL,
            user_id=user_id,
            data={
                'amount': amount,
                'deal_address': deal_address,
            }
        )
        
        await self.send_to_user(user_id, notification)
        self._add_to_history(notification)
    
    def get_stats(self) -> Dict[str, Any]:
        """Pobierz statystyki połączeń"""
        return {
            'total_connections': len(self.connections),
            'unique_users': len(self.user_connections),
            'unique_organizations': len(self.org_connections),
            'connections_by_user': {
                user_id: len(conn_ids)
                for user_id, conn_ids in self.user_connections.items()
            },
            'notification_history_size': len(self.notification_history),
        }
    
    def _add_to_history(self, notification: NotificationMessage):
        """Dodaj powiadomienie do historii"""
        self.notification_history.append(notification)
        
        # Ogranicz historię
        if len(self.notification_history) > self.max_history:
            self.notification_history = self.notification_history[-self.max_history:]
    
    def _get_user_history(
        self,
        user_id: Optional[str],
        limit: int = 50,
    ) -> List[NotificationMessage]:
        """Pobierz historię powiadomień dla użytkownika"""
        if not user_id:
            return []
        
        user_notifications = [
            n for n in self.notification_history
            if n.user_id == user_id or n.user_id is None
        ]
        
        return sorted(
            user_notifications,
            key=lambda n: n.created_at,
            reverse=True
        )[:limit]
    
    async def _mark_notification_read(self, notification_id: str, user_id: Optional[str]):
        """Oznacz powiadomienie jako przeczytane"""
        for notification in self.notification_history:
            if notification.id == notification_id:
                if notification.user_id == user_id or notification.user_id is None:
                    notification.read = True
                    notification.read_at = datetime.utcnow()
                    break


# Singleton instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get singleton WebSocket manager instance"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


# FastAPI WebSocket endpoint handler
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
):
    """
    WebSocket endpoint handler for FastAPI.
    
    Usage in FastAPI:
        @app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket):
            await websocket_endpoint(websocket, user_id="123")
    """
    manager = get_websocket_manager()
    connection = await manager.connect(websocket, user_id, organization_id)
    
    try:
        while True:
            message = await websocket.receive_text()
            await manager.handle_message(connection.id, message)
    except WebSocketDisconnect:
        await manager.disconnect(connection.id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(connection.id)
