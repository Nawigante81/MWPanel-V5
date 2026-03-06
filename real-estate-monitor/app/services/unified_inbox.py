"""
Unified Inbox Service - Centralna Skrzynka Komunikacji

Wszystkie kanały komunikacji w jednym miejscu:
Email, SMS, WhatsApp, Messenger, formularze.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import uuid

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, 
    Integer, Boolean, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Session
from sqlalchemy import func

from app.core.logging import get_logger

logger = get_logger(__name__)


class ChannelType(str, Enum):
    """Kanały komunikacji"""
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    MESSENGER = "messenger"  # Facebook Messenger
    TELEGRAM = "telegram"
    PHONE = "phone"
    WEBSITE_FORM = "website_form"
    PORTAL_INQUIRY = "portal_inquiry"  # Zapytanie z Otodom/OLX
    CHATBOT = "chatbot"
    INTERNAL = "internal"  # Notatki wewnętrzne


class MessageDirection(str, Enum):
    """Kierunek wiadomości"""
    INCOMING = "incoming"      # Od klienta
    OUTGOING = "outgoing"      # Do klienta
    INTERNAL = "internal"      # Wewnętrzna


class MessageStatus(str, Enum):
    """Status wiadomości"""
    NEW = "new"                    # Nowa, nieprzeczytana
    READ = "read"                  # Przeczytana
    PENDING = "pending"            # Oczekuje na odpowiedź
    REPLIED = "replied"            # Odpowiedziano
    RESOLVED = "resolved"          # Rozwiązana/zamknięta
    SPAM = "spam"                  # Spam
    ARCHIVED = "archived"          # Zarchiwizowana


class ConversationStatus(str, Enum):
    """Status rozmowy"""
    ACTIVE = "active"              # Aktywna
    WAITING_FOR_CLIENT = "waiting_for_client"  # Oczekuje na klienta
    WAITING_FOR_AGENT = "waiting_for_agent"    # Oczekuje na agenta
    RESOLVED = "resolved"          # Rozwiązana
    CLOSED = "closed"              # Zamknięta


class Conversation(Base):
    """Rozmowa z klientem"""
    __tablename__ = 'conversations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Identyfikacja klienta
    client_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=True)
    client_name = Column(String(200), nullable=True)
    client_email = Column(String(255), nullable=True)
    client_phone = Column(String(50), nullable=True)
    
    # Przypisanie
    assigned_agent_id = Column(String(100), ForeignKey('users.id'), nullable=True)
    
    # Status
    status = Column(SQLEnum(ConversationStatus), default=ConversationStatus.ACTIVE)
    priority = Column(Integer, default=3)  # 1-5, 1=najwyższy
    
    # Temat
    subject = Column(String(255), nullable=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey('listings.id'), nullable=True)
    
    # Statystyki
    message_count = Column(Integer, default=0)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_message_preview = Column(String(200), nullable=True)
    
    # SLA
    first_response_due = Column(DateTime(timezone=True), nullable=True)
    resolution_due = Column(DateTime(timezone=True), nullable=True)
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Tagi i kategorie
    tags = Column(JSONB, default=list)
    category = Column(String(50), nullable=True)  # inquiry, complaint, follow_up, etc.
    
    # Organizacja
    organization_id = Column(String(100), nullable=True, index=True)
    
    # Relacje
    messages = relationship("InboxMessage", back_populates="conversation", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_conversations_agent_status', 'assigned_agent_id', 'status'),
        Index('idx_conversations_client', 'client_id'),
        Index('idx_conversations_org', 'organization_id', 'status'),
        Index('idx_conversations_updated', 'updated_at'),
    )


class InboxMessage(Base):
    """Pojedyncza wiadomość"""
    __tablename__ = 'inbox_messages'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id'), nullable=False)
    
    # Kanał i kierunek
    channel = Column(SQLEnum(ChannelType), nullable=False)
    direction = Column(SQLEnum(MessageDirection), nullable=False)
    
    # Treść
    content = Column(Text, nullable=False)
    content_type = Column(String(50), default="text")  # text, html, image, file
    
    # Załączniki
    attachments = Column(JSONB, default=list)  # [{"name": "", "url": "", "size": 1234}]
    
    # Nadawca/odbiorca
    sender_name = Column(String(200), nullable=True)
    sender_email = Column(String(255), nullable=True)
    sender_phone = Column(String(50), nullable=True)
    
    # Status
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.NEW)
    read_at = Column(DateTime(timezone=True), nullable=True)
    read_by = Column(String(100), nullable=True)
    
    # Metadane
    external_id = Column(String(255), nullable=True)  # ID z zewnętrznego systemu
    metadata = Column(JSONB, default=dict)  # Dodatkowe dane z kanału
    
    # Timestamps
    sent_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")
    
    __table_args__ = (
        Index('idx_messages_conversation', 'conversation_id', 'sent_at'),
        Index('idx_messages_channel', 'channel', 'created_at'),
    )


class QuickReplyTemplate(Base):
    """Szablony szybkich odpowiedzi"""
    __tablename__ = 'quick_reply_templates'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    name = Column(String(100), nullable=False)
    shortcut = Column(String(50), nullable=False)  # np. "/cena" 
    content = Column(Text, nullable=False)
    
    # Kategorie
    category = Column(String(50), nullable=True)  # greeting, pricing, availability, etc.
    
    # Dla jakich kanałów
    channels = Column(JSONB, default=list)  # ["email", "whatsapp"]
    
    # Własność
    created_by = Column(String(100), nullable=False)
    organization_id = Column(String(100), nullable=True)
    is_shared = Column(Boolean, default=True)  # Dostępne dla wszystkich agentów
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


@dataclass
class ConversationSummary:
    """Podsumowanie rozmowy"""
    conversation_id: str
    client_name: str
    subject: str
    status: str
    priority: int
    
    last_message_at: datetime
    last_message_preview: str
    message_count: int
    
    assigned_agent_id: Optional[str]
    assigned_agent_name: Optional[str]
    
    channel: str
    tags: List[str]
    
    is_unread: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.conversation_id),
            'client_name': self.client_name,
            'subject': self.subject,
            'status': self.status,
            'priority': self.priority,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'last_message_preview': self.last_message_preview,
            'message_count': self.message_count,
            'assigned_agent': self.assigned_agent_name,
            'channel': self.channel,
            'tags': self.tags,
            'is_unread': self.is_unread,
        }


class UnifiedInboxService:
    """
    Centralna skrzynka komunikacji dla biura nieruchomości.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    # ===== ROZMOWY =====
    
    async def get_or_create_conversation(
        self,
        channel: ChannelType,
        client_email: Optional[str] = None,
        client_phone: Optional[str] = None,
        client_id: Optional[uuid.UUID] = None,
        organization_id: Optional[str] = None
    ) -> Conversation:
        """Pobierz istniejącą lub utwórz nową rozmowę"""
        # Szukaj istniejącej aktywnej rozmowy
        query = self.db.query(Conversation).filter(
            Conversation.status.notin_(['resolved', 'closed'])
        )
        
        if client_id:
            query = query.filter(Conversation.client_id == client_id)
        elif client_email:
            query = query.filter(Conversation.client_email == client_email)
        elif client_phone:
            query = query.filter(Conversation.client_phone == client_phone)
        else:
            # Nie można zidentyfikować klienta - utwórz nową
            pass
        
        conversation = query.order_by(Conversation.updated_at.desc()).first()
        
        if conversation:
            return conversation
        
        # Utwórz nową rozmowę
        conversation = Conversation(
            client_id=client_id,
            client_email=client_email,
            client_phone=client_phone,
            organization_id=organization_id,
            status=ConversationStatus.ACTIVE
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation
    
    async def receive_message(
        self,
        channel: ChannelType,
        content: str,
        client_email: Optional[str] = None,
        client_phone: Optional[str] = None,
        client_name: Optional[str] = None,
        sender_name: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        external_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        organization_id: Optional[str] = None
    ) -> InboxMessage:
        """Odbierz wiadomość z dowolnego kanału"""
        # Znajdź lub utwórz rozmowę
        conversation = await self.get_or_create_conversation(
            channel=channel,
            client_email=client_email,
            client_phone=client_phone,
            organization_id=organization_id
        )
        
        # Aktualizuj dane klienta w rozmowie
        if client_name and not conversation.client_name:
            conversation.client_name = client_name
        
        # Utwórz wiadomość
        message = InboxMessage(
            conversation_id=conversation.id,
            channel=channel,
            direction=MessageDirection.INCOMING,
            content=content,
            sender_name=sender_name or client_name,
            sender_email=client_email,
            sender_phone=client_phone,
            attachments=attachments or [],
            external_id=external_id,
            metadata=metadata or {}
        )
        
        self.db.add(message)
        
        # Aktualizuj rozmowę
        conversation.message_count += 1
        conversation.last_message_at = datetime.utcnow()
        conversation.last_message_preview = content[:200] if content else ""
        conversation.updated_at = datetime.utcnow()
        
        # Ustaw SLA jeśli to pierwsza wiadomość
        if conversation.message_count == 1:
            conversation.first_response_due = datetime.utcnow() + timedelta(hours=2)
        
        self.db.commit()
        self.db.refresh(message)
        
        # Powiadom agenta (w produkcji)
        await self._notify_agents(conversation, message)
        
        logger.info(f"Received {channel.value} message in conversation {conversation.id}")
        
        return message
    
    async def send_message(
        self,
        conversation_id: uuid.UUID,
        content: str,
        agent_id: str,
        channel: Optional[ChannelType] = None,
        attachments: Optional[List[Dict]] = None
    ) -> InboxMessage:
        """Wyślij wiadomość do klienta"""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Użyj kanału z ostatniej wiadomości jeśli nie podano
        if not channel:
            last_message = self.db.query(InboxMessage).filter(
                InboxMessage.conversation_id == conversation_id
            ).order_by(InboxMessage.sent_at.desc()).first()
            
            channel = last_message.channel if last_message else ChannelType.EMAIL
        
        # Utwórz wiadomość
        message = InboxMessage(
            conversation_id=conversation_id,
            channel=channel,
            direction=MessageDirection.OUTGOING,
            content=content,
            sender_name="Agent",  # Pobierz z bazy
            attachments=attachments or [],
            status=MessageStatus.REPLIED
        )
        
        self.db.add(message)
        
        # Aktualizuj rozmowę
        conversation.message_count += 1
        conversation.last_message_at = datetime.utcnow()
        conversation.last_message_preview = content[:200] if content else ""
        conversation.updated_at = datetime.utcnow()
        conversation.status = ConversationStatus.WAITING_FOR_CLIENT
        
        # Ustaw first response jeśli pierwsza odpowiedź
        if not conversation.first_response_at:
            conversation.first_response_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(message)
        
        # Wyślij przez odpowiedni kanał (w produkcji)
        await self._send_via_channel(channel, conversation, message)
        
        return message
    
    async def assign_conversation(
        self,
        conversation_id: uuid.UUID,
        agent_id: str,
        assigned_by: str
    ) -> Optional[Conversation]:
        """Przypisz rozmowę do agenta"""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return None
        
        conversation.assigned_agent_id = agent_id
        conversation.status = ConversationStatus.WAITING_FOR_AGENT
        self.db.commit()
        
        # Dodaj notatkę wewnętrzną
        await self.add_internal_note(
            conversation_id=conversation_id,
            content=f"Rozmowa przypisana do agenta {agent_id}",
            agent_id=assigned_by
        )
        
        return conversation
    
    async def close_conversation(
        self,
        conversation_id: uuid.UUID,
        agent_id: str,
        resolution: Optional[str] = None
    ) -> Optional[Conversation]:
        """Zamknij rozmowę"""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return None
        
        conversation.status = ConversationStatus.RESOLVED
        conversation.resolved_at = datetime.utcnow()
        self.db.commit()
        
        # Dodaj notatkę
        if resolution:
            await self.add_internal_note(
                conversation_id=conversation_id,
                content=f"Rozmowa zamknięta: {resolution}",
                agent_id=agent_id
            )
        
        return conversation
    
    async def add_internal_note(
        self,
        conversation_id: uuid.UUID,
        content: str,
        agent_id: str
    ) -> InboxMessage:
        """Dodaj notatkę wewnętrzną (widoczna tylko dla agentów)"""
        message = InboxMessage(
            conversation_id=conversation_id,
            channel=ChannelType.INTERNAL,
            direction=MessageDirection.INTERNAL,
            content=content,
            sender_name=f"Agent {agent_id}",
            status=MessageStatus.READ
        )
        
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    # ===== LISTY I FILTRY =====
    
    async def get_conversations(
        self,
        organization_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        status: Optional[ConversationStatus] = None,
        channel: Optional[ChannelType] = None,
        assigned_only: bool = False,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[ConversationSummary]:
        """Pobierz listę rozmów z filtrami"""
        query = self.db.query(Conversation)
        
        if organization_id:
            query = query.filter(Conversation.organization_id == organization_id)
        
        if agent_id:
            query = query.filter(Conversation.assigned_agent_id == agent_id)
        
        if status:
            query = query.filter(Conversation.status == status)
        
        if assigned_only:
            query = query.filter(Conversation.assigned_agent_id.isnot(None))
        
        # Pobierz rozmowy
        conversations = query.order_by(
            Conversation.priority.asc(),
            Conversation.last_message_at.desc()
        ).offset(offset).limit(limit).all()
        
        summaries = []
        for conv in conversations:
            # Sprawdź czy są nieprzeczytane wiadomości
            has_unread = self.db.query(InboxMessage).filter(
                InboxMessage.conversation_id == conv.id,
                InboxMessage.status == MessageStatus.NEW,
                InboxMessage.direction == MessageDirection.INCOMING
            ).first() is not None
            
            summaries.append(ConversationSummary(
                conversation_id=str(conv.id),
                client_name=conv.client_name or "Nieznany",
                subject=conv.subject or "Bez tematu",
                status=conv.status.value,
                priority=conv.priority,
                last_message_at=conv.last_message_at,
                last_message_preview=conv.last_message_preview or "",
                message_count=conv.message_count,
                assigned_agent_id=conv.assigned_agent_id,
                assigned_agent_name=None,  # Pobierz z bazy
                channel=conv.messages[0].channel.value if conv.messages else "unknown",
                tags=conv.tags or [],
                is_unread=has_unread
            ))
        
        return summaries
    
    async def get_conversation_details(
        self,
        conversation_id: uuid.UUID,
        mark_as_read: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Pobierz szczegóły rozmowy z wiadomościami"""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return None
        
        # Oznacz jako przeczytane
        if mark_as_read:
            self.db.query(InboxMessage).filter(
                InboxMessage.conversation_id == conversation_id,
                InboxMessage.status == MessageStatus.NEW
            ).update({
                'status': MessageStatus.READ,
                'read_at': datetime.utcnow()
            })
            self.db.commit()
        
        # Pobierz wiadomości
        messages = self.db.query(InboxMessage).filter(
            InboxMessage.conversation_id == conversation_id
        ).order_by(InboxMessage.sent_at).all()
        
        return {
            'conversation': {
                'id': str(conversation.id),
                'client_name': conversation.client_name,
                'client_email': conversation.client_email,
                'client_phone': conversation.client_phone,
                'subject': conversation.subject,
                'status': conversation.status.value,
                'priority': conversation.priority,
                'tags': conversation.tags,
            },
            'messages': [
                {
                    'id': str(m.id),
                    'channel': m.channel.value,
                    'direction': m.direction.value,
                    'content': m.content,
                    'sender_name': m.sender_name,
                    'sent_at': m.sent_at.isoformat(),
                    'attachments': m.attachments,
                    'status': m.status.value,
                }
                for m in messages
            ]
        }
    
    # ===== SZABLONY =====
    
    async def create_quick_reply(
        self,
        name: str,
        shortcut: str,
        content: str,
        created_by: str,
        category: Optional[str] = None,
        channels: Optional[List[str]] = None,
        organization_id: Optional[str] = None,
        is_shared: bool = True
    ) -> QuickReplyTemplate:
        """Utwórz szablon szybkiej odpowiedzi"""
        template = QuickReplyTemplate(
            name=name,
            shortcut=shortcut,
            content=content,
            category=category,
            channels=channels or ["email", "whatsapp"],
            created_by=created_by,
            organization_id=organization_id,
            is_shared=is_shared
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    async def get_quick_replies(
        self,
        organization_id: Optional[str] = None,
        category: Optional[str] = None,
        channel: Optional[str] = None
    ) -> List[QuickReplyTemplate]:
        """Pobierz szablony szybkich odpowiedzi"""
        query = self.db.query(QuickReplyTemplate)
        
        if organization_id:
            query = query.filter(
                or_(
                    QuickReplyTemplate.organization_id == organization_id,
                    QuickReplyTemplate.is_shared == True
                )
            )
        
        if category:
            query = query.filter(QuickReplyTemplate.category == category)
        
        if channel:
            query = query.filter(QuickReplyTemplate.channels.contains([channel]))
        
        return query.order_by(QuickReplyTemplate.name).all()
    
    async def apply_quick_reply(
        self,
        conversation_id: uuid.UUID,
        template_id: uuid.UUID,
        agent_id: str
    ) -> InboxMessage:
        """Użyj szablonu do odpowiedzi"""
        template = self.db.query(QuickReplyTemplate).filter(
            QuickReplyTemplate.id == template_id
        ).first()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Personalizuj treść (w produkcji: zmienne jak {{client_name}})
        content = template.content
        
        return await self.send_message(
            conversation_id=conversation_id,
            content=content,
            agent_id=agent_id
        )
    
    # ===== STATYSTYKI =====
    
    async def get_inbox_statistics(
        self,
        organization_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Statystyki inboxu"""
        since = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(Conversation)
        
        if organization_id:
            query = query.filter(Conversation.organization_id == organization_id)
        if agent_id:
            query = query.filter(Conversation.assigned_agent_id == agent_id)
        
        # Nowe rozmowy
        new_conversations = query.filter(Conversation.created_at >= since).count()
        
        # Nieprzeczytane
        unread_messages = self.db.query(InboxMessage).filter(
            InboxMessage.status == MessageStatus.NEW,
            InboxMessage.direction == MessageDirection.INCOMING
        ).count()
        
        # Oczekujące na odpowiedź
        waiting = query.filter(Conversation.status == ConversationStatus.WAITING_FOR_AGENT).count()
        
        # Średni czas pierwszej odpowiedzi
        resolved = query.filter(
            Conversation.status == ConversationStatus.RESOLVED,
            Conversation.first_response_at.isnot(None)
        ).all()
        
        avg_response_time = 0
        if resolved:
            times = [
                (c.first_response_at - c.created_at).total_seconds() / 3600
                for c in resolved
            ]
            avg_response_time = sum(times) / len(times)
        
        return {
            'period_days': days,
            'new_conversations': new_conversations,
            'unread_messages': unread_messages,
            'waiting_for_agent': waiting,
            'avg_first_response_hours': round(avg_response_time, 1),
        }
    
    # ===== POMOCNICZE =====
    
    async def _notify_agents(self, conversation: Conversation, message: InboxMessage):
        """Powiadom agentów o nowej wiadomości"""
        # W produkcji: WebSocket, Push, Email
        logger.info(f"New message in conversation {conversation.id} - would notify agents")
    
    async def _send_via_channel(
        self,
        channel: ChannelType,
        conversation: Conversation,
        message: InboxMessage
    ):
        """Wyślij wiadomość przez odpowiedni kanał"""
        # W produkcji: integracje z WhatsApp API, Email SMTP, itp.
        logger.info(f"Would send via {channel.value}: {message.content[:50]}...")
