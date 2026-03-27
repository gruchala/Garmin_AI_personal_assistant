"""Generowanie insightów za pomocą AI"""

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from openai import OpenAI
from .prompts import (
    SYSTEM_PROMPT,
    get_daily_summary_prompt,
    get_trainer_note_prompt,
    get_training_suggestion_prompt,
    get_trend_analysis_prompt,
    get_training_recommendation_prompt,
    get_sleep_analysis_prompt,
    get_correlation_analysis_prompt
)

logger = logging.getLogger(__name__)


def load_agent_notes(notes_file: str = "agent_notes.md", max_entries: int = 30) -> Optional[str]:
    """
    Ładuje notatki agenta (notatnik trenera).
    Zwraca ostatnie `max_entries` wpisów aby nie przeładować kontekstu.
    """
    path = Path(notes_file)
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    # Podziel na wpisy po separatorze '## YYYY-MM-DD'
    import re
    entries = re.split(r'(?=^## \d{4}-\d{2}-\d{2})', content, flags=re.MULTILINE)
    entries = [e.strip() for e in entries if e.strip() and not e.startswith('#!')]
    if not entries:
        return content
    recent = entries[-max_entries:]
    return "\n\n".join(recent)


def append_agent_note(note: str, notes_file: str = "agent_notes.md", target_date: str = "") -> None:
    """Dopisuje datowaną notatkę do pliku notatnika agenta."""
    path = Path(notes_file)
    header = f"\n\n## {target_date}\n" if target_date else "\n\n---\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(header + note.strip() + "\n")
    logger.info(f"Zapisano notatkę trenera do {notes_file}")


def load_user_context(context_file: str = "user_context.md") -> Optional[str]:
    """
    Ładuje plik z kontekstem użytkownika.
    Zwraca None jeśli plik nie istnieje lub jest pusty (same komentarze).
    """
    path = Path(context_file)
    if not path.exists():
        return None
    
    content = path.read_text(encoding="utf-8").strip()
    # Usuń linie będące tylko komentarzami HTML lub puste
    meaningful = [
        line for line in content.splitlines()
        if line.strip() and not line.strip().startswith("<!--") and not line.strip() == "-->"
    ]
    return "\n".join(meaningful) if meaningful else None


class InsightsGenerator:
    """Generuje insighty za pomocą AI (OpenAI)"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini",
                 context_file: str = "user_context.md"):
        """
        Args:
            api_key: Klucz API OpenAI (jeśli None, pobiera z OPENAI_API_KEY)
            model: Model do użycia (domyślnie gpt-4o-mini)
            context_file: Ścieżka do pliku z profilem użytkownika
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        
        user_context = load_user_context(context_file)
        agent_notes = load_agent_notes()

        self.system_prompt = SYSTEM_PROMPT
        if user_context:
            self.system_prompt += f"\n\n## Profil użytkownika\n{user_context}"
            logger.info("Załadowano profil użytkownika z user_context.md")
        if agent_notes:
            self.system_prompt += f"\n\n## Notatki trenera (poprzednie sesje)\n{agent_notes}"
            logger.info("Załadowano notatki trenera z agent_notes.md")
        
        if not self.client:
            logger.warning("Brak klucza API OpenAI - generowanie insightów będzie niedostępne")
    
    def generate_trainer_note(
        self,
        readiness_data: Dict[str, Any],
        sleep_data: Dict[str, Any],
        hrv_trend: Dict[str, Any],
        activities: list,
        weight_data: Optional[Dict[str, Any]] = None,
        vo2max_data: Optional[Dict[str, Any]] = None,
        report_date: str = ""
    ) -> Optional[str]:
        """Generuje krótką notatkę do notatnika trenera (2-4 punkty)."""
        if not self.client:
            return None
        try:
            data = {
                'readiness': readiness_data,
                'sleep': sleep_data,
                'hrv_trend': hrv_trend,
                'activities': activities,
                'weight': weight_data or {},
                'vo2max': vo2max_data or {},
                'report_date': report_date,
            }
            prompt = get_trainer_note_prompt(data)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=200
            )
            note = response.choices[0].message.content
            logger.info("Wygenerowano notatkę trenera")
            return note
        except Exception as e:
            logger.error(f"Błąd podczas generowania notatki trenera: {e}")
            return None

    def generate_daily_summary(
        self,
        readiness_data: Dict[str, Any],
        sleep_data: Dict[str, Any],
        hrv_trend: Dict[str, Any],
        activities: list,
        weight_data: Optional[Dict[str, Any]] = None,
        vo2max_data: Optional[Dict[str, Any]] = None,
        quick_note: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generuje dzienne podsumowanie
        
        Args:
            readiness_data: Dane o gotowości
            sleep_data: Dane o śnie
            hrv_trend: Trend HRV
            activities: Lista aktywności
            weight_data: Dane o masie ciała (opcjonalne)
            vo2max_data: Dane VO2max (opcjonalne)
            
        Returns:
            Wygenerowane podsumowanie lub None
        """
        if not self.client:
            return None
        
        try:
            data = {
                'readiness': readiness_data,
                'sleep': sleep_data,
                'hrv_trend': hrv_trend,
                'activities': activities,
                'weight': weight_data or {},
                'vo2max': vo2max_data or {},
                'quick_note': quick_note or '',
            }

            prompt = get_daily_summary_prompt(data)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content
            logger.info("Wygenerowano dzienne podsumowanie")
            return summary
            
        except Exception as e:
            logger.error(f"Błąd podczas generowania dziennego podsumowania: {e}")
            return None

    def generate_training_suggestion(
        self,
        day_name: str,
        planned_workout: str,
        body_battery: Optional[int],
        body_battery_trend: str,
        avg_stress: Optional[int],
        readiness: Dict[str, Any],
        hrv_trend: Dict[str, Any],
        sleep_data: Dict[str, Any],
        sleep_today_hours=None,
        today_activities: list = None,
        prev_activities: list = None,
        recent_activities: list = None,
        training_plan_notes: str = "",
        quick_note: Optional[str] = None,
    ) -> Optional[str]:
        """Generuje spersonalizowaną propozycję treningu na dziś."""
        if not self.client:
            return None
        try:
            data = {
                'day_name': day_name,
                'planned_workout': planned_workout,
                'body_battery': body_battery,
                'body_battery_trend': body_battery_trend,
                'avg_stress': avg_stress,
                'readiness': readiness,
                'hrv_trend': hrv_trend,
                'sleep': sleep_data,
                'sleep_today_hours': sleep_today_hours,
                'today_activities': today_activities or [],
                'prev_activities': prev_activities or recent_activities or [],
                'training_plan_notes': training_plan_notes,
                'quick_note': quick_note or '',
            }
            prompt = get_training_suggestion_prompt(data)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=400
            )
            suggestion = response.choices[0].message.content
            logger.info("Wygenerowano propozycję treningu")
            return suggestion
        except Exception as e:
            logger.error(f"Błąd podczas generowania propozycji treningu: {e}")
            return None

    def generate_trend_analysis(
        self,
        sleep_trends: Dict[str, Any],
        hrv_trend: Dict[str, Any],
        recovery_report: Dict[str, Any],
        days: int = 7
    ) -> Optional[str]:
        """
        Generuje analizę trendów
        
        Args:
            sleep_trends: Trendy snu
            hrv_trend: Trend HRV
            recovery_report: Raport regeneracji
            days: Liczba dni analizy
            
        Returns:
            Analiza trendów lub None
        """
        if not self.client:
            return None
        
        try:
            data = {
                'sleep_trends': sleep_trends,
                'hrv_trend': hrv_trend,
                'recovery_report': recovery_report,
                'days': days
            }
            
            prompt = get_trend_analysis_prompt(data)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=700
            )
            
            analysis = response.choices[0].message.content
            logger.info("Wygenerowano analizę trendów")
            return analysis
            
        except Exception as e:
            logger.error(f"Błąd podczas generowania analizy trendów: {e}")
            return None
    
    def answer_training_question(
        self,
        question: str,
        readiness: Dict[str, Any],
        recent_activities: list,
        training_load: Dict[str, Any]
    ) -> Optional[str]:
        """
        Odpowiada na pytanie o trening
        
        Args:
            question: Pytanie użytkownika
            readiness: Dane o gotowości
            recent_activities: Ostatnie aktywności
            training_load: Obciążenie treningowe
            
        Returns:
            Odpowiedź lub None
        """
        if not self.client:
            return None
        
        try:
            data = {
                'question': question,
                'readiness': readiness,
                'recent_activities': recent_activities,
                'training_load': training_load
            }
            
            prompt = get_training_recommendation_prompt(data)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            answer = response.choices[0].message.content
            logger.info(f"Udzielono odpowiedzi na pytanie: {question[:50]}...")
            return answer
            
        except Exception as e:
            logger.error(f"Błąd podczas odpowiadania na pytanie: {e}")
            return None
    
    def analyze_sleep_patterns(
        self,
        sleep_trends: Dict[str, Any],
        consistency: Dict[str, Any],
        recent_sleep: list
    ) -> Optional[str]:
        """
        Analizuje wzorce snu
        
        Args:
            sleep_trends: Trendy snu
            consistency: Regularność snu
            recent_sleep: Ostatnie noce
            
        Returns:
            Analiza snu lub None
        """
        if not self.client:
            return None
        
        try:
            data = {
                'sleep_trends': sleep_trends,
                'consistency': consistency,
                'recent_sleep': recent_sleep
            }
            
            prompt = get_sleep_analysis_prompt(data)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            analysis = response.choices[0].message.content
            logger.info("Wygenerowano analizę snu")
            return analysis
            
        except Exception as e:
            logger.error(f"Błąd podczas analizy snu: {e}")
            return None
    
    def analyze_correlation(
        self,
        correlation_type: str,
        datapoints: list
    ) -> Optional[str]:
        """
        Analizuje korelację między metrykami
        
        Args:
            correlation_type: Typ korelacji (np. "sleep_vs_rhr")
            datapoints: Punkty danych
            
        Returns:
            Analiza korelacji lub None
        """
        if not self.client:
            return None
        
        try:
            data = {
                'type': correlation_type,
                'datapoints': datapoints
            }
            
            prompt = get_correlation_analysis_prompt(data)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            analysis = response.choices[0].message.content
            logger.info(f"Wygenerowano analizę korelacji: {correlation_type}")
            return analysis
            
        except Exception as e:
            logger.error(f"Błąd podczas analizy korelacji: {e}")
            return None
    
    def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Ogólna funkcja czatu z kontekstem
        
        Args:
            message: Wiadomość użytkownika
            context: Opcjonalny kontekst (dane biometryczne)
            
        Returns:
            Odpowiedź AI lub None
        """
        if not self.client:
            return None
        
        try:
            # Zbuduj wiadomość z kontekstem
            full_message = message
            
            if context:
                context_str = "\n\nDOSTĘPNE DANE:\n"
                for key, value in context.items():
                    context_str += f"{key}: {value}\n"
                full_message = context_str + "\n" + message
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": full_message}
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            answer = response.choices[0].message.content
            logger.info("Udzielono odpowiedzi w trybie czatu")
            return answer
            
        except Exception as e:
            logger.error(f"Błąd podczas czatu: {e}")
            return None


class InsightsAssistant:
    """Asystent łączący dane z repozytorium i generator AI"""
    
    def __init__(self, repository, insights_generator: InsightsGenerator):
        """
        Args:
            repository: Repozytorium danych
            insights_generator: Generator insightów AI
        """
        self.repo = repository
        self.ai = insights_generator
    
    def get_daily_insight(self, target_date: Optional[date] = None, quick_note: Optional[str] = None) -> Optional[str]:
        """
        Generuje insight dla konkretnego dnia
        
        Args:
            target_date: Data (domyślnie dzisiaj)
            
        Returns:
            Insight lub None
        """
        if target_date is None:
            target_date = date.today()
        
        # Pobierz dane z processorów (importowane w miejscu użycia)
        from ..processors.recovery_score import RecoveryScore
        from ..processors.sleep_metrics import SleepMetrics
        from ..processors.hrv_metrics import HRVMetrics
        
        recovery_calculator = RecoveryScore(self.repo)
        sleep_metrics = SleepMetrics(self.repo)
        hrv_metrics = HRVMetrics(self.repo)
        
        # Zbierz dane
        readiness = recovery_calculator.calculate_daily_readiness(target_date)
        sleep_trends = sleep_metrics.get_sleep_trends(7)
        hrv_trend = hrv_metrics.get_hrv_trend(7)
        
        # Pobierz aktywności z dziś
        activities = self.repo.get_activities_in_date_range(target_date, target_date)
        
        # Pobierz dane wagowe i VO2max
        raw_weight = self.repo.get_latest_weight()
        weight_data = None
        if raw_weight:
            weight_data = {
                'weight_kg': (raw_weight.weight_grams / 1000) if raw_weight.weight_grams else None,
                'bmi': raw_weight.bmi,
                'body_fat_percent': raw_weight.body_fat_percent
            }
        
        raw_vo2max = self.repo.get_latest_vo2max()
        vo2max_data = None
        if raw_vo2max:
            vo2max_data = {
                'vo2max_precise': raw_vo2max.vo2max_precise,
                'fitness_age': raw_vo2max.fitness_age
            }
        
        # Generuj insight
        insight = self.ai.generate_daily_summary(
            readiness_data=readiness,
            sleep_data=sleep_trends,
            hrv_trend=hrv_trend,
            activities=activities,
            weight_data=weight_data,
            vo2max_data=vo2max_data,
            quick_note=quick_note,
        )

        # Zapisz do bazy
        if insight:
            self.repo.save_ai_insight(
                target_date=target_date,
                insight_type='daily_summary',
                title=f'Podsumowanie dnia {target_date}',
                content=insight,
                priority='medium'
            )

        # Wygeneruj i zapisz notatkę trenera
        trainer_note = self.ai.generate_trainer_note(
            readiness_data=readiness,
            sleep_data=sleep_trends,
            hrv_trend=hrv_trend,
            activities=activities,
            weight_data=weight_data,
            vo2max_data=vo2max_data,
            report_date=str(target_date)
        )
        if trainer_note:
            append_agent_note(trainer_note, target_date=str(target_date))

        return insight
