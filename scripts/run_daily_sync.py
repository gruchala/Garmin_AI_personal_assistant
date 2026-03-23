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
from app.services.workflows import run_full_sync

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
    
    try:
        # Inicjalizacja bazy danych
        logger.info("Inicjalizacja bazy danych...")
        engine, SessionLocal = init_db()
        session = SessionLocal()
        repo = GarminRepository(session)

        logger.info("Uruchamiam pełną synchronizację...")
        sync_result = run_full_sync(repo)
        logger.info("Zsynchronizowano %s dni ✓", sync_result["summary"]["synced_days"])
        logger.info(
            "Zsynchronizowano %s nowych aktywności ✓",
            sync_result["summary"]["synced_recent_activities"],
        )
        
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
