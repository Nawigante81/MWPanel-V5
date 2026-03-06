"""
AI Chatbot Service - Chatbot AI dla Klientów

Automatyczne odpowiadanie na pytania klientów,
kwalifikacja leadów, umawianie prezentacji.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid
import re

from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConversationStatus(str, Enum):
    """Status konwersacji"""
    ACTIVE = "active"            # Aktywna
    PAUSED = "paused"            # Wstrzymana
    CLOSED = "closed"            # Zamknięta
    ESCALATED = "escalated"      # Przekazana do agenta


class MessageType(str, Enum):
    """Typ wiadomości"""
    TEXT = "text"                # Tekst
    QUICK_REPLY = "quick_reply"  # Szybka odpowiedź
    CAROUSEL = "carousel"        # Karuzela ofert
    IMAGE = "image"              # Obraz
    LOCATION = "location"        # Lokalizacja


class Intent(str, Enum):
    """Intencja użytkownika"""
    GREETING = "greeting"                    # Powitanie
    SEARCH_PROPERTY = "search_property"      # Szukanie nieruchomości
    PRICE_INQUIRY = "price_inquiry"          # Pytanie o cenę
    VIEWING_REQUEST = "viewing_request"      # Prośba o prezentację
    CONTACT_REQUEST = "contact_request"      # Prośba o kontakt
    AVAILABILITY = "availability"            # Dostępność
    LOCATION = "location"                    # Lokalizacja
    FINANCING = "financing"                  # Finansowanie
    DOCUMENTS = "documents"                  # Dokumenty
    COMMISSION = "commission"                # Prowizja
    GOODBYE = "goodbye"                      # Pożegnanie
    UNKNOWN = "unknown"                      # Nieznana


@dataclass
class ChatMessage:
    """Wiadomość czatu"""
    id: str
    conversation_id: str
    
    # Autor
    is_from_user: bool           # True = użytkownik, False = bot
    author_id: Optional[str]     # ID użytkownika/agenta
    
    # Treść
    type: MessageType
    content: str
    quick_replies: List[Dict[str, str]] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadane
    intent: Optional[Intent] = None
    confidence: float = 0.0      # Pewność rozpoznania intencji
    
    # Czas
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'is_from_user': self.is_from_user,
            'type': self.type.value,
            'content': self.content,
            'quick_replies': self.quick_replies,
            'attachments': self.attachments,
            'intent': self.intent.value if self.intent else None,
            'confidence': round(self.confidence, 2),
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class Conversation:
    """Konwersacja z klientem"""
    id: str
    user_id: Optional[str]       # Znany użytkownik
    user_name: Optional[str]
    user_phone: Optional[str]
    user_email: Optional[str]
    
    # Status
    status: ConversationStatus
    
    # Kontekst
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Wiadomości
    messages: List[ChatMessage] = field(default_factory=list)
    
    # Lead qualification
    lead_score: int = 0          # 0-100
    lead_qualified: bool = False
    
    # Przekazanie do agenta
    assigned_agent_id: Optional[str] = None
    escalated_reason: Optional[str] = None
    
    # Daty
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user': {
                'id': self.user_id,
                'name': self.user_name,
                'phone': self.user_phone,
                'email': self.user_email,
            },
            'status': self.status.value,
            'context': self.context,
            'messages': [m.to_dict() for m in self.messages[-10:]],  # Ostatnie 10
            'lead_score': self.lead_score,
            'lead_qualified': self.lead_qualified,
            'assigned_agent': self.assigned_agent_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity_at.isoformat(),
        }


class ChatbotAIService:
    """
    Serwis chatbota AI.
    
    Automatycznie odpowiada na pytania klientów,
    kwalifikuje leady i umawia prezentacje.
    """
    
    # Słowa kluczowe dla intencji
    INTENT_KEYWORDS = {
        Intent.GREETING: ['cześć', 'witaj', 'hej', 'dzień dobry', 'dobry wieczór', 'siema', 'halo'],
        Intent.SEARCH_PROPERTY: ['szukam', 'poszukuję', 'chcę kupić', 'chcę wynająć', 'mieszkanie', 'dom', 'oferta'],
        Intent.PRICE_INQUIRY: ['cena', 'ile kosztuje', 'za ile', 'cennik', 'opłaty', 'koszt'],
        Intent.VIEWING_REQUEST: ['obejrzeć', 'zobaczyć', 'prezentacja', 'oglądanie', 'wizyta', 'spotkanie'],
        Intent.CONTACT_REQUEST: ['kontakt', 'zadzwonić', 'napisać', 'email', 'telefon', 'porozmawiać'],
        Intent.AVAILABILITY: ['dostępne', 'wolne', 'kiedy', 'termin', 'dostępność'],
        Intent.LOCATION: ['gdzie', 'lokalizacja', 'adres', 'dzielnica', 'miasto', 'okolica'],
        Intent.FINANCING: ['kredyt', 'finansowanie', 'raty', 'bank', 'hipoteka', 'gotówka'],
        Intent.DOCUMENTS: ['dokumenty', 'umowa', 'akt', 'notarialnie', 'prawnik'],
        Intent.COMMISSION: ['prowizja', 'prowizję', 'płatność', 'opłata', 'koszt biura'],
        Intent.GOODBYE: ['do widzenia', 'żegnam', 'na razie', 'dzięki', 'dziękuję'],
    }
    
    # Odpowiedzi bota
    RESPONSES = {
        Intent.GREETING: [
            "Cześć! 👋 Jestem asystentem biura nieruchomości. W czym mogę pomóc?",
            "Dzień dobry! Jestem tutaj, aby pomóc Ci znaleźć wymarzoną nieruchomość. Co Cię interesuje?",
        ],
        Intent.SEARCH_PROPERTY: [
            "Chętnie pomogę znaleźć odpowiednią nieruchomość! 🏠\n\nPowiedz mi proszę:\n"
            "• Jakiego typu szukasz? (mieszkanie/dom/działka)\n"
            "• Kupno czy wynajem?\n"
            "• Które miasto/dzielnica?\n"
            "• Jaki budżet?",
        ],
        Intent.PRICE_INQUIRY: [
            "Ceny zależą od wielu czynników: lokalizacji, metrażu, standardu. "
            "Mogę pokazać Ci oferty w Twoim budżecie. Jaki jest Twój maksymalny budżet? 💰",
        ],
        Intent.VIEWING_REQUEST: [
            "Świetnie! Chętnie umówię Cię na prezentację. 📅\n\n"
            "Która oferta Cię interesuje? Podaj adres lub ID oferty, "
            "a podam dostępne terminy.",
        ],
        Intent.CONTACT_REQUEST: [
            "Oczywiście! 📞 Możesz skontaktować się z nami:\n\n"
            "📱 Telefon: +48 123 456 789\n"
            "📧 Email: kontakt@biuro.pl\n\n"
            "Godziny pracy: Pon-Pt 9:00-18:00\n\n"
            "Czy chcesz, żebym poprosił agenta o kontakt z Tobą?",
        ],
        Intent.AVAILABILITY: [
            "Sprawdzę dostępność dla Ciebie. 📅\n\n"
            "Jaki termin Ci najbardziej odpowiada? "
            "Jesteśmy dostępni od poniedziałku do piątku w godzinach 9:00-18:00.",
        ],
        Intent.LOCATION: [
            "Mamy oferty w wielu lokalizacjach! 🗺️\n\n"
            "Powiedz mi, która dzielnica/miasto Cię interesuje, "
            "a pokażę dostępne nieruchomości w tej okolicy.",
        ],
        Intent.FINANCING: [
            "Pomagamy również w uzyskaniu kredytu! 🏦\n\n"
            "Współpracujemy z wieloma bankami i możemy pomóc Ci przejść przez cały proces. "
            "Czy chcesz, żebyśmy umówili Cię z naszym doradcą kredytowym?",
        ],
        Intent.DOCUMENTS: [
            "Dbamy o pełną transparentność i bezpieczeństwo transakcji. 📄\n\n"
            "Wspieramy Cię na każdym etapie - od przeglądu dokumentów po finalizację umowy u notariusza. "
            "Masz konkretne pytanie o dokumenty?",
        ],
        Intent.COMMISSION: [
            "Nasza prowizja jest konkurencyjna i zależy od typu transakcji. 💼\n\n"
            "Zazwyczaj wynosi 2-3% dla sprzedaży i 50-100% czynszu dla wynajmu. "
            "Szczegóły omówimy podczas pierwszego spotkania.",
        ],
        Intent.GOODBYE: [
            "Dziękuję za rozmowę! 😊 Jeśli będziesz miał więcej pytań, jestem tutaj. Miłego dnia!",
            "Do zobaczenia! 👋 Powodzenia w poszukiwaniach!",
        ],
        Intent.UNKNOWN: [
            "Przepraszam, nie do końca rozumiem. 🤔\n\n"
            "Możesz spytać mnie o:\n"
            "• Dostępne oferty\n"
            "• Ceny i prowizje\n"
            "• Umówienie prezentacji\n"
            "• Kontakt z agentem\n\n"
            "W czym mogę pomóc?",
        ],
    }
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.conversations: Dict[str, Conversation] = {}
    
    async def start_conversation(
        self,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        user_phone: Optional[str] = None,
        user_email: Optional[str] = None,
        channel: str = "website",
    ) -> Conversation:
        """Rozpocznij nową konwersację"""
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            user_name=user_name,
            user_phone=user_phone,
            user_email=user_email,
            status=ConversationStatus.ACTIVE,
            context={'channel': channel},
        )
        
        self.conversations[conversation.id] = conversation
        
        # Wyślij powitanie
        greeting = await self._generate_response(
            conversation,
            "",
            Intent.GREETING,
        )
        
        conversation.messages.append(greeting)
        
        logger.info(f"Conversation started: {conversation.id}")
        
        return conversation
    
    async def process_message(
        self,
        conversation_id: str,
        message_text: str,
    ) -> ChatMessage:
        """
        Przetwórz wiadomość od użytkownika i wygeneruj odpowiedź.
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Rozpoznaj intencję
        intent, confidence = self._detect_intent(message_text)
        
        # Zapisz wiadomość użytkownika
        user_message = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            is_from_user=True,
            author_id=conversation.user_id,
            type=MessageType.TEXT,
            content=message_text,
            intent=intent,
            confidence=confidence,
        )
        
        conversation.messages.append(user_message)
        conversation.last_activity_at = datetime.utcnow()
        
        # Aktualizuj kontekst
        self._update_context(conversation, intent, message_text)
        
        # Kwalifikuj lead
        self._qualify_lead(conversation)
        
        # Sprawdź czy przekazać do agenta
        if self._should_escalate(conversation):
            return await self._escalate_to_agent(conversation)
        
        # Generuj odpowiedź
        bot_response = await self._generate_response(
            conversation,
            message_text,
            intent,
        )
        
        conversation.messages.append(bot_response)
        
        return bot_response
    
    def _detect_intent(self, text: str) -> tuple[Intent, float]:
        """Rozpoznaj intencję z tekstu"""
        text_lower = text.lower()
        
        scores = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[intent] = score
        
        if scores:
            best_intent = max(scores, key=scores.get)
            confidence = min(scores[best_intent] / 2, 1.0)
            return best_intent, confidence
        
        return Intent.UNKNOWN, 0.0
    
    async def _generate_response(
        self,
        conversation: Conversation,
        user_message: str,
        intent: Intent,
    ) -> ChatMessage:
        """Wygeneruj odpowiedź bota"""
        responses = self.RESPONSES.get(intent, self.RESPONSES[Intent.UNKNOWN])
        
        # Wybierz odpowiedź (w zaawansowanej wersji - z kontekstem)
        content = responses[0]
        
        # Dodaj quick replies dla niektórych intencji
        quick_replies = []
        if intent == Intent.GREETING:
            quick_replies = [
                {'title': 'Szukam mieszkania', 'payload': 'search_apartment'},
                {'title': 'Szukam domu', 'payload': 'search_house'},
                {'title': 'Chcę wynająć', 'payload': 'search_rental'},
                {'title': 'Kontakt z agentem', 'payload': 'contact_agent'},
            ]
        elif intent == Intent.SEARCH_PROPERTY:
            quick_replies = [
                {'title': 'Warszawa', 'payload': 'city_warsaw'},
                {'title': 'Kraków', 'payload': 'city_krakow'},
                {'title': 'Wrocław', 'payload': 'city_wroclaw'},
                {'title': 'Inne miasto', 'payload': 'city_other'},
            ]
        
        return ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            is_from_user=False,
            author_id=None,
            type=MessageType.QUICK_REPLY if quick_replies else MessageType.TEXT,
            content=content,
            quick_replies=quick_replies,
            intent=intent,
            confidence=1.0,
        )
    
    def _update_context(
        self,
        conversation: Conversation,
        intent: Intent,
        message: str,
    ):
        """Aktualizuj kontekst konwersacji"""
        # Ekstrakcja informacji z wiadomości
        message_lower = message.lower()
        
        # Typ nieruchomości
        if 'mieszkanie' in message_lower or 'kawalerka' in message_lower:
            conversation.context['property_type'] = 'apartment'
        elif 'dom' in message_lower:
            conversation.context['property_type'] = 'house'
        elif 'działka' in message_lower:
            conversation.context['property_type'] = 'land'
        
        # Transakcja
        if 'kupić' in message_lower or 'kupno' in message_lower:
            conversation.context['transaction_type'] = 'buy'
        elif 'wynająć' in message_lower or 'wynajem' in message_lower:
            conversation.context['transaction_type'] = 'rent'
        
        # Budżet
        budget_match = re.search(r'(\d+[\s\.]?\d*)\s*(tyś|tysięcy|mln|milionów)?', message_lower)
        if budget_match:
            amount = budget_match.group(1).replace(' ', '').replace('.', '')
            multiplier = budget_match.group(2)
            if multiplier in ['tyś', 'tysięcy']:
                amount = int(amount) * 1000
            elif multiplier in ['mln', 'milionów']:
                amount = int(amount) * 1000000
            else:
                amount = int(amount)
            conversation.context['budget'] = amount
        
        # Lokalizacja
        cities = ['warszawa', 'kraków', 'wrocław', 'gdańsk', 'poznań', 'łódź', 'katowice']
        for city in cities:
            if city in message_lower:
                conversation.context['city'] = city.capitalize()
                break
    
    def _qualify_lead(self, conversation: Conversation):
        """Oceń jakość leadu"""
        score = 0
        
        # Punkty za podane informacje
        if conversation.context.get('property_type'):
            score += 20
        if conversation.context.get('transaction_type'):
            score += 15
        if conversation.context.get('budget'):
            score += 25
        if conversation.context.get('city'):
            score += 15
        if conversation.user_phone:
            score += 15
        if conversation.user_email:
            score += 10
        
        conversation.lead_score = min(score, 100)
        conversation.lead_qualified = score >= 50
    
    def _should_escalate(self, conversation: Conversation) -> bool:
        """Sprawdź czy przekazać do agenta"""
        # Przekaż jeśli lead jest wysokiej jakości
        if conversation.lead_qualified and conversation.lead_score >= 70:
            return True
        
        # Przekaż po wielu wiadomościach
        if len(conversation.messages) >= 15:
            return True
        
        # Przekaż jeśli użytkownik prosi o agenta
        last_message = conversation.messages[-1].content.lower()
        if any(word in last_message for word in ['agent', 'człowiek', 'osoba', 'dzwonie']):
            return True
        
        return False
    
    async def _escalate_to_agent(
        self,
        conversation: Conversation,
    ) -> ChatMessage:
        """Przekaż konwersację do agenta"""
        conversation.status = ConversationStatus.ESCALATED
        conversation.escalated_reason = "High quality lead"
        
        # W rzeczywistej implementacji: powiadom agentów
        
        return ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            is_from_user=False,
            author_id=None,
            type=MessageType.TEXT,
            content="Dziękuję za informacje! 🎯\n\n"
                   "Na podstawie Twoich odpowiedzi przygotowałem oferty, które mogą Cię zainteresować. "
                   "Wkrótce skontaktuje się z Tobą jeden z naszych agentów, aby omówić szczegóły.\n\n"
                   "Czy mogę jeszcze w czymś pomóc?",
        )
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Pobierz konwersację"""
        return self.conversations.get(conversation_id)
    
    async def close_conversation(
        self,
        conversation_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Zamknij konwersację"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False
        
        conversation.status = ConversationStatus.CLOSED
        conversation.closed_at = datetime.utcnow()
        
        logger.info(f"Conversation closed: {conversation_id}, reason: {reason}")
        
        return True
    
    async def assign_to_agent(
        self,
        conversation_id: str,
        agent_id: str,
    ) -> bool:
        """Przypisz konwersację do agenta"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False
        
        conversation.assigned_agent_id = agent_id
        conversation.status = ConversationStatus.ESCALATED
        
        return True
    
    async def get_active_conversations(self) -> List[Conversation]:
        """Pobierz aktywne konwersacje"""
        return [
            c for c in self.conversations.values()
            if c.status == ConversationStatus.ACTIVE
        ]
    
    async def get_qualified_leads(self) -> List[Conversation]:
        """Pobierz zakwalifikowane leady"""
        return [
            c for c in self.conversations.values()
            if c.lead_qualified and c.status != ConversationStatus.CLOSED
        ]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Statystyki chatbota"""
        total = len(self.conversations)
        active = len([c for c in self.conversations.values() if c.status == ConversationStatus.ACTIVE])
        closed = len([c for c in self.conversations.values() if c.status == ConversationStatus.CLOSED])
        escalated = len([c for c in self.conversations.values() if c.status == ConversationStatus.ESCALATED])
        qualified = len([c for c in self.conversations.values() if c.lead_qualified])
        
        avg_score = sum(c.lead_score for c in self.conversations.values()) / total if total > 0 else 0
        
        return {
            'total_conversations': total,
            'active': active,
            'closed': closed,
            'escalated': escalated,
            'qualified_leads': qualified,
            'average_lead_score': round(avg_score, 2),
            'conversion_rate': round(qualified / total * 100, 2) if total > 0 else 0,
        }


# Singleton
def get_chatbot_service(db_session: Session) -> ChatbotAIService:
    return ChatbotAIService(db_session)
