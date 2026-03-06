"""
Mobile API - Endpointy dla Aplikacji Mobilnej Agenta

API zoptymalizowane pod aplikację mobilną - szybkie, lekkie,
z obsługą offline i synchronizacją.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from pydantic import BaseModel, Field
import uuid

from app.core.security import get_current_user
from app.core.logging import get_logger
from app.db.session import get_db
from sqlalchemy.orm import Session

logger = get_logger(__name__)

router = APIRouter(prefix="/mobile", tags=["mobile"])


# ===== MODELE =====

class MobileListingSummary(BaseModel):
    """Skrócone dane oferty dla mobilki"""
    id: str
    title: str
    price: float
    price_formatted: str
    address: str
    city: str
    area_sqm: Optional[float]
    rooms: Optional[int]
    main_image_url: Optional[str]
    status: str
    owner_name: str
    owner_phone: str
    key_status: str
    presentation_count: int
    last_presentation_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class MobileListingDetail(BaseModel):
    """Pełne dane oferty"""
    id: str
    title: str
    description: Optional[str]
    price: float
    price_negotiable: bool
    address: str
    city: str
    district: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    area_sqm: Optional[float]
    rooms: Optional[int]
    floor: Optional[int]
    total_floors: Optional[int]
    build_year: Optional[int]
    condition: Optional[str]
    
    # Udogodnienia
    has_balcony: bool
    has_garden: bool
    has_parking: bool
    has_elevator: bool
    has_air_conditioning: bool
    is_furnished: bool
    
    # Właściciel
    owner_name: str
    owner_phone: str
    owner_email: Optional[str]
    
    # Klucze
    key_status: str
    key_location: Optional[str]
    key_code: Optional[str]
    
    # Zdjęcia
    images: List[Dict[str, str]]
    
    # Statystyki
    view_count: int
    inquiry_count: int
    presentation_count: int
    
    # Portale
    published_on_otodom: bool
    published_on_olx: bool
    published_on_facebook: bool
    
    class Config:
        from_attributes = True


class MobileClientSummary(BaseModel):
    """Skrócone dane klienta"""
    id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    status: str
    priority: str
    score: int
    budget_formatted: str
    preferred_location: Optional[str]
    last_contact_date: Optional[datetime]
    next_follow_up_date: Optional[datetime]
    assigned_listings_count: int
    
    class Config:
        from_attributes = True


class MobileEventSummary(BaseModel):
    """Wydarzenie w kalendarzu"""
    id: str
    title: str
    event_type: str
    start_time: datetime
    end_time: datetime
    location: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    client_name: Optional[str]
    client_phone: Optional[str]
    listing_id: Optional[str]
    listing_address: Optional[str]
    status: str
    
    class Config:
        from_attributes = True


class QuickAddListingRequest(BaseModel):
    """Szybkie dodawanie oferty (głos/dyktowanie)"""
    title: str
    price: float
    address: str
    city: str
    owner_phone: str
    owner_name: Optional[str] = ""
    description: Optional[str] = ""
    area_sqm: Optional[float] = None
    rooms: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    voice_note_url: Optional[str] = None  # URL do nagrania głosowego


class CompletePresentationRequest(BaseModel):
    """Zakończenie prezentacji"""
    presentation_id: str
    client_interested: bool
    client_feedback: Optional[str] = None
    agent_notes: Optional[str] = None
    offer_submitted: bool = False
    offer_amount: Optional[float] = None
    photos: Optional[List[str]] = []  # URL-e zdjęć zrobionych podczas prezentacji


class SyncRequest(BaseModel):
    """Żądanie synchronizacji"""
    last_sync_at: Optional[datetime] = None
    pending_changes: List[Dict[str, Any]] = []  # Zmiany zrobione offline


class SyncResponse(BaseModel):
    """Odpowiedź synchronizacji"""
    server_time: datetime
    changes: List[Dict[str, Any]]  # Zmiany do zastosowania
    conflicts: List[Dict[str, Any]]  # Konflikty do rozwiązania


class DashboardStats(BaseModel):
    """Statystyki na dashboard"""
    active_listings: int
    presentations_today: int
    presentations_this_week: int
    sold_this_month: int
    new_inquiries: int
    pending_follow_ups: int
    upcoming_presentations: List[MobileEventSummary]


# ===== ENDPOINTY =====

@router.get("/dashboard", response_model=DashboardStats)
async def mobile_dashboard(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dashboard agenta - podsumowanie dnia"""
    from app.services.listing_management import ListingManagementService
    from app.services.calendar_service import CalendarService
    
    listing_service = ListingManagementService(db)
    calendar_service = CalendarService(db)
    
    # Statystyki ofert
    stats = await listing_service.get_agent_dashboard(
        agent_id=current_user.id,
        organization_id=current_user.organization_id
    )
    
    # Nadchodzące prezentacje
    today = datetime.utcnow()
    tomorrow = today + timedelta(days=1)
    schedule = await calendar_service.get_agent_schedule(
        agent_id=current_user.id,
        date_from=today,
        date_to=tomorrow
    )
    
    upcoming = []
    if schedule:
        for day in schedule:
            for event in day.events:
                upcoming.append(MobileEventSummary(
                    id=str(event.id),
                    title=event.title,
                    event_type=event.event_type.value,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    location=event.location,
                    latitude=event.location_lat,
                    longitude=event.location_lng,
                    client_name=event.attendees[0]['name'] if event.attendees else None,
                    client_phone=event.attendees[0]['phone'] if event.attendees else None,
                    listing_id=str(event.listing_id) if event.listing_id else None,
                    listing_address=event.location,
                    status=event.status.value
                ))
    
    return DashboardStats(
        active_listings=stats['active_listings'],
        presentations_today=stats['presentations_today'],
        presentations_this_week=0,  # TODO
        sold_this_month=stats['sold_this_month'],
        new_inquiries=stats.get('new_inquiries', 0),
        pending_follow_ups=0,  # TODO
        upcoming_presentations=upcoming[:5]
    )


@router.get("/listings", response_model=List[MobileListingSummary])
async def mobile_listings(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista ofert (optymalizowana dla mobilki)"""
    from app.services.listing_management import ListingManagementService, Listing, ListingStatus
    
    service = ListingManagementService(db)
    
    query = db.query(Listing).filter(
        Listing.organization_id == current_user.organization_id
    )
    
    if status:
        query = query.filter(Listing.status == status)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Listing.title.ilike(search_filter)) |
            (Listing.address.ilike(search_filter)) |
            (Listing.city.ilike(search_filter))
        )
    
    # Tylko oferty przypisane do agenta lub całe biuro
    if not current_user.is_admin:
        query = query.filter(Listing.assigned_agent_id == current_user.id)
    
    listings = query.order_by(Listing.updated_at.desc()).offset(offset).limit(limit).all()
    
    result = []
    for l in listings:
        result.append(MobileListingSummary(
            id=str(l.id),
            title=l.title,
            price=l.price,
            price_formatted=f"{l.price:,.0f} zł".replace(",", " "),
            address=l.address,
            city=l.city,
            area_sqm=l.area_sqm,
            rooms=l.rooms,
            main_image_url=l.images[0].url if l.images else None,
            status=l.status.value,
            owner_name=l.owner.full_name if l.owner else "",
            owner_phone=l.owner.phone if l.owner else "",
            key_status=l.key_status.value,
            presentation_count=l.presentation_count,
            last_presentation_at=l.last_presentation_at
        ))
    
    return result


@router.get("/listings/{listing_id}", response_model=MobileListingDetail)
async def mobile_listing_detail(
    listing_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Szczegóły oferty"""
    from app.services.listing_management import ListingManagementService
    
    service = ListingManagementService(db)
    listing = await service.get_listing(uuid.UUID(listing_id))
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    return MobileListingDetail(
        id=str(listing.id),
        title=listing.title,
        description=listing.description,
        price=listing.price,
        price_negotiable=listing.price_negotiable,
        address=listing.address,
        city=listing.city,
        district=listing.district,
        latitude=listing.latitude,
        longitude=listing.longitude,
        area_sqm=listing.area_sqm,
        rooms=listing.rooms,
        floor=listing.floor,
        total_floors=listing.total_floors,
        build_year=listing.build_year,
        condition=listing.condition,
        has_balcony=listing.has_balcony,
        has_garden=listing.has_garden,
        has_parking=listing.has_parking,
        has_elevator=listing.has_elevator,
        has_air_conditioning=listing.has_air_conditioning,
        is_furnished=listing.is_furnished,
        owner_name=listing.owner.full_name if listing.owner else "",
        owner_phone=listing.owner.phone if listing.owner else "",
        owner_email=listing.owner.email if listing.owner else None,
        key_status=listing.key_status.value,
        key_location=listing.key_location,
        key_code=listing.key_code,
        images=[{"url": img.url, "thumbnail": img.thumbnail_url} for img in listing.images],
        view_count=listing.view_count,
        inquiry_count=listing.inquiry_count,
        presentation_count=listing.presentation_count,
        published_on_otodom=listing.published_on_otodom,
        published_on_olx=listing.published_on_olx,
        published_on_facebook=listing.published_on_facebook
    )


@router.post("/listings/quick-add")
async def mobile_quick_add_listing(
    request: QuickAddListingRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Szybkie dodanie oferty z terenu (głos/dyktowanie)"""
    from app.services.listing_management import ListingManagementService, PropertyOwner
    
    service = ListingManagementService(db)
    
    # Znajdź lub utwórz właściciela
    owner = await service.find_owner_by_phone(request.owner_phone)
    if not owner:
        owner = await service.create_owner(
            first_name=request.owner_name.split()[0] if request.owner_name else "",
            last_name=" ".join(request.owner_name.split()[1:]) if request.owner_name and len(request.owner_name.split()) > 1 else "",
            phone=request.owner_phone,
            organization_id=current_user.organization_id
        )
    
    # Utwórz ofertę
    listing = await service.create_listing(
        title=request.title,
        owner_id=owner.id,
        price=request.price,
        address=request.address,
        city=request.city,
        assigned_agent_id=current_user.id,
        organization_id=current_user.organization_id,
        description=request.description,
        area_sqm=request.area_sqm,
        rooms=request.rooms,
        latitude=request.latitude,
        longitude=request.longitude
    )
    
    return {
        "success": True,
        "listing_id": str(listing.id),
        "message": "Oferta dodana pomyślnie"
    }


@router.post("/listings/{listing_id}/photos")
async def mobile_upload_photos(
    listing_id: str,
    photos: List[UploadFile] = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload zdjęć z telefonu"""
    # W produkcji: upload do S3/Cloudinary
    uploaded_urls = []
    
    for photo in photos:
        # Symulacja uploadu
        url = f"https://storage.example.com/{listing_id}/{photo.filename}"
        uploaded_urls.append(url)
    
    return {
        "success": True,
        "uploaded_count": len(uploaded_urls),
        "urls": uploaded_urls
    }


@router.get("/clients", response_model=List[MobileClientSummary])
async def mobile_clients(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista klientów (leadów)"""
    from app.services.lead_management import LeadManagementService, Lead, LeadStatus
    
    service = LeadManagementService(db)
    
    leads = await service.search_leads(
        organization_id=current_user.organization_id,
        assigned_agent_id=current_user.id if not current_user.is_admin else None,
        status=LeadStatus(status) if status else None,
        search_query=search,
        limit=limit
    )
    
    result = []
    for lead in leads:
        budget = ""
        if lead.budget_min and lead.budget_max:
            budget = f"{lead.budget_min:,.0f} - {lead.budget_max:,.0f} zł"
        elif lead.budget_max:
            budget = f"do {lead.budget_max:,.0f} zł"
        elif lead.budget_min:
            budget = f"od {lead.budget_min:,.0f} zł"
        
        result.append(MobileClientSummary(
            id=str(lead.id),
            name=f"{lead.first_name} {lead.last_name}",
            phone=lead.phone,
            email=lead.email,
            status=lead.status.value,
            priority=lead.priority.name if lead.priority else "MEDIUM",
            score=lead.score,
            budget_formatted=budget,
            preferred_location=lead.preferred_location,
            last_contact_date=lead.last_contact_date,
            next_follow_up_date=lead.next_follow_up_date,
            assigned_listings_count=len(lead.interested_offers) if lead.interested_offers else 0
        ))
    
    return result


@router.get("/calendar/events", response_model=List[MobileEventSummary])
async def mobile_calendar(
    date_from: datetime,
    date_to: datetime,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Wydarzenia w kalendarzu"""
    from app.services.calendar_service import CalendarService
    
    service = CalendarService(db)
    schedule = await service.get_agent_schedule(
        agent_id=current_user.id,
        date_from=date_from,
        date_to=date_to
    )
    
    events = []
    for day in schedule:
        for event in day.events:
            events.append(MobileEventSummary(
                id=str(event.id),
                title=event.title,
                event_type=event.event_type.value,
                start_time=event.start_time,
                end_time=event.end_time,
                location=event.location,
                latitude=event.location_lat,
                longitude=event.location_lng,
                client_name=event.attendees[0]['name'] if event.attendees else None,
                client_phone=event.attendees[0]['phone'] if event.attendees else None,
                listing_id=str(event.listing_id) if event.listing_id else None,
                listing_address=event.location,
                status=event.status.value
            ))
    
    return events


@router.post("/presentations/{presentation_id}/complete")
async def mobile_complete_presentation(
    presentation_id: str,
    request: CompletePresentationRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Zakończenie prezentacji (raport z terenu)"""
    from app.services.listing_management import ListingManagementService
    
    service = ListingManagementService(db)
    
    presentation = await service.complete_presentation(
        presentation_id=uuid.UUID(presentation_id),
        client_interested=request.client_interested,
        agent_notes=request.agent_notes,
        client_feedback=request.client_feedback
    )
    
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    # Jeśli klient zainteresowany, utwórz lead
    if request.client_interested and request.offer_submitted:
        # TODO: Automatyczne tworzenie oferty kupna
        pass
    
    return {
        "success": True,
        "message": "Prezentacja zakończona",
        "next_action": "schedule_followup" if request.client_interested else "archive"
    }


@router.get("/presentations/today", response_model=List[MobileEventSummary])
async def mobile_today_presentations(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dzisiejsze prezentacje (szybki dostęp)"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    return await mobile_calendar(
        date_from=today,
        date_to=tomorrow,
        current_user=current_user,
        db=db
    )


@router.post("/sync")
async def mobile_sync(
    request: SyncRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Synchronizacja danych (offline mode)"""
    # W produkcji: obsługa zmian offline
    
    # Zastosuj zmiany z urządzenia
    for change in request.pending_changes:
        # TODO: Zastosuj zmiany
        pass
    
    # Pobierz zmiany z serwera
    changes = []  # TODO: Pobierz zmiany od last_sync_at
    
    return SyncResponse(
        server_time=datetime.utcnow(),
        changes=changes,
        conflicts=[]
    )


@router.get("/search/nearby")
async def mobile_search_nearby(
    lat: float,
    lng: float,
    radius_km: float = Query(2.0, ge=0.1, le=50),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Wyszukiwanie ofert w pobliżu (GPS)"""
    from app.services.listing_management import Listing, ListingStatus
    from math import radians, sin, cos, sqrt, atan2
    
    # Pobierz wszystkie aktywne oferty
    listings = db.query(Listing).filter(
        Listing.organization_id == current_user.organization_id,
        Listing.status == ListingStatus.ACTIVE,
        Listing.latitude.isnot(None),
        Listing.longitude.isnot(None)
    ).all()
    
    # Filtruj po odległości
    nearby = []
    R = 6371  # Promień Ziemi w km
    
    lat1, lng1 = radians(lat), radians(lng)
    
    for listing in listings:
        lat2, lng2 = radians(listing.latitude), radians(listing.longitude)
        
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        if distance <= radius_km:
            nearby.append({
                "id": str(listing.id),
                "title": listing.title,
                "price": listing.price,
                "address": listing.address,
                "distance_km": round(distance, 2),
                "latitude": listing.latitude,
                "longitude": listing.longitude
            })
    
    # Sortuj po odległości
    nearby.sort(key=lambda x: x['distance_km'])
    
    return nearby


@router.get("/quick-actions")
async def mobile_quick_actions(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Szybkie akcje na dashboardzie"""
    return {
        "actions": [
            {
                "id": "add_listing",
                "title": "Dodaj ofertę",
                "icon": "plus",
                "route": "/listings/add"
            },
            {
                "id": "add_client",
                "title": "Dodaj klienta",
                "icon": "user-plus",
                "route": "/clients/add"
            },
            {
                "id": "today_presentations",
                "title": "Dzisiejsze prezentacje",
                "icon": "calendar",
                "route": "/calendar/today"
            },
            {
                "id": "voice_note",
                "title": "Notatka głosowa",
                "icon": "mic",
                "route": "/voice-note"
            },
            {
                "id": "scan_document",
                "title": "Skanuj dokument",
                "icon": "scan",
                "route": "/scan"
            }
        ]
    }
