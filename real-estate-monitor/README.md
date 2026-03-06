# Real Estate Monitor - Kompletny System

System monitorowania ofert nieruchomości z frontendem React i backendem FastAPI.

## 📁 Struktura Projektu

```
real-estate-monitor/
├── app/                    # Backend FastAPI
│   ├── api/               # Endpointy API
│   ├── services/          # Serwisy biznesowe
│   ├── db/                # Modele i konfiguracja bazy
│   └── main.py            # Główna aplikacja
├── frontend/              # Frontend React (opcjonalnie)
├── requirements.txt       # Zależności Python
├── docker-compose.yml     # Konfiguracja Docker
├── install.sh             # Skrypt instalacyjny
├── quickstart.sh          # Szybkie uruchomienie
└── seed_data.py           # Skrypt seedujący dane
```

## 🚀 Szybkie Uruchomienie

### Opcja 1: Automatyczna Instalacja (Ubuntu)

```bash
sudo ./install.sh
```

### Opcja 2: Docker

```bash
docker-compose up -d
```

### Opcja 3: Ręczna Instalacja

```bash
# 1. Zainstaluj zależności
pip install -r requirements.txt

# 2. Skonfiguruj bazę danych (PostgreSQL)
# Utwórz bazę: realestate_dev
# Użytkownik: realestate / hasło: dev_password

# 3. Uruchom backend
cd app
uvicorn main:app --reload
```

## 📝 Seed Danych

```bash
# Upewnij się że baza jest skonfigurowana
python seed_data.py
```

Dodaje:
- 5 ofert (mieszkania, domy, działki, lokale)
- 4 kontakty (klienci, właściciele, partnerzy)
- 4 zadania (różne statusy i priorytety)

## 🔌 Endpointy API

| Endpoint | Opis |
|----------|------|
| `GET /` | Info o systemie |
| `GET /health` | Health check |
| `GET /docs` | Dokumentacja Swagger |
| `GET /listings` | Lista ofert |
| `GET /listings/{id}` | Szczegóły oferty |
| `GET /contacts` | Lista kontaktów |
| `GET /tasks` | Lista zadań |

## 🛠️ Stack Technologiczny

**Backend:**
- Python 3.11
- FastAPI
- SQLAlchemy (async)
- PostgreSQL
- Redis
- Celery

**Frontend (opcjonalnie):**
- React 18 + TypeScript
- Vite
- Tailwind CSS
- React Query

## 📊 Funkcje

- ✅ Monitorowanie ofert 24/7
- ✅ System powiadomień
- ✅ Zarządzanie kontaktami (CRM)
- ✅ System zadań dla agentów
- ✅ Predykcja cen (ML)
- ✅ Monitoring konkurencji
- ✅ AI Copywriter
- ✅ Integracja Google Maps
- ✅ WebSocket powiadomienia
- ✅ Import/Export Excel
- ✅ System ocen i recenzji
- ✅ Kampanie reklamowe (Facebook/Instagram)
- ✅ AI Chatbot
- ✅ System rekomendacji
- ✅ API dla partnerów
- ✅ Program lojalnościowy

## 📖 Dokumentacja

- [DEPLOYMENT_UBUNTU.md](DEPLOYMENT_UBUNTU.md) - Szczegółowy przewodnik instalacji
- [QUICKSTART.md](QUICKSTART.md) - Szybkie uruchomienie
- [AGENCY_FEATURES_COMPLETE.md](AGENCY_FEATURES_COMPLETE.md) - Opis wszystkich funkcji

## 🔧 Konfiguracja

Zmienne środowiskowe (`.env`):

```bash
# Baza danych
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db

# Redis
REDIS_URL=redis://localhost:6379/0

# API
SECRET_KEY=your-secret-key
DEBUG=false

# Opcjonalne integracje
GOOGLE_MAPS_API_KEY=...
WHATSAPP_API_KEY=...
SMTP_HOST=...
```

## 🧪 Testy

```bash
# Backend
cd app
pytest

# Frontend
cd frontend
npm run build
npm run lint
```

## 📜 Licencja

MIT
