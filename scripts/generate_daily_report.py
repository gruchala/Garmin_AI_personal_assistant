#!/usr/bin/env python3
"""Skrypt do generowania dziennego raportu"""

import os
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
from app.processors.recovery_score import RecoveryScore
from app.processors.sleep_metrics import SleepMetrics
from app.processors.hrv_metrics import HRVMetrics
from app.ai.insights import InsightsGenerator, InsightsAssistant
from app.notifications.whatsapp import send_whatsapp_report

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
        
        # Inicjalizacja procesorów
        recovery = RecoveryScore(repo)
        sleep_metrics = SleepMetrics(repo)
        hrv_metrics = HRVMetrics(repo)
        
        # === GOTOWOŚĆ DO TRENINGU ===
        print_section("GOTOWOŚĆ DO TRENINGU")
        
        readiness = recovery.calculate_daily_readiness()
        
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
        
        sleep_trends = sleep_metrics.get_sleep_trends(7)

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
        consistency = sleep_metrics.analyze_sleep_consistency(14)
        print(f"\n  Regularność: {consistency['consistency_score']:.1f}/100")
        print(f"  {consistency['message']}")
        
        # === TRENDY HRV ===
        print_section("ANALIZA HRV (7 DNI)")
        
        baseline = hrv_metrics.calculate_baseline(28)
        if baseline:
            print(f"\n  Baseline (28 dni):")
            print(f"    • Średnia: {baseline['mean']:.1f}")
            print(f"    • Odchylenie: {baseline['stdev']:.1f}")
            print(f"    • Zakres: {baseline['min']:.1f} - {baseline['max']:.1f}")
        
        hrv_trend = hrv_metrics.get_hrv_trend(7)
        print(f"\n  Trend 7-dniowy: {hrv_trend['trend'].upper()}")
        print(f"  Średnia HRV: {hrv_trend['average_hrv']:.1f}")
        print(f"  Zmiana: {hrv_trend['change_percent']:+.1f}%")
        
        # Ryzyko przetrenowania
        overtraining = hrv_metrics.detect_overtraining_risk(14)
        print(f"\n  ⚠️  Ryzyko przetrenowania: {overtraining['risk_level'].upper()}")
        print(f"  {overtraining['message']}")

        # === MASA CIAŁA I VO2MAX ===
        print_section("SKŁAD CIAŁA I VO2MAX")

        latest_weight = repo.get_latest_weight()
        if latest_weight:
            weight_kg = latest_weight.weight_grams / 1000 if latest_weight.weight_grams else None
            print(f"\n  Masa ciała ({latest_weight.date}):")
            if weight_kg:
                print(f"    • Waga:          {weight_kg:.1f} kg")
            if latest_weight.bmi:
                print(f"    • BMI:           {latest_weight.bmi:.1f}")
            if latest_weight.body_fat_percent:
                print(f"    • Tkanka tłuszcz:{latest_weight.body_fat_percent:.1f}%")
            if latest_weight.muscle_mass_grams:
                print(f"    • Masa mięśniowa:{latest_weight.muscle_mass_grams / 1000:.1f} kg")
        else:
            print("\n  Brak danych o masie ciała")
            print("  (Zważenie w Garmin Connect lub kompatybilna waga)")

        latest_vo2 = repo.get_latest_vo2max()
        if latest_vo2:
            print(f"\n  VO2max ({latest_vo2.date}):")
            print(f"    • VO2max:        {latest_vo2.vo2max_precise:.1f} ml/kg/min")
            if latest_vo2.fitness_age:
                print(f"    • Wiek fitness:  {latest_vo2.fitness_age} lat")
        else:
            print("\n  Brak danych VO2max")
            print("  (Wymaga biegania z GPS i pulsometrem)")

        # === RAPORT TYGODNIOWY ===
        print_section("RAPORT TYGODNIOWY")
        
        weekly = recovery.get_weekly_recovery_report()
        
        print(f"\n  Średnia gotowość: {weekly['average_readiness']:.1f}/100")
        print(f"  Trend: {weekly['trend'].upper()}")
        
        print(f"\n  Dzienne wyniki:")
        for day_score in weekly['daily_scores']:
            score_bar = "█" * int(day_score['score'] / 10)
            print(f"    {day_score['date']}: {score_bar} {day_score['score']:.1f} ({day_score['category']})")
        
        # === AI INSIGHT ===
        print_section("AI INSIGHT")
        
        ai = InsightsGenerator()
        assistant = InsightsAssistant(repo, ai)
        insight = None

        if ai.client:
            print("\n  Generowanie insightu...")
            insight = assistant.get_daily_insight()
            
            if insight:
                print(f"\n{insight}")
                
                # Zapisz do bazy
                repo.save_ai_insight(
                    target_date=date.today(),
                    insight_type='daily_report',
                    title=f'Raport dzienny {date.today()}',
                    content=insight,
                    priority='high'
                )
            else:
                print("\n  Nie udało się wygenerować insightu")
        else:
            print("\n  ⚠️  Brak klucza API OpenAI - pomiń generowanie AI insight")
            print("  Ustaw zmienną środowiskową OPENAI_API_KEY aby włączyć tę funkcję")
        
        # === PODSUMOWANIE ===
        print("\n" + "=" * 60)
        print(f"  Raport wygenerowany: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")

        # === WYSYŁKA WHATSAPP ===
        weight_kg = None
        vo2max_val = None
        if latest_weight and latest_weight.weight_grams:
            weight_kg = latest_weight.weight_grams / 1000
        if latest_vo2 and latest_vo2.vo2max_precise:
            vo2max_val = latest_vo2.vo2max_precise

        sent = send_whatsapp_report(
            report_date=str(date.today()),
            readiness=readiness,
            sleep=sleep_trends,
            hrv=hrv_trend,
            weight_kg=weight_kg,
            vo2max=vo2max_val,
            ai_insight=insight if ai.client else None,
        )
        if sent:
            print("  📱 Raport wysłany na WhatsApp ✓\n")

        # Zamknięcie sesji
        session.close()
        engine.dispose()
        
    except Exception as e:
        logger.error(f"Błąd podczas generowania raportu: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
