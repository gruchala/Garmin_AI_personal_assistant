"""Klient do komunikacji z Garmin Connect API"""

import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, List, Any
from garth.exc import GarthHTTPError
from garminconnect import Garmin
import garth

logger = logging.getLogger(__name__)


class GarminClient:
    """Obsługuje połączenie i pobieranie danych z Garmin Connect"""
    
    def __init__(self, email: str, password: str, tokens_dir: str = ".garmin_tokens"):
        """
        Args:
            email: Email do konta Garmin Connect
            password: Hasło do konta Garmin Connect
            tokens_dir: Katalog do przechowywania tokenów OAuth
        """
        self.email = email
        self.password = password
        self.tokens_dir = Path(tokens_dir)
        self.client: Optional[Garmin] = None
        
        # Utwórz katalog na tokeny jeśli nie istnieje
        self.tokens_dir.mkdir(exist_ok=True)
        
    def connect(self) -> bool:
        """
        Nawiązuje połączenie z Garmin Connect.
        Próbuje najpierw użyć zapisanych tokenów OAuth (dla 2FA),
        jeśli to się nie uda, loguje się email/hasło.
        
        Returns:
            True jeśli połączenie udane, False w przeciwnym wypadku
        """
        try:
            # Próba 1: Użyj zapisanych tokenów (dla 2FA)
            if self._try_token_login():
                logger.info("Połączono z Garmin Connect używając tokenów OAuth ✓")
                return True
            
            # Próba 2: Logowanie email/hasło przez garth (zapisze tokeny)
            logger.info("Brak tokenów - logowanie email/hasło...")
            
            # Zaloguj przez garth aby otrzymać tokeny OAuth
            garth.login(self.email, self.password)
            
            # Zapisz tokeny
            garth.save(self.tokens_dir)
            logger.info(f"Zapisano tokeny OAuth w: {self.tokens_dir}")
            
            # Utwórz klienta i załaduj właśnie zapisane tokeny
            self.client = Garmin()
            self.client.garth.load(str(self.tokens_dir))
            self.client.display_name = self.client.garth.profile.get('displayName')
            
            logger.info("Połączono z Garmin Connect i zapisano tokeny OAuth ✓")
            logger.info("Następne logowania będą automatyczne bez 2FA!")
            return True
            
        except GarthHTTPError as e:
            if "MFA" in str(e) or "2FA" in str(e) or "OTP" in str(e):
                logger.error("=" * 60)
                logger.error("WYMAGANE 2FA!")
                logger.error("=" * 60)
                logger.error("\nGarmin wymaga weryfikacji dwuetapowej.")
                logger.error("\nAby skonfigurować automatyczne logowanie:")
                logger.error("1. Uruchom skrypt: python scripts/setup_garmin_2fa.py")
                logger.error("2. Sprawdź maila i kliknij link weryfikacyjny")
                logger.error("3. Tokeny zostaną zapisane i nie będziesz już pytany o 2FA")
                logger.error("\n" + "=" * 60)
            else:
                logger.error(f"Błąd połączenia z Garmin Connect: {e}")
            return False
        except Exception as e:
            logger.error(f"Nieoczekiwany błąd podczas łączenia: {e}")
            return False
    
    def _try_token_login(self) -> bool:
        """
        Próbuje zalogować się używając zapisanych tokenów OAuth
        
        Returns:
            True jeśli udało się zalogować tokenami
        """
        try:
            # Sprawdź czy istnieją tokeny
            oauth1_file = self.tokens_dir / "oauth1_token.json"
            oauth2_file = self.tokens_dir / "oauth2_token.json"
            
            if not oauth1_file.exists():
                logger.debug("Brak pliku oauth1_token.json")
                return False
            
            logger.debug(f"Próba załadowania tokenów z {self.tokens_dir}")
            
            # Załaduj tokeny i utwórz klienta
            self.client = Garmin()
            self.client.garth.load(str(self.tokens_dir))
            
            # Ustaw display_name z profilu garth (wymagane przez get_user_summary i get_rhr_day)
            self.client.display_name = self.client.garth.profile.get('displayName')
            
            logger.debug("Tokeny załadowane pomyślnie")
            return True
            
        except Exception as e:
            logger.debug(f"Nie udało się użyć tokenów: {e}")
            # Usuń nieprawidłowe tokeny
            try:
                if (self.tokens_dir / "oauth1_token.json").exists():
                    (self.tokens_dir / "oauth1_token.json").unlink()
                if (self.tokens_dir / "oauth2_token.json").exists():
                    (self.tokens_dir / "oauth2_token.json").unlink()
                logger.debug("Usunięto nieprawidłowe tokeny")
            except:
                pass
            return False
    
    def _save_tokens(self):
        """Zapisuje tokeny OAuth do pliku"""
        try:
            garth.save(self.tokens_dir)
            logger.info(f"Zapisano tokeny OAuth w: {self.tokens_dir}")
        except Exception as e:
            logger.warning(f"Nie udało się zapisać tokenów: {e}")
    
    def get_daily_stats(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Pobiera statystyki dzienne
        
        Args:
            target_date: Data dla której pobieramy statystyki
            
        Returns:
            Słownik ze statystykami lub None w przypadku błędu
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None
            
        try:
            date_str = target_date.isoformat()
            stats = self.client.get_stats(date_str)
            logger.info(f"Pobrano statystyki dzienne dla {date_str}")
            return stats
        except Exception as e:
            logger.error(f"Błąd podczas pobierania statystyk dziennych: {e}")
            return None
    
    def get_sleep_data(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Pobiera dane o śnie
        
        Args:
            target_date: Data dla której pobieramy dane
            
        Returns:
            Słownik z danymi o śnie lub None w przypadku błędu
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None
            
        try:
            date_str = target_date.isoformat()
            sleep_data = self.client.get_sleep_data(date_str)
            logger.info(f"Pobrano dane o śnie dla {date_str}")
            return sleep_data
        except Exception as e:
            logger.error(f"Błąd podczas pobierania danych o śnie: {e}")
            return None
    
    def get_hrv_data(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Pobiera dane HRV (Heart Rate Variability)
        
        Args:
            target_date: Data dla której pobieramy dane
            
        Returns:
            Słownik z danymi HRV lub None w przypadku błędu
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None
            
        try:
            date_str = target_date.isoformat()
            hrv_data = self.client.get_hrv_data(date_str)
            logger.info(f"Pobrano dane HRV dla {date_str}")
            return hrv_data
        except Exception as e:
            logger.error(f"Błąd podczas pobierania danych HRV: {e}")
            return None
    
    def get_resting_heart_rate(self, target_date: date) -> Optional[int]:
        """
        Pobiera spoczynkowe tętno
        
        Args:
            target_date: Data dla której pobieramy dane
            
        Returns:
            Wartość RHR lub None w przypadku błędu
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None
            
        try:
            date_str = target_date.isoformat()
            heart_rates = self.client.get_heart_rates(date_str)
            
            if heart_rates and 'restingHeartRate' in heart_rates:
                rhr = heart_rates['restingHeartRate']
                logger.info(f"Pobrano RHR dla {date_str}: {rhr}")
                return rhr
            return None
        except Exception as e:
            logger.error(f"Błąd podczas pobierania RHR: {e}")
            return None
    
    def get_body_battery(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Pobiera dane Body Battery
        
        Args:
            target_date: Data dla której pobieramy dane
            
        Returns:
            Słownik z danymi Body Battery lub None w przypadku błędu
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None
            
        try:
            date_str = target_date.isoformat()
            body_battery = self.client.get_body_battery(date_str)
            logger.info(f"Pobrano Body Battery dla {date_str}")
            return body_battery
        except Exception as e:
            logger.error(f"Błąd podczas pobierania Body Battery: {e}")
            return None
    
    def get_activities(self, start_index: int = 0, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """
        Pobiera listę aktywności
        
        Args:
            start_index: Indeks początkowy
            limit: Limit aktywności do pobrania
            
        Returns:
            Lista aktywności lub None w przypadku błędu
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None
            
        try:
            activities = self.client.get_activities(start_index, limit)
            logger.info(f"Pobrano {len(activities)} aktywności")
            return activities
        except Exception as e:
            logger.error(f"Błąd podczas pobierania aktywności: {e}")
            return None
    
    def get_activity_details(self, activity_id: int) -> Optional[Dict[str, Any]]:
        """
        Pobiera szczegóły aktywności
        
        Args:
            activity_id: ID aktywności
            
        Returns:
            Słownik ze szczegółami lub None w przypadku błędu
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None
            
        try:
            details = self.client.get_activity(activity_id)
            logger.info(f"Pobrano szczegóły aktywności {activity_id}")
            return details
        except Exception as e:
            logger.error(f"Błąd podczas pobierania szczegółów aktywności: {e}")
            return None
    
    def get_stress_data(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Pobiera dane o stresie
        
        Args:
            target_date: Data dla której pobieramy dane
            
        Returns:
            Słownik z danymi o stresie lub None w przypadku błędu
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None
            
        try:
            date_str = target_date.isoformat()
            stress_data = self.client.get_stress_data(date_str)
            logger.info(f"Pobrano dane o stresie dla {date_str}")
            return stress_data
        except Exception as e:
            logger.error(f"Błąd podczas pobierania danych o stresie: {e}")
            return None

    def get_weight_data(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Pobiera dane o masie ciała i składzie ciała dla konkretnej daty.
        Używa get_weigh_ins z zakresem jednego dnia.
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None

        try:
            date_str = target_date.isoformat()
            data = self.client.get_weigh_ins(date_str, date_str)
            summaries = data.get('dailyWeightSummaries', []) if data else []
            if summaries:
                latest = summaries[0].get('latestWeight')
                logger.info(f"Pobrano dane wagowe dla {date_str}")
                return latest
            return None
        except Exception as e:
            logger.error(f"Błąd podczas pobierania danych wagowych: {e}")
            return None

    def get_vo2max_data(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Pobiera dane VO2max z training status.
        Zwraca słownik z mostRecentVO2Max.generic lub None.
        """
        if not self.client:
            logger.error("Brak połączenia z Garmin Connect")
            return None

        try:
            date_str = target_date.isoformat()
            data = self.client.get_training_status(date_str)
            if not data:
                return None
            vo2 = data.get('mostRecentVO2Max', {}).get('generic')
            if vo2:
                logger.info(f"Pobrano VO2max dla {date_str}: {vo2.get('vo2MaxPreciseValue')}")
            return vo2
        except Exception as e:
            logger.error(f"Błąd podczas pobierania VO2max: {e}")
            return None
