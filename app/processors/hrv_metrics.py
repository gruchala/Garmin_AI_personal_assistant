"""Analiza metryk HRV (Heart Rate Variability)"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Any, Optional
from statistics import mean, stdev

logger = logging.getLogger(__name__)


class HRVMetrics:
    """Analizuje dane HRV i oblicza wskaźniki regeneracji"""
    
    def __init__(self, repository):
        """
        Args:
            repository: Repozytorium do pobierania danych
        """
        self.repo = repository
    
    def calculate_baseline(self, days: int = 28) -> Optional[Dict[str, float]]:
        """
        Oblicza bazową linię HRV z ostatnich N dni
        
        Args:
            days: Liczba dni do obliczenia baseline (domyślnie 28)
            
        Returns:
            Słownik z wartościami baseline lub None
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        hrv_records = self.repo.get_hrv_data_range(start_date, end_date)
        
        if len(hrv_records) < 7:  # Minimum 7 dni dla wiarygodnego baseline
            logger.warning(f"Zbyt mało danych HRV ({len(hrv_records)} dni) do obliczenia baseline")
            return None
        
        # Wyciągnij wartości HRV
        hrv_values = []
        for record in hrv_records:
            hrv_value = record.get('weeklyAvg') or record.get('lastNightAvg')
            if hrv_value:
                hrv_values.append(hrv_value)
        
        if not hrv_values:
            return None
        
        baseline_mean = mean(hrv_values)
        baseline_stdev = stdev(hrv_values) if len(hrv_values) > 1 else 0
        
        return {
            'mean': round(baseline_mean, 2),
            'stdev': round(baseline_stdev, 2),
            'min': round(min(hrv_values), 2),
            'max': round(max(hrv_values), 2),
            'sample_size': len(hrv_values)
        }
    
    def get_hrv_status(self, current_hrv: float, baseline: Dict[str, float]) -> str:
        """
        Określa status HRV w stosunku do baseline
        
        Args:
            current_hrv: Aktualna wartość HRV
            baseline: Baseline obliczony z calculate_baseline()
            
        Returns:
            'very_high', 'high', 'normal', 'low', 'very_low'
        """
        baseline_mean = baseline['mean']
        baseline_stdev = baseline['stdev']
        
        # Odchylenie od średniej w jednostkach odchylenia standardowego
        if baseline_stdev > 0:
            z_score = (current_hrv - baseline_mean) / baseline_stdev
        else:
            z_score = 0
        
        if z_score > 1.5:
            return 'very_high'
        elif z_score > 0.5:
            return 'high'
        elif z_score > -0.5:
            return 'normal'
        elif z_score > -1.5:
            return 'low'
        else:
            return 'very_low'
    
    def get_hrv_trend(self, days: int = 7) -> Dict[str, Any]:
        """
        Analizuje trend HRV z ostatnich N dni
        
        Args:
            days: Liczba dni do analizy
            
        Returns:
            Analiza trendu HRV
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        hrv_records = self.repo.get_hrv_data_range(start_date, end_date)
        
        if len(hrv_records) < 3:
            return {
                'trend': 'insufficient_data',
                'average_hrv': 0,
                'change_percent': 0
            }
        
        # Wyciągnij wartości
        hrv_values = []
        dates = []
        
        for record in hrv_records:
            hrv_value = record.get('lastNightAvg')
            record_date = record.get('calendarDate')
            
            if hrv_value and record_date:
                hrv_values.append(hrv_value)
                dates.append(record_date)
        
        if len(hrv_values) < 3:
            return {
                'trend': 'insufficient_data',
                'average_hrv': 0,
                'change_percent': 0
            }
        
        # Porównaj pierwszą i drugą połowę okresu
        mid_point = len(hrv_values) // 2
        first_half_avg = mean(hrv_values[:mid_point])
        second_half_avg = mean(hrv_values[mid_point:])
        
        change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        # Określ trend
        if change_percent > 5:
            trend = 'improving'
        elif change_percent < -5:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'average_hrv': round(mean(hrv_values), 2),
            'change_percent': round(change_percent, 1),
            'first_half_avg': round(first_half_avg, 2),
            'second_half_avg': round(second_half_avg, 2),
            'data_points': len(hrv_values)
        }
    
    def calculate_recovery_index(
        self,
        current_hrv: float,
        baseline: Dict[str, float],
        resting_hr: Optional[int] = None,
        resting_hr_baseline: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Oblicza indeks regeneracji na podstawie HRV i RHR
        
        Args:
            current_hrv: Aktualna wartość HRV
            baseline: Baseline HRV
            resting_hr: Aktualne spoczynkowe tętno
            resting_hr_baseline: Baseline RHR
            
        Returns:
            Indeks regeneracji (0-100) i interpretacja
        """
        recovery_score = 50.0  # Start od środka
        
        # HRV component (0-60 punktów)
        hrv_status = self.get_hrv_status(current_hrv, baseline)
        hrv_points = {
            'very_high': 60,
            'high': 45,
            'normal': 30,
            'low': 15,
            'very_low': 0
        }
        recovery_score += hrv_points.get(hrv_status, 30) - 30
        
        # RHR component (0-40 punktów), jeśli dostępne
        if resting_hr and resting_hr_baseline:
            rhr_diff = resting_hr - resting_hr_baseline
            
            if rhr_diff <= -3:
                recovery_score += 40
            elif rhr_diff <= 0:
                recovery_score += 30
            elif rhr_diff <= 3:
                recovery_score += 15
            elif rhr_diff <= 6:
                recovery_score += 5
            else:
                recovery_score += 0
        
        recovery_score = max(0, min(100, recovery_score))
        
        # Interpretacja
        if recovery_score >= 80:
            interpretation = 'Doskonała regeneracja - gotowy na intensywny trening'
            recommendation = 'Możesz zaplanować ciężki trening lub interwały'
        elif recovery_score >= 60:
            interpretation = 'Dobra regeneracja - możesz trenować normalnie'
            recommendation = 'Trening o umiarkowanej intensywności będzie optymalny'
        elif recovery_score >= 40:
            interpretation = 'Umiarkowana regeneracja - rozważ lżejszy trening'
            recommendation = 'Rozważ lekki trening regeneracyjny lub odpoczynek aktywny'
        elif recovery_score >= 20:
            interpretation = 'Słaba regeneracja - potrzebujesz odpoczynku'
            recommendation = 'Zalecany odpoczynek lub bardzo lekka aktywność'
        else:
            interpretation = 'Bardzo słaba regeneracja - konieczny odpoczynek'
            recommendation = 'Konieczny pełny odpoczynek, unikaj intensywnego wysiłku'
        
        return {
            'recovery_score': round(recovery_score, 1),
            'interpretation': interpretation,
            'recommendation': recommendation,
            'hrv_status': hrv_status,
            'hrv_value': current_hrv,
            'hrv_baseline': baseline['mean']
        }
    
    def detect_overtraining_risk(self, days: int = 14) -> Dict[str, Any]:
        """
        Wykrywa ryzyko przetrenowania na podstawie HRV
        
        Args:
            days: Liczba dni do analizy
            
        Returns:
            Analiza ryzyka przetrenowania
        """
        baseline = self.calculate_baseline(28)
        if not baseline:
            return {
                'risk_level': 'unknown',
                'message': 'Niewystarczające dane do analizy'
            }
        
        # Pobierz ostatnie dane
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        hrv_records = self.repo.get_hrv_data_range(start_date, end_date)
        
        if len(hrv_records) < 7:
            return {
                'risk_level': 'unknown',
                'message': 'Niewystarczające dane z ostatnich dni'
            }
        
        # Sprawdź ile dni HRV jest poniżej baseline
        low_hrv_days = 0
        very_low_hrv_days = 0
        
        for record in hrv_records:
            hrv_value = record.get('lastNightAvg')
            if not hrv_value:
                continue
            
            status = self.get_hrv_status(hrv_value, baseline)
            if status in ['low', 'very_low']:
                low_hrv_days += 1
            if status == 'very_low':
                very_low_hrv_days += 1
        
        # Określ ryzyko
        if very_low_hrv_days >= 3 or low_hrv_days >= 7:
            risk_level = 'high'
            message = 'Wysokie ryzyko przetrenowania - potrzebny odpoczynek'
        elif very_low_hrv_days >= 2 or low_hrv_days >= 5:
            risk_level = 'moderate'
            message = 'Umiarkowane ryzyko - rozważ zmniejszenie obciążenia'
        elif low_hrv_days >= 3:
            risk_level = 'low'
            message = 'Niskie ryzyko, ale monitoruj dalej'
        else:
            risk_level = 'minimal'
            message = 'Minimalne ryzyko przetrenowania'
        
        return {
            'risk_level': risk_level,
            'message': message,
            'low_hrv_days': low_hrv_days,
            'very_low_hrv_days': very_low_hrv_days,
            'total_days_analyzed': len(hrv_records)
        }
