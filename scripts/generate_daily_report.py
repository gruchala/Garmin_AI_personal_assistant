#!/usr/bin/env python3
"""Skrypt do generowania dziennego raportu"""

import sys
import logging
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv

# Załaduj zmienne z .env
load_dotenv()

# Dodaj ścieżkę do modułu app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import init_db
from app.db.repository import GarminRepository
from app.services.workflows import build_daily_report

# Upewnij się, że katalog logs istnieje
Path("logs").mkdir(exist_ok=True)

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/daily_report.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Wyświetla sekcję raportu"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def main():
    """Główna funkcja generowania raportu"""
    print("\n" + "🏃 DZIENNY RAPORT GARMIN AI 🏃".center(60))
    print(f"Data: {date.today().strftime('%Y-%m-%d')}".center(60))
    
    try:
        # Inicjalizacja bazy danych
        engine, SessionLocal = init_db()
        session = SessionLocal()
        repo = GarminRepository(session)
        report = build_daily_report(repo, target_date=date.today(), send_notifications=True)
        readiness = report["readiness"]
        sleep_trends = report["sleep"]
        sleep_consistency = report["sleep_consistency"]
        hrv_trend = report["hrv"]
        hrv_baseline = report["hrv_baseline"]
        weekly = report["weekly"]
        latest_weight = report["weight"]
        latest_vo2 = report["vo2max"]
        insight = report["insight"]

        print_section("SYNCHRONIZACJA")
        print(f"\n  Zsynchronizowano dni: {report['sync']['synced_days']}")
        print(f"  Nowe aktywności (ostatnie): {report['sync']['synced_recent_activities']}")
        print(f"  Nowe aktywności dla dziś: {report['sync']['synced_target_day_activities']}")

        print_section("GOTOWOŚĆ DO TRENINGU")
        print(f"\n  Wynik gotowości: {readiness['readiness_score']:.1f}/100")
        print(f"  Kategoria: {readiness['category'].upper()}")
        print(f"\n  📝 Rekomendacja:")
        print(f"  {readiness['recommendation']}")
        
        # Komponenty
        if 'components' in readiness:
            print(f"\n  Składowe:")
            components = readiness['components']
            
            if 'hrv' in components:
                hrv_comp = components['hrv']
                print(f"    • HRV: {hrv_comp['score']:.1f}/100 (wartość: {hrv_comp['value']}, baseline: {hrv_comp['baseline']:.1f})")
            
            if 'sleep' in components:
                sleep_comp = components['sleep']
                print(f"    \u2022 Sen: {sleep_comp['score']:.1f}/100 ({sleep_comp['duration_hours']:.1f} h \u2014 dzisiejsza noc)")
            
            if 'rhr' in components:
                rhr_comp = components['rhr']
                print(f"    • RHR: {rhr_comp['score']:.1f}/100 (wartość: {rhr_comp['value']}, baseline: {rhr_comp['baseline']:.1f})")
        
        # === TRENDY SNU ===
        print_section("ANALIZA SNU (7 DNI)")
        
        # Dzisiejsza noc (z komponentu gotowości)
        _sc = (readiness.get('components') or {}).get('sleep', {})
        if _sc:
            print(f"\n  Dzisiejsza noc:   {_sc['duration_hours']:.1f} h  |  jakość {_sc['score']:.0f}/100")
            print(f"  {'─' * 42}")

        print(f"  Średnia 7-dniowa: {sleep_trends['average_duration_hours']:.1f} h  |  jakość {sleep_trends['average_quality_score']:.0f}/100")
        print(f"  Głęboki sen: {sleep_trends['average_deep_sleep_percent']:.1f}%")
        print(f"  REM: {sleep_trends['average_rem_sleep_percent']:.1f}%")
        print(f"  Trend: {sleep_trends['trend'].upper()}")
        
        # Regularność
        print(f"\n  Regularność: {sleep_consistency['consistency_score']:.1f}/100")
        print(f"  {sleep_consistency['message']}")
        
        # === TRENDY HRV ===
        print_section("ANALIZA HRV (7 DNI)")
        
        if hrv_baseline:
            print(f"\n  Baseline (28 dni):")
            print(f"    • Średnia: {hrv_baseline.get('mean', 0):.1f}")
            print(f"    • Odchylenie: {hrv_baseline.get('stdev', 0):.1f}")
            print(f"    • Zakres: {hrv_baseline.get('min', 0):.1f} - {hrv_baseline.get('max', 0):.1f}")

        print(f"\n  Trend 7-dniowy: {hrv_trend['trend'].upper()}")
        print(f"  Średnia HRV: {hrv_trend['average_hrv']:.1f}")
        print(f"  Zmiana: {hrv_trend['change_percent']:+.1f}%")

        overtraining = weekly["overtraining_risk"]
        print(f"\n  ⚠️  Ryzyko przetrenowania: {overtraining['risk_level'].upper()}")
        print(f"  {overtraining['message']}")

        # === MASA CIAŁA I VO2MAX ===
        print_section("SKŁAD CIAŁA I VO2MAX")

        weight_kg = latest_weight.get("weight_kg")
        if latest_weight.get("date"):
            print(f"\n  Masa ciała ({latest_weight['date']}):")
            if weight_kg:
                print(f"    • Waga:          {weight_kg:.1f} kg")
            if latest_weight.get("bmi"):
                print(f"    • BMI:           {latest_weight['bmi']:.1f}")
            if latest_weight.get("body_fat_percent"):
                print(f"    • Tkanka tłuszcz:{latest_weight['body_fat_percent']:.1f}%")
        else:
            print("\n  Brak danych o masie ciała")
            print("  (Zważenie w Garmin Connect lub kompatybilna waga)")

        if latest_vo2.get("date"):
            print(f"\n  VO2max ({latest_vo2['date']}):")
            print(f"    • VO2max:        {latest_vo2['vo2max']:.1f} ml/kg/min")
            if latest_vo2.get("fitness_age"):
                print(f"    • Wiek fitness:  {latest_vo2['fitness_age']} lat")
        else:
            print("\n  Brak danych VO2max")
            print("  (Wymaga biegania z GPS i pulsometrem)")

        # === RAPORT TYGODNIOWY ===
        print_section("RAPORT TYGODNIOWY")
        
        print(f"\n  Średnia gotowość: {weekly['average_readiness']:.1f}/100")
        print(f"  Trend: {weekly['trend'].upper()}")
        
        print(f"\n  Dzienne wyniki:")
        for day_score in weekly['daily_scores']:
            score_bar = "█" * int(day_score['score'] / 10)
            print(f"    {day_score['date']}: {score_bar} {day_score['score']:.1f} ({day_score['category']})")
        
        # === AI INSIGHT ===
        print_section("AI INSIGHT")
        
        if insight:
            print(f"\n{insight}")
        else:
            print("\n  Brak insightu AI")
        
        # === PODSUMOWANIE ===
        print("\n" + "=" * 60)
        print(f"  Raport wygenerowany: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")

        if report["notifications"]["whatsapp_sent"]:
            print("  📱 Raport wysłany na WhatsApp ✓\n")

        if report["notifications"]["email_sent"]:
            print("  📧 Raport wysłany na email ✓\n")

        # Zamknięcie sesji
        session.close()
        engine.dispose()
        
    except Exception as e:
        logger.error(f"Błąd podczas generowania raportu: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
