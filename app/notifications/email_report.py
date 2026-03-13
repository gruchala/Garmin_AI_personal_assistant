"""Moduł do wysyłki raportów przez email (SMTP)"""

import os
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import date

logger = logging.getLogger(__name__)


def _score_emoji(score: float) -> str:
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    return "🔴"


def _build_daily_report_html(
    report_date: str,
    readiness: dict,
    sleep: dict,
    hrv: dict,
    weight_kg: Optional[float],
    vo2max: Optional[float],
    ai_insight: Optional[str],
) -> tuple[str, str]:
    """Zwraca (subject, html_body) dla raportu dziennego."""
    score = readiness.get('readiness_score', 0)
    category = readiness.get('category', '').upper()
    emoji = _score_emoji(score)

    subject = f"{emoji} Garmin AI — Raport {report_date} | Gotowość {score:.0f}/100 ({category})"

    sleep_h = sleep.get('average_duration_hours', 0)
    sleep_q = sleep.get('average_quality_score', 0)
    hrv_val = hrv.get('average_hrv', 0)
    hrv_trend = hrv.get('trend', 'brak').upper()
    hrv_change = hrv.get('change_percent', 0)
    recommendation = readiness.get('recommendation', '')

    rows = [
        ("Gotowość", f"{score:.0f}/100 ({category})", emoji),
        ("Sen", f"{sleep_h:.1f} h  |  jakość {sleep_q:.0f}/100", "😴"),
        ("HRV", f"{hrv_val:.0f}  |  trend {hrv_trend}  ({hrv_change:+.1f}%)", "💓"),
    ]
    if weight_kg:
        rows.append(("Waga", f"{weight_kg:.1f} kg", "⚖️"))
    if vo2max:
        rows.append(("VO2max", f"{vo2max:.1f} ml/kg/min", "🫁"))

    table_rows = "\n".join(
        f"""<tr>
          <td style="padding:8px 12px;font-size:20px">{r[2]}</td>
          <td style="padding:8px 12px;color:#888;font-weight:600">{r[0]}</td>
          <td style="padding:8px 12px;font-size:16px;font-weight:700">{r[1]}</td>
        </tr>"""
        for r in rows
    )

    ai_block = ""
    if ai_insight:
        ai_text = ai_insight.strip().replace("\n", "<br>")
        ai_block = f"""
        <div style="background:#f0f4ff;border-left:4px solid #4f8ef7;border-radius:6px;padding:16px;margin-top:24px">
          <div style="font-size:13px;color:#4f8ef7;font-weight:700;margin-bottom:8px">🤖 AI INSIGHT</div>
          <div style="font-size:15px;line-height:1.6;color:#333">{ai_text}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)">

    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:24px 28px">
      <div style="color:#fff;font-size:22px;font-weight:700">🏃 Garmin AI Analytics</div>
      <div style="color:#aaa;font-size:14px;margin-top:4px">Raport dzienny — {report_date}</div>
    </div>

    <div style="padding:24px 28px">
      <table style="width:100%;border-collapse:collapse">
        {table_rows}
      </table>

      <div style="margin-top:20px;padding:14px 16px;background:#fafafa;border-radius:8px;border:1px solid #eee">
        <div style="font-size:12px;color:#888;font-weight:600;margin-bottom:6px">📋 REKOMENDACJA</div>
        <div style="font-size:15px;color:#333">{recommendation}</div>
      </div>
      {ai_block}
    </div>

    <div style="padding:14px 28px;background:#fafafa;border-top:1px solid #eee;text-align:center;font-size:12px;color:#aaa">
      Wygenerowano automatycznie przez Garmin AI Analytics
    </div>
  </div>
</body>
</html>"""

    return subject, html


def _build_training_suggestion_html(
    report_date: str,
    day_name: str,
    planned_workout: str,
    body_battery: Optional[int],
    readiness_score: float,
    sleep_today_hours: Optional[float],
    suggestion: str,
) -> tuple[str, str]:
    """Zwraca (subject, html_body) dla propozycji treningu."""
    bb_str = f"{body_battery}/100" if body_battery is not None else "brak"
    sleep_str = f"{sleep_today_hours:.1f} h" if sleep_today_hours else "brak"

    subject = f"💪 Propozycja treningu — {day_name} {report_date} | BB {bb_str}"

    suggestion_html = suggestion.strip().replace("\n", "<br>")

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)">

    <div style="background:linear-gradient(135deg,#1a2e1a,#163e16);padding:24px 28px">
      <div style="color:#fff;font-size:22px;font-weight:700">💪 Propozycja Treningu AI</div>
      <div style="color:#aaa;font-size:14px;margin-top:4px">{day_name}, {report_date}</div>
    </div>

    <div style="padding:24px 28px">
      <table style="width:100%;border-collapse:collapse">
        <tr>
          <td style="padding:8px 12px;font-size:20px">🔋</td>
          <td style="padding:8px 12px;color:#888;font-weight:600">Body Battery</td>
          <td style="padding:8px 12px;font-size:16px;font-weight:700">{bb_str}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;font-size:20px">📊</td>
          <td style="padding:8px 12px;color:#888;font-weight:600">Gotowość</td>
          <td style="padding:8px 12px;font-size:16px;font-weight:700">{readiness_score:.0f}/100</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;font-size:20px">😴</td>
          <td style="padding:8px 12px;color:#888;font-weight:600">Sen dziś</td>
          <td style="padding:8px 12px;font-size:16px;font-weight:700">{sleep_str}</td>
        </tr>
      </table>

      <div style="margin-top:16px;padding:14px 16px;background:#fafafa;border-radius:8px;border:1px solid #eee">
        <div style="font-size:12px;color:#888;font-weight:600;margin-bottom:6px">📅 PLAN NA DZIŚ</div>
        <div style="font-size:14px;color:#555">{planned_workout}</div>
      </div>

      <div style="background:#f0f7f0;border-left:4px solid #4caf50;border-radius:6px;padding:16px;margin-top:20px">
        <div style="font-size:13px;color:#4caf50;font-weight:700;margin-bottom:8px">🤖 PROPOZYCJA AI</div>
        <div style="font-size:15px;line-height:1.6;color:#333">{suggestion_html}</div>
      </div>
    </div>

    <div style="padding:14px 28px;background:#fafafa;border-top:1px solid #eee;text-align:center;font-size:12px;color:#aaa">
      Wygenerowano automatycznie przez Garmin AI Analytics
    </div>
  </div>
</body>
</html>"""

    return subject, html


def _send_email(subject: str, html_body: str) -> bool:
    """
    Wysyła email przez SMTP.

    Zmienne środowiskowe:
        EMAIL_SMTP_HOST     — serwer SMTP (np. smtp.gmail.com)
        EMAIL_SMTP_PORT     — port (domyślnie 465 dla SSL, 587 dla TLS)
        EMAIL_SMTP_USER     — login / adres nadawcy
        EMAIL_SMTP_PASSWORD — hasło lub App Password
        EMAIL_TO            — adres odbiorcy (może być taki sam jak nadawca)
    """
    smtp_host = os.environ.get("EMAIL_SMTP_HOST")
    smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "465"))
    smtp_user = os.environ.get("EMAIL_SMTP_USER")
    smtp_pass = os.environ.get("EMAIL_SMTP_PASSWORD")
    email_to   = os.environ.get("EMAIL_TO")

    if not all([smtp_host, smtp_user, smtp_pass, email_to]):
        logger.warning(
            "Brak konfiguracji email — pomiń wysyłkę. "
            "Ustaw EMAIL_SMTP_HOST, EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD, EMAIL_TO w .env"
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if smtp_port == 587:
            # STARTTLS
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, email_to, msg.as_string())
        else:
            # SSL (port 465)
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context(), timeout=15) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, email_to, msg.as_string())

        logger.info(f"Email wysłany do {email_to}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Błąd wysyłki email: {e}", exc_info=True)
        return False


def send_daily_report_email(
    report_date: str,
    readiness: dict,
    sleep: dict,
    hrv: dict,
    weight_kg: Optional[float] = None,
    vo2max: Optional[float] = None,
    ai_insight: Optional[str] = None,
) -> bool:
    """Wysyła dzienny raport zdrowotny na email."""
    subject, html = _build_daily_report_html(
        report_date=report_date,
        readiness=readiness,
        sleep=sleep,
        hrv=hrv,
        weight_kg=weight_kg,
        vo2max=vo2max,
        ai_insight=ai_insight,
    )
    return _send_email(subject, html)


def send_training_suggestion_email(
    report_date: str,
    day_name: str,
    planned_workout: str,
    body_battery: Optional[int],
    readiness_score: float,
    sleep_today_hours: Optional[float],
    suggestion: str,
) -> bool:
    """Wysyła propozycję treningu na email."""
    subject, html = _build_training_suggestion_html(
        report_date=report_date,
        day_name=day_name,
        planned_workout=planned_workout,
        body_battery=body_battery,
        readiness_score=readiness_score,
        sleep_today_hours=sleep_today_hours,
        suggestion=suggestion,
    )
    return _send_email(subject, html)
