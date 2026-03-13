"""Analiza metryk snu"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from statistics import mean, stdev

logger = logging.getLogger(__name__)


class SleepMetrics:
    """Analizuje dane snu i oblicza metryki"""
    
    def __init__(self, repository):
        """
        Args:
            repository: Repozytorium do pobierania danych
        """
        self.repo = repository
    
    def calculate_sleep_quality_score(self, sleep_data: Dict[str, Any]) -> float:
        """
        Oblicza ogólny wskaźnik jakości snu (0-100)
        
        Args:
            sleep_data: Dane o śnie z pojedynczej nocy
            
        Returns:
            Wskaźnik jakości snu
        """
        score = 0.0
        
        # Długość snu (30 punktów)
        total_sleep_minutes = sleep_data.get('sleepTimeSeconds', 0) / 60
        if total_sleep_minutes >= 420:  # 7+ godzin
            score += 30
        elif total_sleep_minutes >= 360:  # 6-7 godzin
            score += 20
        elif total_sleep_minutes >= 300:  # 5-6 godzin
            score += 10
        
        # Procent głębokiego snu (25 punktów)
        deep_sleep_seconds = sleep_data.get('deepSleepSeconds', 0)
        if total_sleep_minutes > 0:
            deep_sleep_percent = (deep_sleep_seconds / 60) / total_sleep_minutes * 100
            if deep_sleep_percent >= 20:
                score += 25
            elif deep_sleep_percent >= 15:
                score += 20
            elif deep_sleep_percent >= 10:
                score += 15
        
        # Procent REM (25 punktów)
        rem_sleep_seconds = sleep_data.get('remSleepSeconds', 0)
        if total_sleep_minutes > 0:
            rem_sleep_percent = (rem_sleep_seconds / 60) / total_sleep_minutes * 100
            if rem_sleep_percent >= 20:
                score += 25
            elif rem_sleep_percent >= 15:
                score += 20
            elif rem_sleep_percent >= 10:
                score += 15
        
        # Liczba przebudzeń (20 punktów)
        awake_count = sleep_data.get('awakeCount', 0)
        if awake_count <= 2:
            score += 20
        elif awake_count <= 4:
            score += 15
        elif awake_count <= 6:
            score += 10
        
        return min(score, 100.0)
    
    def get_sleep_trends(self, days: int = 7) -> Dict[str, Any]:
        """
        Oblicza trendy snu z ostatnich N dni
        
        Args:
            days: Liczba dni do analizy
            
        Returns:
            Słownik z trendami
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        sleep_records = self.repo.get_sleep_data_range(start_date, end_date)
        
        if not sleep_records:
            return {
                'average_duration_hours': 0,
                'average_quality_score': 0,
                'trend': 'insufficient_data'
            }
        
        durations = []
        quality_scores = []
        deep_sleep_percentages = []
        rem_sleep_percentages = []
        
        for record in sleep_records:
            # Długość snu
            duration_hours = record.get('sleepTimeSeconds', 0) / 3600
            durations.append(duration_hours)
            
            # Jakość snu
            quality_score = self.calculate_sleep_quality_score(record)
            quality_scores.append(quality_score)
            
            # Fazy snu
            total_sleep = record.get('sleepTimeSeconds', 0)
            if total_sleep > 0:
                deep_sleep_percentages.append(
                    (record.get('deepSleepSeconds', 0) / total_sleep) * 100
                )
                rem_sleep_percentages.append(
                    (record.get('remSleepSeconds', 0) / total_sleep) * 100
                )
        
        # Oblicz średnie
        avg_duration = mean(durations) if durations else 0
        avg_quality = mean(quality_scores) if quality_scores else 0
        avg_deep = mean(deep_sleep_percentages) if deep_sleep_percentages else 0
        avg_rem = mean(rem_sleep_percentages) if rem_sleep_percentages else 0
        
        # Określ trend
        trend = self._determine_sleep_trend(quality_scores)
        
        return {
            'average_duration_hours': round(avg_duration, 2),
            'average_quality_score': round(avg_quality, 1),
            'average_deep_sleep_percent': round(avg_deep, 1),
            'average_rem_sleep_percent': round(avg_rem, 1),
            'trend': trend,
            'data_points': len(sleep_records)
        }
    
    def _determine_sleep_trend(self, scores: List[float]) -> str:
        """
        Określa trend na podstawie ostatnich wyników
        
        Args:
            scores: Lista wyników jakości snu
            
        Returns:
            'improving', 'stable', 'declining' lub 'insufficient_data'
        """
        if len(scores) < 3:
            return 'insufficient_data'
        
        # Porównaj pierwszą i drugą połowę
        mid_point = len(scores) // 2
        first_half_avg = mean(scores[:mid_point])
        second_half_avg = mean(scores[mid_point:])
        
        diff = second_half_avg - first_half_avg
        
        if diff > 5:
            return 'improving'
        elif diff < -5:
            return 'declining'
        else:
            return 'stable'
    
    def analyze_sleep_consistency(self, days: int = 14) -> Dict[str, Any]:
        """
        Analizuje regularność snu
        
        Args:
            days: Liczba dni do analizy
            
        Returns:
            Analiza regularności snu
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        sleep_records = self.repo.get_sleep_data_range(start_date, end_date)
        
        if len(sleep_records) < 3:
            return {
                'consistency_score': 0,
                'message': 'Niewystarczające dane'
            }
        
        # Godziny zaśnięcia
        sleep_times = []
        wake_times = []
        durations = []
        
        for record in sleep_records:
            sleep_start = record.get('sleepStartTimestampLocal')
            sleep_end = record.get('sleepEndTimestampLocal')
            
            if sleep_start and sleep_end:
                # Wyciągnij godzinę (0-23) - obsługa Unix ms i ISO string
                if isinstance(sleep_start, int):
                    sleep_hour = datetime.fromtimestamp(sleep_start / 1000, tz=timezone.utc).hour
                    wake_hour = datetime.fromtimestamp(sleep_end / 1000, tz=timezone.utc).hour
                else:
                    sleep_hour = int(sleep_start[11:13])
                    wake_hour = int(sleep_end[11:13])
                
                sleep_times.append(sleep_hour)
                wake_times.append(wake_hour)
                
                duration = record.get('sleepTimeSeconds', 0) / 3600
                durations.append(duration)
        
        consistency_score = 100.0
        
        # Odchylenie standardowe czasu zaśnięcia
        if len(sleep_times) > 1:
            sleep_time_stdev = stdev(sleep_times)
            consistency_score -= min(sleep_time_stdev * 10, 30)
        
        # Odchylenie standardowe czasu budzenia
        if len(wake_times) > 1:
            wake_time_stdev = stdev(wake_times)
            consistency_score -= min(wake_time_stdev * 10, 30)
        
        # Odchylenie standardowe długości snu
        if len(durations) > 1:
            duration_stdev = stdev(durations)
            consistency_score -= min(duration_stdev * 15, 40)
        
        consistency_score = max(consistency_score, 0)
        
        return {
            'consistency_score': round(consistency_score, 1),
            'avg_sleep_hour': round(mean(sleep_times), 1) if sleep_times else None,
            'avg_wake_hour': round(mean(wake_times), 1) if wake_times else None,
            'message': self._get_consistency_message(consistency_score)
        }
    
    def _get_consistency_message(self, score: float) -> str:
        """Zwraca wiadomość na podstawie wyniku regularności"""
        if score >= 80:
            return 'Bardzo regularne godziny snu'
        elif score >= 60:
            return 'Umiarkowanie regularne godziny snu'
        elif score >= 40:
            return 'Nieregularne godziny snu'
        else:
            return 'Bardzo nieregularne godziny snu'
