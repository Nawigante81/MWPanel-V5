# Funkcjonalności dla Biura Nieruchomości

## 📋 Wdrożone Funkcje

### ✅ 1. Zarządzanie Komisem (Baza Własnych Ofert)
**Plik:** `app/services/listing_management.py`

#### Statusy Ofert:
- `ACTIVE` - Dostępna, widoczna na portalach
- `RESERVED` - Zarezerwowana (czeka na podpis)
- `PRELIMINARY_RESERVED` - Wstępna rezerwacja (ustna)
- `UNDER_NEGOTIATION` - W trakcie negocjacji
- `OFFER_SUBMITTED` - Złożono ofertę kupna
- `SOLD` / `RENTED` - Sprzedana/Wynajęta
- `WITHDRAWN` - Wycofana przez właściciela
- `EXPIRED` - Umowa wygasła
- `PRIVATE` - Prywatna (tylko dla klientów biura)
- `COMING_SOON` - Wkrótce w ofercie

#### Ekskluzywność:
- `OPEN` - Otwarta (wiele biur)
- `EXCLUSIVE` - Wyłączność
- `EXCLUSIVE_WITH_MARKETING` - Wyłączność z marketingiem
- `SOLE_MANDATE` - Jedyny pełnomocnik

#### Zarządzanie Kluczami:
- Rejestr lokalizacji kluczy
- Kody do skrzynek
- Historia wypożyczeń

---

### ✅ 2. Kalendarz i Prezentacje
**Plik:** `app/services/calendar_service.py`

#### Funkcje:
- **Planowanie prezentacji** z przypomnieniami (SMS, push)
- **Optymalizacja trasy** - automatyczne planowanie kolejności wizyt
- **Sloty rezerwacyjne** - klienci sami wybierają terminy (jak Calendly)
- **Powtarzalne wydarzenia** - np. co wtorek otwarte domy
- **Dostępność agenta** - godziny pracy, przerwy, urlopy
- **Nawigacja** - eksport tras do Google Maps

#### Przypomnienia:
- 60 minut przed (push)
- 30 minut przed (SMS)
- Potwierdzenie rezerwacji dla klienta

---

### ✅ 3. Auto-Matching (Inteligentne Parowanie)
**Plik:** `app/services/auto_matching.py`

#### Scoring Dopasowania (0-100%):
- **Lokalizacja** (25%) - miasto, dzielnica, odległość
- **Cena** (25%) - w zakresie budżetu
- **Powierzchnia** (15%) - m²
- **Pokoje** (15%) - liczba
- **Udogodnienia** (10%) - balkon, parking, winda
- **Inne** (10%) - rok budowy, stan

#### Poziomy Dopasowania:
- `PERFECT` (95-100%) - Idealne dopasowanie
- `EXCELLENT` (85-94%) - Bardzo dobre
- `GOOD` (70-84%) - Dobre
- `FAIR` (55-69%) - Średnie
- `POOR` (<55%) - Słabe

#### Automatyczne Powiadomienia:
- "Nowa oferta pasuje do 3 Twoich klientów"
- Szczegóły dopasowania dla każdego klienta
- Lista pasujących ofert w dashboardzie

---

### ✅ 4. Centralny Inbox (Komunikacja Omnichannel)
**Plik:** `app/services/unified_inbox.py`

#### Kanały:
- Email
- SMS
- WhatsApp
- Facebook Messenger
- Telegram
- Formularze ze strony
- Zapytania z portali (Otodom, OLX)

#### Funkcje:
- **Jedna skrzynka** - wszystkie wiadomości w jednym miejscu
- **Przypisanie agenta** - kto odpowiada
- **Statusy rozmów** - nowa, w trakcie, oczekuje, zamknięta
- **Szablony odpowiedzi** - szybkie odpowiedzi (np. "/cena")
- **SLA** - śledzenie czasu odpowiedzi
- **Notatki wewnętrzne** - tylko dla agentów

---

### ✅ 5. Generator Umów i Dokumentów
**Plik:** `app/services/document_generator.py`

#### Szablony:
- **Umowa pośrednictwa sprzedaży**
- **Umowa pośrednictwa najmu**
- **Umowa wyłączności**
- **Umowa rezerwacyjna**
- **Protokół prezentacji**
- **Protokół zdawczo-odbiorczy**
- **Pełnomocnictwo**

#### Funkcje:
- **Automatyczne wypełnianie** danymi z systemu
- **Konwersja liczb na słowa** (np. 350000 → "trzysta pięćdziesiąt tysięcy")
- **Export do PDF**
- **Podpis elektroniczny** (integracja z DocuSign/Autenti)
- **Wersjonowanie** dokumentów

---

### ✅ 6. API dla Aplikacji Mobilnej
**Plik:** `app/api/mobile_api.py`

#### Endpointy:
- `GET /mobile/dashboard` - Podsumowanie dnia
- `GET /mobile/listings` - Lista ofert (optymalizowana)
- `GET /mobile/listings/{id}` - Szczegóły oferty
- `POST /mobile/listings/quick-add` - Szybkie dodanie (głos)
- `POST /mobile/listings/{id}/photos` - Upload zdjęć
- `GET /mobile/clients` - Lista klientów
- `GET /mobile/calendar/events` - Wydarzenia
- `GET /mobile/presentations/today` - Dzisiejsze prezentacje
- `POST /mobile/presentations/{id}/complete` - Zakończenie prezentacji
- `GET /mobile/search/nearby` - Oferty w pobliżu (GPS)
- `POST /mobile/sync` - Synchronizacja offline

#### Funkcje Mobilne:
- **Szybkie dodanie oferty** - zdjęcie + dyktowanie
- **Offline mode** - przeglądanie bez internetu
- **Nawigacja** - szybkie uruchomienie mapy
- **Skaner dokumentów** - zdjęcie umowy → PDF
- **Notatki głosowe** - dyktowanie po prezentacji

---

### ✅ 7. System Prowizji i Rozliczeń
**Plik:** `app/services/commission_service.py`

#### Podział Prowizji:
- Agent wprowadzający (listing agent)
- Agent sprzedający (selling agent)
- Biuro (office share)

#### Konfiguracja:
- Domyślny % prowizji (np. 3%)
- Minimalna prowizja (PLN)
- Podział między agentami (np. 50/50)

#### Cele Sprzedażowe:
- Cele miesięczne/kwartalne/roczne
- Liczba transakcji
- Wartość prowizji
- Progi bonusowe

#### Bonusy:
- Za osiągnięcie celu
- Za najlepszy wynik
- Za polecenie klienta
- Za ekskluzywność

#### Statusy Wypłat:
- `PENDING` - Nienależna
- `EARNED` - Należna (po podpisaniu)
- `INVOICED` - Zafakturowana
- `PAID` - Wypłacona

---

### ✅ 8. Raporty dla Właścicieli Biura
**Plik:** `app/services/office_reports.py`

#### Raporty:

##### Ranking Agentów:
- Pozycja w biurze
- Liczba transakcji
- Wartość sprzedaży
- Prowizja zarobiona
- Konwersja (lead → transakcja)
- Trend vs poprzedni okres

##### Wydajność Ofert:
- Nowe oferty
- Sprzedane
- Wycofane
- Średni czas sprzedaży
- Konwersja: zapytanie → prezentacja → oferta → sprzedaż
- Średnia obniżka ceny

##### Konwersja Leadów:
- Nowe leady
- Skonwertowane
- Utracone
- Konwersja by źródło
- Średni wynik leadu

##### Finansowy:
- Całkowita prowizja
- Ze sprzedaży / z najmu
- Należne niezapłacone
- Wypłacone
- Trend vs poprzedni okres

##### Dashboard Właściciela:
- Transakcje dzisiaj/ten miesiąc
- Nowe oferty
- Prezentacje
- Top agenci
- Alerty (np. oferty długo nie sprzedane)

---

### ✅ 9. Zarządzanie Właścicielami
**Plik:** `app/services/listing_management.py` (PropertyOwner)

#### Baza Właścicieli:
- Dane kontaktowe
- Historia współpracy (ile ofert, ile sprzedanych)
- Ocena współpracy (1-5 gwiazdek)
- Preferencje kontaktu
- Notatki

#### Raporty dla Właścicieli:
- "Państwa mieszkanie wyświetlono 450 razy"
- "12 osób dzwoniło, 3 prezentacje"
- Automatyczne raporty miesięczne

---

### ✅ 10. Biblioteka Mediów
**Plik:** `app/services/listing_management.py` (ListingImage)

#### Funkcje:
- Centralne repozytorium zdjęć
- Oznaczanie pomieszczeń (salon, sypialnia)
- Kolejność wyświetlania
- Miniaturki
- Główne zdjęcie oferty

---

## 📊 Podsumowanie Architektury

### Serwisy:
```
app/services/
├── listing_management.py      # Zarządzanie komisem
├── calendar_service.py        # Kalendarz i prezentacje
├── auto_matching.py           # Inteligentne parowanie
├── unified_inbox.py           # Centralna skrzynka
├── document_generator.py      # Generator umów
├── commission_service.py      # Prowizje i rozliczenia
└── office_reports.py          # Raporty dla właściciela
```

### API:
```
app/api/
├── mobile_api.py              # Endpointy mobilne
├── listings_api.py            # CRUD ofert
├── calendar_api.py            # Kalendarz
├── inbox_api.py               # Komunikacja
└── reports_api.py             # Raporty
```

---

## 🎯 Kluczowe Korzyści dla Biura

### 1. **Organizacja**
- Wszystkie oferty w jednym miejscu
- Statusy i historia zmian
- Rejestr kluczy

### 2. **Efektywność**
- Auto-matching oszczędza czas
- Optymalizacja tras
- Szybkie odpowiedzi (szablony)

### 3. **Kontrola**
- Raporty w czasie rzeczywistym
- Ranking agentów
- Śledzenie celów

### 4. **Profesjonalizm**
- Profesjonalne umowy
- Systematyczne raporty dla właścicieli
- Historia kontaktu z klientem

### 5. **Motywacja**
- Transparentny system prowizji
- Cele i bonusy
- Rankingi

---

## 🚀 Następne Kroki

### Pozostałe do wdrożenia:
1. **Monitoring konkurencji** - śledzenie ofert innych biur
2. **AI Copywriter** - generowanie opisów ofert

### Integracje:
- Podpis elektroniczny (DocuSign, Autenti)
- Księgowość (Comarch, Optima)
- Telefonia VoIP
- SMS/WhatsApp API

---

## 📈 Przykładowe Scenariusze Użycia

### Scenariusz 1: Nowa Oferta
1. Agent dodaje ofertę przez aplikację mobilną (zdjęcie + dyktowanie)
2. System wyszukuje pasujących klientów (auto-matching)
3. Agent dostaje powiadomienie: "3 klientów pasuje"
4. Dzwoni do klientów, umawia prezentacje
5. System optymalizuje trasę na dany dzień

### Scenariusz 2: Prezentacja
1. Klient rezerwuje termin przez link (Calendly-style)
2. Agent dostaje przypomnienie 30 min przed
3. Po prezentacji agent wypełnia raport w aplikacji
4. Jeśli klient zainteresowany - system tworzy lead
5. Jeśli oferta kupna - generuje się umowa rezerwacyjna

### Scenariusz 3: Transakcja
1. Agent rejestruje transakcję w systemie
2. Prowizja automatycznie dzieli się między agentów
3. System generuje umowę pośrednictwa do podpisu
4. Właściciel dostaje raport: "Nowa transakcja, prowizja 15 000 PLN"
5. Agent widzi w dashboardzie: "Zarobiłeś 7 500 PLN"

---

**System gotowy do wdrożenia w biurze nieruchomości!**
