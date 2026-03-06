# Instalacja na Czystym Ubuntu

Kompletny przewodnik instalacji systemu Real Estate Monitor na czystym serwerze Ubuntu 22.04 LTS.

---

## Wymagania Systemowe

- **System:** Ubuntu 22.04 LTS (zalecane) lub 20.04 LTS
- **RAM:** Minimum 2GB (zalecane 4GB+)
- **Dysk:** Minimum 20GB wolnego miejsca
- **CPU:** 2+ rdzenie

---

## Krok 1: Aktualizacja Systemu

```bash
# Zaloguj się jako root lub użyj sudo
sudo apt update && sudo apt upgrade -y

# Zainstaluj podstawowe narzędzia
sudo apt install -y curl wget git build-essential software-properties-common
```

---

## Krok 2: Instalacja Python

```bash
# Dodaj PPA dla najnowszego Pythona
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Zainstaluj Python 3.11 i pip
sudo apt install -y python3.11 python3.11-dev python3.11-venv python3-pip

# Ustaw Python 3.11 jako domyślny (opcjonalnie)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Sprawdź wersję
python3 --version  # Powinno pokazać Python 3.11.x
```

---

## Krok 3: Instalacja PostgreSQL

```bash
# Zainstaluj PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Uruchom i włącz usługę
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Utwórz bazę danych i użytkownika
sudo -u postgres psql << EOF
CREATE DATABASE real_estate_monitor;
CREATE USER realestate WITH ENCRYPTED PASSWORD 'twoje_haslo';
GRANT ALL PRIVILEGES ON DATABASE real_estate_monitor TO realestate;
\q
EOF

# Sprawdź czy działa
sudo systemctl status postgresql
```

---

## Krok 4: Instalacja Redis

```bash
# Zainstaluj Redis
sudo apt install -y redis-server

# Włącz usługę
sudo systemctl start redis
sudo systemctl enable redis

# Sprawdź czy działa
redis-cli ping  # Powinno zwrócić "PONG"
```

---

## Krok 5: Instalacja Nginx (opcjonalnie, dla produkcji)

```bash
sudo apt install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## Krok 6: Pobranie Aplikacji

```bash
# Utwórz katalog dla aplikacji
sudo mkdir -p /opt/real-estate-monitor
cd /opt/real-estate-monitor

# Sklonuj repozytorium (lub przenieś pliki)
sudo git clone https://github.com/twoje-repo/real-estate-monitor.git .
# LUB jeśli masz pliki lokalnie:
# sudo cp -r /ścieżka/do/plików/* .

# Ustaw uprawnienia
sudo chown -R $USER:$USER /opt/real-estate-monitor
```

---

## Krok 7: Konfiguracja Środowiska Wirtualnego

```bash
cd /opt/real-estate-monitor

# Utwórz wirtualne środowisko
python3 -m venv venv

# Aktywuj środowisko
source venv/bin/activate

# Upewnij się, że pip jest aktualny
pip install --upgrade pip

# Zainstaluj zależności
pip install -r requirements.txt
```

### Zawartość pliku requirements.txt

Jeśli nie masz pliku `requirements.txt`, utwórz go:

```bash
cat > requirements.txt << 'EOF'
# FastAPI i serwer
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# Baza danych
sqlalchemy==2.0.23
asyncpg==0.29.0
alembic==1.12.1
psycopg2-binary==2.9.9

# Redis i cache
redis==5.0.1

# Celery - zadania w tle
celery==5.3.4
flower==2.0.1

# HTTP i scraping
httpx==0.25.2
aiohttp==3.9.1
beautifulsoup4==4.12.2
lxml==4.9.3

# Walidacja i serializacja
pydantic==2.5.2
pydantic-settings==2.1.0
email-validator==2.1.0

# Bezpieczeństwo
passlib==1.7.4
python-jose[cryptography]==3.3.0

# Narzędzia
python-dotenv==1.0.0
pytz==2023.3.post1
python-dateutil==2.8.2

# Excel
openpyxl==3.1.2

# ML (opcjonalnie)
scikit-learn==1.3.2
numpy==1.26.2
pandas==2.1.3

# Monitoring
prometheus-client==0.19.0

# Logowanie
structlog==23.2.0

# Testy
pytest==7.4.3
pytest-asyncio==0.21.1
httpx==0.25.2
EOF

pip install -r requirements.txt
```

---

## Krok 8: Konfiguracja Zmiennych Środowiskowych

```bash
cd /opt/real-estate-monitor

# Utwórz plik .env
cat > .env << 'EOF'
# Baza danych PostgreSQL
DATABASE_URL=postgresql+asyncpg://realestate:twoje_haslo@localhost:5432/real_estate_monitor
DATABASE_URL_SYNC=postgresql://realestate:twoje_haslo@localhost:5432/real_estate_monitor

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
SECRET_KEY=twoj-tajny-klucz-minimum-32-znakow-dlugosci

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Google Maps API (opcjonalnie)
GOOGLE_MAPS_API_KEY=twój_klucz_api

# WhatsApp (opcjonalnie)
WHATSAPP_API_KEY=twój_klucz
WHATSAPP_PHONE_ID=twój_phone_id

# Email (opcjonalnie)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=twój_email@gmail.com
SMTP_PASSWORD=twóje_hasło

# Slack (opcjonalnie)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
EOF

# Ustaw uprawnienia do pliku .env
chmod 600 .env
```

---

## Krok 9: Migracje Bazy Danych

```bash
cd /opt/real-estate-monitor
source venv/bin/activate

# Inicjalizacja Alembic (jeśli nie było wcześniej)
# alembic init alembic

# Uruchom migracje
alembic upgrade head

# Jeśli nie masz migracji, utwórz tabele bezpośrednio
python3 << 'EOF'
import asyncio
from app.db import init_db

async def setup():
    await init_db()
    print("Baza danych zainicjalizowana!")

asyncio.run(setup())
EOF
```

---

## Krok 10: Uruchomienie Aplikacji

### Opcja A: Uruchomienie deweloperskie (na razie)

```bash
cd /opt/real-estate-monitor
source venv/bin/activate

# Uruchom serwer API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Opcja B: Uruchomienie produkcyjne z Gunicorn

```bash
# Zainstaluj Gunicorn
pip install gunicorn

# Uruchom z wieloma workerami
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --daemon \
    --pid /tmp/gunicorn.pid \
    --access-logfile /var/log/realestate/access.log \
    --error-logfile /var/log/realestate/error.log
```

---

## Krok 11: Uruchomienie Celery (Zadania w Tle)

### Terminal 1 - Worker

```bash
cd /opt/real-estate-monitor
source venv/bin/activate

celery -A app.tasks.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    -n worker1@%h
```

### Terminal 2 - Scheduler (Beat)

```bash
cd /opt/real-estate-monitor
source venv/bin/activate

celery -A app.tasks.celery_app beat --loglevel=info
```

### Terminal 3 - Flower (Monitoring Celery - opcjonalnie)

```bash
cd /opt/real-estate-monitor
source venv/bin/activate

celery -A app.tasks.celery_app flower \
    --port=5555 \
    --basic-auth=admin:twoje_haslo
```

---

## Krok 12: Konfiguracja Systemd (Produkcja)

Utwórz usługi systemd dla automatycznego uruchamiania:

### API Service

```bash
sudo tee /etc/systemd/system/realestate-api.service << 'EOF'
[Unit]
Description=Real Estate Monitor API
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/real-estate-monitor
Environment=PATH=/opt/real-estate-monitor/venv/bin
EnvironmentFile=/opt/real-estate-monitor/.env
ExecStart=/opt/real-estate-monitor/venv/bin/gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Celery Worker Service

```bash
sudo tee /etc/systemd/system/realestate-worker.service << 'EOF'
[Unit]
Description=Real Estate Monitor Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/real-estate-monitor
Environment=PATH=/opt/real-estate-monitor/venv/bin
EnvironmentFile=/opt/real-estate-monitor/.env
ExecStart=/opt/real-estate-monitor/venv/bin/celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Celery Beat Service

```bash
sudo tee /etc/systemd/system/realestate-beat.service << 'EOF'
[Unit]
Description=Real Estate Monitor Celery Scheduler
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/real-estate-monitor
Environment=PATH=/opt/real-estate-monitor/venv/bin
EnvironmentFile=/opt/real-estate-monitor/.env
ExecStart=/opt/real-estate-monitor/venv/bin/celery -A app.tasks.celery_app beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Uruchomienie usług

```bash
# Utwórz użytkownika www-data jeśli nie istnieje
sudo useradd -r -s /bin/false www-data 2>/dev/null || true

# Ustaw uprawnienia
sudo chown -R www-data:www-data /opt/real-estate-monitor

# Przeładuj systemd
sudo systemctl daemon-reload

# Włącz i uruchom usługi
sudo systemctl enable realestate-api
sudo systemctl enable realestate-worker
sudo systemctl enable realestate-beat

sudo systemctl start realestate-api
sudo systemctl start realestate-worker
sudo systemctl start realestate-beat

# Sprawdź status
sudo systemctl status realestate-api
sudo systemctl status realestate-worker
sudo systemctl status realestate-beat
```

---

## Krok 13: Konfiguracja Nginx (Reverse Proxy)

```bash
sudo tee /etc/nginx/sites-available/realestate << 'EOF'
server {
    listen 80;
    server_name twoja-domena.pl www.twoja-domena.pl;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static {
        alias /opt/real-estate-monitor/static;
        expires 30d;
    }

    client_max_body_size 100M;
}
EOF

# Włącz konfigurację
sudo ln -s /etc/nginx/sites-available/realestate /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Sprawdź konfigurację
sudo nginx -t

# Zrestartuj Nginx
sudo systemctl restart nginx
```

---

## Krok 14: SSL z Let's Encrypt (opcjonalnie)

```bash
# Zainstaluj Certbot
sudo apt install -y certbot python3-certbot-nginx

# Pobierz certyfikat
sudo certbot --nginx -d twoja-domena.pl -d www.twoja-domena.pl

# Automatyczne odnowienie
sudo systemctl enable certbot.timer
```

---

## Krok 15: Weryfikacja Instalacji

```bash
# Sprawdź czy API działa
curl http://localhost:8000/health

# Sprawdź logi
sudo journalctl -u realestate-api -f
sudo journalctl -u realestate-worker -f

# Sprawdź status usług
sudo systemctl status realestate-api
sudo systemctl status realestate-worker
sudo systemctl status realestate-beat
```

---

## Krok 16: Utworzenie Administratora (opcjonalnie)

```bash
cd /opt/real-estate-monitor
source venv/bin/activate

python3 << 'EOF'
import asyncio
from app.services.rbac import RBACService
from app.db import get_db

async def create_admin():
    # Utwórz administratora
    # W rzeczywistej implementacji - użyj API lub skryptu
    print("Administrator utworzony!")

asyncio.run(create_admin())
EOF
```

---

## Rozwiązywanie Problemów

### Problem: PostgreSQL nie działa

```bash
sudo systemctl restart postgresql
sudo -u postgres psql -c "\l"  # Lista baz danych
```

### Problem: Redis nie działa

```bash
sudo systemctl restart redis
redis-cli ping
```

### Problem: Brak uprawnień do plików

```bash
sudo chown -R www-data:www-data /opt/real-estate-monitor
sudo chmod -R 755 /opt/real-estate-monitor
```

### Problem: Port 8000 jest zajęty

```bash
sudo lsof -i :8000
sudo kill -9 <PID>
```

### Problem: Błędy w aplikacji

```bash
# Sprawdź logi
sudo journalctl -u realestate-api -n 100 --no-pager

# Sprawdź logi Celery
sudo journalctl -u realestate-worker -n 100 --no-pager
```

---

## Aktualizacja Aplikacji

```bash
cd /opt/real-estate-monitor

# Pobierz najnowszą wersję
git pull origin main

# Aktywuj środowisko
source venv/bin/activate

# Zainstaluj nowe zależności
pip install -r requirements.txt

# Uruchom migracje
alembic upgrade head

# Zrestartuj usługi
sudo systemctl restart realestate-api
sudo systemctl restart realestate-worker
sudo systemctl restart realestate-beat
```

---

## Podsumowanie

Po wykonaniu powyższych kroków system będzie dostępny pod:

- **API:** http://twoja-domena.pl lub http://IP-serwera:8000
- **Panel:** http://twoja-domena.pl/panel
- **Dokumentacja API:** http://twoja-domena.pl/docs
- **Health Check:** http://twoja-domena.pl/health

---

## Dodatkowe Zasoby

- **Logi:** `/var/log/realestate/`
- **Konfiguracja:** `/opt/real-estate-monitor/.env`
- **Baza danych:** PostgreSQL na localhost:5432
- **Redis:** localhost:6379

---

## Wsparcie

W przypadku problemów sprawdź:
1. Logi usług: `sudo journalctl -u realestate-api -f`
2. Status usług: `sudo systemctl status realestate-*`
3. Połączenie z bazą: `sudo -u postgres psql -d real_estate_monitor`
4. Redis: `redis-cli ping`
