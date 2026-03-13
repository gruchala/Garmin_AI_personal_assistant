#!/usr/bin/env python3
"""Skrypt do codziennej synchronizacji danych z Garmin Connect"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Załaduj zmienne z .env
load_dotenv()

# Dodaj ścieżkę do modułu app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import init_db
from app.db.repository import GarminRepository
from app.collectors.garmin_client import GarminClient
from app.collectors.sync_daily import DailyDataSync
from app.collectors.sync_activities import ActivitiesSync

# Upewnij się, że katalog logs istnieje
Path("logs").mkdir(exist_ok=True)

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/sync_daily.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Główna funkcja synchronizacji"""
    logger.info("=" * 60)
    logger.info(f"Rozpoczęcie synchronizacji: {datetime.now()}")
    logger.info("=" * 60)
    
    # Pobierz dane logowania z zmiennych środowiskowych
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    
    if not email or not password:
        logger.error("Brak danych logowania! Ustaw zmienne GARMIN_EMAIL i GARMIN_PASSWORD")
        sys.exit(1)
    
    try:
        # Inicjalizacja bazy danych
        logger.info("Inicjalizacja bazy danych...")
        engine, SessionLocal = init_db()
        session = SessionLocal()
        
        # Połączenie z Garmin Connect
        logger.info("Łączenie z Garmin Connect...")
        client = GarminClient(email, password)
        
        if not client.connect():
            logger.error("Nie udało się połączyć z Garmin Connect")
            sys.exit(1)
        
        logger.info("Połączono z Garmin Connect ✓")
        
        # Utworzenie repozytorium
        repo = GarminRepository(session)
        
        # Synchronizacja danych dziennych
        logger.info("Synchronizacja danych dziennych...")
        daily_sync = DailyDataSync(client, repo)
        synced_days = daily_sync.sync_last_n_days(7)  # Ostatnie 7 dni
        logger.info(f"Zsynchronizowano {synced_days} dni ✓")
        
        # Synchronizacja aktywności
        logger.info("Synchronizacja aktywności...")
        activities_sync = ActivitiesSync(client, repo)
        synced_activities = activities_sync.sync_recent_activities(20)
        logger.info(f"Zsynchronizowano {synced_activities} aktywności ✓")
        
        # Zamknięcie sesji
        session.close()
        engine.dispose()
        
        logger.info("=" * 60)
        logger.info(f"Synchronizacja zakończona pomyślnie: {datetime.now()}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Błąd podczas synchronizacji: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
