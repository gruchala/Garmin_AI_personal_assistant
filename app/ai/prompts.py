"""Szablony promptów dla AI"""

from typing import Dict, Any, List


SYSTEM_PROMPT = """Jesteś ekspertem ds. zdrowia, regeneracji i treningu sportowego. 
Analizujesz dane biometryczne i treningowe użytkownika z Garmin Connect, w tym:
- HRV (zmienność rytmu serca)
- Spoczynkowe tętno (RHR)
- Dane o śnie (długość, fazy, jakość)
- Aktywności treningowe
- Body Battery
- Poziomy stresu

Twoim zadaniem jest dostarczanie praktycznych, opartych na danych insightów i rekomendacji.
Odpowiadaj zawsze po polsku, w sposób przystępny i konkretny."""


def get_training_suggestion_prompt(data: Dict[str, Any]) -> str:
    """
    Tworzy prompt do generowania propozycji treningu na dziś.
    Konfrontuje plan tygodniowy z aktualnym Body Battery, gotowością i HRV.
    """
    day_name = data.get('day_name', 'dziś')
    planned = data.get('planned_workout', 'brak planu')
    body_battery = data.get('body_battery', 'brak')
    body_battery_trend = data.get('body_battery_trend', '')
    avg_stress = data.get('avg_stress', 'brak')
    readiness = data.get('readiness', {})
    hrv_trend = data.get('hrv_trend', {})
    sleep = data.get('sleep', {})
    sleep_today_hours = data.get('sleep_today_hours')
    today_activities = data.get('today_activities', [])
    prev_activities = data.get('prev_activities', [])
    training_plan_notes = data.get('training_plan_notes', '')

    def fmt_activity(a):
        name = a.get('activityName') or a.get('activity_name') or '?'
        atype = a.get('activityType') or {}
        if isinstance(atype, dict):
            atype = atype.get('typeKey', '') or ''
        dist_m = a.get('distance') or 0
        dur_s = a.get('duration') or a.get('movingDuration') or 0
        dist_km = round(dist_m / 1000, 2) if dist_m else None
        dur_min = int(round(dur_s / 60, 0)) if dur_s else None
        avg_hr = a.get('averageHR') or a.get('average_hr')
        max_hr_val = a.get('maxHR') or a.get('max_hr')
        te = a.get('aerobicTrainingEffect') or a.get('aerobic_training_effect')
        bb_delta = a.get('differenceBodyBattery')
        dt = str(a.get('startTimeLocal') or a.get('date') or '?')[:16]
        parts = [f"{name}"]
        if atype:
            parts[0] += f" ({atype})"
        if dur_min is not None:
            parts.append(f"{dur_min} min")
        if dist_km:
            parts.append(f"{dist_km} km")
        if avg_hr:
            parts.append(f"HR śr {avg_hr}/{max_hr_val}")
        if te:
            parts.append(f"TE aerob {te:.1f}")
        if bb_delta is not None:
            parts.append(f"BB Δ{bb_delta:+d}")
        return f"  [{dt}] " + ", ".join(parts)

    today_str = "\n".join(fmt_activity(a) for a in today_activities) or "  (żaden)"
    prev_str  = "\n".join(fmt_activity(a) for a in (prev_activities or [])[:7]) or "  brak danych"

    bb_info = f"{body_battery}/100" if body_battery else "brak"
    if body_battery_trend:
        bb_info += f" ({body_battery_trend})"

    sleep_today_str = f"{sleep_today_hours:.1f} h" if sleep_today_hours else "brak danych"
    sleep_avg_str   = f"{sleep.get('average_duration_hours', '?')} h" if sleep.get('average_duration_hours') else "brak"
    quick_note = data.get('quick_note', '')

    return f"""Dzień tygodnia: {day_name}
Kolejność dni tygodnia: Poniedziałek → Wtorek → Środa → Czwartek → Piątek → Sobota → Niedziela.

AKTUALNY STAN (pobrano przed chwilą z Garmin):
- Body Battery: {bb_info}
- Stres (dziś): {avg_stress}/100
- Gotowość do treningu: {readiness.get('readiness_score', 'brak')}/100 ({readiness.get('category', '')})
- Sen DZISIEJSZEJ nocy: {sleep_today_str}  |  średnia 7-dniowa: {sleep_avg_str}
- HRV trend (7 dni): {hrv_trend.get('trend', 'brak')}, średnia {hrv_trend.get('average_hrv', 'brak')}, zmiana {hrv_trend.get('change_percent', 'brak')}%

TRENINGI JUŻ WYKONANE DZIŚ ({day_name}):
{today_str}

PLAN NA DZIŚ ({day_name}):
{planned}

HISTORIA TRENINGÓW (poprzednie 6 dni):
{prev_str}

ZASADY Z PLANU TRENINGOWEGO:
{training_plan_notes}

UWAGA OD UŻYTKOWNIKA NA DZIŚ:
{quick_note if quick_note else "(brak)"}

INSTRUKCJE:
1. Uwzględnij treningi wykonane DZIŚ — jeśli coś już było, oceń co POZOSTAŁO do zrobienia (np. popołudniowy trening).
2. Podaj konkretną propozycję na RESZTĘ dnia (typ, dystans/czas, intensywność, strefy tętna jeśli biegowy).
3. Uzasadnij krótko (2-3 zdania, powołuj się na konkretne liczby).
4. Jeśli proponujesz przeniesienie czegoś — podaj konkretny dzień (pamiętaj: sob przed nd, nd kończy tydzień).

Odpowiedź max 200 słów, konkretna i praktyczna."""


def get_trainer_note_prompt(data: Dict[str, Any]) -> str:
    """
    Tworzy prompt do generowania krótkiej notatki trenera.
    Notatka jest przeznaczona dla agenta — do odczytu przy kolejnych sesjach.
    """
    readiness = data.get('readiness', {})
    sleep = data.get('sleep', {})
    hrv = data.get('hrv_trend', {})
    weight = data.get('weight', {})
    vo2max = data.get('vo2max', {})
    activities = data.get('activities', [])
    report_date = data.get('report_date', 'nieznana')

    acts_summary = ", ".join(
        f"{a.get('activity_type','?')} {a.get('duration_minutes','?')} min"
        for a in (activities or [])[:3]
    ) or "brak"

    return f"""Na podstawie danych z dnia {report_date} zapisz 2-4 zwięzłe obserwacje do swojego notatnika trenera.

DANE DNIA:
- Gotowość: {readiness.get('readiness_score', 'brak')}/100 ({readiness.get('category', '')})
- Sen: {sleep.get('average_duration_hours', sleep.get('duration_hours', 'brak'))} h, jakość {sleep.get('average_quality_score', sleep.get('quality_score', 'brak'))}/100, trend: {sleep.get('trend', 'brak')}
- HRV: {hrv.get('average_hrv', 'brak')}, zmiana {hrv.get('change_percent', 'brak')}%, trend: {hrv.get('trend', 'brak')}
- Waga: {weight.get('weight_kg', 'brak')} kg, tkanka tłuszczowa: {weight.get('body_fat_percent', 'brak')}%
- VO2max: {vo2max.get('vo2max_precise', 'brak')} ml/kg/min
- Aktywności: {acts_summary}

Zapisz TYLKO fakty i obserwacje istotne dla przyszłych sesji — trendy które widzisz, niepokojące wzorce, postępy, rzeczy do monitorowania. Format: lista punktowana, każdy punkt max 1 zdanie. BEZ powtarzania prostych statystyk, TYLKO wnioski."""


def get_daily_summary_prompt(data: Dict[str, Any]) -> str:
    """
    Tworzy prompt do generowania dziennego podsumowania
    
    Args:
        data: Dane do analizy (HRV, sen, RHR, aktywności)
        
    Returns:
        Prompt dla modelu AI
    """
    readiness = data.get('readiness', {})
    sleep = data.get('sleep', {})
    hrv_trend = data.get('hrv_trend', {})
    activities = data.get('activities', [])
    weight = data.get('weight', {})
    vo2max = data.get('vo2max', {})

    body_section = ""
    if weight or vo2max:
        body_section = "\nSKŁAD CIAŁA I VO2MAX:\n"
        if weight:
            w_kg = weight.get('weight_kg')
            body_section += f"- Waga: {w_kg:.1f} kg\n" if w_kg else ""
            if weight.get('body_fat_percent'):
                body_section += f"- Tkanka tłuszczowa: {weight.get('body_fat_percent'):.1f}%\n"
            if weight.get('bmi'):
                body_section += f"- BMI: {weight.get('bmi'):.1f}\n"
        if vo2max:
            body_section += f"- VO2max: {vo2max.get('vo2max_precise')} ml/kg/min\n"
            if vo2max.get('fitness_age'):
                body_section += f"- Wiek fitness: {vo2max.get('fitness_age')} lat\n"

    prompt = f"""Przeanalizuj poniższe dane z dzisiejszego dnia i stwórz zwięzłe podsumowanie (max 150 słów).

GOTOWOŚĆ DO TRENINGU:
- Wynik: {readiness.get('readiness_score', 'brak')}/100
- Kategoria: {readiness.get('category', 'brak')}
- Rekomendacja: {readiness.get('recommendation', 'brak')}

SEN:
- Długość: {sleep.get('average_duration_hours', sleep.get('duration_hours', 'brak'))} godzin
- Jakość: {sleep.get('average_quality_score', sleep.get('quality_score', 'brak'))}/100
- Głęboki sen: {sleep.get('average_deep_sleep_percent', sleep.get('deep_sleep_percent', 'brak'))}%
- REM: {sleep.get('average_rem_sleep_percent', sleep.get('rem_sleep_percent', 'brak'))}%
- Trend snu: {sleep.get('trend', 'brak')}

HRV:
- Trend 7-dniowy: {hrv_trend.get('trend', 'brak')}
- Średnia wartość: {hrv_trend.get('average_hrv', 'brak')}
- Zmiana: {hrv_trend.get('change_percent', 'brak')}%
{body_section}
AKTYWNOŚCI:
{_format_activities(activities)}

UWAGA OD UŻYTKOWNIKA NA DZIŚ:
{data.get('quick_note') or "(brak)"}

Stwórz krótkie, praktyczne podsumowanie dnia ze szczególnym uwzględnieniem gotowości do treningu."""
    
    return prompt


def get_trend_analysis_prompt(data: Dict[str, Any]) -> str:
    """
    Tworzy prompt do analizy trendów
    
    Args:
        data: Dane trendów z ostatnich tygodni
        
    Returns:
        Prompt dla modelu AI
    """
    sleep_trends = data.get('sleep_trends', {})
    hrv_trend = data.get('hrv_trend', {})
    recovery_report = data.get('recovery_report', {})
    
    prompt = f"""Przeanalizuj trendy z ostatnich {data.get('days', 7)} dni i wskaż kluczowe obserwacje.

TRENDY SNU:
- Średnia długość: {sleep_trends.get('average_duration_hours', 'brak')} h
- Średnia jakość: {sleep_trends.get('average_quality_score', 'brak')}/100
- Trend: {sleep_trends.get('trend', 'brak')}
- Regularność: {sleep_trends.get('consistency_score', 'brak')}/100

TRENDY HRV:
- Trend: {hrv_trend.get('trend', 'brak')}
- Średnia: {hrv_trend.get('average_hrv', 'brak')}
- Zmiana: {hrv_trend.get('change_percent', 'brak')}%

REGENERACJA:
- Średnia gotowość: {recovery_report.get('average_readiness', 'brak')}/100
- Trend: {recovery_report.get('trend', 'brak')}

RYZYKO PRZETRENOWANIA:
{recovery_report.get('overtraining_risk', {}).get('message', 'brak danych')}

Wskaż:
1. Najważniejsze trendy (pozytywne i negatywne)
2. Czy są sygnały ostrzegawcze
3. Konkretne rekomendacje na najbliższe dni"""
    
    return prompt


def get_training_recommendation_prompt(data: Dict[str, Any]) -> str:
    """
    Tworzy prompt do rekomendacji treningowych
    
    Args:
        data: Dane o aktualnym stanie i planowanych treningach
        
    Returns:
        Prompt dla modelu AI
    """
    readiness = data.get('readiness', {})
    recent_activities = data.get('recent_activities', [])
    training_load = data.get('training_load', {})
    user_question = data.get('question', '')
    
    prompt = f"""Użytkownik pyta: "{user_question}"

AKTUALNA GOTOWOŚĆ:
- Wynik: {readiness.get('readiness_score', 'brak')}/100
- HRV status: {readiness.get('components', {}).get('hrv', {}).get('status', 'brak')}
- Jakość snu: {readiness.get('components', {}).get('sleep', {}).get('score', 'brak')}/100

OSTATNIE TRENINGI (7 dni):
{_format_training_summary(recent_activities)}

OBCIĄŻENIE TRENINGOWE:
- Łączne obciążenie: {training_load.get('total_load', 'brak')}
- Liczba treningów: {training_load.get('activity_count', 'brak')}

Na podstawie tych danych:
1. Odpowiedz na pytanie użytkownika
2. Zasugeruj konkretny typ treningu (jeśli ma trenować)
3. Określ odpowiednią intensywność i czas trwania
4. Ostrzeż przed przeciążeniem jeśli to konieczne"""
    
    return prompt


def get_sleep_analysis_prompt(data: Dict[str, Any]) -> str:
    """
    Tworzy prompt do analizy snu
    
    Args:
        data: Dane o śnie z ostatnich dni
        
    Returns:
        Prompt dla modelu AI
    """
    sleep_trends = data.get('sleep_trends', {})
    consistency = data.get('consistency', {})
    recent_sleep = data.get('recent_sleep', [])
    
    prompt = f"""Przeanalizuj jakość i wzorce snu.

OGÓLNE TRENDY:
- Średnia długość: {sleep_trends.get('average_duration_hours', 'brak')} h
- Średnia jakość: {sleep_trends.get('average_quality_score', 'brak')}/100
- Głęboki sen: {sleep_trends.get('average_deep_sleep_percent', 'brak')}%
- REM: {sleep_trends.get('average_rem_sleep_percent', 'brak')}%
- Trend: {sleep_trends.get('trend', 'brak')}

REGULARNOŚĆ:
- Wynik regularności: {consistency.get('consistency_score', 'brak')}/100
- Średnia godzina snu: {consistency.get('avg_sleep_hour', 'brak')}
- Średnia godzina budzenia: {consistency.get('avg_wake_hour', 'brak')}

OSTATNIE NOCE:
{_format_sleep_details(recent_sleep)}

Wskaż:
1. Jak sen wpływa na regenerację
2. Czy są wzorce do poprawy
3. Konkretne rekomendacje higieniczne (godziny, rutyna)"""
    
    return prompt


def get_correlation_analysis_prompt(data: Dict[str, Any]) -> str:
    """
    Tworzy prompt do analizy korelacji
    
    Args:
        data: Dane do analizy korelacji
        
    Returns:
        Prompt dla modelu AI
    """
    correlation_type = data.get('type', 'sleep_vs_rhr')
    datapoints = data.get('datapoints', [])
    
    prompt = f"""Przeanalizuj korelację między: {correlation_type}

DANE:
{_format_correlation_data(datapoints)}

Oceń:
1. Czy istnieje wyraźna korelacja
2. Co mówi ta korelacja o regeneracji użytkownika
3. Czy są wartości odstające, które wymagają uwagi
4. Praktyczne wnioski i rekomendacje"""
    
    return prompt


# === FUNKCJE POMOCNICZE ===

def _format_activities(activities: List[Dict[str, Any]]) -> str:
    """Formatuje listę aktywności do promptu"""
    if not activities:
        return "Brak aktywności dzisiaj"
    
    formatted = []
    for activity in activities[:3]:  # Max 3 najnowsze
        name = activity.get('activityName', 'Nieznana')
        activity_type = activity.get('activityType', 'Nieznany typ')
        duration = activity.get('duration', 0) / 60  # minuty
        distance = activity.get('distance', 0) / 1000  # km
        
        formatted.append(f"- {name} ({activity_type}): {duration:.0f} min, {distance:.1f} km")
    
    return "\n".join(formatted)


def _format_training_summary(activities: List[Dict[str, Any]]) -> str:
    """Formatuje podsumowanie treningów"""
    if not activities:
        return "Brak treningów w ostatnich 7 dniach"
    
    total_count = len(activities)
    total_time = sum(a.get('duration', 0) for a in activities) / 3600  # godziny
    total_distance = sum(a.get('distance', 0) for a in activities) / 1000  # km
    
    types = {}
    for activity in activities:
        atype = activity.get('activityType', 'Nieznany')
        types[atype] = types.get(atype, 0) + 1
    
    summary = f"- Łącznie: {total_count} treningi, {total_time:.1f} h, {total_distance:.1f} km\n"
    summary += "- Typy: " + ", ".join([f"{t} ({c}x)" for t, c in types.items()])
    
    return summary


def _format_sleep_details(sleep_data: List[Dict[str, Any]]) -> str:
    """Formatuje szczegóły snu"""
    if not sleep_data:
        return "Brak danych o śnie"
    
    formatted = []
    for i, sleep in enumerate(sleep_data[:5], 1):  # Max 5 nocy
        duration = sleep.get('sleepTimeSeconds', 0) / 3600
        quality = sleep.get('quality_score', 'brak')
        
        formatted.append(f"Noc {i}: {duration:.1f}h, jakość: {quality}/100")
    
    return "\n".join(formatted)


def _format_correlation_data(datapoints: List[Dict[str, Any]]) -> str:
    """Formatuje dane korelacji"""
    if not datapoints:
        return "Brak danych do analizy"
    
    formatted = []
    for point in datapoints[:10]:  # Max 10 punktów
        x = point.get('x', 'brak')
        y = point.get('y', 'brak')
        date = point.get('date', 'brak daty')
        
        formatted.append(f"{date}: x={x}, y={y}")
    
    return "\n".join(formatted)
