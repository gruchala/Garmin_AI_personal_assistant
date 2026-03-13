FROM python:3.11-slim

WORKDIR /app

# Instalacja zależności systemowych
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Kopiowanie requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie kodu aplikacji
COPY app ./app
COPY scripts ./scripts

# Utworzenie katalogu na logi
RUN mkdir -p logs

# Ustawienie zmiennych środowiskowych
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Domyślna komenda
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
