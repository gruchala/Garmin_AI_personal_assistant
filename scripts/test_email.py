"""Testowy skrypt wysyłki email — sprawdza konfigurację SMTP bez uruchamiania pełnego raportu."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.notifications.email_report import send_daily_report_email, send_training_suggestion_email

print("=" * 60)
print("  TEST WYSYŁKI EMAIL — Garmin AI")
print("=" * 60)

# Sprawdź konfigurację
required = ["EMAIL_SMTP_HOST", "EMAIL_SMTP_USER", "EMAIL_SMTP_PASSWORD", "EMAIL_TO"]
missing = [v for v in required if not os.environ.get(v)]
if missing:
    print(f"\n❌ Brak zmiennych w .env: {', '.join(missing)}")
    print("\nDodaj do .env:")
    print("  EMAIL_SMTP_HOST=smtp.gmail.com")
    print("  EMAIL_SMTP_PORT=465")
    print("  EMAIL_SMTP_USER=twoj_email@gmail.com")
    print("  EMAIL_SMTP_PASSWORD=xxxx_xxxx_xxxx_xxxx  ← App Password z Google")
    print("  EMAIL_TO=twoj_email@gmail.com")
    print("\nGmail: Konto Google → Bezpieczeństwo → Weryfikacja dwuetapowa → Hasła do aplikacji")
    sys.exit(1)

print(f"\n✓ Konfiguracja SMTP: {os.environ['EMAIL_SMTP_HOST']}:{os.environ.get('EMAIL_SMTP_PORT', '465')}")
print(f"✓ Nadawca:  {os.environ['EMAIL_SMTP_USER']}")
print(f"✓ Odbiorca: {os.environ['EMAIL_TO']}")

# --- TEST 1: Raport dzienny ---
print("\n[1/2] Wysyłam testowy raport dzienny...")

ok1 = send_daily_report_email(
    report_date="2026-03-13",
    readiness={
        "readiness_score": 73.5,
        "category": "Good",
        "recommendation": "Dobra gotowość — umiarkowany trening zalecany. Monitoruj sen w najbliższych dniach.",
    },
    sleep={
        "average_duration_hours": 6.8,
        "average_quality_score": 78,
    },
    hrv={
        "average_hrv": 62,
        "trend": "stable",
        "change_percent": 1.2,
    },
    weight_kg=87.2,
    vo2max=47.4,
    ai_insight=(
        "Dziś gotowość na poziomie 73/100 wskazuje na dobrą regenerację po wczorajszym treningu. "
        "HRV stabilny, sen nieco poniżej optimum (6.8h vs. zalecane 7-8h). "
        "Możesz dziś wykonać trening o umiarkowanej intensywności — preferuj bieganie aerobowe lub sesję siłową z zachowaniem techniki."
    ),
)

if ok1:
    print("  ✅ Raport dzienny wysłany!")
else:
    print("  ❌ Błąd wysyłki — sprawdź logi powyżej")

# --- TEST 2: Propozycja treningu ---
print("\n[2/2] Wysyłam testową propozycję treningu...")

ok2 = send_training_suggestion_email(
    report_date="2026-03-13",
    day_name="Czwartek",
    planned_workout="Bieganie 10 km",
    body_battery=72,
    readiness_score=73.5,
    sleep_today_hours=6.8,
    suggestion=(
        "Na podstawie Twoich danych proponuję bieg aerobowy 8-10 km w tempie komfortowym (Z2).\n\n"
        "Body Battery 72/100 i gotowość 73/100 to dobry wynik — stać Cię na porządną jednostkę, "
        "ale nie przeciążaj się przed weekendem.\n\n"
        "Sugestia:\n"
        "• Rozgrzewka: 10 min marsz/trucht\n"
        "• Główna część: 8 km @5:30/km (strefa 2)\n"
        "• Chłodzenie: 5 min spacer + rozciąganie"
    ),
)

if ok2:
    print("  ✅ Propozycja treningu wysłana!")
else:
    print("  ❌ Błąd wysyłki — sprawdź logi powyżej")

# --- Podsumowanie ---
print("\n" + "=" * 60)
if ok1 and ok2:
    print("  ✅ Oba emaile wysłane pomyślnie!")
    print(f"  Sprawdź skrzynkę: {os.environ['EMAIL_TO']}")
elif ok1 or ok2:
    print("  ⚠️  Jeden z emaili nie został wysłany — sprawdź logi")
else:
    print("  ❌ Żaden email nie został wysłany — sprawdź konfigurację")
print("=" * 60 + "\n")
