"""Moduł do wysyłki raportów przez WhatsApp (Twilio)"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _build_report_message(
    report_date: str,
    readiness: dict,
    sleep: dict,
    hrv: dict,
    weight_kg: Optional[float],
    vo2max: Optional[float],
    ai_insight: Optional[str],
) -> str:
    """Buduje treść wiadomości WhatsApp z raportu."""
    score = readiness.get('readiness_score', 0)
    category = readiness.get('category', '').upper()

    if score >= 80:
        score_emoji = "🟢"
    elif score >= 60:
        score_emoji = "🟡"
    else:
        score_emoji = "🔴"

    lines = [
        f"🏃 *Raport Garmin AI — {report_date}*",
        "",
        f"{score_emoji} *Gotowość:* {score:.0f}/100 ({category})",
        f"😴 *Sen:* {sleep.get('average_duration_hours', 0):.1f} h  |  jakość {sleep.get('average_quality_score', 0):.0f}/100",
        f"💓 *HRV:* {hrv.get('average_hrv', 0):.0f}  |  trend {hrv.get('trend', 'brak').upper()}  ({hrv.get('change_percent', 0):+.1f}%)",
    ]

    if weight_kg:
        lines.append(f"⚖️  *Waga:* {weight_kg:.1f} kg")
    if vo2max:
        lines.append(f"🫁 *VO2max:* {vo2max:.1f} ml/kg/min")

    lines.append("")
    lines.append(f"📋 *Rekomendacja:* {readiness.get('recommendation', '')}")

    if ai_insight:
        # Ogranicz AI insight do ~600 znaków żeby zmieścić w jednej wiadomości
        short_insight = ai_insight.strip()
        if len(short_insight) > 600:
            short_insight = short_insight[:597] + "..."
        lines.append("")
        lines.append("🤖 *AI:*")
        lines.append(short_insight)

    return "\n".join(lines)


def send_whatsapp_report(
    report_date: str,
    readiness: dict,
    sleep: dict,
    hrv: dict,
    weight_kg: Optional[float] = None,
    vo2max: Optional[float] = None,
    ai_insight: Optional[str] = None,
) -> bool:
    """
    Wysyła raport poranny przez WhatsApp (Twilio).

    Zmienne środowiskowe:
        TWILIO_ACCOUNT_SID   — SID konta Twilio
        TWILIO_AUTH_TOKEN    — token uwierzytelniający
        TWILIO_WHATSAPP_FROM — numer nadawcy w formacie whatsapp:+14155238886
        TWILIO_WHATSAPP_TO   — Twój numer w formacie whatsapp:+48XXXXXXXXX

    Returns:
        True jeśli wiadomość wysłana, False w przeciwnym razie.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM")
    to_number = os.environ.get("TWILIO_WHATSAPP_TO")

    if not all([account_sid, auth_token, from_number, to_number]):
        logger.warning(
            "Brak konfiguracji Twilio — pomiń wysyłkę WhatsApp. "
            "Ustaw TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "TWILIO_WHATSAPP_FROM, TWILIO_WHATSAPP_TO w pliku .env"
        )
        return False

    try:
        from twilio.rest import Client  # import leniwy — twilio jest opcjonalne

        body = _build_report_message(
            report_date=report_date,
            readiness=readiness,
            sleep=sleep,
            hrv=hrv,
            weight_kg=weight_kg,
            vo2max=vo2max,
            ai_insight=ai_insight,
        )

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to_number,
        )
        logger.info(f"Raport WhatsApp wysłany — SID: {message.sid}")
        return True

    except ImportError:
        logger.error("Pakiet twilio nie jest zainstalowany. Uruchom: pip install twilio")
        return False
    except Exception as e:
        logger.error(f"Błąd wysyłki WhatsApp: {e}", exc_info=True)
        return False
