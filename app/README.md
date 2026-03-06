# Real Estate Monitor - Frontend

Aplikacja webowa dla systemu monitorowania ofert nieruchomości.

## Funkcje

- **Dashboard** - Przegląd statystyk i aktywności
- **Oferty** - Lista, szczegóły, zmiana statusu
- **Kontakty** - Zarządzanie klientami i właścicielami (CRUD)
- **Zadania** - Lista zadań ze zmianą statusu
- **Ustawienia** - Konfiguracja profilu i powiadomień

## Stack Technologiczny

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS + shadcn/ui
- React Query (data fetching)
- React Router (routing)
- Axios (HTTP client)

## Wymagania

- Node.js 18+
- npm lub yarn
- Backend API (FastAPI) uruchomiony na porcie 8000

## Instalacja

```bash
# 1. Zainstaluj zależności
npm install

# 2. Skonfiguruj zmienne środowiskowe
cp .env.example .env
# Edytuj .env i ustaw VITE_API_BASE_URL

# 3. Uruchom w trybie deweloperskim
npm run dev
```

## Skrypty

```bash
npm run dev      # Tryb deweloperski
npm run build    # Build produkcyjny
npm run preview  # Podgląd buildu
npm run lint     # Sprawdzenie lint
```

## Konfiguracja

### Zmienne środowiskowe

| Zmienna | Opis | Domyślnie |
|---------|------|-----------|
| `VITE_API_BASE_URL` | URL backend API | `http://localhost:8000` |
| `VITE_DEV_AUTH_BYPASS` | Bypass auth w dev | `true` |

### Auth Bypass (tylko dev)

W trybie deweloperskim można włączyć bypass autentykacji:

```bash
VITE_DEV_AUTH_BYPASS=true
```

**WAŻNE:** Ta opcja działa TYLKO w `NODE_ENV=development` i jest ignorowana w produkcji.

## Struktura Projektu

```
src/
├── components/       # Komponenty UI
│   ├── layout/      # Layout (AppShell, Sidebar, Topbar)
│   └── ui/          # shadcn/ui komponenty
├── hooks/           # Custom hooks (useAuth)
├── lib/             # Utils, API client
├── pages/           # Strony aplikacji
├── types/           # TypeScript types
├── App.tsx          # Główny komponent
└── main.tsx         # Entry point
```

## Routing

| Ścieżka | Opis |
|---------|------|
| `/` | Dashboard |
| `/listings` | Lista ofert |
| `/listings/:id` | Szczegóły oferty |
| `/contacts` | Kontakty (CRM) |
| `/tasks` | Zadania |
| `/settings` | Ustawienia |
| `/login` | Logowanie |

## Stany UI

Każdy ekran obsługuje:
- **Loading** - Skeleton podczas ładowania
- **Error** - Komunikat błędu z retry
- **Empty** - Pusty stan z CTA
- **Success** - Normalny widok z danymi

## Error Boundary

Globalny ErrorBoundary łapie nieobsłużone błędy i wyświetla przyjazny fallback UI.

## Toasty

Powiadomienia toast dla:
- Sukcesu operacji (create/update/delete)
- Błędów API
- Walidacji formularzy
