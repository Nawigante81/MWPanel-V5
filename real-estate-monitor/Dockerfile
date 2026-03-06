FROM python:3.11-slim

# Ustawienia środowiska
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Instalacja zależności systemowych
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Katalog roboczy
WORKDIR /app

# Kopiowanie requirements
COPY requirements.txt .

# Instalacja zależności Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Kopiowanie aplikacji
COPY . .

# Skrypt startowy
RUN chmod +x /app/entrypoint.sh

# Utworzenie użytkownika nie-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

# Domyślna komenda
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
