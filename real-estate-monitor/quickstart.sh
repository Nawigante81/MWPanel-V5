#!/bin/bash

# =============================================================================
# Szybkie Uruchomienie (Tryb Deweloperski)
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Real Estate Monitor - Quick Start${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Sprawdź czy jesteśmy w odpowiednim katalogu
if [ ! -f "app/main.py" ]; then
    echo -e "${YELLOW}Błąd: Uruchom skrypt z katalogu głównego projektu${NC}"
    exit 1
fi

# Sprawdź czy Python jest zainstalowany
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python3 nie jest zainstalowany. Instalacja...${NC}"
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip
fi

# Sprawdź czy PostgreSQL jest zainstalowany
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}PostgreSQL nie jest zainstalowany. Instalacja...${NC}"
    sudo apt install -y postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
fi

# Sprawdź czy Redis jest zainstalowany
if ! command -v redis-cli &> /dev/null; then
    echo -e "${YELLOW}Redis nie jest zainstalowany. Instalacja...${NC}"
    sudo apt install -y redis-server
    sudo systemctl start redis-server
fi

# Utwórz wirtualne środowisko jeśli nie istnieje
if [ ! -d "venv" ]; then
    echo -e "${GREEN}Tworzenie wirtualnego środowiska...${NC}"
    python3 -m venv venv
fi

# Aktywuj środowisko
source venv/bin/activate

# Zainstaluj zależności
echo -e "${GREEN}Instalacja zależności...${NC}"
pip install --upgrade pip -q

# Utwórz minimalny requirements.txt jeśli nie istnieje
if [ ! -f "requirements.txt" ]; then
    cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
asyncpg==0.29.0
alembic==1.12.1
psycopg2-binary==2.9.9
redis==5.0.1
celery==5.3.4
httpx==0.25.2
pydantic==2.5.2
pydantic-settings==2.1.0
python-dotenv==1.0.0
openpyxl==3.1.2
prometheus-client==0.19.0
EOF
fi

pip install -r requirements.txt -q

# Utwórz plik .env jeśli nie istnieje
if [ ! -f ".env" ]; then
    echo -e "${GREEN}Tworzenie pliku konfiguracyjnego .env...${NC}"
    
    # Sprawdź czy baza istnieje, jeśli nie - utwórz
    DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='realestate_dev'" 2>/dev/null || echo "0")
    
    if [ "$DB_EXISTS" != "1" ]; then
        echo -e "${YELLOW}Tworzenie bazy danych...${NC}"
        sudo -u postgres psql << EOF 2>/dev/null || true
CREATE DATABASE realestate_dev;
CREATE USER realestate WITH ENCRYPTED PASSWORD 'dev_password';
GRANT ALL PRIVILEGES ON DATABASE realestate_dev TO realestate;
\q
EOF
    fi
    
    cat > .env << 'EOF'
# Baza danych
DATABASE_URL=postgresql+asyncpg://realestate:dev_password@localhost:5432/realestate_dev
DATABASE_URL_SYNC=postgresql://realestate:dev_password@localhost:5432/realestate_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
EOF
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Gotowe! Uruchamianie aplikacji...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}API będzie dostępne pod:${NC}"
echo -e "  ${GREEN}http://localhost:8000${NC}"
echo ""
echo -e "${YELLOW}Endpointy:${NC}"
echo -e "  ${GREEN}/health${NC} - Status systemu"
echo -e "  ${GREEN}/panel${NC} - Panel webowy"
echo -e "  ${GREEN}/docs${NC} - Dokumentacja API (Swagger)"
echo -e "  ${GREEN}/redoc${NC} - Dokumentacja API (ReDoc)"
echo ""
echo -e "${YELLOW}Naciśnij Ctrl+C aby zatrzymać${NC}"
echo ""

# Uruchom aplikację
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
