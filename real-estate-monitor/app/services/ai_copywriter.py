"""
AI Copywriter Service - Inteligentny Generator Opisów Ofert

Automatyczne generowanie profesjonalnych, unikalnych opisów nieruchomości
na podstawie parametrów, zdjęć i lokalizacji.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import random

from app.core.logging import get_logger

logger = get_logger(__name__)


class DescriptionTone(str, Enum):
    """Ton opisu"""
    PROFESSIONAL = "professional"      # Profesjonalny, formalny
    FRIENDLY = "friendly"              # Przyjazny, ciepły
    LUXURY = "luxury"                  # Ekskluzywny, prestiżowy
    DYNAMIC = "dynamic"                # Dynamiczny, zachęcający
    INFORMATIVE = "informative"        # Informacyjny, szczegółowy


class PropertyHighlight(str, Enum):
    """Wyróżniki nieruchomości"""
    LOCATION = "location"              # Lokalizacja
    PRICE = "price"                    # Cena
    SIZE = "size"                      # Powierzchnia
    CONDITION = "condition"            # Stan
    VIEW = "view"                      # Widok
    GARDEN = "garden"                  # Ogród
    BALCONY = "balcony"                # Balkon
    PARKING = "parking"                # Parking
    QUIET = "quiet"                    # Cichość
    SUNNY = "sunny"                    # Nasłonecznienie
    MODERN = "modern"                  # Nowoczesność
    RENOVATED = "renovated"            # Po remoncie


@dataclass
class GeneratedDescription:
    """Wygenerowany opis"""
    title: str
    description: str
    highlights: List[str]
    key_features: List[str]
    call_to_action: str
    seo_keywords: List[str]
    
    # Metadane
    tone: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'description': self.description,
            'highlights': self.highlights,
            'key_features': self.key_features,
            'call_to_action': self.call_to_action,
            'seo_keywords': self.seo_keywords,
            'tone': self.tone,
            'generated_at': self.generated_at.isoformat(),
        }


class AICopywriterService:
    """
    Serwis AI do generowania opisów ofert nieruchomości.
    
    W produkcji można zintegrować z OpenAI GPT, Claude, lub lokalnym modelem.
    Obecnie używamy zaawansowanych szablonów z wariacjami.
    """
    
    # Szablony tytułów
    TITLE_TEMPLATES = {
        PropertyHighlight.LOCATION: [
            "{rooms}-pokojowe w świetnej lokalizacji - {district}",
            "Przestronne mieszkanie w {district} - blisko centrum",
            "Idealna lokalizacja! {property_type} w {district}",
        ],
        PropertyHighlight.PRICE: [
            "{rooms}-pokojowe w atrakcyjnej cenie!",
            "Okazja! {area} m² w {district}",
            "Bardzo dobra cena za {rooms}-pokojowe w {city}",
        ],
        PropertyHighlight.SIZE: [
            "Przestronne {area} m² w {district}",
            "Duże {rooms}-pokojowe - {area} m²",
            "Rodzinne mieszkanie {area} m² w {district}",
        ],
        PropertyHighlight.CONDITION: [
            "Gotowe do zamieszkania! {rooms}-pokojowe w {district}",
            "Świeżo po remoncie - {rooms}-pokojowe w {district}",
            "Wysoki standard - {property_type} w {district}",
        ],
        PropertyHighlight.GARDEN: [
            "Z ogródkiem! {rooms}-pokojowe w {district}",
            "Przytulne z ogrodem - {area} m² w {district}",
            "Idealne dla rodziny - z ogródkiem w {district}",
        ],
        PropertyHighlight.BALCONY: [
            "Z balkonem! {rooms}-pokojowe w {district}",
            "Przytulny balkon - {rooms}-pokojowe w {district}",
        ],
        PropertyHighlight.PARKING: [
            "Z parkingiem! {rooms}-pokojowe w {district}",
            "Miejsce parkingowe w cenie - {rooms}-pokojowe",
        ],
        PropertyHighlight.VIEW: [
            "Z pięknym widokiem! {rooms}-pokojowe w {district}",
            "Widok na panoramę miasta - {rooms}-pokojowe",
        ],
        PropertyHighlight.QUIET: [
            "Ciche i spokojne - {rooms}-pokojowe w {district}",
            "Z dala od hałasu - {rooms}-pokojowe w {district}",
        ],
        PropertyHighlight.SUNNY: [
            "Słoneczne {rooms}-pokojowe w {district}",
            "Jasne i przestronne - {rooms}-pokojowe",
        ],
    }
    
    # Szablony wstępów
    INTRO_TEMPLATES = {
        DescriptionTone.PROFESSIONAL: [
            "Mamy przyjemność zaprezentować Państwu {property_type} o powierzchni {area} m², zlokalizowane w {district}.",
            "Prezentujemy na sprzedaż {property_type} o powierzchni {area} m², usytuowane w {district}.",
            "Oferta sprzedaży {property_type} o powierzchni {area} m² w {district}.",
        ],
        DescriptionTone.FRIENDLY: [
            "Serdecznie zapraszam do zapoznania się z tym uroczym mieszkaniem w {district}!",
            "Chciałbym przedstawić Ci to wyjątkowe mieszkanie w {district}.",
            "Zobacz to przytulne {rooms}-pokojowe mieszkanie w świetnej lokalizacji!",
        ],
        DescriptionTone.LUXURY: [
            "Ekskluzywna rezydencja w prestiżowej dzielnicy {district}.",
            "Luksusowe {property_type} w najlepszej lokalizacji {district}.",
            "Prestiżowa nieruchomość w ekskluzywnej dzielnicy {district}.",
        ],
        DescriptionTone.DYNAMIC: [
            "Nie przegap tej okazji! {property_type} w świetnej lokalizacji {district}.",
            "Szybko znikające z rynku! {property_type} w {district}.",
            "Ostatnie takie mieszkanie w tej cenie! {property_type} w {district}.",
        ],
    }
    
    # Szablony opisu pomieszczeń
    ROOMS_TEMPLATES = [
        "Mieszkanie składa się z {rooms} pokoi: {room_list}.",
        "Rozkład pomieszczeń: {room_list}.",
        "W skład nieruchomości wchodzą: {room_list}.",
    ]
    
    # Szablony lokalizacji
    LOCATION_TEMPLATES = {
        "transport": [
            "Doskonała komunikacja - w pobliżu przystanki autobusowe i tramwajowe.",
            "Świetny dojazd do centrum - blisko przystanki komunikacji miejskiej.",
            "Dogodny dojazd do centrum miasta.",
        ],
        "shops": [
            "W okolicy sklepy, apteki i punkty usługowe.",
            "Blisko centrum handlowego i sklepów spożywczych.",
            "W pobliżu pełna infrastruktura handlowo-usługowa.",
        ],
        "schools": [
            "W sąsiedztwie szkoły i przedszkola.",
            "Dobry dostęp do placówek edukacyjnych.",
            "Blisko szkoły i placówki oświatowe.",
        ],
        "green": [
            "W pobliżu parki i tereny zielone.",
            "Bliskość natury - parki i ścieżki rowerowe.",
            "Spokojna okolina z dużą ilością zieleni.",
        ],
    }
    
    # Szablony zachęt
    CALLS_TO_ACTION = {
        DescriptionTone.PROFESSIONAL: [
            "Zapraszamy na prezentację. Więcej informacji udzieli Państwu nasz agent.",
            "Polecam i zapraszam do kontaktu w celu umówienia prezentacji.",
            "Serdecznie zapraszam do obejrzenia nieruchomości.",
        ],
        DescriptionTone.FRIENDLY: [
            "Chętnie odpowiem na pytania i umówię prezentację!",
            "Zapraszam na oględziny - zadzwoń lub napisz!",
            "Nie czekaj, umów się na prezentację już dziś!",
        ],
        DescriptionTone.LUXURY: [
            "Prezentacje dla poważnie zainteresowanych klientów.",
            "Zapraszamy do kontaktu - ta nieruchomość nie czeka długo.",
            "Luksusowe nieruchomości wymagają wyjątkowych klientów.",
        ],
        DescriptionTone.DYNAMIC: [
            "Śpiesz się! Takie oferty znikają w kilka dni!",
            "Nie przegap okazji - zadzwoń teraz!",
            "Ostatnie wolne terminy na prezentację!",
        ],
    }
    
    # Słowa kluczowe SEO
    SEO_KEYWORDS = [
        "mieszkanie na sprzedaż",
        "mieszkanie",
        "sprzedaż",
        "nieruchomość",
        "dom",
        "apartament",
        "kawalerka",
        "mieszkanie rodzinne",
        "inwestycja",
        "okazja",
    ]
    
    def __init__(self):
        pass
    
    async def generate_description(
        self,
        property_type: str,
        area_sqm: float,
        rooms: int,
        city: str,
        district: str,
        price: float,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        build_year: Optional[int] = None,
        condition: Optional[str] = None,
        has_balcony: bool = False,
        has_garden: bool = False,
        has_parking: bool = False,
        has_elevator: bool = False,
        is_furnished: bool = False,
        tone: DescriptionTone = DescriptionTone.PROFESSIONAL,
        custom_highlights: Optional[List[PropertyHighlight]] = None
    ) -> GeneratedDescription:
        """
        Generuj opis oferty na podstawie parametrów.
        """
        # Określ główne wyróżniki
        highlights = custom_highlights or self._determine_highlights(
            area_sqm, rooms, has_garden, has_balcony, has_parking, price, condition
        )
        
        # Generuj tytuł
        title = self._generate_title(
            property_type, rooms, area_sqm, city, district, highlights
        )
        
        # Generuj wstęp
        intro = self._generate_intro(
            property_type, area_sqm, district, rooms, tone
        )
        
        # Generuj opis pomieszczeń
        rooms_desc = self._generate_rooms_description(rooms)
        
        # Generuj opis lokalizacji
        location_desc = self._generate_location_description(district)
        
        # Generuj opis stanu/standardu
        condition_desc = self._generate_condition_description(condition, build_year)
        
        # Generuj opis udogodnień
        features_desc = self._generate_features_description(
            has_balcony, has_garden, has_parking, has_elevator, is_furnished
        )
        
        # Generuj zachętę
        call_to_action = self._generate_call_to_action(tone)
        
        # Połącz wszystko
        description_parts = [
            intro,
            "",
            rooms_desc,
            "",
            features_desc,
            "",
            condition_desc,
            "",
            location_desc,
            "",
            call_to_action,
        ]
        
        description = "\n".join(filter(None, description_parts))
        
        # Wygeneruj listę kluczowych cech
        key_features = self._generate_key_features(
            area_sqm, rooms, floor, total_floors, build_year,
            has_balcony, has_garden, has_parking, has_elevator
        )
        
        # Wygeneruj słowa kluczowe SEO
        seo_keywords = self._generate_seo_keywords(
            property_type, rooms, city, district
        )
        
        return GeneratedDescription(
            title=title,
            description=description,
            highlights=[h.value for h in highlights],
            key_features=key_features,
            call_to_action=call_to_action,
            seo_keywords=seo_keywords,
            tone=tone.value
        )
    
    def _determine_highlights(
        self,
        area_sqm: float,
        rooms: int,
        has_garden: bool,
        has_balcony: bool,
        has_parking: bool,
        price: float,
        condition: Optional[str]
    ) -> List[PropertyHighlight]:
        """Określ główne wyróżniki nieruchomości"""
        highlights = []
        
        if area_sqm > 70:
            highlights.append(PropertyHighlight.SIZE)
        
        if has_garden:
            highlights.append(PropertyHighlight.GARDEN)
        elif has_balcony:
            highlights.append(PropertyHighlight.BALCONY)
        
        if has_parking:
            highlights.append(PropertyHighlight.PARKING)
        
        if condition and condition.lower() in ['excellent', 'very_good', 'po_remocie']:
            highlights.append(PropertyHighlight.CONDITION)
        
        if not highlights:
            highlights.append(PropertyHighlight.LOCATION)
        
        return highlights[:2]  # Max 2 główne wyróżniki
    
    def _generate_title(
        self,
        property_type: str,
        rooms: int,
        area_sqm: float,
        city: str,
        district: str,
        highlights: List[PropertyHighlight]
    ) -> str:
        """Generuj tytuł oferty"""
        # Wybierz szablon na podstawie głównego wyróżnika
        main_highlight = highlights[0] if highlights else PropertyHighlight.LOCATION
        
        templates = self.TITLE_TEMPLATES.get(main_highlight, self.TITLE_TEMPLATES[PropertyHighlight.LOCATION])
        template = random.choice(templates)
        
        # Wypełnij szablon
        title = template.format(
            rooms=rooms,
            area=int(area_sqm),
            city=city,
            district=district,
            property_type=property_type
        )
        
        return title
    
    def _generate_intro(
        self,
        property_type: str,
        area_sqm: float,
        district: str,
        rooms: int,
        tone: DescriptionTone
    ) -> str:
        """Generuj wstęp opisu"""
        templates = self.INTRO_TEMPLATES.get(tone, self.INTRO_TEMPLATES[DescriptionTone.PROFESSIONAL])
        template = random.choice(templates)
        
        return template.format(
            property_type=property_type,
            area=int(area_sqm),
            district=district,
            rooms=rooms
        )
    
    def _generate_rooms_description(self, rooms: int) -> str:
        """Generuj opis układu pomieszczeń"""
        if rooms == 1:
            room_list = "salon z aneksem kuchennym, łazienka"
        elif rooms == 2:
            room_list = "salon z aneksem kuchennym, sypialnia, łazienka"
        elif rooms == 3:
            room_list = "salon z aneksem kuchennym, dwie sypialnie, łazienka"
        elif rooms == 4:
            room_list = "salon z kuchnią, trzy sypialnie, łazienka, dodatkowa toaleta"
        else:
            room_list = f"salon z kuchnią, {rooms-1} sypialni, łazienka"
        
        template = random.choice(self.ROOMS_TEMPLATES)
        return template.format(rooms=rooms, room_list=room_list)
    
    def _generate_location_description(self, district: str) -> str:
        """Generuj opis lokalizacji"""
        parts = []
        
        # Losowo wybierz aspekty lokalizacji
        aspects = random.sample(list(self.LOCATION_TEMPLATES.keys()), 
                               min(3, len(self.LOCATION_TEMPLATES)))
        
        for aspect in aspects:
            template = random.choice(self.LOCATION_TEMPLATES[aspect])
            parts.append(template)
        
        return " ".join(parts)
    
    def _generate_condition_description(
        self,
        condition: Optional[str],
        build_year: Optional[int]
    ) -> str:
        """Generuj opis stanu/standardu"""
        parts = []
        
        if condition:
            condition_desc = {
                'excellent': "Nieruchomość w doskonałym stanie, gotowa do zamieszkania.",
                'very_good': "Mieszkanie w bardzo dobrym stanie technicznym.",
                'good': "Mieszkanie w dobrym stanie, nie wymaga większych nakładów.",
                'average': "Mieszkanie do odświeżenia.",
                'poor': "Mieszkanie do remontu - idealna okazja do aranżacji według własnego pomysłu.",
                'renovation_needed': "Mieszkanie do remontu - idealna okazja do aranżacji według własnego pomysłu.",
            }
            parts.append(condition_desc.get(condition.lower(), ""))
        
        if build_year:
            current_year = datetime.now().year
            age = current_year - build_year
            
            if age < 5:
                parts.append(f"Budynek z {build_year} roku - nowoczesna konstrukcja.")
            elif age < 20:
                parts.append(f"Budynek z {build_year} roku.")
            else:
                parts.append(f"Kamienica z {build_year} roku - solidna konstrukcja.")
        
        return " ".join(parts)
    
    def _generate_features_description(
        self,
        has_balcony: bool,
        has_garden: bool,
        has_parking: bool,
        has_elevator: bool,
        is_furnished: bool
    ) -> str:
        """Generuj opis udogodnień"""
        features = []
        
        if has_garden:
            features.append("Ogród - idealny do relaksu i spędzania czasu na świeżym powietrzu.")
        elif has_balcony:
            features.append("Balkon - doskonałe miejsce na poranną kawę.")
        
        if has_parking:
            features.append("Miejsce parkingowe - duża zaleta w tej lokalizacji.")
        
        if has_elevator:
            features.append("Winda w budynku.")
        
        if is_furnished:
            features.append("Mieszkanie umeblowane - można wprowadzić się od razu.")
        
        return " ".join(features)
    
    def _generate_call_to_action(self, tone: DescriptionTone) -> str:
        """Generuj zachętę do kontaktu"""
        templates = self.CALLS_TO_ACTION.get(tone, self.CALLS_TO_ACTION[DescriptionTone.PROFESSIONAL])
        return random.choice(templates)
    
    def _generate_key_features(
        self,
        area_sqm: float,
        rooms: int,
        floor: Optional[int],
        total_floors: Optional[int],
        build_year: Optional[int],
        has_balcony: bool,
        has_garden: bool,
        has_parking: bool,
        has_elevator: bool
    ) -> List[str]:
        """Generuj listę kluczowych cech"""
        features = [
            f"Powierzchnia: {area_sqm} m²",
            f"Liczba pokoi: {rooms}",
        ]
        
        if floor is not None and total_floors:
            features.append(f"Piętro: {floor}/{total_floors}")
        
        if build_year:
            features.append(f"Rok budowy: {build_year}")
        
        if has_balcony:
            features.append("Balkon")
        
        if has_garden:
            features.append("Ogród")
        
        if has_parking:
            features.append("Miejsce parkingowe")
        
        if has_elevator:
            features.append("Winda")
        
        return features
    
    def _generate_seo_keywords(
        self,
        property_type: str,
        rooms: int,
        city: str,
        district: str
    ) -> List[str]:
        """Generuj słowa kluczowe SEO"""
        keywords = [
            f"mieszkanie {rooms}-pokojowe {city}",
            f"mieszkanie {district}",
            f"{property_type} na sprzedaż {city}",
            f"nieruchomość {district}",
            f"kupię mieszkanie {city}",
        ]
        
        return keywords
    
    async def generate_variations(
        self,
        property_type: str,
        area_sqm: float,
        rooms: int,
        city: str,
        district: str,
        price: float,
        count: int = 3
    ) -> List[GeneratedDescription]:
        """Generuj kilka wariantów opisu"""
        variations = []
        tones = [DescriptionTone.PROFESSIONAL, DescriptionTone.FRIENDLY, DescriptionTone.DYNAMIC]
        
        for i in range(min(count, len(tones))):
            desc = await self.generate_description(
                property_type=property_type,
                area_sqm=area_sqm,
                rooms=rooms,
                city=city,
                district=district,
                price=price,
                tone=tones[i]
            )
            variations.append(desc)
        
        return variations
    
    async def translate_description(
        self,
        description: str,
        target_language: str = "en"
    ) -> str:
        """
        Tłumacz opis na inny język.
        W produkcji: integracja z API tłumacza (Google Translate, DeepL)
        """
        # Placeholder - w produkcji prawdziwe tłumaczenie
        logger.info(f"Would translate description to {target_language}")
        return description


# Funkcja pomocnicza do szybkiego generowania

async def quick_generate_description(
    area_sqm: float,
    rooms: int,
    city: str,
    district: str,
    price: float,
    **kwargs
) -> Dict[str, Any]:
    """Szybkie generowanie opisu"""
    service = AICopywriterService()
    
    result = await service.generate_description(
        property_type="mieszkanie",
        area_sqm=area_sqm,
        rooms=rooms,
        city=city,
        district=district,
        price=price,
        **kwargs
    )
    
    return result.to_dict()
