"""Obliczanie wskaźników regeneracji i gotowości do treningu"""

import logging
from datetime import date, timedelta
from typing import Dict, Any, Optional
from .hrv_metrics import HRVMetrics
from .sleep_metrics import SleepMetrics

logger = logging.getLogger(__name__)


class RecoveryScore:
    """Oblicza kompleksowy wskaźnik regeneracji"""
    
    def __init__(self, repository):
        """
        Args:
            repository: Repozytorium do pobierania danych
        """
        self.repo = repository
        self.hrv_metrics = HRVMetrics(repository)
        self.sleep_metrics = SleepMetrics(repository)
    
    def calculate_daily_readiness(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Oblicza gotowość do treningu na dany dzień
        
        Args:
            target_date: Data dla której obliczamy gotowość (domyślnie dzisiaj)
            
        Returns:
            Kompleksowa ocena gotowości
        """
        if target_date is None:
            target_date = date.today()
        
        readiness_score = 0.0
        components = {}
        
        # 1. HRV (40% wagi)
        hrv_data = self.repo.get_hrv_data_for_date(target_date)
        if hrv_data:
            baseline = self.hrv_metrics.calculate_baseline(28)
            if baseline:
                current_hrv = hrv_data.get('lastNightAvg')
                if current_hrv:
                    hrv_status = self.hrv_metrics.get_hrv_status(current_hrv, baseline)
                    hrv_score = self._hrv_status_to_score(hrv_status)
                    readiness_score += hrv_score * 0.4
                    components['hrv'] = {
                        'score': hrv_score,
                        'value': current_hrv,
                        'baseline': baseline['mean'],
                        'status': hrv_status
                    }
        
        # 2. Sen (35% wagi)
        sleep_data = self.repo.get_sleep_data_for_date(target_date)
        if sleep_data:
            sleep_quality = self.sleep_metrics.calculate_sleep_quality_score(sleep_data)
            readiness_score += sleep_quality * 0.35
            components['sleep'] = {
                'score': sleep_quality,
                'duration_hours': sleep_data.get('sleepTimeSeconds', 0) / 3600
            }
        
        # 3. RHR (15% wagi)
        rhr = self.repo.get_resting_heart_rate_for_date(target_date)
        if rhr:
            rhr_baseline = self._calculate_rhr_baseline()
            if rhr_baseline:
                rhr_score = self._calculate_rhr_score(rhr, rhr_baseline)
                readiness_score += rhr_score * 0.15
                components['rhr'] = {
                    'score': rhr_score,
                    'value': rhr,
                    'baseline': rhr_baseline
                }
        
        # 4. Obciążenie treningowe z ostatnich 7 dni (10% wagi)
        training_load = self._calculate_recent_training_load()
        load_score = self._training_load_to_score(training_load)
        readiness_score += load_score * 0.1
        components['training_load'] = {
            'score': load_score,
            'load': training_load
        }
        
        # Normalizuj wynik do 0-100
        readiness_score = min(100, max(0, readiness_score))
        
        # Określ kategorię i rekomendacje
        category, recommendation = self._get_readiness_category(readiness_score)
        
        return {
            'date': target_date.isoformat(),
            'readiness_score': round(readiness_score, 1),
            'category': category,
            'recommendation': recommendation,
            'components': components
        }
    
    def _hrv_status_to_score(self, status: str) -> float:
        """Konwertuje status HRV na wynik 0-100"""
        scores = {
            'very_high': 100,
            'high': 80,
            'normal': 60,
            'low': 30,
            'very_low': 0
        }
        return scores.get(status, 50)
    
    def _calculate_rhr_baseline(self, days: int = 28) -> Optional[float]:
        """Oblicza bazowe spoczynkowe tętno"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        rhr_values = self.repo.get_resting_heart_rate_range(start_date, end_date)
        
        if len(rhr_values) < 7:
            return None
        
        from statistics import mean
        return mean(rhr_values)
    
    def _calculate_rhr_score(self, current_rhr: int, baseline: float) -> float:
        """Oblicza wynik na podstawie RHR"""
        diff = current_rhr - baseline
        
        if diff <= -5:
            return 100
        elif diff <= -2:
            return 80
        elif diff <= 2:
            return 60
        elif diff <= 5:
            return 40
        elif diff <= 8:
            return 20
        else:
            return 0
    
    def _calculate_recent_training_load(self, days: int = 7) -> float:
        """
        Oblicza obciążenie treningowe z ostatnich N dni
        
        Returns:
            Wartość obciążenia (niższa = lepsze dla readiness)
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        activities = self.repo.get_activities_in_date_range(start_date, end_date)
        
        total_load = 0.0
        for activity in activities:
            # Proste obliczenie obciążenia na podstawie czasu i intensywności
            duration_hours = activity.get('duration', 0) / 3600
            avg_hr = activity.get('averageHR', 0)
            
            # Im wyższe HR i dłuższy czas, tym większe obciążenie
            load = duration_hours * (avg_hr / 100) if avg_hr > 0 else duration_hours
            total_load += load
        
        return total_load
    
    def _training_load_to_score(self, load: float) -> float:
        """
        Konwertuje obciążenie treningowe na wynik
        Wysokie obciążenie = niższy wynik (większe zmęczenie)
        """
        if load < 5:
            return 100  # Bardzo niskie obciążenie
        elif load < 10:
            return 80
        elif load < 15:
            return 60
        elif load < 20:
            return 40
        elif load < 25:
            return 20
        else:
            return 0  # Bardzo wysokie obciążenie
    
    def _get_readiness_category(self, score: float) -> tuple[str, str]:
        """Zwraca kategorię i rekomendację na podstawie wyniku"""
        if score >= 80:
            return (
                'excellent',
                'Doskonała gotowość - możesz zaplanować intensywny trening lub interwały'
            )
        elif score >= 65:
            return (
                'good',
                'Dobra gotowość - możesz trenować normalnie, unikaj jednak bardzo ciężkich sesji'
            )
        elif score >= 50:
            return (
                'moderate',
                'Umiarkowana gotowość - rozważ trening o średniej intensywności lub regeneracyjny'
            )
        elif score >= 35:
            return (
                'low',
                'Niska gotowość - zalecany lekki trening lub odpoczynek aktywny'
            )
        else:
            return (
                'very_low',
                'Bardzo niska gotowość - zdecydowanie potrzebujesz odpoczynku'
            )
    
    def get_weekly_recovery_report(self) -> Dict[str, Any]:
        """
        Generuje tygodniowy raport regeneracji
        
        Returns:
            Raport z ostatnich 7 dni
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
        
        daily_scores = []
        current_date = start_date
        
        while current_date <= end_date:
            readiness = self.calculate_daily_readiness(current_date)
            daily_scores.append({
                'date': current_date.isoformat(),
                'score': readiness['readiness_score'],
                'category': readiness['category']
            })
            current_date += timedelta(days=1)
        
        # Oblicz średnie
        from statistics import mean
        scores = [d['score'] for d in daily_scores]
        avg_score = mean(scores) if scores else 0
        
        # Trend
        if len(scores) >= 3:
            mid_point = len(scores) // 2
            first_half = mean(scores[:mid_point])
            second_half = mean(scores[mid_point:])
            
            if second_half - first_half > 10:
                trend = 'improving'
            elif second_half - first_half < -10:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        # Sprawdź ryzyko przetrenowania
        overtraining_risk = self.hrv_metrics.detect_overtraining_risk(14)
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'average_readiness': round(avg_score, 1),
            'trend': trend,
            'daily_scores': daily_scores,
            'overtraining_risk': overtraining_risk
        }
