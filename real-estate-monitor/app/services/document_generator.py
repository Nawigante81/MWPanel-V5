"""
Document Generator Service - Generator Umów i Dokumentów

Automatyczne generowanie umów pośrednictwa, protokołów, 
rezerwacji z wypełnianiem danych z systemu.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import uuid
import io

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, 
    Integer, Boolean, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentType(str, Enum):
    """Typy dokumentów"""
    # Umowy pośrednictwa
    BROKERAGE_AGREEMENT_SALE = "brokerage_agreement_sale"           # Umowa pośrednictwa sprzedaży
    BROKERAGE_AGREEMENT_RENT = "brokerage_agreement_rent"           # Umowa pośrednictwa najmu
    EXCLUSIVE_AGREEMENT = "exclusive_agreement"                     # Umowa wyłączności
    
    # Rezerwacje i protokoły
    RESERVATION_AGREEMENT = "reservation_agreement"                 # Umowa rezerwacyjna
    PRESENTATION_PROTOCOL = "presentation_protocol"                 # Protokół prezentacji
    HANDOVER_PROTOCOL = "handover_protocol"                         # Protokół zdawczo-odbiorczy
    
    # Oferty i informacje
    PROPERTY_OFFER = "property_offer"                               # Oferta nieruchomości (PDF)
    CLIENT_INFORMATION = "client_information"                       # Informacja o kliencie
    
    # Inne
    POWER_OF_ATTORNEY = "power_of_attorney"                         # Pełnomocnictwo
    COMMISSION_INVOICE = "commission_invoice"                       # Faktura prowizyjna
    MARKET_REPORT = "market_report"                                 # Raport rynkowy


class DocumentStatus(str, Enum):
    """Status dokumentu"""
    DRAFT = "draft"                    # Szkic
    GENERATED = "generated"            # Wygenerowany
    SENT = "sent"                      # Wysłany do podpisu
    SIGNED = "signed"                  # Podpisany
    EXPIRED = "expired"                # Wygasł
    CANCELLED = "cancelled"            # Anulowany


class GeneratedDocument(Base):
    """Wygenerowany dokument"""
    __tablename__ = 'generated_documents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Typ i status
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.DRAFT)
    
    # Powiązania
    listing_id = Column(UUID(as_uuid=True), ForeignKey('listings.id'), nullable=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('property_owners.id'), nullable=True)
    
    # Dane do wypełnienia
    template_data = Column(JSONB, default=dict)  # Dane użyte do generowania
    
    # Pliki
    file_url = Column(String(500), nullable=True)  # URL do wygenerowanego PDF
    signed_file_url = Column(String(500), nullable=True)  # URL do podpisanego dokumentu
    
    # Podpis
    signature_required = Column(Boolean, default=True)
    signature_method = Column(String(50), nullable=True)  # docusign, autenti, manual
    signature_url = Column(String(500), nullable=True)  # Link do podpisu elektronicznego
    signed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Ważność
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Twórca
    created_by = Column(String(100), nullable=False)
    organization_id = Column(String(100), nullable=True)
    
    # Notatki
    notes = Column(Text, nullable=True)


class DocumentTemplate(Base):
    """Szablon dokumentu"""
    __tablename__ = 'document_templates'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    name = Column(String(100), nullable=False)
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    description = Column(Text, nullable=True)
    
    # Treść szablonu (HTML/Jinja2)
    template_content = Column(Text, nullable=False)
    
    # Style
    css_styles = Column(Text, nullable=True)
    header_template = Column(Text, nullable=True)
    footer_template = Column(Text, nullable=True)
    
    # Wymagane pola
    required_fields = Column(JSONB, default=list)  # ["client_name", "property_address", "price"]
    
    # Własność
    organization_id = Column(String(100), nullable=True)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)


@dataclass
class DocumentData:
    """Dane do wypełnienia dokumentu"""
    # Dane biura
    office_name: str = ""
    office_address: str = ""
    office_phone: str = ""
    office_email: str = ""
    office_nip: str = ""
    office_regon: str = ""
    agent_name: str = ""
    agent_phone: str = ""
    agent_email: str = ""
    agent_license_number: str = ""
    
    # Dane klienta/właściciela
    client_name: str = ""
    client_first_name: str = ""
    client_last_name: str = ""
    client_address: str = ""
    client_phone: str = ""
    client_email: str = ""
    client_pesel: str = ""
    client_nip: str = ""
    
    # Dane nieruchomości
    property_address: str = ""
    property_city: str = ""
    property_district: str = ""
    property_type: str = ""
    property_area: str = ""
    property_rooms: str = ""
    property_floor: str = ""
    property_build_year: str = ""
    property_book_number: str = ""  # Numer księgi wieczystej
    property_land_register: str = ""
    
    # Dane oferty
    listing_title: str = ""
    listing_price: str = ""
    listing_price_words: str = ""  # Słownie
    listing_commission_percent: str = ""
    listing_commission_amount: str = ""
    listing_exclusive: bool = False
    listing_exclusive_until: str = ""
    
    # Dane transakcji
    reservation_amount: str = ""
    reservation_date: str = ""
    payment_deadline: str = ""
    
    # Daty
    current_date: str = ""
    current_date_words: str = ""
    agreement_start_date: str = ""
    agreement_end_date: str = ""
    
    # Dodatkowe
    custom_fields: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konwertuj na słownik"""
        data = {
            'office_name': self.office_name,
            'office_address': self.office_address,
            'office_phone': self.office_phone,
            'office_email': self.office_email,
            'office_nip': self.office_nip,
            'office_regon': self.office_regon,
            'agent_name': self.agent_name,
            'agent_phone': self.agent_phone,
            'agent_email': self.agent_email,
            'agent_license_number': self.agent_license_number,
            'client_name': self.client_name,
            'client_first_name': self.client_first_name,
            'client_last_name': self.client_last_name,
            'client_address': self.client_address,
            'client_phone': self.client_phone,
            'client_email': self.client_email,
            'client_pesel': self.client_pesel,
            'client_nip': self.client_nip,
            'property_address': self.property_address,
            'property_city': self.property_city,
            'property_district': self.property_district,
            'property_type': self.property_type,
            'property_area': self.property_area,
            'property_rooms': self.property_rooms,
            'property_floor': self.property_floor,
            'property_build_year': self.property_build_year,
            'property_book_number': self.property_book_number,
            'property_land_register': self.property_land_register,
            'listing_title': self.listing_title,
            'listing_price': self.listing_price,
            'listing_price_words': self.listing_price_words,
            'listing_commission_percent': self.listing_commission_percent,
            'listing_commission_amount': self.listing_commission_amount,
            'listing_exclusive': self.listing_exclusive,
            'listing_exclusive_until': self.listing_exclusive_until,
            'reservation_amount': self.reservation_amount,
            'reservation_date': self.reservation_date,
            'payment_deadline': self.payment_deadline,
            'current_date': self.current_date or datetime.now().strftime('%d.%m.%Y'),
            'current_date_words': self.current_date_words,
            'agreement_start_date': self.agreement_start_date,
            'agreement_end_date': self.agreement_end_date,
        }
        data.update(self.custom_fields)
        return data


class DocumentGeneratorService:
    """
    Serwis generowania dokumentów dla biura nieruchomości.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    # ===== SZABLONY =====
    
    async def create_template(
        self,
        name: str,
        document_type: DocumentType,
        template_content: str,
        created_by: str,
        organization_id: Optional[str] = None,
        description: Optional[str] = None,
        required_fields: Optional[List[str]] = None,
        is_default: bool = False
    ) -> DocumentTemplate:
        """Utwórz nowy szablon dokumentu"""
        template = DocumentTemplate(
            name=name,
            document_type=document_type,
            description=description,
            template_content=template_content,
            required_fields=required_fields or [],
            organization_id=organization_id,
            is_default=is_default,
            created_at=datetime.utcnow()
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"Created document template: {name}")
        return template
    
    async def get_template(
        self,
        document_type: DocumentType,
        organization_id: Optional[str] = None
    ) -> Optional[DocumentTemplate]:
        """Pobierz szablon dla danego typu dokumentu"""
        # Najpierw szukaj w organizacji
        if organization_id:
            template = self.db.query(DocumentTemplate).filter(
                DocumentTemplate.document_type == document_type,
                DocumentTemplate.organization_id == organization_id,
                DocumentTemplate.is_active == True
            ).order_by(DocumentTemplate.is_default.desc()).first()
            
            if template:
                return template
        
        # Potem szukaj domyślnego
        return self.db.query(DocumentTemplate).filter(
            DocumentTemplate.document_type == document_type,
            DocumentTemplate.is_default == True,
            DocumentTemplate.is_active == True
        ).first()
    
    # ===== GENEROWANIE =====
    
    async def generate_document(
        self,
        document_type: DocumentType,
        data: DocumentData,
        created_by: str,
        listing_id: Optional[uuid.UUID] = None,
        client_id: Optional[uuid.UUID] = None,
        owner_id: Optional[uuid.UUID] = None,
        organization_id: Optional[str] = None,
        template_id: Optional[uuid.UUID] = None
    ) -> GeneratedDocument:
        """Wygeneruj dokument na podstawie szablonu"""
        # Pobierz szablon
        if template_id:
            template = self.db.query(DocumentTemplate).filter(
                DocumentTemplate.id == template_id
            ).first()
        else:
            template = await self.get_template(document_type, organization_id)
        
        if not template:
            raise ValueError(f"No template found for {document_type.value}")
        
        # Sprawdź wymagane pola
        missing_fields = []
        for field in template.required_fields:
            if not getattr(data, field, None):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Generuj dokument (w produkcji: HTML -> PDF)
        html_content = self._render_template(template.template_content, data.to_dict())
        
        # Zapisz dokument
        doc = GeneratedDocument(
            document_type=document_type,
            listing_id=listing_id,
            client_id=client_id,
            owner_id=owner_id,
            template_data=data.to_dict(),
            created_by=created_by,
            organization_id=organization_id,
            status=DocumentStatus.GENERATED
        )
        
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        
        # Zapisz plik (w produkcji: S3, lokalny dysk)
        file_url = f"/documents/{doc.id}.pdf"
        doc.file_url = file_url
        self.db.commit()
        
        logger.info(f"Generated document: {doc.id} ({document_type.value})")
        
        return doc
    
    def _render_template(self, template: str, data: Dict[str, Any]) -> str:
        """Renderuj szablon z danymi (prosta wersja, w produkcji: Jinja2)"""
        result = template
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value) if value is not None else "")
        return result
    
    # ===== DOKUMENTY GOTOWE DO UŻYCIA =====
    
    async def generate_brokerage_agreement(
        self,
        listing_id: uuid.UUID,
        owner_id: uuid.UUID,
        agent_id: str,
        organization_id: Optional[str] = None,
        exclusive: bool = False,
        duration_months: int = 6
    ) -> GeneratedDocument:
        """Wygeneruj umowę pośrednictwa sprzedaży"""
        from app.services.listing_management import ListingManagementService
        
        listing_service = ListingManagementService(self.db)
        listing = await listing_service.get_listing(listing_id)
        owner = await listing_service.db.query(
            ListingManagementService.db.session.query().select_from(PropertyOwner)
        ).filter(PropertyOwner.id == owner_id).first()
        
        if not listing or not owner:
            raise ValueError("Listing or owner not found")
        
        # Przygotuj dane
        data = DocumentData(
            client_name=owner.full_name,
            client_first_name=owner.first_name,
            client_last_name=owner.last_name,
            client_address=owner.address or "",
            client_phone=owner.phone,
            client_email=owner.email or "",
            property_address=listing.address,
            property_city=listing.city,
            property_district=listing.district or "",
            property_type=listing.property_type,
            property_area=str(listing.area_sqm) if listing.area_sqm else "",
            property_rooms=str(listing.rooms) if listing.rooms else "",
            property_floor=str(listing.floor) if listing.floor else "",
            property_build_year=str(listing.build_year) if listing.build_year else "",
            listing_title=listing.title,
            listing_price=f"{listing.price:,.2f}".replace(",", " "),
            listing_price_words=self._number_to_words(int(listing.price)),
            listing_commission_percent=str(listing.commission_percent),
            listing_commission_amount=f"{listing.price * listing.commission_percent / 100:,.2f}".replace(",", " "),
            listing_exclusive=exclusive,
            listing_exclusive_until=(datetime.now() + timedelta(days=30*duration_months)).strftime('%d.%m.%Y') if exclusive else "",
            agreement_start_date=datetime.now().strftime('%d.%m.%Y'),
            agreement_end_date=(datetime.now() + timedelta(days=30*duration_months)).strftime('%d.%m.%Y'),
        )
        
        doc_type = DocumentType.EXCLUSIVE_AGREEMENT if exclusive else DocumentType.BROKERAGE_AGREEMENT_SALE
        
        return await self.generate_document(
            document_type=doc_type,
            data=data,
            created_by=agent_id,
            listing_id=listing_id,
            owner_id=owner_id,
            organization_id=organization_id
        )
    
    async def generate_reservation_agreement(
        self,
        listing_id: uuid.UUID,
        client_id: uuid.UUID,
        agent_id: str,
        reservation_amount: float,
        payment_days: int = 7,
        organization_id: Optional[str] = None
    ) -> GeneratedDocument:
        """Wygeneruj umowę rezerwacyjną"""
        from app.services.listing_management import ListingManagementService
        from app.services.lead_management import Lead
        
        listing_service = ListingManagementService(self.db)
        listing = await listing_service.get_listing(listing_id)
        client = self.db.query(Lead).filter(Lead.id == client_id).first()
        
        if not listing or not client:
            raise ValueError("Listing or client not found")
        
        data = DocumentData(
            client_name=f"{client.first_name} {client.last_name}",
            client_first_name=client.first_name,
            client_last_name=client.last_name,
            client_phone=client.phone or "",
            client_email=client.email or "",
            property_address=listing.address,
            property_city=listing.city,
            listing_title=listing.title,
            listing_price=f"{listing.price:,.2f}".replace(",", " "),
            reservation_amount=f"{reservation_amount:,.2f}".replace(",", " "),
            reservation_date=datetime.now().strftime('%d.%m.%Y'),
            payment_deadline=(datetime.now() + timedelta(days=payment_days)).strftime('%d.%m.%Y'),
        )
        
        return await self.generate_document(
            document_type=DocumentType.RESERVATION_AGREEMENT,
            data=data,
            created_by=agent_id,
            listing_id=listing_id,
            client_id=client_id,
            organization_id=organization_id
        )
    
    async def generate_presentation_protocol(
        self,
        listing_id: uuid.UUID,
        client_id: uuid.UUID,
        agent_id: str,
        presentation_date: datetime,
        organization_id: Optional[str] = None
    ) -> GeneratedDocument:
        """Wygeneruj protokół prezentacji"""
        from app.services.listing_management import ListingManagementService
        from app.services.lead_management import Lead
        
        listing_service = ListingManagementService(self.db)
        listing = await listing_service.get_listing(listing_id)
        client = self.db.query(Lead).filter(Lead.id == client_id).first()
        
        if not listing or not client:
            raise ValueError("Listing or client not found")
        
        data = DocumentData(
            client_name=f"{client.first_name} {client.last_name}",
            client_first_name=client.first_name,
            client_last_name=client.last_name,
            client_address=client.requirements_notes or "",  # Fallback
            client_phone=client.phone or "",
            property_address=listing.address,
            property_city=listing.city,
            listing_title=listing.title,
            listing_price=f"{listing.price:,.2f}".replace(",", " "),
            current_date=presentation_date.strftime('%d.%m.%Y'),
        )
        
        return await self.generate_document(
            document_type=DocumentType.PRESENTATION_PROTOCOL,
            data=data,
            created_by=agent_id,
            listing_id=listing_id,
            client_id=client_id,
            organization_id=organization_id
        )
    
    # ===== POMOCNICZE =====
    
    def _number_to_words(self, number: int) -> str:
        """Konwertuj liczbę na słowa (uproszczona wersja)"""
        # W produkcji: pełna implementacja lub biblioteka
        units = ['', 'jeden', 'dwa', 'trzy', 'cztery', 'pięć', 'sześć', 'siedem', 'osiem', 'dziewięć']
        teens = ['dziesięć', 'jedenaście', 'dwanaście', 'trzynaście', 'czternaście', 'piętnaście', 
                 'szesnaście', 'siedemnaście', 'osiemnaście', 'dziewiętnaście']
        tens = ['', '', 'dwadzieścia', 'trzydzieści', 'czterdzieści', 'pięćdziesiąt', 
                'sześćdziesiąt', 'siedemdziesiąt', 'osiemdziesiąt', 'dziewięćdziesiąt']
        hundreds = ['', 'sto', 'dwieście', 'trzysta', 'czterysta', 'pięćset', 
                    'sześćset', 'siedemset', 'osiemset', 'dziewięćset']
        
        if number == 0:
            return "zero"
        
        if number < 10:
            return units[number]
        elif number < 20:
            return teens[number - 10]
        elif number < 100:
            return tens[number // 10] + (" " + units[number % 10] if number % 10 != 0 else "")
        elif number < 1000:
            return hundreds[number // 100] + (" " + self._number_to_words(number % 100) if number % 100 != 0 else "")
        elif number < 1000000:
            thousands = number // 1000
            remainder = number % 1000
            thousands_word = self._number_to_words(thousands)
            if thousands == 1:
                thousands_word = "tysiąc"
            elif thousands in [2, 3, 4]:
                thousands_word += " tysiące"
            else:
                thousands_word += " tysięcy"
            return thousands_word + (" " + self._number_to_words(remainder) if remainder != 0 else "")
        else:
            millions = number // 1000000
            remainder = number % 1000000
            millions_word = self._number_to_words(millions)
            if millions == 1:
                millions_word += " milion"
            elif millions in [2, 3, 4]:
                millions_word += " miliony"
            else:
                millions_word += " milionów"
            return millions_word + (" " + self._number_to_words(remainder) if remainder != 0 else "")
    
    # ===== DOMYŚLNE SZABLONY =====
    
    async def create_default_templates(self, organization_id: Optional[str] = None):
        """Utwórz domyślne szablony dokumentów"""
        
        # Umowa pośrednictwa sprzedaży
        brokerage_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }
        h1 { text-align: center; font-size: 18px; margin-bottom: 30px; }
        .section { margin-bottom: 20px; }
        .signature { margin-top: 50px; }
        .signature-line { border-top: 1px solid #000; width: 200px; margin-top: 50px; }
    </style>
</head>
<body>
    <h1>UMOWA POŚREDNICTWA W SPRZEDAŻY NIERUCHOMOŚCI</h1>
    
    <div class="section">
        <p><strong>Zawarta w dniu {{current_date}} r. w {{property_city}} pomiędzy:</strong></p>
        <p>{{office_name}} z siedzibą w {{office_address}}, NIP: {{office_nip}}, REGON: {{office_regon}}, 
        reprezentowanym przez {{agent_name}} - dalej zwanym "Pośrednikiem",</p>
        <p><strong>a</strong></p>
        <p>{{client_name}}, zamieszkałym: {{client_address}}, tel: {{client_phone}} - dalej zwanym "Zleceniodawcą"</p>
    </div>
    
    <div class="section">
        <h2>§ 1. PRZEDMIOT UMOWY</h2>
        <p>1. Zleceniodawca zleca Pośrednikowi, a Pośrednik przyjmuje do realizacji zadanie polegające 
        na poszukiwaniu kupującego na następującą nieruchomość:</p>
        <p><strong>Adres:</strong> {{property_address}}, {{property_city}}</p>
        <p><strong>Typ:</strong> {{property_type}}</p>
        <p><strong>Powierzchnia:</strong> {{property_area}} m²</p>
        <p><strong>Liczba pokoi:</strong> {{property_rooms}}</p>
        <p><strong>Cena:</strong> {{listing_price}} zł (słownie: {{listing_price_words}} złotych)</p>
    </div>
    
    <div class="section">
        <h2>§ 2. WYSOKOŚĆ I TERMIN WYPŁATY WYNAGRODZENIA</h2>
        <p>1. Za wykonanie usługi pośrednictwa Zleceniodawca zobowiązuje się zapłacić Pośrednikowi 
        wynagrodzenie w wysokości {{listing_commission_percent}}% od ceny sprzedaży, 
        nie mniej jednak niż {{listing_commission_amount}} zł.</p>
        <p>2. Wynagrodzenie staje się wymagalne w dniu zawarcia umowy sprzedaży nieruchomości.</p>
    </div>
    
    <div class="section">
        <h2>§ 3. CZAS TRWANIA UMOWY</h2>
        <p>Umowa zostaje zawarta na czas oznaczony od {{agreement_start_date}} do {{agreement_end_date}}.</p>
    </div>
    
    <div class="signature">
        <table style="width: 100%;">
            <tr>
                <td style="width: 50%;">
                    <p>..................................</p>
                    <p>(podpis Pośrednika)</p>
                </td>
                <td style="width: 50%;">
                    <p>..................................</p>
                    <p>(podpis Zleceniodawcy)</p>
                </td>
            </tr>
        </table>
    </div>
</body>
</html>
"""
        
        await self.create_template(
            name="Umowa pośrednictwa sprzedaży",
            document_type=DocumentType.BROKERAGE_AGREEMENT_SALE,
            template_content=brokerage_template,
            created_by="system",
            organization_id=organization_id,
            required_fields=[
                'office_name', 'office_address', 'office_nip', 'agent_name',
                'client_name', 'client_address', 'property_address', 'property_city',
                'listing_price', 'listing_commission_percent'
            ],
            is_default=True
        )
        
        # Protokół prezentacji
        presentation_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { text-align: center; font-size: 16px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        td, th { border: 1px solid #000; padding: 10px; }
    </style>
</head>
<body>
    <h1>PROTOKÓŁ PREZENTACJI NIERUCHOMOŚCI</h1>
    
    <table>
        <tr>
            <td><strong>Data prezentacji:</strong></td>
            <td>{{current_date}}</td>
        </tr>
        <tr>
            <td><strong>Adres nieruchomości:</strong></td>
            <td>{{property_address}}, {{property_city}}</td>
        </tr>
        <tr>
            <td><strong>Cena:</strong></td>
            <td>{{listing_price}} zł</td>
        </tr>
        <tr>
            <td><strong>Klient:</strong></td>
            <td>{{client_name}}<br>Tel: {{client_phone}}</td>
        </tr>
        <tr>
            <td><strong>Agent:</strong></td>
            <td>{{agent_name}}<br>{{office_name}}</td>
        </tr>
    </table>
    
    <p style="margin-top: 30px;">
        Ja niżej podpisany/a oświadczam, że zapoznałem/am się z powyższą nieruchomością 
        w obecności agenta {{office_name}}.
    </p>
    
    <p style="margin-top: 50px;">
        ....................................................<br>
        (podpis klienta)
    </p>
    
    <p style="margin-top: 30px; font-size: 12px; color: #666;">
        Podpisując ten protokół klient potwierdza, że nieruchomość została mu zaprezentowana 
        przez {{office_name}}. W przypadku zakupu tej nieruchomości w ciągu 12 miesięcy 
        od daty prezentacji, klient zobowiązuje się do zapłaty prowizji dla biura.
    </p>
</body>
</html>
"""
        
        await self.create_template(
            name="Protokół prezentacji",
            document_type=DocumentType.PRESENTATION_PROTOCOL,
            template_content=presentation_template,
            created_by="system",
            organization_id=organization_id,
            required_fields=['property_address', 'property_city', 'client_name', 'agent_name'],
            is_default=True
        )
        
        logger.info("Default document templates created")
