#!/usr/bin/env python3
"""
Skrypt seedujący dane do bazy dla MVP.
Uruchom: python seed_data.py
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Konfiguracja bazy
DATABASE_URL = "postgresql+asyncpg://realestate:dev_password@localhost:5432/realestate_dev"

# Dane seed
LISTINGS = [
    {
        "title": "Mieszkanie 3-pokojowe, 65m², Warszawa Mokotów",
        "price": 650000,
        "currency": "PLN",
        "city": "Warszawa",
        "district": "Mokotów",
        "street": "ul. Puławska 123",
        "area_sqm": 65,
        "rooms": 3,
        "floor": 3,
        "total_floors": 5,
        "year_built": 2010,
        "property_type": "apartment",
        "transaction_type": "sale",
        "status": "active",
        "description": "Przestronne mieszkanie w świetnej lokalizacji. Blisko metro, sklepy, park.",
        "owner_name": "Anna Nowak",
        "owner_phone": "+48 500 123 456",
        "owner_email": "anna.nowak@example.com",
        "commission_percent": 2.5,
    },
    {
        "title": "Dom wolnostojący 150m², Kraków Podgórze",
        "price": 1200000,
        "currency": "PLN",
        "city": "Kraków",
        "district": "Podgórze",
        "street": "ul. Wielicka 45",
        "area_sqm": 150,
        "rooms": 5,
        "floor": 0,
        "total_floors": 2,
        "year_built": 2015,
        "property_type": "house",
        "transaction_type": "sale",
        "status": "active",
        "description": "Nowoczesny dom z ogrodem i garażem. Spokojna okolica.",
        "owner_name": "Piotr Kowalski",
        "owner_phone": "+48 501 234 567",
        "owner_email": "piotr.kowalski@example.com",
        "commission_percent": 2.0,
    },
    {
        "title": "Kawalerka 32m² do wynajęcia, Wrocław Śródmieście",
        "price": 2500,
        "currency": "PLN",
        "city": "Wrocław",
        "district": "Śródmieście",
        "street": "ul. Oławska 8",
        "area_sqm": 32,
        "rooms": 1,
        "floor": 2,
        "total_floors": 4,
        "year_built": 2005,
        "property_type": "apartment",
        "transaction_type": "rent",
        "status": "active",
        "description": "Przytulna kawalerka w centrum. Dostępna od zaraz.",
        "owner_name": "Maria Wiśniewska",
        "owner_phone": "+48 502 345 678",
        "owner_email": "maria.w@example.com",
        "commission_percent": 100,
    },
    {
        "title": "Działka budowlana 1000m², Poznań",
        "price": 350000,
        "currency": "PLN",
        "city": "Poznań",
        "district": "Nowe Miasto",
        "street": "ul. Działkowa 12",
        "area_sqm": 1000,
        "property_type": "land",
        "transaction_type": "sale",
        "status": "reserved",
        "description": "Piękna działka z widokiem. Wszystkie media.",
        "owner_name": "Tomasz Zieliński",
        "owner_phone": "+48 503 456 789",
        "commission_percent": 3.0,
    },
    {
        "title": "Lokal usługowy 80m², Gdańsk Wrzeszcz",
        "price": 450000,
        "currency": "PLN",
        "city": "Gdańsk",
        "district": "Wrzeszcz",
        "street": "ul. Grunwaldzka 156",
        "area_sqm": 80,
        "rooms": 2,
        "floor": 0,
        "total_floors": 3,
        "year_built": 2000,
        "property_type": "commercial",
        "transaction_type": "sale",
        "status": "sold",
        "description": "Lokal w świetnej lokalizacji handlowej.",
        "owner_name": "Firma XYZ Sp. z o.o.",
        "owner_phone": "+48 504 567 890",
        "owner_email": "kontakt@firma-xyz.pl",
        "commission_percent": 2.5,
    },
]

CONTACTS = [
    {
        "name": "Jan Kowalski",
        "phone": "+48 600 111 222",
        "email": "jan.kowalski@example.com",
        "type": "client",
        "notes": "Szuka mieszkania 2-3 pokoje, Warszawa, budżet do 700k",
    },
    {
        "name": "Anna Nowak",
        "phone": "+48 601 222 333",
        "email": "anna.nowak@example.com",
        "type": "owner",
        "notes": "Właściciel 2 mieszkań na Mokotowie",
    },
    {
        "name": "Piotr Wiśniewski",
        "phone": "+48 602 333 444",
        "email": "piotr.w@example.com",
        "type": "client",
        "notes": "Interesuje się domami w Krakowie",
    },
    {
        "name": "Maria Zielińska",
        "phone": "+48 603 444 555",
        "email": "maria.z@example.com",
        "type": "partner",
        "notes": "Współpraca przy inwestycjach deweloperskich",
    },
]

TASKS = [
    {
        "title": "Skontaktować się z Janem Kowalskim",
        "description": "Przedstawić nowe oferty mieszkań",
        "status": "pending",
        "priority": "high",
        "due_date": (datetime.utcnow() + timedelta(days=2)).isoformat(),
    },
    {
        "title": "Przygotować prezentację dla Nowak",
        "description": "Mieszkanie na Mokotowie, ul. Puławska",
        "status": "in_progress",
        "priority": "medium",
        "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    },
    {
        "title": "Zaktualizować zdjęcia oferty #3",
        "description": "Nowa sesja zdjęciowa dla kawalerki",
        "status": "pending",
        "priority": "low",
        "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
    },
    {
        "title": "Wystawić fakturę prowizyjną",
        "description": "Transakcja dla lokal usługowy Gdańsk",
        "status": "completed",
        "priority": "high",
        "due_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
    },
]


async def seed_database():
    """Seed database with sample data."""
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Check if data already exists
            from app.db.models import Offer, Contact, Task
            
            result = await session.execute(select(Offer).limit(1))
            if result.scalar_one_or_none():
                print("⚠️  Baza danych już zawiera dane. Pomijam seed.")
                return
            
            # Seed listings
            print("📝 Dodawanie ofert...")
            for listing_data in LISTINGS:
                offer = Offer(
                    id=str(uuid.uuid4()),
                    **listing_data,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(offer)
            
            # Seed contacts
            print("👥 Dodawanie kontaktów...")
            for contact_data in CONTACTS:
                contact = Contact(
                    id=str(uuid.uuid4()),
                    **contact_data,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(contact)
            
            # Seed tasks
            print("✅ Dodawanie zadań...")
            for task_data in TASKS:
                task = Task(
                    id=str(uuid.uuid4()),
                    **task_data,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(task)
            
            await session.commit()
            print("\n✅ Seed zakończony sukcesem!")
            print(f"   - {len(LISTINGS)} ofert")
            print(f"   - {len(CONTACTS)} kontaktów")
            print(f"   - {len(TASKS)} zadań")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Błąd podczas seedowania: {e}")
            raise


if __name__ == "__main__":
    print("🌱 Rozpoczynam seedowanie bazy danych...")
    asyncio.run(seed_database())
