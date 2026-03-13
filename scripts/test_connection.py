#!/usr/bin/env python3
"""
Test połączenia z Garmin Connect
"""

import os
import sys
from pathlib import Path
from datetime import date
from dotenv import load_dotenv

# Załaduj zmienne z .env
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.collectors.garmin_client import GarminClient


def main():
    print("=" * 60)
    print("  TEST POŁĄCZENIA Z GARMIN CONNECT")
    print("=" * 60)
    
    # Pobierz dane z .env
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    
    if not email or not password:
        print("\n❌ Brak danych logowania w .env")
        print("\nEdytuj plik .env i ustaw:")
        print("  GARMIN_EMAIL=twoj_email@garmin.com")
        print("  GARMIN_PASSWORD=twoje_haslo\n")
        return
    
    print(f"\nEmail: {email}")
    print("Hasło: {'*' * len(password)}")
    
    # Sprawdź czy są tokeny
    tokens_dir = Path(".garmin_tokens")
    if tokens_dir.exists() and (tokens_dir / "oauth1_token.json").exists():
        print(f"\n✓ Znaleziono tokeny OAuth w: {tokens_dir}")
        print("  (Logowanie bez 2FA)")
    else:
        print(f"\n⚠️  Brak tokenów OAuth")
        print("  (Może być potrzebny kod 2FA)")
    
    # Test połączenia
    print("\n" + "-" * 60)
    print("Próba połączenia...")
    print("-" * 60 + "\n")
    
    client = GarminClient(email, password)
    
    if not client.connect():
        print("\n❌ BŁĄD POŁĄCZENIA")
        print("\nJeśli masz włączone 2FA, uruchom:")
        print("  python scripts/setup_garmin_2fa.py\n")
        return
    
    print("✅ POŁĄCZENIE OK!\n")
    
    # Test pobierania danych
    print("-" * 60)
    print("Test pobierania danych...")
    print("-" * 60 + "\n")
    
    today = date.today()
    
    # Test statystyk
    stats = client.get_daily_stats(today)
    if stats:
        print(f"✓ Statystyki dzienne: {len(stats)} pól")
        steps = stats.get('totalSteps', 0)
        print(f"  Kroki dzisiaj: {steps}")
    else:
        print("⚠️  Brak statystyk (to normalne jeśli dopiero rano)")
    
    # Test snu
    sleep = client.get_sleep_data(today)
    if sleep:
        print(f"✓ Dane o śnie: OK")
        
        # Sprawdź różne możliwe nazwy pól
        sleep_seconds = (
            sleep.get('sleepTimeSeconds') or 
            sleep.get('totalSleepTimeSeconds') or
            sleep.get('dailySleepDTO', {}).get('sleepTimeSeconds') or 0
        )
        sleep_hours = sleep_seconds / 3600
        print(f"  Ostatni sen: {sleep_hours:.1f}h")
        
        # Debug - pokaż dostępne klucze
        if sleep_hours == 0:
            print(f"  📋 Dostępne pola w sleep: {list(sleep.keys())[:10]}")
    else:
        print("⚠️  Brak danych o śnie (to normalne jeśli jeszcze nie spałeś)")
    
    # Test HRV
    hrv = client.get_hrv_data(today)
    if hrv:
        print(f"✓ Dane HRV: OK")
        
        # Sprawdź różne możliwe nazwy pól
        hrv_value = (
            hrv.get('lastNightAvg') or 
            hrv.get('weeklyAvg') or
            hrv.get('hrvSummary', {}).get('lastNightAvg') or 0
        )
        print(f"  HRV ostatniej nocy: {hrv_value}")
        
        # Debug - pokaż dostępne klucze
        if hrv_value == 0:
            print(f"  📋 Dostępne pola w HRV: {list(hrv.keys())}")
    else:
        print("⚠️  Brak danych HRV")
    
    # Test RHR
    rhr = client.get_resting_heart_rate(today)
    if rhr:
        print(f"✓ Spoczynkowe tętno: {rhr} bpm")
    else:
        print("⚠️  Brak RHR")
    
    # Test aktywności
    activities = client.get_activities(0, 5)
    if activities:
        print(f"✓ Aktywności: {len(activities)} ostatnich")
        if activities:
            last = activities[0]
            print(f"  Ostatnia: {last.get('activityName', 'Nieznana')}")
    else:
        print("⚠️  Brak aktywności")
    
    print("\n" + "=" * 60)
    print("TEST ZAKOŃCZONY POMYŚLNIE!")
    print("=" * 60)
    print("\nMożesz teraz uruchomić:")
    print("  python quickstart.py")
    print("  python scripts/run_daily_sync.py")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
