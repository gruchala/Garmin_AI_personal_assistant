"""Wspólne workflow do synchronizacji i generowania odpowiedzi."""

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

from ..ai.insights import InsightsAssistant, InsightsGenerator
from ..collectors.garmin_client import GarminClient
from ..collectors.sync_activities import ActivitiesSync
from ..collectors.sync_daily import DailyDataSync
from ..db.repository import GarminRepository
from ..notifications.email_report import (
    send_daily_report_email,
    send_training_suggestion_email,
)
from ..notifications.whatsapp import send_whatsapp_report
from ..processors.hrv_metrics import HRVMetrics
from ..processors.recovery_score import RecoveryScore
from ..processors.sleep_metrics import SleepMetrics

logger = logging.getLogger(__name__)

load_dotenv()

DAY_NAMES_PL = {
    0: "Poniedziałek",
    1: "Wtorek",
    2: "Środa",
    3: "Czwartek",
    4: "Piątek",
    5: "Sobota",
    6: "Niedziela",
}


def load_training_plan(plan_file: str = "training_plan.md") -> dict[str, str]:
    """Parsuje plan treningowy z pliku markdown."""
    path = Path(plan_file)
    if not path.exists():
        logger.warning("Brak pliku %s — uruchamiam bez planu", plan_file)
        return {}

    content = path.read_text(encoding="utf-8")
    plan: dict[str, list[str]] = {}
    current_day: Optional[str] = None
    notes_section: list[str] = []
    in_notes = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue

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

    result = {day: "\n".join(lines) for day, lines in plan.items() if lines}
    result["_notes"] = "\n".join(notes_section)
    return result


def extract_body_battery(raw_data: Any) -> tuple[Optional[int], str]:
    """Wyciąga bieżący poziom Body Battery i prosty trend."""
    if not raw_data:
        return None, ""

    if isinstance(raw_data, list) and raw_data:
        item = raw_data[0] if isinstance(raw_data[0], dict) else None
        if item:
            values_array = item.get("bodyBatteryValuesArray", [])
            if values_array:
                levels = [
                    entry[1]
                    for entry in values_array
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

            charged = item.get("charged")
            return (int(charged) if charged is not None else None), ""

    if isinstance(raw_data, dict):
        value = (
            raw_data.get("bodyBatteryLevel")
            or raw_data.get("charged")
            or raw_data.get("bodyBatteryHighestValue")
        )
        return (int(value) if value is not None else None), ""

    return None, ""


def connect_garmin_from_env() -> GarminClient:
    """Łączy się z Garmin Connect używając sekretów z .env."""
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if not email or not password:
        raise RuntimeError("Brak GARMIN_EMAIL lub GARMIN_PASSWORD w środowisku")

    client = GarminClient(email, password)
    if not client.connect():
        raise RuntimeError("Nie udało się połączyć z Garmin Connect")

    return client


def run_full_sync(
    repository: GarminRepository,
    target_date: Optional[date] = None,
    sync_days: int = 7,
    activity_limit: int = 50,
) -> dict[str, Any]:
    """Wykonuje pełną synchronizację potrzebną do świeżej analizy."""
    target_date = target_date or date.today()
    client = connect_garmin_from_env()

    daily_sync = DailyDataSync(client, repository)
    synced_days = daily_sync.sync_last_n_days(sync_days)

    activities_sync = ActivitiesSync(client, repository)
    synced_recent_activities = activities_sync.sync_recent_activities(activity_limit)
    synced_target_day_activities = activities_sync.sync_activities_for_date(target_date)

    return {
        "client": client,
        "summary": {
            "target_date": target_date.isoformat(),
            "synced_days": synced_days,
            "synced_recent_activities": synced_recent_activities,
            "synced_target_day_activities": synced_target_day_activities,
            "activity_limit": activity_limit,
        },
    }


def build_daily_report(
    repository: GarminRepository,
    target_date: Optional[date] = None,
    send_notifications: bool = False,
    quick_note: Optional[str] = None,
) -> dict[str, Any]:
    """Generuje świeży raport dzienny po pełnej synchronizacji."""
    target_date = target_date or date.today()
    sync_result = run_full_sync(repository, target_date=target_date)

    recovery = RecoveryScore(repository)
    sleep_metrics = SleepMetrics(repository)
    hrv_metrics = HRVMetrics(repository)

    readiness = recovery.calculate_daily_readiness(target_date)
    sleep_trends = sleep_metrics.get_sleep_trends(7)
    sleep_consistency = sleep_metrics.analyze_sleep_consistency(14)
    hrv_baseline = hrv_metrics.calculate_baseline(28)
    hrv_trend = hrv_metrics.get_hrv_trend(7)
    weekly = recovery.get_weekly_recovery_report()

    ai = InsightsGenerator()
    assistant = InsightsAssistant(repository, ai)
    insight = assistant.get_daily_insight(target_date, quick_note=quick_note) if ai.client else None

    latest_weight = repository.get_latest_weight()
    latest_vo2 = repository.get_latest_vo2max()
    weight_kg = (latest_weight.weight_grams / 1000) if latest_weight and latest_weight.weight_grams else None
    vo2max_value = latest_vo2.vo2max_precise if latest_vo2 and latest_vo2.vo2max_precise else None

    notifications = {"whatsapp_sent": False, "email_sent": False}
    if send_notifications:
        notifications["whatsapp_sent"] = send_whatsapp_report(
            report_date=target_date.isoformat(),
            readiness=readiness,
            sleep=sleep_trends,
            hrv=hrv_trend,
            weight_kg=weight_kg,
            vo2max=vo2max_value,
            ai_insight=insight if ai.client else None,
        )
        notifications["email_sent"] = send_daily_report_email(
            report_date=target_date.isoformat(),
            readiness=readiness,
            sleep=sleep_trends,
            hrv=hrv_trend,
            weight_kg=weight_kg,
            vo2max=vo2max_value,
            ai_insight=insight if ai.client else None,
        )

    return {
        "date": target_date.isoformat(),
        "sync": sync_result["summary"],
        "readiness": readiness,
        "sleep": sleep_trends,
        "sleep_consistency": sleep_consistency,
        "hrv": hrv_trend,
        "hrv_baseline": hrv_baseline,
        "weekly": weekly,
        "weight": {
            "date": latest_weight.date.isoformat() if latest_weight else None,
            "weight_kg": weight_kg,
            "bmi": latest_weight.bmi if latest_weight else None,
            "body_fat_percent": latest_weight.body_fat_percent if latest_weight else None,
        },
        "vo2max": {
            "date": latest_vo2.date.isoformat() if latest_vo2 else None,
            "vo2max": vo2max_value,
            "fitness_age": latest_vo2.fitness_age if latest_vo2 else None,
        },
        "insight": insight,
        "notifications": notifications,
    }


def build_training_suggestion(
    repository: GarminRepository,
    target_date: Optional[date] = None,
    send_email: bool = False,
    quick_note: Optional[str] = None,
) -> dict[str, Any]:
    """Generuje świeżą propozycję treningową po pełnym syncu."""
    target_date = target_date or date.today()
    sync_result = run_full_sync(repository, target_date=target_date)
    client: GarminClient = sync_result["client"]

    body_battery_raw = client.get_body_battery(target_date)
    body_battery, body_battery_trend = extract_body_battery(body_battery_raw)

    recovery = RecoveryScore(repository)
    sleep_metrics = SleepMetrics(repository)
    hrv_metrics = HRVMetrics(repository)

    readiness = recovery.calculate_daily_readiness(target_date)
    sleep_trends = sleep_metrics.get_sleep_trends(7)
    hrv_trend = hrv_metrics.get_hrv_trend(7)

    start_date = target_date - timedelta(days=6)
    all_recent = repository.get_activities_in_date_range(start_date, target_date)
    target_day_prefix = str(target_date)
    today_activities = [
        activity for activity in all_recent
        if str(activity.get("startTimeLocal", ""))[:10] == target_day_prefix
    ]
    previous_activities = [
        activity for activity in all_recent
        if str(activity.get("startTimeLocal", ""))[:10] != target_day_prefix
    ]

    sleep_today_hours = (readiness.get("components") or {}).get("sleep", {}).get("duration_hours")
    daily_metrics = repository.get_daily_metrics(target_date)
    avg_stress = daily_metrics.avg_stress_level if daily_metrics else None

    day_name = DAY_NAMES_PL[target_date.weekday()]
    plan = load_training_plan()
    planned_workout = plan.get(day_name, "Brak wpisu w planie na ten dzień")
    training_plan_notes = plan.get("_notes", "")

    ai = InsightsGenerator()
    suggestion = None
    if ai.client:
        suggestion = ai.generate_training_suggestion(
            day_name=day_name,
            planned_workout=planned_workout,
            body_battery=body_battery,
            body_battery_trend=body_battery_trend,
            avg_stress=avg_stress,
            readiness=readiness,
            hrv_trend=hrv_trend,
            sleep_data=sleep_trends,
            sleep_today_hours=sleep_today_hours,
            today_activities=today_activities,
            prev_activities=previous_activities,
            training_plan_notes=training_plan_notes,
            quick_note=quick_note,
        )

    email_sent = False
    if suggestion:
        repository.save_ai_insight(
            target_date=target_date,
            insight_type="training_suggestion",
            title=f"Propozycja treningu {target_date} ({day_name})",
            content=suggestion,
            priority="high",
        )
        if send_email:
            email_sent = send_training_suggestion_email(
                report_date=target_date.isoformat(),
                day_name=day_name,
                planned_workout=planned_workout,
                body_battery=body_battery,
                readiness_score=readiness.get("readiness_score", 0),
                sleep_today_hours=sleep_today_hours,
                suggestion=suggestion,
            )

    return {
        "date": target_date.isoformat(),
        "day_name": day_name,
        "sync": sync_result["summary"],
        "readiness": readiness,
        "sleep": sleep_trends,
        "hrv": hrv_trend,
        "body_battery": {
            "value": body_battery,
            "trend": body_battery_trend,
        },
        "avg_stress": avg_stress,
        "planned_workout": planned_workout,
        "training_plan_notes": training_plan_notes,
        "today_activities": today_activities,
        "suggestion": suggestion,
        "email_sent": email_sent,
    }
