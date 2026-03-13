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

import os
import sys
import logging
import argparse
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import init_db
from app.db.repository import GarminRepository
from app.collectors.garmin_client import GarminClient
from app.processors.recovery_score import RecoveryScore
from app.processors.sleep_metrics import SleepMetrics
from app.processors.hrv_metrics import HRVMetrics
from app.ai.insights import InsightsGenerator
from app.notifications.email_report import send_training_suggestion_email

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

# Nazwy dni po polsku (weekday(): 0=pon, 6=nd)
DAY_NAMES_PL = {
    0: "Poniedziałek",
    1: "Wtorek",
    2: "Środa",
    3: "Czwartek",
    4: "Piątek",
    5: "Sobota",
    6: "Niedziela",
}


def load_training_plan(plan_file: str = "training_plan.md") -> dict:
    """
    Parsuje training_plan.md.
    Zwraca dict {'Poniedziałek': 'opis treningu', ..., '_notes': 'sekcja uwag'}
    """
    path = Path(plan_file)
    if not path.exists():
        logger.warning(f"Brak pliku {plan_file} — uruchom bez planu")
        return {}

    content = path.read_text(encoding="utf-8")
    plan = {}
    current_day = None
    notes_section = []
    in_notes = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue

        # Nagłówek dnia (## Poniedziałek etc.)
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            if heading in DAY_NAMES_PL.values():
                current_day = heading
                plan[current_day] = []
                in_notes = False
            elif "uwag" in heading.lower() or "priorytet" in heading.lower():
                in_notes = True
                current_day = None
            else:
                current_day = None
                in_notes = False
        elif current_day:
            plan[current_day].append(stripped.lstrip("- "))
        elif in_notes:
            notes_section.append(stripped.lstrip("- "))

    # Zamień listy na stringi
    result = {day: "\n".join(lines) for day, lines in plan.items() if lines}
    result["_notes"] = "\n".join(notes_section)
    return result


def extract_body_battery(raw_data) -> tuple[int | None, str]:
    """
    Wyciąga aktualny Body Battery i trend z surowych danych API.
    Garmin zwraca: [{"bodyBatteryValuesArray": [[timestamp_ms, level], ...], "charged": X, ...}]
    Zwraca (bieżąca wartość, opis_trendu).
    """
    if not raw_data:
        return None, ""

    # Główny format: lista z jednym dictem zawierającym bodyBatteryValuesArray
    if isinstance(raw_data, list) and raw_data:
        item = raw_data[0] if isinstance(raw_data[0], dict) else None
        if item:
            values_array = item.get("bodyBatteryValuesArray", [])
            if values_array:
                # Każdy wpis to [timestamp_ms, poziom] lub [timestamp_ms, poziom, status]
                levels = [
                    entry[1] for entry in values_array
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2 and entry[1] is not None
                ]
                if levels:
                    current = levels[-1]
                    if len(levels) >= 4:
                        earlier = levels[max(0, len(levels) - 4)]
                        diff = current - earlier
                        if diff >= 5:
                            trend = "ładowanie ↑"
                        elif diff <= -5:
                            trend = "rozładowanie ↓"
                        else:
                            trend = "stabilny →"
                    else:
                        trend = ""
                    return int(current), trend
            # fallback: pole "charged" = poziom po naładowaniu
            val = item.get("charged")
            return (int(val) if val is not None else None), ""

    # Fallback dla dictów
    if isinstance(raw_data, dict):
        val = (raw_data.get("bodyBatteryLevel")
               or raw_data.get("charged")
               or raw_data.get("bodyBatteryHighestValue"))
        return (int(val) if val is not None else None), ""

    return None, ""


def main():
    parser = argparse.ArgumentParser(description="Propozycja treningu na dziś")
    parser.add_argument("--date", help="Data w formacie YYYY-MM-DD (domyślnie: dziś)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    day_name = DAY_NAMES_PL[target_date.weekday()]

    print("\n" + "💪 PROPOZYCJA TRENINGU AI".center(60))
    print(f"{'Data: ' + str(target_date) + '  (' + day_name + ')':^60}")
    print("=" * 60)

    # === BAZA DANYCH ===
    engine, SessionLocal = init_db()
    session = SessionLocal()
    repo = GarminRepository(session)

    # === POŁĄCZENIE Z GARMIN — świeże dane ===
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    print("\n  Pobieranie aktualnych danych z Garmin...")
    garmin = GarminClient(email, password) if email and password else None

    body_battery_raw = None
    stress_raw = None

    if garmin and garmin.connect():
        body_battery_raw = garmin.get_body_battery(target_date)
        stress_raw = garmin.get_daily_stats(target_date)
        # Zapisz do bazy (odśwież)
        if stress_raw:
            repo.save_daily_metrics(target_date, stress_raw)
        print("  Dane Garmin odświeżone ✓")
    else:
        print("  ⚠️  Brak połączenia z Garmin — używam danych z bazy")

    # Body Battery
    body_battery, bb_trend = extract_body_battery(body_battery_raw)

    # Stres ze statystyk dziennych
    daily = repo.get_daily_metrics(target_date)
    avg_stress = daily.avg_stress_level if daily else None

    # === DANE Z PROCESORÓW ===
    recovery = RecoveryScore(repo)
    sleep_metrics = SleepMetrics(repo)
    hrv_metrics = HRVMetrics(repo)

    readiness = recovery.calculate_daily_readiness(target_date)
    sleep_trends = sleep_metrics.get_sleep_trends(7)
    hrv_trend = hrv_metrics.get_hrv_trend(7)
    from datetime import timedelta
    all_recent = repo.get_activities_in_date_range(
        target_date - timedelta(days=6), target_date
    )
    # Podziel na treningi już wykonane DZIŚ i historię poprzednich dni
    today_str = str(target_date)
    today_activities = [a for a in all_recent if str(a.get('startTimeLocal', ''))[:10] == today_str]
    prev_activities  = [a for a in all_recent if str(a.get('startTimeLocal', ''))[:10] != today_str]

    # Sen dziś (z komponentów gotowości) vs 7-dniowa średnia
    sleep_today_hours = (readiness.get('components') or {}).get('sleep', {}).get('duration_hours')

    # === PLAN TRENINGOWY ===
    plan = load_training_plan()
    planned_workout = plan.get(day_name, "Brak wpisu w planie na ten dzień")
    training_plan_notes = plan.get("_notes", "")

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
    if today_activities:
        print(f"\n  Treningi dziś ({len(today_activities)}):")
        for a in today_activities:
            dur = round(a.get('duration', 0)/60, 0)
            dist = round(a.get('distance', 0)/1000, 2)
            print(f"    ✓ {a.get('activityName','?')}  {int(dur)} min  {dist} km")
    print(f"\n  Plan na {day_name}:")
    print(f"  {planned_workout}")

    # === AI SUGGESTION ===
    print("\n" + "=" * 60)
    ai = InsightsGenerator()

    if not ai.client:
        print("\n  ⚠️  Brak klucza OPENAI_API_KEY — nie można wygenerować propozycji AI")
        sys.exit(0)

    print("\n  Generowanie propozycji treningu...")

    suggestion = ai.generate_training_suggestion(
        day_name=day_name,
        planned_workout=planned_workout,
        body_battery=body_battery,
        body_battery_trend=bb_trend,
        avg_stress=avg_stress,
        readiness=readiness,
        hrv_trend=hrv_trend,
        sleep_data=sleep_trends,
        sleep_today_hours=sleep_today_hours,
        today_activities=today_activities,
        prev_activities=prev_activities,
        training_plan_notes=training_plan_notes,
    )

    if suggestion:
        print(f"\n{suggestion}\n")
        # Zapisz do bazy jako insight
        repo.save_ai_insight(
            target_date=target_date,
            insight_type='training_suggestion',
            title=f'Propozycja treningu {target_date} ({day_name})',
            content=suggestion,
            priority='high'
        )
        # Wyslij na email
        send_training_suggestion_email(
            report_date=str(target_date),
            day_name=day_name,
            planned_workout=planned_workout,
            body_battery=body_battery,
            readiness_score=score,
            sleep_today_hours=sleep_today_hours,
            suggestion=suggestion,
        )
    else:
        print("\n  Nie udało się wygenerować propozycji")

    print("=" * 60 + "\n")
    session.close()
    engine.dispose()


if __name__ == "__main__":
    main()
