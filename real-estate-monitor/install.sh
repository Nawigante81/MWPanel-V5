#!/bin/bash

# =============================================================================
# Skrypt Instalacyjny Real Estate Monitor na Ubuntu
# =============================================================================

set -e  # Zatrzymaj przy błędzie

# Kolory dla outputu
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Konfiguracja
APP_DIR="/opt/real-estate-monitor"
DB_NAME="real_estate_monitor"
DB_USER="realestate"
DB_PASS=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 16)
SECRET_KEY=$(openssl rand -base64 64 | tr -dc 'a-zA-Z0-9' | head -c 50)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Instalacja Real Estate Monitor${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Sprawdź czy root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Uruchom skrypt jako root: sudo ./install.sh${NC}"
    exit 1
fi

# Funkcja logowania
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[OSTRZEŻENIE] $1${NC}"
}

error() {
    echo -e "${RED}[BŁĄD] $1${NC}"
}

# =============================================================================
# KROK 1: Aktualizacja systemu
# =============================================================================
log "Krok 1/10: Aktualizacja systemu..."
apt update && apt upgrade -y
apt install -y curl wget git build-essential software-properties-common

# =============================================================================
# KROK 2: Instalacja Python
# =============================================================================
log "Krok 2/10: Instalacja Python 3.11..."
add-apt-repository ppa:deadsnakes/ppa -y
apt update
apt install -y python3.11 python3.11-dev python3.11-venv python3-pip
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# =============================================================================
# KROK 3: Instalacja PostgreSQL
# =============================================================================
log "Krok 3/10: Instalacja PostgreSQL..."
apt install -y postgresql postgresql-contrib
systemctl start postgresql
systemctl enable postgresql

# Utwórz bazę danych i użytkownika
sudo -u postgres psql << EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH ENCRYPTED PASSWORD '$DB_PASS';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
\q
EOF

log "Baza danych utworzona: $DB_NAME"

# =============================================================================
# KROK 4: Instalacja Redis
# =============================================================================
log "Krok 4/10: Instalacja Redis..."
apt install -y redis-server
systemctl start redis-server
systemctl enable redis-server

# =============================================================================
# KROK 5: Instalacja Nginx
# =============================================================================
log "Krok 5/10: Instalacja Nginx..."
apt install -y nginx
systemctl start nginx
systemctl enable nginx

# =============================================================================
# KROK 6: Przygotowanie katalogu aplikacji
# =============================================================================
log "Krok 6/10: Przygotowanie katalogu aplikacji..."
mkdir -p $APP_DIR
mkdir -p /var/log/realestate

# Sprawdź czy pliki aplikacji istnieją
if [ ! -f "app/main.py" ]; then
    error "Nie znaleziono plików aplikacji!"
    error "Upewnij się, że uruchamiasz skrypt z katalogu zawierającego aplikację."
    exit 1
fi

# Kopiowanie plików
cp -r . $APP_DIR/
cd $APP_DIR

# =============================================================================
# KROK 7: Tworzenie środowiska wirtualnego
# =============================================================================
log "Krok 7/10: Tworzenie środowiska wirtualnego..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Tworzenie requirements.txt jeśli nie istnieje
if [ ! -f "requirements.txt" ]; then
    log "Tworzenie pliku requirements.txt..."
    cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
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
structlog==23.2.0
gunicorn==21.2.0
EOF
fi

pip install -r requirements.txt

# =============================================================================
# KROK 8: Konfiguracja środowiska
# =============================================================================
log "Krok 8/10: Konfiguracja zmiennych środowiskowych..."

cat > $APP_DIR/.env << EOF
# Baza danych
DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
DATABASE_URL_SYNC=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
SECRET_KEY=$SECRET_KEY

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
EOF

chmod 600 $APP_DIR/.env

# =============================================================================
# KROK 9: Tworzenie usług systemd
# =============================================================================
log "Krok 9/10: Konfiguracja usług systemd..."

# Tworzenie użytkownika www-data
useradd -r -s /bin/false www-data 2>/dev/null || true

# API Service
cat > /etc/systemd/system/realestate-api.service << EOF
[Unit]
Description=Real Estate Monitor API
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Celery Worker
cat > /etc/systemd/system/realestate-worker.service << EOF
[Unit]
Description=Real Estate Monitor Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat
cat > /etc/systemd/system/realestate-beat.service << EOF
[Unit]
Description=Real Estate Monitor Celery Scheduler
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/celery -A app.tasks.celery_app beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Uprawnienia
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# Przeładowanie systemd
systemctl daemon-reload

# Włączenie usług
systemctl enable realestate-api
systemctl enable realestate-worker
systemctl enable realestate-beat

# =============================================================================
# KROK 10: Konfiguracja Nginx
# =============================================================================
log "Krok 10/10: Konfiguracja Nginx..."

# Pobierz IP serwera
SERVER_IP=$(hostname -I | awk '{print $1}')

cat > /etc/nginx/sites-available/realestate << EOF
server {
    listen 80;
    server_name $SERVER_IP localhost;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 100M;
}
EOF

ln -sf /etc/nginx/sites-available/realestate /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl restart nginx

# =============================================================================
# Uruchomienie usług
# =============================================================================
log "Uruchamianie usług..."
systemctl start realestate-api
systemctl start realestate-worker
systemctl start realestate-beat

sleep 3

# =============================================================================
# Podsumowanie
# =============================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Instalacja Zakończona!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}System jest dostępny pod:${NC}"
echo -e "  ${YELLOW}http://$SERVER_IP${NC}"
echo -e "  ${YELLOW}http://localhost${NC}"
echo ""
echo -e "${GREEN}Endpointy:${NC}"
echo -e "  ${YELLOW}/health${NC} - Status systemu"
echo -e "  ${YELLOW}/panel${NC} - Panel webowy"
echo -e "  ${YELLOW}/docs${NC} - Dokumentacja API"
echo ""
echo -e "${GREEN}Zarządzanie usługami:${NC}"
echo -e "  ${YELLOW}sudo systemctl status realestate-api${NC}"
echo -e "  ${YELLOW}sudo systemctl status realestate-worker${NC}"
echo -e "  ${YELLOW}sudo systemctl status realestate-beat${NC}"
echo ""
echo -e "${GREEN}Logi:${NC}"
echo -e "  ${YELLOW}sudo journalctl -u realestate-api -f${NC}"
echo ""
echo -e "${YELLOW}Dane dostępowe do bazy:${NC}"
echo -e "  Baza: $DB_NAME"
echo -e "  Użytkownik: $DB_USER"
echo -e "  Hasło: $DB_PASS"
echo ""
echo -e "${GREEN}========================================${NC}"

# Zapisz dane dostępowe
mkdir -p /root/.realestate
cat > /root/.realestate/credentials.txt << EOF
Real Estate Monitor - Dane dostępowe
=====================================
Data instalacji: $(date)

BAZA DANYCH PostgreSQL:
  Nazwa: $DB_NAME
  Użytkownik: $DB_USER
  Hasło: $DB_PASS

API:
  URL: http://$SERVER_IP
  Secret Key: $SECRET_KEY

Ścieżka aplikacji: $APP_DIR
EOF

chmod 600 /root/.realestate/credentials.txt

log "Dane dostępowe zapisane w: /root/.realestate/credentials.txt"
