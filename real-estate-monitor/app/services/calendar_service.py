"""
Calendar Service - Kalendarz i Zarządzanie Terminami

System kalendarza dla agentów z planowaniem prezentacji,
otymalizacją tras i przypomnieniami.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import uuid

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, 
    Integer, Boolean, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Session
from sqlalchemy import func, and_, or_

from app.core.logging import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    """Typy wydarzeń w kalendarzu"""
    PRESENTATION = "presentation"              # Prezentacja nieruchomości
    MEETING = "meeting"                        # Spotkanie z klientem
    PHONE_CALL = "phone_call"                  # Zaplanowana rozmowa
    OPEN_HOUSE = "open_house"                  # Dzień otwarty
    PHOTO_SESSION = "photo_session"            # Sesja zdjęciowa
    DOCUMENT_SIGNING = "document_signing"      # Podpisywanie umów
    TRAINING = "training"                      # Szkolenie
    PERSONAL = "personal"                      # Prywatne
    OTHER = "other"                            # Inne


class EventStatus(str, Enum):
    """Status wydarzenia"""
    SCHEDULED = "scheduled"                    # Zaplanowane
    CONFIRMED = "confirmed"                    # Potwierdzone
    IN_PROGRESS = "in_progress"                # W trakcie
    COMPLETED = "completed"                    # Zakończone
    CANCELLED = "cancelled"                    # Odwołane
    NO_SHOW = "no_show"                        # Klient nie przyszedł
    RESCHEDULED = "rescheduled"                # Przełożone


class ReminderType(str, Enum):
    """Typ przypomnienia"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WHATSAPP = "whatsapp"


class CalendarEvent(Base):
    """Wydarzenie w kalendarzu"""
    __tablename__ = 'calendar_events'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Podstawowe informacje
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(SQLEnum(EventType), default=EventType.MEETING)
    status = Column(SQLEnum(EventStatus), default=EventStatus.SCHEDULED)
    
    # Termin
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(String(50), default='Europe/Warsaw')
    
    # Lokalizacja
    location = Column(String(255), nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    is_online = Column(Boolean, default=False)
    online_link = Column(String(500), nullable=True)  # Zoom, Meet, Teams
    
    # Powiązania
    agent_id = Column(String(100), nullable=False, index=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey('listings.id'), nullable=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=True)
    
    # Dla prezentacji
    presentation_id = Column(UUID(as_uuid=True), ForeignKey('property_presentations.id'), nullable=True)
    
    # Organizacja
    organization_id = Column(String(100), nullable=True, index=True)
    
    # Przypomnienia
    reminders = Column(JSONB, default=list)  # [{"type": "sms", "minutes_before": 30}]
    reminders_sent = Column(JSONB, default=list)  # Które przypomnienia już wysłano
    
    # Powtarzalność
    is_recurring = Column(Boolean, default=False)
    recurrence_rule = Column(JSONB, nullable=True)  # {"frequency": "weekly", "interval": 1, "days": [1, 3, 5]}
    parent_event_id = Column(UUID(as_uuid=True), nullable=True)  # Dla wydarzeń cyklicznych
    
    # Uczestnicy
    attendees = Column(JSONB, default=list)  # [{"name": "", "email": "", "phone": "", "status": "accepted"}]
    
    # Metadane
    color = Column(String(7), nullable=True)  # Hex color np. #FF5733
    tags = Column(JSONB, default=list)
    internal_notes = Column(Text, nullable=True)
    
    # Rezerwacja online (jak Calendly)
    is_bookable = Column(Boolean, default=False)  # Czy klienci mogą sami rezerwować
    booking_link = Column(String(100), nullable=True, unique=True)  # Unikalny link do rezerwacji
    booking_config = Column(JSONB, nullable=True)  # {"duration": 60, "buffer": 15, "advance_days": 14}


class CalendarAvailability(Base):
    """Dostępność agenta (godziny pracy, przerwy)"""
    __tablename__ = 'calendar_availability'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(100), nullable=False, index=True)
    
    # Dzień tygodnia (0=poniedziałek, 6=niedziela)
    day_of_week = Column(Integer, nullable=False)
    
    # Godziny pracy
    start_time = Column(String(5), nullable=False)  # HH:MM
    end_time = Column(String(5), nullable=False)
    is_working = Column(Boolean, default=True)
    
    # Przerwy (np. lunch)
    breaks = Column(JSONB, default=list)  # [{"start": "12:00", "end": "13:00", "name": "Lunch"}]
    
    # Wyjątki (urlop, choroba)
    date_from = Column(DateTime(timezone=True), nullable=True)
    date_to = Column(DateTime(timezone=True), nullable=True)
    reason = Column(String(100), nullable=True)


class RouteOptimization(Base):
    """Zoptymalizowana trasa prezentacji na dany dzień"""
    __tablename__ = 'route_optimizations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(100), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    
    # Trasa
    events_order = Column(JSONB, default=list)  # [event_id_1, event_id_2, ...]
    total_distance_km = Column(Float, nullable=True)
    total_duration_minutes = Column(Integer, nullable=True)
    
    # Szczegóły trasy
    route_details = Column(JSONB, nullable=True)  # Dla Google Maps
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


@dataclass
class TimeSlot:
    """Wolny slot czasowy"""
    start: datetime
    end: datetime
    is_available: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
            'duration_minutes': int((self.end - self.start).total_seconds() / 60),
        }


@dataclass
class DailySchedule:
    """Plan dnia agenta"""
    date: datetime
    events: List[CalendarEvent]
    route_optimized: bool = False
    total_travel_time: int = 0  # minuty
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'date': self.date.strftime('%Y-%m-%d'),
            'events': [
                {
                    'id': str(e.id),
                    'title': e.title,
                    'start': e.start_time.isoformat(),
                    'end': e.end_time.isoformat(),
                    'type': e.event_type.value,
                    'location': e.location,
                    'status': e.status.value,
                }
                for e in sorted(self.events, key=lambda x: x.start_time)
            ],
            'route_optimized': self.route_optimized,
            'total_travel_time_min': self.total_travel_time,
        }


class CalendarService:
    """
    Serwis kalendarza dla agentów nieruchomości.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    # ===== PODSTAWOWE CRUD =====
    
    async def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        agent_id: str,
        event_type: EventType = EventType.MEETING,
        **kwargs
    ) -> CalendarEvent:
        """Utwórz nowe wydarzenie w kalendarzu"""
        event = CalendarEvent(
            title=title,
            start_time=start_time,
            end_time=end_time,
            agent_id=agent_id,
            event_type=event_type,
            **kwargs
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        
        # Zaplanuj przypomnienia
        await self._schedule_reminders(event)
        
        logger.info(f"Created event: {title} at {start_time}")
        return event
    
    async def get_event(self, event_id: uuid.UUID) -> Optional[CalendarEvent]:
        """Pobierz wydarzenie"""
        return self.db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    
    async def update_event(
        self,
        event_id: uuid.UUID,
        **kwargs
    ) -> Optional[CalendarEvent]:
        """Aktualizuj wydarzenie"""
        event = await self.get_event(event_id)
        if not event:
            return None
        
        for key, value in kwargs.items():
            if hasattr(event, key):
                setattr(event, key, value)
        
        event.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        
        return event
    
    async def delete_event(self, event_id: uuid.UUID) -> bool:
        """Usuń wydarzenie"""
        event = await self.get_event(event_id)
        if not event:
            return False
        
        self.db.delete(event)
        self.db.commit()
        
        return True
    
    # ===== PREZENTACJE =====
    
    async def schedule_presentation(
        self,
        listing_id: uuid.UUID,
        agent_id: str,
        client_id: Optional[uuid.UUID],
        client_name: Optional[str],
        client_phone: Optional[str],
        client_email: Optional[str],
        scheduled_at: datetime,
        duration_minutes: int = 60,
        send_confirmation: bool = True,
        organization_id: Optional[str] = None
    ) -> CalendarEvent:
        """Zaplanuj prezentację nieruchomości"""
        from app.services.listing_management import ListingManagementService
        
        listing_service = ListingManagementService(self.db)
        listing = await listing_service.get_listing(listing_id)
        
        if not listing:
            raise ValueError(f"Listing {listing_id} not found")
        
        # Utwórz wydarzenie w kalendarzu
        end_time = scheduled_at + timedelta(minutes=duration_minutes)
        
        attendees = []
        if client_name:
            attendees.append({
                'name': client_name,
                'phone': client_phone,
                'email': client_email,
                'status': 'pending'
            })
        
        event = await self.create_event(
            title=f"Prezentacja: {listing.title[:50]}...",
            start_time=scheduled_at,
            end_time=end_time,
            agent_id=agent_id,
            event_type=EventType.PRESENTATION,
            listing_id=listing_id,
            client_id=client_id,
            location=listing.address,
            location_lat=listing.latitude,
            location_lng=listing.longitude,
            organization_id=organization_id,
            attendees=attendees,
            reminders=[
                {'type': 'push', 'minutes_before': 60},
                {'type': 'sms', 'minutes_before': 30},
            ],
            color='#4CAF50'  # Zielony dla prezentacji
        )
        
        # Utwórz też rekord prezentacji w listing_management
        presentation = await listing_service.schedule_presentation(
            listing_id=listing_id,
            agent_id=agent_id,
            scheduled_at=scheduled_at,
            client_id=client_id,
            client_name=client_name,
            client_phone=client_phone
        )
        
        # Powiąż wydarzenie z prezentacją
        event.presentation_id = presentation.id
        self.db.commit()
        
        # Wyślij potwierdzenie
        if send_confirmation and client_phone:
            await self._send_confirmation(event, client_phone)
        
        return event
    
    # ===== DOSTĘPNOŚĆ I SLOTS =====
    
    async def get_available_slots(
        self,
        agent_id: str,
        date: datetime,
        duration_minutes: int = 60,
        buffer_minutes: int = 15
    ) -> List[TimeSlot]:
        """Pobierz wolne sloty czasowe w danym dniu"""
        # Pobierz godziny pracy agenta
        day_of_week = date.weekday()
        availability = self.db.query(CalendarAvailability).filter(
            CalendarAvailability.agent_id == agent_id,
            CalendarAvailability.day_of_week == day_of_week,
            CalendarAvailability.is_working == True
        ).first()
        
        if not availability:
            return []
        
        # Parsuj godziny
        start_hour, start_min = map(int, availability.start_time.split(':'))
        end_hour, end_min = map(int, availability.end_time.split(':'))
        
        work_start = date.replace(hour=start_hour, minute=start_min, second=0)
        work_end = date.replace(hour=end_hour, minute=end_min, second=0)
        
        # Pobierz istniejące wydarzenia
        existing_events = self.db.query(CalendarEvent).filter(
            CalendarEvent.agent_id == agent_id,
            CalendarEvent.start_time >= date,
            CalendarEvent.start_time < date + timedelta(days=1),
            CalendarEvent.status.notin_(['cancelled'])
        ).order_by(CalendarEvent.start_time).all()
        
        # Uwzględnij przerwy
        breaks = availability.breaks or []
        
        # Znajdź wolne sloty
        slots = []
        current_time = work_start
        
        while current_time + timedelta(minutes=duration_minutes) <= work_end:
            slot_end = current_time + timedelta(minutes=duration_minutes)
            
            # Sprawdź czy slot nie koliduje z przerwą
            in_break = False
            for break_time in breaks:
                break_start = date.replace(
                    hour=int(break_time['start'].split(':')[0]),
                    minute=int(break_time['start'].split(':')[1])
                )
                break_end = date.replace(
                    hour=int(break_time['end'].split(':')[0]),
                    minute=int(break_time['end'].split(':')[1])
                )
                
                if current_time < break_end and slot_end > break_start:
                    in_break = True
                    current_time = break_end + timedelta(minutes=buffer_minutes)
                    break
            
            if in_break:
                continue
            
            # Sprawdź czy slot nie koliduje z wydarzeniem
            is_available = True
            for event in existing_events:
                if current_time < event.end_time and slot_end > event.start_time:
                    is_available = False
                    current_time = event.end_time + timedelta(minutes=buffer_minutes)
                    break
            
            if is_available:
                slots.append(TimeSlot(start=current_time, end=slot_end))
                current_time = slot_end + timedelta(minutes=buffer_minutes)
            
        return slots
    
    async def get_public_booking_link(
        self,
        agent_id: str,
        listing_id: Optional[uuid.UUID] = None,
        duration_minutes: int = 60,
        days_ahead: int = 14
    ) -> str:
        """Generuj link do samodzielnej rezerwacji (jak Calendly)"""
        booking_code = str(uuid.uuid4())[:8]
        
        event = CalendarEvent(
            title="Slot rezerwacyjny",
            start_time=datetime.utcnow(),  # Placeholder
            end_time=datetime.utcnow(),
            agent_id=agent_id,
            is_bookable=True,
            booking_link=booking_code,
            booking_config={
                'duration': duration_minutes,
                'buffer': 15,
                'advance_days': days_ahead,
                'listing_id': str(listing_id) if listing_id else None
            }
        )
        
        self.db.add(event)
        self.db.commit()
        
        return f"https://biuro.pl/rezerwacja/{booking_code}"
    
    # ===== OPTYMALIZACJA TRASY =====
    
    async def optimize_daily_route(
        self,
        agent_id: str,
        date: datetime
    ) -> Optional[RouteOptimization]:
        """Zoptymalizuj trasę prezentacji na dany dzień"""
        # Pobierz wszystkie wydarzenia z lokalizacją
        events = self.db.query(CalendarEvent).filter(
            CalendarEvent.agent_id == agent_id,
            CalendarEvent.start_time >= date,
            CalendarEvent.start_time < date + timedelta(days=1),
            CalendarEvent.location_lat.isnot(None),
            CalendarEvent.location_lng.isnot(None),
            CalendarEvent.status.notin_(['cancelled'])
        ).all()
        
        if len(events) < 2:
            return None
        
        # Prosty algorytm najbliższego sąsiada (można zamienić na TSP)
        # W produkcji: integracja z Google Maps Distance Matrix API
        
        sorted_events = sorted(events, key=lambda e: e.start_time)
        
        # Oblicz przybliżony dystans
        total_distance = 0
        for i in range(len(sorted_events) - 1):
            dist = self._calculate_distance(
                sorted_events[i].location_lat, sorted_events[i].location_lng,
                sorted_events[i+1].location_lat, sorted_events[i+1].location_lng
            )
            total_distance += dist
        
        route = RouteOptimization(
            agent_id=agent_id,
            date=date,
            events_order=[str(e.id) for e in sorted_events],
            total_distance_km=total_distance,
            total_duration_minutes=len(events) * 60 + int(total_distance * 2)  # 2 min na km
        )
        
        self.db.add(route)
        self.db.commit()
        
        return route
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Przybliżony dystans w km (Haversine)"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Promień Ziemi w km
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    # ===== PRZYPOMNIENIA =====
    
    async def _schedule_reminders(self, event: CalendarEvent):
        """Zaplanuj przypomnienia dla wydarzenia"""
        # W produkcji: dodaj do kolejki Celery
        pass
    
    async def _send_confirmation(self, event: CalendarEvent, phone: str):
        """Wyślij potwierdzenie rezerwacji"""
        # W produkcji: integracja z WhatsApp/SMS
        logger.info(f"Would send confirmation to {phone} for event {event.id}")
    
    # ===== DASHBOARD I STATYSTYKI =====
    
    async def get_agent_schedule(
        self,
        agent_id: str,
        date_from: datetime,
        date_to: datetime
    ) -> List[DailySchedule]:
        """Pobierz plan agenta na zakres dat"""
        events = self.db.query(CalendarEvent).filter(
            CalendarEvent.agent_id == agent_id,
            CalendarEvent.start_time >= date_from,
            CalendarEvent.start_time < date_to,
            CalendarEvent.status.notin_(['cancelled'])
        ).order_by(CalendarEvent.start_time).all()
        
        # Grupuj po dniach
        by_day = {}
        for event in events:
            day = event.start_time.date()
            if day not in by_day:
                by_day[day] = []
            by_day[day].append(event)
        
        schedules = []
        for day, day_events in sorted(by_day.items()):
            schedules.append(DailySchedule(
                date=datetime.combine(day, datetime.min.time()),
                events=day_events
            ))
        
        return schedules
    
    async def get_statistics(
        self,
        agent_id: str,
        month: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Statystyki aktywności agenta"""
        if month is None:
            month = datetime.utcnow()
        
        month_start = month.replace(day=1, hour=0, minute=0, second=0)
        if month.month == 12:
            month_end = month.replace(year=month.year + 1, month=1, day=1)
        else:
            month_end = month.replace(month=month.month + 1, day=1)
        
        # Liczba wydarzeń
        total_events = self.db.query(CalendarEvent).filter(
            CalendarEvent.agent_id == agent_id,
            CalendarEvent.start_time >= month_start,
            CalendarEvent.start_time < month_end
        ).count()
        
        # Prezentacje
        presentations = self.db.query(CalendarEvent).filter(
            CalendarEvent.agent_id == agent_id,
            CalendarEvent.event_type == EventType.PRESENTATION,
            CalendarEvent.start_time >= month_start,
            CalendarEvent.start_time < month_end
        ).count()
        
        # Spotkania
        meetings = self.db.query(CalendarEvent).filter(
            CalendarEvent.agent_id == agent_id,
            CalendarEvent.event_type == EventType.MEETING,
            CalendarEvent.start_time >= month_start,
            CalendarEvent.start_time < month_end
        ).count()
        
        # Godziny pracy (przybliżone)
        total_hours = sum([
            (e.end_time - e.start_time).total_seconds() / 3600
            for e in self.db.query(CalendarEvent).filter(
                CalendarEvent.agent_id == agent_id,
                CalendarEvent.start_time >= month_start,
                CalendarEvent.start_time < month_end
            ).all()
        ])
        
        return {
            'month': month.strftime('%Y-%m'),
            'total_events': total_events,
            'presentations': presentations,
            'meetings': meetings,
            'estimated_work_hours': round(total_hours, 1),
        }
