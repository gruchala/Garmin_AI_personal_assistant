"""Synchronizacja aktywności z Garmin Connect"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from .garmin_client import GarminClient
from ..db.repository import GarminRepository

logger = logging.getLogger(__name__)


class ActivitiesSync:
    """Synchronizuje aktywności z Garmin Connect do bazy danych"""
    
    def __init__(self, garmin_client: GarminClient, repository: GarminRepository):
        """
        Args:
            garmin_client: Klient Garmin Connect
            repository: Repozytorium do zapisywania danych
        """
        self.client = garmin_client
        self.repo = repository
    
    def sync_recent_activities(self, limit: int = 20) -> int:
        """
        Synchronizuje ostatnie aktywności
        
        Args:
            limit: Liczba aktywności do pobrania
            
        Returns:
            Liczba zsynchronizowanych aktywności
        """
        logger.info(f"Rozpoczynam synchronizację {limit} ostatnich aktywności")
        
        activities = self.client.get_activities(0, limit)
        if not activities:
            logger.warning("Nie pobrano żadnych aktywności")
            return 0
        
        synced_count = 0
        for activity in activities:
            activity_id = activity.get('activityId')
            if not activity_id:
                continue
            
            # Sprawdź czy aktywność już istnieje w bazie
            if self.repo.activity_exists(activity_id):
                logger.debug(f"Aktywność {activity_id} już istnieje w bazie")
                continue
            
            # Zapisz podstawowe dane aktywności
            self.repo.save_activity(activity)
            
            # Pobierz szczegóły aktywności
            details = self.client.get_activity_details(activity_id)
            if details:
                self.repo.save_activity_details(activity_id, details)
            
            synced_count += 1
            logger.info(f"Zsynchronizowano aktywność {activity_id}")
        
        logger.info(f"Zsynchronizowano {synced_count} nowych aktywności")
        return synced_count
    
    def sync_activities_for_date(self, target_date: date) -> int:
        """
        Synchronizuje aktywności dla konkretnego dnia
        
        Args:
            target_date: Data dla której pobieramy aktywności
            
        Returns:
            Liczba zsynchronizowanych aktywności
        """
        # Pobierz większą liczbę aktywności i filtruj po dacie
        activities = self.client.get_activities(0, 100)
        if not activities:
            return 0
        
        synced_count = 0
        for activity in activities:
            # Sprawdź datę aktywności
            start_time_str = activity.get('startTimeLocal')
            if not start_time_str:
                continue
            
            # Parsuj datę (format: "2024-03-10 10:30:00")
            try:
                activity_date = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S").date()
            except ValueError:
                continue
            
            if activity_date != target_date:
                continue
            
            activity_id = activity.get('activityId')
            if not activity_id or self.repo.activity_exists(activity_id):
                continue
            
            # Zapisz aktywność
            self.repo.save_activity(activity)
            
            # Pobierz szczegóły
            details = self.client.get_activity_details(activity_id)
            if details:
                self.repo.save_activity_details(activity_id, details)
            
            synced_count += 1
        
        logger.info(f"Zsynchronizowano {synced_count} aktywności dla {target_date}")
        return synced_count
    
    def get_activity_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Pobiera podsumowanie aktywności z ostatnich N dni
        
        Args:
            days: Liczba dni wstecz
            
        Returns:
            Słownik z podsumowaniem
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        activities = self.repo.get_activities_in_date_range(start_date, end_date)
        
        summary = {
            'total_activities': len(activities),
            'total_distance_km': 0,
            'total_duration_minutes': 0,
            'activity_types': {},
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
        
        for activity in activities:
            # Dystans
            distance = activity.get('distance', 0)
            summary['total_distance_km'] += distance / 1000
            
            # Czas trwania
            duration = activity.get('duration', 0)
            summary['total_duration_minutes'] += duration / 60
            
            # Typ aktywności
            activity_type = activity.get('activityType', {}).get('typeKey', 'unknown')
            if activity_type not in summary['activity_types']:
                summary['activity_types'][activity_type] = 0
            summary['activity_types'][activity_type] += 1
        
        return summary
