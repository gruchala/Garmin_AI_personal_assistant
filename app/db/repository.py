"""Repozytorium do operacji na bazie danych"""

import logging
import os
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from .models import (
    DailyMetrics, SleepSession, HRVData, RestingHeartRate,
    Activity, ActivityDetail, RecoveryMetrics, AIInsight,
    BodyWeight, VO2MaxData
)

logger = logging.getLogger(__name__)


class GarminRepository:
    """Repozytorium do zarządzania danymi Garmin"""
    
    def __init__(self, session: Session):
        """
        Args:
            session: Sesja SQLAlchemy
        """
        self.session = session
        self.raw_data_mode = self._detect_raw_data_mode()

    def _detect_raw_data_mode(self) -> str:
        """Dobiera strategię przechowywania raw_data.

        Tryby:
        - full: zapis pełnego payloadu
        - essential: zapis tylko pól potrzebnych aplikacji
        - none: brak zapisu raw_data
        """
        configured = os.getenv("RAW_DATA_STORAGE", "").strip().lower()
        if configured in {"full", "essential", "none"}:
            return configured

        bind = self.session.get_bind()
        if bind is not None and inspect(bind).dialect.name == "sqlite":
            return "essential"
        return "full"

    def _prepare_raw_data(self, dataset: str, data: Any) -> Any:
        """Normalizuje payload do rozmiaru akceptowalnego dla wybranego backendu."""
        if self.raw_data_mode == "none":
            return None
        # Aktywności są najbardziej zróżnicowanym zbiorem Garmin. Pełny payload
        # zachowuje pola specyficzne dla biegu, roweru, siły, pływania itd.
        if dataset in {"activity", "activity_detail"}:
            return data
        if self.raw_data_mode == "full":
            return data

        compactor = {
            "daily_metrics": self._compact_daily_metrics,
            "sleep": self._compact_sleep_data,
            "hrv": self._compact_hrv_data,
            "activity": self._compact_activity_data,
            "activity_detail": self._compact_activity_detail_data,
            "weight": self._compact_weight_data,
            "vo2max": self._compact_vo2max_data,
        }.get(dataset)

        if compactor is None:
            return data
        return compactor(data)

    @staticmethod
    def _compact_daily_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "calendarDate": data.get("calendarDate"),
            "totalSteps": data.get("totalSteps"),
            "totalDistanceMeters": data.get("totalDistanceMeters"),
            "totalKilocalories": data.get("totalKilocalories"),
            "activeKilocalories": data.get("activeKilocalories"),
            "bmrKilocalories": data.get("bmrKilocalories"),
            "moderateIntensityMinutes": data.get("moderateIntensityMinutes"),
            "vigorousIntensityMinutes": data.get("vigorousIntensityMinutes"),
        }

    @staticmethod
    def _compact_sleep_data(data: Dict[str, Any]) -> Dict[str, Any]:
        dto = data.get("dailySleepDTO", {})
        return {
            "dailySleepDTO": {
                "sleepTimeSeconds": dto.get("sleepTimeSeconds"),
                "napTimeSeconds": dto.get("napTimeSeconds"),
                "deepSleepSeconds": dto.get("deepSleepSeconds"),
                "lightSleepSeconds": dto.get("lightSleepSeconds"),
                "remSleepSeconds": dto.get("remSleepSeconds"),
                "awakeSleepSeconds": dto.get("awakeSleepSeconds"),
                "sleepScores": dto.get("sleepScores"),
                "awakeCount": dto.get("awakeCount"),
                "avgSleepStress": dto.get("avgSleepStress"),
                "averageRespirationValue": dto.get("averageRespirationValue"),
                "lowestRespirationValue": dto.get("lowestRespirationValue"),
                "highestRespirationValue": dto.get("highestRespirationValue"),
                "averageSpO2Value": dto.get("averageSpO2Value"),
                "lowestSpO2Value": dto.get("lowestSpO2Value"),
                "sleepStartTimestampLocal": dto.get("sleepStartTimestampLocal"),
                "sleepEndTimestampLocal": dto.get("sleepEndTimestampLocal"),
            }
        }

    @staticmethod
    def _compact_hrv_data(data: Dict[str, Any]) -> Dict[str, Any]:
        summary = data.get("hrvSummary", {})
        return {
            "hrvSummary": {
                "weeklyAvg": summary.get("weeklyAvg"),
                "lastNightAvg": summary.get("lastNightAvg"),
                "lastNight5MinHigh": summary.get("lastNight5MinHigh"),
                "status": summary.get("status"),
            }
        }

    @staticmethod
    def _compact_activity_data(data: Dict[str, Any]) -> Dict[str, Any]:
        activity_type = data.get("activityType", {})
        return {
            "activityId": data.get("activityId"),
            "activityName": data.get("activityName"),
            "activityType": {
                "typeKey": activity_type.get("typeKey") if isinstance(activity_type, dict) else activity_type
            },
            "startTimeLocal": data.get("startTimeLocal"),
            "distance": data.get("distance"),
            "duration": data.get("duration"),
            "movingDuration": data.get("movingDuration"),
            "elapsedDuration": data.get("elapsedDuration"),
            "averageHR": data.get("averageHR"),
            "maxHR": data.get("maxHR"),
            "calories": data.get("calories"),
            "averageSpeed": data.get("averageSpeed"),
            "maxSpeed": data.get("maxSpeed"),
            "elevationGain": data.get("elevationGain"),
            "elevationLoss": data.get("elevationLoss"),
            "aerobicTrainingEffect": data.get("aerobicTrainingEffect"),
            "anaerobicTrainingEffect": data.get("anaerobicTrainingEffect"),
        }

    @staticmethod
    def _compact_activity_detail_data(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "timeInHeartRateZones": data.get("timeInHeartRateZones"),
            "avgRunningCadence": data.get("avgRunningCadence"),
            "maxRunningCadence": data.get("maxRunningCadence"),
            "avgStrideLength": data.get("avgStrideLength"),
            "vO2MaxValue": data.get("vO2MaxValue"),
        }

    @staticmethod
    def _compact_weight_data(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "weight": data.get("weight"),
            "bmi": data.get("bmi"),
            "bodyFat": data.get("bodyFat"),
            "bodyWater": data.get("bodyWater"),
            "muscleMass": data.get("muscleMass"),
            "boneMass": data.get("boneMass"),
        }

    @staticmethod
    def _compact_vo2max_data(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "vo2MaxPreciseValue": data.get("vo2MaxPreciseValue"),
            "vo2MaxValue": data.get("vo2MaxValue"),
            "fitnessAge": data.get("fitnessAge"),
        }

    @staticmethod
    def _daily_metrics_to_dict(metric: DailyMetrics) -> Dict[str, Any]:
        return {
            "calendarDate": metric.date.isoformat() if metric.date else None,
            "totalSteps": metric.total_steps,
            "totalDistanceMeters": metric.total_distance_meters,
            "totalKilocalories": metric.total_calories,
            "activeKilocalories": metric.active_calories,
            "moderateIntensityMinutes": metric.moderate_intensity_minutes,
            "vigorousIntensityMinutes": metric.vigorous_intensity_minutes,
        }

    @staticmethod
    def _sleep_to_dict(sleep: SleepSession) -> Dict[str, Any]:
        return {
            "dailySleepDTO": {
                "sleepTimeSeconds": sleep.sleep_time_seconds,
                "napTimeSeconds": sleep.nap_time_seconds,
                "deepSleepSeconds": sleep.deep_sleep_seconds,
                "lightSleepSeconds": sleep.light_sleep_seconds,
                "remSleepSeconds": sleep.rem_sleep_seconds,
                "awakeSleepSeconds": sleep.awake_seconds,
                "sleepScores": sleep.sleep_scores,
                "awakeCount": sleep.awake_count,
                "avgSleepStress": sleep.avg_sleep_stress,
                "averageRespirationValue": sleep.avg_respiration_value,
                "lowestRespirationValue": sleep.lowest_respiration_value,
                "highestRespirationValue": sleep.highest_respiration_value,
                "averageSpO2Value": sleep.avg_spo2_value,
                "lowestSpO2Value": sleep.lowest_spo2_value,
                "sleepStartTimestampLocal": sleep.sleep_start_timestamp.isoformat() if sleep.sleep_start_timestamp else None,
                "sleepEndTimestampLocal": sleep.sleep_end_timestamp.isoformat() if sleep.sleep_end_timestamp else None,
            }
        }

    @staticmethod
    def _hrv_to_dict(hrv: HRVData) -> Dict[str, Any]:
        return {
            "hrvSummary": {
                "weeklyAvg": hrv.weekly_avg,
                "lastNightAvg": hrv.last_night_avg,
                "lastNight5MinHigh": hrv.last_night_5_min_high,
                "status": hrv.status,
            }
        }

    @staticmethod
    def _activity_to_dict(activity: Activity) -> Dict[str, Any]:
        return {
            "activityId": activity.activity_id,
            "activityName": activity.activity_name,
            "activityType": {"typeKey": activity.activity_type},
            "startTimeLocal": activity.start_time_local.strftime("%Y-%m-%d %H:%M:%S") if activity.start_time_local else None,
            "distance": activity.distance,
            "duration": activity.duration,
            "movingDuration": activity.moving_duration,
            "elapsedDuration": activity.elapsed_duration,
            "elevationGain": activity.elevation_gain,
            "elevationLoss": activity.elevation_loss,
            "averageHR": activity.average_hr,
            "maxHR": activity.max_hr,
            "averageSpeed": activity.average_speed,
            "maxSpeed": activity.max_speed,
            "calories": activity.calories,
            "aerobicTrainingEffect": activity.aerobic_training_effect,
            "anaerobicTrainingEffect": activity.anaerobic_training_effect,
        }
    
    # === DAILY METRICS ===
    
    def save_daily_metrics(self, target_date: date, data: Dict[str, Any]) -> DailyMetrics:
        """Zapisuje metryki dzienne"""
        metric = self.session.query(DailyMetrics).filter_by(date=target_date).first()
        
        if not metric:
            metric = DailyMetrics(date=target_date)
            self.session.add(metric)
        
        # Mapowanie danych
        metric.total_steps = data.get('totalSteps')
        metric.total_distance_meters = data.get('totalDistanceMeters')
        metric.total_calories = data.get('totalKilocalories')
        metric.active_calories = data.get('activeKilocalories')
        metric.moderate_intensity_minutes = data.get('moderateIntensityMinutes')
        metric.vigorous_intensity_minutes = data.get('vigorousIntensityMinutes')
        metric.raw_data = self._prepare_raw_data("daily_metrics", data)
        
        self.session.commit()
        logger.info(f"Zapisano metryki dzienne dla {target_date}")
        return metric
    
    def get_daily_metrics(self, target_date: date) -> Optional[DailyMetrics]:
        """Pobiera metryki dzienne dla konkretnej daty"""
        return self.session.query(DailyMetrics).filter_by(date=target_date).first()
    
    # === SLEEP DATA ===
    
    @staticmethod
    def _normalize_sleep(raw_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Spłaszcza dailySleepDTO do poziomu głównego"""
        if not raw_data:
            return None
        dto = raw_data.get('dailySleepDTO', {})
        return {**raw_data, **dto} if dto else raw_data

    def save_sleep_data(self, target_date: date, data: Dict[str, Any]) -> SleepSession:
        """Zapisuje dane o śnie"""
        sleep = self.session.query(SleepSession).filter_by(date=target_date).first()
        
        if not sleep:
            sleep = SleepSession(date=target_date)
            self.session.add(sleep)
        
        # Garmin API zwraca dane w zagnieżdżonym dailySleepDTO
        dto = data.get('dailySleepDTO', {})
        
        def _get(key):
            return dto.get(key) or data.get(key)
        
        # Parsowanie timestamps
        sleep_start = _get('sleepStartTimestampLocal')
        sleep_end = _get('sleepEndTimestampLocal')
        
        def _parse_ts(ts):
            if ts is None:
                return None
            if isinstance(ts, int):
                from datetime import timezone
                return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            return datetime.fromisoformat(str(ts).replace('Z', '+00:00'))

        if sleep_start:
            sleep.sleep_start_timestamp = _parse_ts(sleep_start)
        if sleep_end:
            sleep.sleep_end_timestamp = _parse_ts(sleep_end)
        
        # Czasy snu
        sleep.sleep_time_seconds = _get('sleepTimeSeconds')
        sleep.nap_time_seconds = _get('napTimeSeconds')
        sleep.deep_sleep_seconds = _get('deepSleepSeconds')
        sleep.light_sleep_seconds = _get('lightSleepSeconds')
        sleep.rem_sleep_seconds = _get('remSleepSeconds')
        sleep.awake_seconds = _get('awakeSleepSeconds')
        
        # Jakość
        sleep.sleep_scores = _get('sleepScores')
        sleep.awake_count = _get('awakeCount')
        sleep.avg_sleep_stress = _get('avgSleepStress')
        
        # Respiracja
        sleep.avg_respiration_value = _get('averageRespirationValue') or _get('avgRespirationValue')
        sleep.lowest_respiration_value = _get('lowestRespirationValue')
        sleep.highest_respiration_value = _get('highestRespirationValue')
        
        # SpO2
        sleep.avg_spo2_value = _get('averageSpO2Value') or _get('avgSpo2Value')
        sleep.lowest_spo2_value = _get('lowestSpO2Value') or _get('lowestSpo2Value')
        
        sleep.raw_data = self._prepare_raw_data("sleep", data)
        
        self.session.commit()
        logger.info(f"Zapisano dane o śnie dla {target_date}")
        return sleep
    
    def get_sleep_data_for_date(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Pobiera dane o śnie dla konkretnej daty"""
        sleep = self.session.query(SleepSession).filter_by(date=target_date).first()
        if not sleep:
            return None
        raw_data = sleep.raw_data or self._sleep_to_dict(sleep)
        return self._normalize_sleep(raw_data)
    
    def get_sleep_data_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera dane o śnie dla zakresu dat"""
        sessions = self.session.query(SleepSession).filter(
            SleepSession.date >= start_date,
            SleepSession.date <= end_date
        ).order_by(SleepSession.date).all()
        
        return [self._normalize_sleep(s.raw_data or self._sleep_to_dict(s)) for s in sessions]
    
    # === HRV DATA ===
    
    @staticmethod
    def _normalize_hrv(raw_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Spłaszcza hrvSummary do poziomu głównego"""
        if not raw_data:
            return None
        summary = raw_data.get('hrvSummary', {})
        return {**raw_data, **summary} if summary else raw_data

    def save_hrv_data(self, target_date: date, data: Dict[str, Any]) -> HRVData:
        """Zapisuje dane HRV"""
        hrv = self.session.query(HRVData).filter_by(date=target_date).first()
        
        if not hrv:
            hrv = HRVData(date=target_date)
            self.session.add(hrv)
        
        # Garmin API zwraca dane HRV w zagnieżdżonym hrvSummary
        summary = data.get('hrvSummary', {})
        hrv.weekly_avg = summary.get('weeklyAvg') or data.get('weeklyAvg')
        hrv.last_night_avg = summary.get('lastNightAvg') or data.get('lastNightAvg')
        hrv.last_night_5_min_high = summary.get('lastNight5MinHigh') or data.get('lastNight5MinHigh')
        hrv.status = summary.get('status') or data.get('status')
        hrv.raw_data = self._prepare_raw_data("hrv", data)
        
        self.session.commit()
        logger.info(f"Zapisano dane HRV dla {target_date}")
        return hrv
    
    def get_hrv_data_for_date(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Pobiera dane HRV dla konkretnej daty"""
        hrv = self.session.query(HRVData).filter_by(date=target_date).first()
        if not hrv:
            return None
        raw_data = hrv.raw_data or self._hrv_to_dict(hrv)
        return self._normalize_hrv(raw_data)
    
    def get_hrv_data_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera dane HRV dla zakresu dat"""
        hrv_records = self.session.query(HRVData).filter(
            HRVData.date >= start_date,
            HRVData.date <= end_date
        ).order_by(HRVData.date).all()
        
        return [self._normalize_hrv(h.raw_data or self._hrv_to_dict(h)) for h in hrv_records]
    
    # === RESTING HEART RATE ===
    
    def save_resting_heart_rate(self, target_date: date, value: int) -> RestingHeartRate:
        """Zapisuje spoczynkowe tętno"""
        rhr = self.session.query(RestingHeartRate).filter_by(date=target_date).first()
        
        if not rhr:
            rhr = RestingHeartRate(date=target_date)
            self.session.add(rhr)
        
        rhr.value = value
        
        self.session.commit()
        logger.info(f"Zapisano RHR dla {target_date}: {value}")
        return rhr
    
    def get_resting_heart_rate_for_date(self, target_date: date) -> Optional[int]:
        """Pobiera RHR dla konkretnej daty"""
        rhr = self.session.query(RestingHeartRate).filter_by(date=target_date).first()
        return rhr.value if rhr else None
    
    def get_resting_heart_rate_range(self, start_date: date, end_date: date) -> List[int]:
        """Pobiera wartości RHR dla zakresu dat"""
        rhr_records = self.session.query(RestingHeartRate).filter(
            RestingHeartRate.date >= start_date,
            RestingHeartRate.date <= end_date
        ).order_by(RestingHeartRate.date).all()
        
        return [r.value for r in rhr_records]
    
    # === BODY BATTERY ===
    
    def save_body_battery(self, target_date: date, data: Dict[str, Any]) -> DailyMetrics:
        """Zapisuje dane Body Battery"""
        metric = self.session.query(DailyMetrics).filter_by(date=target_date).first()
        
        if not metric:
            metric = DailyMetrics(date=target_date)
            self.session.add(metric)
        
        # Wyciągnij wartości Body Battery z listy
        if isinstance(data, list) and len(data) > 0:
            latest = data[-1]
            metric.body_battery_charged = latest.get('charged')
            metric.body_battery_drained = latest.get('drained')
            metric.body_battery_highest = max([d.get('value', 0) for d in data])
            metric.body_battery_lowest = min([d.get('value', 100) for d in data])
        
        self.session.commit()
        return metric
    
    # === STRESS DATA ===
    
    def save_stress_data(self, target_date: date, data: Dict[str, Any]) -> DailyMetrics:
        """Zapisuje dane o stresie"""
        metric = self.session.query(DailyMetrics).filter_by(date=target_date).first()
        
        if not metric:
            metric = DailyMetrics(date=target_date)
            self.session.add(metric)
        
        metric.avg_stress_level = data.get('avgStressLevel')
        metric.max_stress_level = data.get('maxStressLevel')
        metric.stress_duration_seconds = data.get('stressDuration')
        metric.rest_duration_seconds = data.get('restDuration')
        metric.low_stress_duration_seconds = data.get('lowStressDuration')
        metric.medium_stress_duration_seconds = data.get('mediumStressDuration')
        metric.high_stress_duration_seconds = data.get('highStressDuration')
        
        self.session.commit()
        return metric
    
    # === ACTIVITIES ===
    
    def save_activity(self, data: Dict[str, Any]) -> Activity:
        """Zapisuje aktywność"""
        activity_id = data.get('activityId')
        activity = self.session.query(Activity).filter_by(activity_id=activity_id).first()
        
        if not activity:
            activity = Activity(activity_id=activity_id)
            self.session.add(activity)
        
        activity.activity_name = data.get('activityName')
        
        # Typ aktywności
        activity_type = data.get('activityType', {})
        activity.activity_type = activity_type.get('typeKey') if isinstance(activity_type, dict) else str(activity_type)
        activity.sport_type_id = data.get('sportTypeId')
        activity.time_zone_id = data.get('timeZoneId')
        event_type = data.get('eventType', {})
        activity.event_type = event_type.get('typeKey') if isinstance(event_type, dict) else event_type
        activity.device_id = data.get('deviceId')
        activity.manufacturer = data.get('manufacturer')
        activity.location_name = data.get('locationName')
        
        # Czas
        start_time = data.get('startTimeLocal')
        if start_time:
            activity.start_time_local = self._parse_activity_datetime(start_time)
        start_time_gmt = data.get('startTimeGMT')
        if start_time_gmt:
            activity.start_time_gmt = self._parse_activity_datetime(start_time_gmt)
        
        # Metryki
        activity.distance = data.get('distance')
        activity.duration = data.get('duration')
        activity.moving_duration = data.get('movingDuration')
        activity.elapsed_duration = data.get('elapsedDuration')
        
        # Wysokość
        activity.elevation_gain = data.get('elevationGain')
        activity.elevation_loss = data.get('elevationLoss')
        activity.min_elevation = data.get('minElevation')
        activity.max_elevation = data.get('maxElevation')
        activity.avg_elevation = data.get('avgElevation')
        
        # Tętno
        activity.average_hr = data.get('averageHR')
        activity.max_hr = data.get('maxHR')
        activity.min_hr = data.get('minHR')
        activity.recovery_hr = data.get('recoveryHeartRate')
        
        # Prędkość
        activity.average_speed = data.get('averageSpeed')
        activity.max_speed = data.get('maxSpeed')
        activity.avg_grade_adjusted_speed = data.get('avgGradeAdjustedSpeed')
        
        # Kalorie
        activity.calories = data.get('calories')
        activity.bmr_calories = data.get('bmrCalories')
        activity.steps = data.get('steps')
        
        # Training effect
        activity.aerobic_training_effect = data.get('aerobicTrainingEffect') or data.get('trainingEffect')
        activity.anaerobic_training_effect = data.get('anaerobicTrainingEffect')
        activity.training_effect_label = data.get('trainingEffectLabel')
        activity.aerobic_training_effect_message = data.get('aerobicTrainingEffectMessage')
        activity.anaerobic_training_effect_message = data.get('anaerobicTrainingEffectMessage')
        activity.activity_training_load = data.get('activityTrainingLoad')

        activity.avg_running_cadence = (
            data.get('averageRunningCadenceInStepsPerMinute')
            or data.get('averageRunCadence')
            or data.get('avgRunningCadence')
        )
        activity.max_running_cadence = (
            data.get('maxRunningCadenceInStepsPerMinute')
            or data.get('maxRunCadence')
            or data.get('maxRunningCadence')
        )
        activity.avg_biking_cadence = data.get('averageBikingCadenceInRevPerMinute') or data.get('averageBikeCadence')
        activity.max_biking_cadence = data.get('maxBikingCadenceInRevPerMinute') or data.get('maxBikeCadence')
        activity.avg_stride_length = data.get('avgStrideLength') or data.get('strideLength')
        activity.avg_ground_contact_time = data.get('avgGroundContactTime') or data.get('groundContactTime')
        activity.avg_ground_contact_balance = data.get('avgGroundContactBalance') or data.get('groundContactBalanceLeft')
        activity.avg_vertical_oscillation = data.get('avgVerticalOscillation') or data.get('verticalOscillation')
        activity.avg_vertical_ratio = data.get('avgVerticalRatio') or data.get('verticalRatio')

        activity.avg_power = data.get('avgPower') or data.get('averagePower')
        activity.max_power = data.get('maxPower')
        activity.normalized_power = data.get('normPower') or data.get('normalizedPower')
        activity.training_stress_score = data.get('trainingStressScore')
        activity.intensity_factor = data.get('intensityFactor')
        activity.total_work = data.get('totalWork')

        activity.avg_respiration_rate = data.get('avgRespirationRate')
        activity.min_respiration_rate = data.get('minRespirationRate')
        activity.max_respiration_rate = data.get('maxRespirationRate')
        activity.avg_temperature = data.get('averageTemperature')
        activity.min_temperature = data.get('minTemperature')
        activity.max_temperature = data.get('maxTemperature')
        activity.avg_stress = data.get('avgStress')
        activity.start_stress = data.get('startStress')
        activity.end_stress = data.get('endStress')
        activity.max_stress = data.get('maxStress')
        activity.difference_stress = data.get('differenceStress')
        activity.difference_body_battery = data.get('differenceBodyBattery')
        activity.begin_potential_stamina = data.get('beginPotentialStamina')
        activity.end_potential_stamina = data.get('endPotentialStamina')
        activity.min_available_stamina = data.get('minAvailableStamina')

        activity.moderate_intensity_minutes = data.get('moderateIntensityMinutes')
        activity.vigorous_intensity_minutes = data.get('vigorousIntensityMinutes')
        activity.active_sets = data.get('activeSets')
        activity.total_sets = data.get('totalSets')
        activity.total_reps = data.get('totalReps') or data.get('totalExerciseReps')
        activity.lap_count = data.get('lapCount')

        activity.start_latitude = data.get('startLatitude')
        activity.start_longitude = data.get('startLongitude')
        activity.end_latitude = data.get('endLatitude')
        activity.end_longitude = data.get('endLongitude')
        
        activity.raw_data = self._prepare_raw_data("activity", data)
        
        self.session.commit()
        logger.info(f"Zapisano aktywność {activity_id}")
        return activity

    @staticmethod
    def _parse_activity_datetime(value: Any) -> datetime:
        """Obsługuje formaty czasu zwracane przez listę i szczegóły Garmin."""
        raw_value = str(value)
        for date_format in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return datetime.strptime(raw_value, date_format)
            except ValueError:
                continue
        return datetime.fromisoformat(raw_value.replace('Z', '+00:00'))
    
    def save_activity_details(self, activity_id: int, data: Dict[str, Any]) -> ActivityDetail:
        """Zapisuje szczegóły aktywności"""
        detail = self.session.query(ActivityDetail).filter_by(activity_id=activity_id).first()
        
        if not detail:
            detail = ActivityDetail(activity_id=activity_id)
            self.session.add(detail)
        
        summary = data.get('summaryDTO', data)
        metrics = dict(summary) if isinstance(summary, dict) else {}

        # Szczegół Garmin zawiera część parametrów, których nie ma na liście
        # aktywności. Scal je z rekordem głównym, zachowując jego metadane.
        activity = self.session.query(Activity).filter_by(activity_id=activity_id).first()
        if activity and isinstance(summary, dict):
            if isinstance(activity.raw_data, dict):
                metrics = {**activity.raw_data, **summary}
            merged_activity = {
                **metrics,
                "activityId": activity_id,
                "activityName": activity.activity_name,
                "activityType": {"typeKey": activity.activity_type},
            }
            self.save_activity(merged_activity)

        # Garmin zwraca strefy jako listę albo osobne pola hrTimeInZone_N.
        time_in_zones = data.get('timeInHeartRateZones', [])
        for i in range(6):
            zone_time = time_in_zones[i] if i < len(time_in_zones) else metrics.get(f'hrTimeInZone_{i}')
            setattr(detail, f'time_in_hr_zone_{i}', zone_time)
        
        # Kadencja
        detail.avg_running_cadence = (
            metrics.get('averageRunningCadenceInStepsPerMinute')
            or metrics.get('averageRunCadence')
            or metrics.get('avgRunningCadence')
        )
        detail.max_running_cadence = (
            metrics.get('maxRunningCadenceInStepsPerMinute')
            or metrics.get('maxRunCadence')
            or metrics.get('maxRunningCadence')
        )
        detail.avg_stride_length = metrics.get('strideLength') or metrics.get('avgStrideLength')
        
        # VO2 Max
        detail.vo2_max_value = metrics.get('vO2MaxValue')
        
        detail.raw_data = self._prepare_raw_data("activity_detail", data)
        
        self.session.commit()
        logger.info(f"Zapisano szczegóły aktywności {activity_id}")
        return detail
    
    def activity_exists(self, activity_id: int) -> bool:
        """Sprawdza czy aktywność istnieje w bazie"""
        return self.session.query(Activity).filter_by(activity_id=activity_id).count() > 0

    def activity_detail_needs_refresh(self, activity_id: int) -> bool:
        """Sprawdza, czy brak pełnego payloadu szczegółów aktywności."""
        detail = self.session.query(ActivityDetail).filter_by(activity_id=activity_id).first()
        return not detail or not isinstance(detail.raw_data, dict) or 'summaryDTO' not in detail.raw_data

    @staticmethod
    def _serialize_model_columns(record: Any, excluded: Optional[set[str]] = None) -> Dict[str, Any]:
        """Serializuje wszystkie kolumny modelu SQLAlchemy do JSON-friendly dict."""
        excluded = excluded or set()
        result = {}

        for column in record.__table__.columns:
            if column.name in excluded:
                continue

            value = getattr(record, column.name)
            if isinstance(value, (date, datetime)):
                value = value.isoformat()
            result[column.name] = value

        return result

    def _activity_document(
        self,
        activity: Activity,
        include_raw: bool = True,
        include_details: bool = True,
    ) -> Dict[str, Any]:
        """Buduje pełny dokument treningu do zwrócenia przez API."""
        document = self._serialize_model_columns(activity, {"raw_data"})

        if include_raw:
            document["raw_data"] = activity.raw_data

        if include_details:
            detail = self.session.query(ActivityDetail).filter_by(
                activity_id=activity.activity_id
            ).first()
            if detail:
                document["details"] = self._serialize_model_columns(detail, {"raw_data"})
                if include_raw:
                    document["details"]["raw_data"] = detail.raw_data
            else:
                document["details"] = None

        return document

    def get_activity_document(
        self,
        activity_id: int,
        include_raw: bool = True,
        include_details: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Pobiera jeden trening wraz ze wszystkimi zapisanymi parametrami."""
        activity = self.session.query(Activity).filter_by(activity_id=activity_id).first()
        if not activity:
            return None
        return self._activity_document(activity, include_raw, include_details)

    def get_activity_history(
        self,
        start_date: date,
        end_date: date,
        activity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_raw: bool = True,
        include_details: bool = True,
    ) -> Dict[str, Any]:
        """Pobiera stronicowaną historię treningów z pełnymi parametrami."""
        query = self.session.query(Activity).filter(
            Activity.start_time_local >= datetime.combine(start_date, datetime.min.time()),
            Activity.start_time_local <= datetime.combine(end_date, datetime.max.time()),
        )

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)

        total = query.count()
        activities = (
            query.order_by(Activity.start_time_local.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(activities) < total,
            "items": [
                self._activity_document(activity, include_raw, include_details)
                for activity in activities
            ],
        }
    
    def get_activities_in_date_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera aktywności z zakresu dat"""
        activities = self.session.query(Activity).filter(
            Activity.start_time_local >= datetime.combine(start_date, datetime.min.time()),
            Activity.start_time_local <= datetime.combine(end_date, datetime.max.time())
        ).order_by(Activity.start_time_local).all()
        
        return [a.raw_data or self._activity_to_dict(a) for a in activities]
    
    # === RECOVERY METRICS ===
    
    def save_recovery_metrics(self, target_date: date, metrics: Dict[str, Any]) -> RecoveryMetrics:
        """Zapisuje wskaźniki regeneracji"""
        recovery = self.session.query(RecoveryMetrics).filter_by(date=target_date).first()
        
        if not recovery:
            recovery = RecoveryMetrics(date=target_date)
            self.session.add(recovery)
        
        recovery.readiness_score = metrics.get('readiness_score')
        recovery.recovery_score = metrics.get('recovery_score')
        recovery.category = metrics.get('category')
        recovery.recommendation = metrics.get('recommendation')
        
        # Komponenty
        components = metrics.get('components', {})
        recovery.hrv_score = components.get('hrv', {}).get('score')
        recovery.sleep_score = components.get('sleep', {}).get('score')
        recovery.rhr_score = components.get('rhr', {}).get('score')
        recovery.training_load_score = components.get('training_load', {}).get('score')
        
        self.session.commit()
        logger.info(f"Zapisano metryki regeneracji dla {target_date}")
        return recovery
    
    # === AI INSIGHTS ===
    
    def save_ai_insight(
        self,
        target_date: date,
        insight_type: str,
        title: str,
        content: str,
        priority: str = 'medium'
    ) -> AIInsight:
        """Zapisuje insight z AI"""
        insight = AIInsight(
            date=target_date,
            insight_type=insight_type,
            title=title,
            content=content,
            priority=priority
        )
        
        self.session.add(insight)
        self.session.commit()
        logger.info(f"Zapisano AI insight: {title}")
        return insight
    
    def get_recent_insights(self, days: int = 7, unread_only: bool = False) -> List[AIInsight]:
        """Pobiera ostatnie insighty"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        query = self.session.query(AIInsight).filter(
            AIInsight.date >= start_date,
            AIInsight.date <= end_date
        )
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        return query.order_by(AIInsight.date.desc()).all()

    # === BODY WEIGHT ===

    def save_weight_data(self, target_date: date, data: Dict[str, Any]) -> BodyWeight:
        """Zapisuje dane o masie ciała"""
        record = self.session.query(BodyWeight).filter_by(date=target_date).first()
        if not record:
            record = BodyWeight(date=target_date)
            self.session.add(record)

        record.weight_grams = data.get('weight')
        record.bmi = data.get('bmi')
        record.body_fat_percent = data.get('bodyFat')
        record.body_water_percent = data.get('bodyWater')
        record.muscle_mass_grams = data.get('muscleMass')
        record.bone_mass_grams = data.get('boneMass')
        record.raw_data = self._prepare_raw_data("weight", data)

        self.session.commit()
        logger.info(f"Zapisano dane wagowe dla {target_date}")
        return record

    def get_weight_data_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera dane wagowe dla zakresu dat"""
        records = self.session.query(BodyWeight).filter(
            BodyWeight.date >= start_date,
            BodyWeight.date <= end_date
        ).order_by(BodyWeight.date).all()
        return [r.raw_data for r in records if r.raw_data]

    def get_latest_weight(self) -> Optional[BodyWeight]:
        """Pobiera ostatni wpis wagowy"""
        return self.session.query(BodyWeight).order_by(BodyWeight.date.desc()).first()

    # === VO2MAX ===

    def save_vo2max_data(self, target_date: date, data: Dict[str, Any]) -> VO2MaxData:
        """Zapisuje dane VO2max"""
        record = self.session.query(VO2MaxData).filter_by(date=target_date).first()
        if not record:
            record = VO2MaxData(date=target_date)
            self.session.add(record)

        record.vo2max_precise = data.get('vo2MaxPreciseValue')
        record.vo2max_value = data.get('vo2MaxValue')
        record.fitness_age = data.get('fitnessAge')
        record.raw_data = self._prepare_raw_data("vo2max", data)

        self.session.commit()
        logger.info(f"Zapisano VO2max dla {target_date}: {data.get('vo2MaxPreciseValue')}")
        return record

    def get_latest_vo2max(self) -> Optional[VO2MaxData]:
        """Pobiera ostatni rekord VO2max"""
        return self.session.query(VO2MaxData).order_by(VO2MaxData.date.desc()).first()

    def get_vo2max_range(self, start_date: date, end_date: date) -> List[VO2MaxData]:
        """Pobiera dane VO2max dla zakresu dat"""
        return self.session.query(VO2MaxData).filter(
            VO2MaxData.date >= start_date,
            VO2MaxData.date <= end_date
        ).order_by(VO2MaxData.date).all()
