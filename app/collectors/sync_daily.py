"""Synchronizacja danych dziennych z Garmin Connect"""

import logging
from datetime import date, timedelta
from typing import Optional
from .garmin_client import GarminClient
from ..db.repository import GarminRepository

logger = logging.getLogger(__name__)


class DailyDataSync:
    """Synchronizuje dzienne dane z Garmin Connect do bazy danych"""
    
    def __init__(self, garmin_client: GarminClient, repository: GarminRepository):
        """
        Args:
            garmin_client: Klient Garmin Connect
            repository: Repozytorium do zapisywania danych
        """
        self.client = garmin_client
        self.repo = repository
    
    def sync_day(self, target_date: date) -> bool:
        """
        Synchronizuje wszystkie dane dzienne dla wybranego dnia
        
        Args:
            target_date: Data do synchronizacji
            
        Returns:
            True jeśli synchronizacja zakończona sukcesem
        """
        logger.info(f"Rozpoczynam synchronizację danych dla {target_date}")
        
        success = True
        
        # Pobierz statystyki dzienne
        daily_stats = self.client.get_daily_stats(target_date)
        if daily_stats:
            self.repo.save_daily_metrics(target_date, daily_stats)
        else:
            logger.warning(f"Brak statystyk dziennych dla {target_date}")
            success = False
        
        # Pobierz dane o śnie
        sleep_data = self.client.get_sleep_data(target_date)
        if sleep_data:
            self.repo.save_sleep_data(target_date, sleep_data)
        else:
            logger.warning(f"Brak danych o śnie dla {target_date}")
        
        # Pobierz dane HRV
        hrv_data = self.client.get_hrv_data(target_date)
        if hrv_data:
            self.repo.save_hrv_data(target_date, hrv_data)
        else:
            logger.warning(f"Brak danych HRV dla {target_date}")
        
        # Pobierz spoczynkowe tętno
        rhr = self.client.get_resting_heart_rate(target_date)
        if rhr:
            self.repo.save_resting_heart_rate(target_date, rhr)
        else:
            logger.warning(f"Brak danych RHR dla {target_date}")
        
        # Pobierz Body Battery
        body_battery = self.client.get_body_battery(target_date)
        if body_battery:
            self.repo.save_body_battery(target_date, body_battery)
        else:
            logger.warning(f"Brak danych Body Battery dla {target_date}")
        
        # Pobierz dane o stresie
        stress_data = self.client.get_stress_data(target_date)
        if stress_data:
            self.repo.save_stress_data(target_date, stress_data)
        else:
            logger.warning(f"Brak danych o stresie dla {target_date}")

        # Pobierz dane o masie ciała (opcjonalne - nie codziennie)
        weight_data = self.client.get_weight_data(target_date)
        if weight_data:
            self.repo.save_weight_data(target_date, weight_data)

        # Pobierz VO2max (opcjonalne - zmienia się rzadko)
        vo2max_data = self.client.get_vo2max_data(target_date)
        if vo2max_data:
            self.repo.save_vo2max_data(target_date, vo2max_data)
        
        logger.info(f"Zakończono synchronizację dla {target_date}")
        return success
    
    def sync_date_range(self, start_date: date, end_date: date) -> int:
        """
        Synchronizuje dane dla zakresu dat
        
        Args:
            start_date: Data początkowa
            end_date: Data końcowa
            
        Returns:
            Liczba pomyślnie zsynchronizowanych dni
        """
        current_date = start_date
        success_count = 0
        
        while current_date <= end_date:
            if self.sync_day(current_date):
                success_count += 1
            current_date += timedelta(days=1)
        
        logger.info(f"Zsynchronizowano {success_count} dni z zakresu {start_date} - {end_date}")
        return success_count
    
    def sync_last_n_days(self, n_days: int = 7) -> int:
        """
        Synchronizuje dane z ostatnich N dni
        
        Args:
            n_days: Liczba dni wstecz do synchronizacji
            
        Returns:
            Liczba pomyślnie zsynchronizowanych dni
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=n_days - 1)
        
        return self.sync_date_range(start_date, end_date)
