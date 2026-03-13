"""
Garmin AI Analytics - Quick Start Guide
=========================================

Ten skrypt pokazuje podstawowe użycie systemu.
"""

import os
from datetime import date
from dotenv import load_dotenv

# Załaduj zmienne z .env
load_dotenv()

from app.db.models import init_db
from app.db.repository import GarminRepository
from app.collectors.garmin_client import GarminClient
from app.collectors.sync_daily import DailyDataSync
from app.processors.recovery_score import RecoveryScore


def main():
    """Przykład użycia"""
    
    print("=" * 60)
    print("GARMIN AI ANALYTICS - QUICK START")
    print("=" * 60)
    
    # 1. Inicjalizacja bazy danych
    print("\n1. Inicjalizacja bazy danych...")
    engine, SessionLocal = init_db()
    session = SessionLocal()
    repo = GarminRepository(session)
    print("   ✓ Baza danych gotowa")
    
    # 2. Połączenie z Garmin (wymaga danych w .env)
    print("\n2. Łączenie z Garmin Connect...")
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    
    if not email or not password:
        print("   ⚠️  Brak danych logowania w .env")
        print("   Edytuj plik .env i ustaw GARMIN_EMAIL oraz GARMIN_PASSWORD")
        return
    
    client = GarminClient(email, password)
    
    if not client.connect():
        print("   ✗ Błąd połączenia")
        return
    
    print("   ✓ Połączono z Garmin Connect")
    
    # 3. Synchronizacja danych
    print("\n3. Synchronizacja danych z ostatnich 7 dni...")
    sync = DailyDataSync(client, repo)
    synced = sync.sync_last_n_days(7)
    print(f"   ✓ Zsynchronizowano {synced} dni")
    
    # 4. Obliczanie gotowości
    print("\n4. Obliczanie gotowości do treningu...")
    recovery = RecoveryScore(repo)
    readiness = recovery.calculate_daily_readiness()
    
    print(f"\n   Wynik gotowości: {readiness['readiness_score']:.1f}/100")
    print(f"   Kategoria: {readiness['category']}")
    print(f"   Rekomendacja: {readiness['recommendation']}")
    
    # 5. Raport tygodniowy
    print("\n5. Raport tygodniowy...")
    weekly = recovery.get_weekly_recovery_report()
    
    print(f"\n   Średnia gotowość: {weekly['average_readiness']:.1f}/100")
    print(f"   Trend: {weekly['trend']}")
    
    print("\n   Ostatnie 7 dni:")
    for day in weekly['daily_scores']:
        bar = "█" * int(day['score'] / 10)
        print(f"   {day['date']}: {bar} {day['score']:.1f}")
    
    # 6. API
    print("\n" + "=" * 60)
    print("NASTĘPNE KROKI:")
    print("=" * 60)
    print("\n✓ Dane zsynchronizowane!")
    print("\nUruchom API:")
    print("  python app/api/main.py")
    print("\nLub:")
    print("  uvicorn app.api.main:app --reload")
    print("\nDokumentacja API:")
    print("  http://localhost:8000/docs")
    print("\nPrzykładowe endpointy:")
    print("  GET  http://localhost:8000/api/v1/readiness")
    print("  GET  http://localhost:8000/api/v1/sleep/trends?days=7")
    print("  GET  http://localhost:8000/api/v1/hrv/analysis")
    print("\n" + "=" * 60 + "\n")
    
    session.close()
    engine.dispose()


if __name__ == "__main__":
    main()
