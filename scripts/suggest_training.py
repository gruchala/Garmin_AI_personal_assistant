#!/usr/bin/env python3
"""
Propozycja treningu na dziś.

Skrypt:
1. Łączy się z Garmin i pobiera AKTUALNY Body Battery + stres (świeże dane)
2. Wczytuje plan tygodniowy z training_plan.md
3. Konfrontuje plan z aktualnym stanem organizmu
4. Generuje spersonalizowaną propozycję treningu przez AI

Użycie:
    ./bin/python scripts/suggest_training.py
    ./bin/python scripts/suggest_training.py --date 2026-03-13  # inny dzień
"""

import sys
import logging
import argparse
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import init_db
from app.db.repository import GarminRepository
from app.services.workflows import build_training_suggestion

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/suggest_training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Propozycja treningu na dziś")
    parser.add_argument("--date", help="Data w formacie YYYY-MM-DD (domyślnie: dziś)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    print("\n" + "💪 PROPOZYCJA TRENINGU AI".center(60))
    print(f"{'Data: ' + str(target_date):^60}")
    print("=" * 60)

    engine, SessionLocal = init_db()
    session = SessionLocal()
    repo = GarminRepository(session)
    result = build_training_suggestion(repo, target_date=target_date, send_email=True)
    day_name = result["day_name"]
    body_battery = result["body_battery"]["value"]
    bb_trend = result["body_battery"]["trend"]
    avg_stress = result["avg_stress"]
    readiness = result["readiness"]
    sleep_trends = result["sleep"]
    sleep_today_hours = (readiness.get('components') or {}).get('sleep', {}).get('duration_hours')
    today_activities = result["today_activities"]
    planned_workout = result["planned_workout"]

    # === WYŚWIETL STAN ===
    bb_display = f"{body_battery}/100" if body_battery is not None else "brak"
    if bb_trend:
        bb_display += f" ({bb_trend})"

    score = readiness.get('readiness_score', 0)
    category = readiness.get('category', '').upper()

    sleep_today_str = f"{sleep_today_hours:.1f} h" if sleep_today_hours else "brak"
    sleep_avg_str   = f"{sleep_trends.get('average_duration_hours', '?'):.1f} h" if sleep_trends.get('average_duration_hours') else "brak"

    print(f"\n  Body Battery:   {bb_display}")
    print(f"  Stres (dziś):   {avg_stress or 'brak'}/100")
    print(f"  Sen dziś:       {sleep_today_str}  (śr. 7-dniowa: {sleep_avg_str})")
    print(f"  Gotowość:       {score:.0f}/100 ({category})")
    print(f"  Sync dni:       {result['sync']['synced_days']}")
    print(f"  Nowe aktywności:{result['sync']['synced_recent_activities']}")
    if today_activities:
        print(f"\n  Treningi dziś ({len(today_activities)}):")
        for a in today_activities:
            dur = round(a.get('duration', 0)/60, 0)
            dist = round(a.get('distance', 0)/1000, 2)
            print(f"    ✓ {a.get('activityName','?')}  {int(dur)} min  {dist} km")
    print(f"\n  Plan na {day_name}:")
    print(f"  {planned_workout}")

    print("\n" + "=" * 60)
    if result["suggestion"]:
        print(f"\n{result['suggestion']}\n")
    else:
        print("\n  Nie udało się wygenerować propozycji")

    print("=" * 60 + "\n")
    session.close()
    engine.dispose()


if __name__ == "__main__":
    main()
