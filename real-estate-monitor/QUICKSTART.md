# Szybkie Uruchomienie

## Opcja 1: Automatyczna Instalacja (Produkcja)

```bash
# 1. Sklonuj repozytorium
git clone <repo-url> real-estate-monitor
cd real-estate-monitor

# 2. Uruchom skrypt instalacyjny jako root
sudo ./install.sh
```

Skrypt automatycznie:
- Zainstaluje Python 3.11, PostgreSQL, Redis, Nginx
- Utworzy bazę danych i użytkownika
- Skonfiguruje środowisko wirtualne
- Zainstaluje wszystkie zależności
- Skonfiguruje usługi systemd
- Uruchomi aplikację

Po instalacji system będzie dostępny pod `http://IP-serwera`

---

## Opcja 2: Szybkie Uruchomienie (Deweloperskie)

```bash
# 1. Sklonuj repozytorium
git clone <repo-url> real-estate-monitor
cd real-estate-monitor

# 2. Uruchom skrypt quickstart
./quickstart.sh
```

To uruchomi aplikację w trybie deweloperskim z auto-reload.

---

## Opcja 3: Ręczna Instalacja

### Wymagania
- Ubuntu 20.04+ / Debian 11+
- Python 3.9+
- PostgreSQL 13+
- Redis 6+

### Krok po kroku

```bash
# 1. Zainstaluj zależności systemowe
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql redis-server

# 2. Utwórz bazę danych
sudo -u postgres psql -c "CREATE DATABASE realestate;"
sudo -u postgres psql -c "CREATE USER realestate WITH PASSWORD 'password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE realestate TO realestate;"

# 3. Skonfiguruj aplikację
cd real-estate-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Utwórz plik .env
cp .env.example .env
# Edytuj .env i ustaw dane dostępowe do bazy

# 5. Uruchom aplikację
uvicorn app.main:app --reload
```

---

## Weryfikacja Instalacji

```bash
# Sprawdź status systemu
curl http://localhost:8000/health

# Panel webowy
open http://localhost:8000/panel

# Dokumentacja API
open http://localhost:8000/docs
```

---

## Zarządzanie Usługami (Produkcja)

```bash
# Status usług
sudo systemctl status realestate-api
sudo systemctl status realestate-worker
sudo systemctl status realestate-beat

# Restart usług
sudo systemctl restart realestate-api
sudo systemctl restart realestate-worker
sudo systemctl restart realestate-beat

# Logi
sudo journalctl -u realestate-api -f
sudo journalctl -u realestate-worker -f
```

---

## Docker (Opcjonalnie)

```bash
# Zbuduj i uruchom
docker-compose up -d

# Logi
docker-compose logs -f

# Zatrzymaj
docker-compose down
```

---

## Problemy?

Sprawdź:
1. [DEPLOYMENT_UBUNTU.md](DEPLOYMENT_UBUNTU.md) - szczegółowy przewodnik
2. Logi: `sudo journalctl -u realestate-api -f`
3. Status bazy: `sudo -u postgres psql -c "\l"`
4. Status Redis: `redis-cli ping`
