"""Repozytorium do operacji na bazie danych"""

import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional
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
        metric.raw_data = data
        
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
        
        sleep.raw_data = data
        
        self.session.commit()
        logger.info(f"Zapisano dane o śnie dla {target_date}")
        return sleep
    
    def get_sleep_data_for_date(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Pobiera dane o śnie dla konkretnej daty"""
        sleep = self.session.query(SleepSession).filter_by(date=target_date).first()
        return self._normalize_sleep(sleep.raw_data) if sleep else None
    
    def get_sleep_data_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera dane o śnie dla zakresu dat"""
        sessions = self.session.query(SleepSession).filter(
            SleepSession.date >= start_date,
            SleepSession.date <= end_date
        ).order_by(SleepSession.date).all()
        
        return [self._normalize_sleep(s.raw_data) for s in sessions if s.raw_data]
    
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
        hrv.raw_data = data
        
        self.session.commit()
        logger.info(f"Zapisano dane HRV dla {target_date}")
        return hrv
    
    def get_hrv_data_for_date(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Pobiera dane HRV dla konkretnej daty"""
        hrv = self.session.query(HRVData).filter_by(date=target_date).first()
        return self._normalize_hrv(hrv.raw_data) if hrv else None
    
    def get_hrv_data_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera dane HRV dla zakresu dat"""
        hrv_records = self.session.query(HRVData).filter(
            HRVData.date >= start_date,
            HRVData.date <= end_date
        ).order_by(HRVData.date).all()
        
        return [self._normalize_hrv(h.raw_data) for h in hrv_records if h.raw_data]
    
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
        
        # Czas
        start_time = data.get('startTimeLocal')
        if start_time:
            activity.start_time_local = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        
        # Metryki
        activity.distance = data.get('distance')
        activity.duration = data.get('duration')
        activity.moving_duration = data.get('movingDuration')
        activity.elapsed_duration = data.get('elapsedDuration')
        
        # Wysokość
        activity.elevation_gain = data.get('elevationGain')
        activity.elevation_loss = data.get('elevationLoss')
        
        # Tętno
        activity.average_hr = data.get('averageHR')
        activity.max_hr = data.get('maxHR')
        
        # Prędkość
        activity.average_speed = data.get('averageSpeed')
        activity.max_speed = data.get('maxSpeed')
        
        # Kalorie
        activity.calories = data.get('calories')
        
        # Training effect
        activity.aerobic_training_effect = data.get('aerobicTrainingEffect')
        activity.anaerobic_training_effect = data.get('anaerobicTrainingEffect')
        
        activity.raw_data = data
        
        self.session.commit()
        logger.info(f"Zapisano aktywność {activity_id}")
        return activity
    
    def save_activity_details(self, activity_id: int, data: Dict[str, Any]) -> ActivityDetail:
        """Zapisuje szczegóły aktywności"""
        detail = self.session.query(ActivityDetail).filter_by(activity_id=activity_id).first()
        
        if not detail:
            detail = ActivityDetail(activity_id=activity_id)
            self.session.add(detail)
        
        # Strefy tętna
        time_in_zones = data.get('timeInHeartRateZones', [])
        for i, zone_time in enumerate(time_in_zones[:6]):
            setattr(detail, f'time_in_hr_zone_{i}', zone_time)
        
        # Kadencja
        detail.avg_running_cadence = data.get('avgRunningCadence')
        detail.max_running_cadence = data.get('maxRunningCadence')
        detail.avg_stride_length = data.get('avgStrideLength')
        
        # VO2 Max
        detail.vo2_max_value = data.get('vO2MaxValue')
        
        detail.raw_data = data
        
        self.session.commit()
        logger.info(f"Zapisano szczegóły aktywności {activity_id}")
        return detail
    
    def activity_exists(self, activity_id: int) -> bool:
        """Sprawdza czy aktywność istnieje w bazie"""
        return self.session.query(Activity).filter_by(activity_id=activity_id).count() > 0
    
    def get_activities_in_date_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera aktywności z zakresu dat"""
        activities = self.session.query(Activity).filter(
            Activity.start_time_local >= datetime.combine(start_date, datetime.min.time()),
            Activity.start_time_local <= datetime.combine(end_date, datetime.max.time())
        ).order_by(Activity.start_time_local).all()
        
        return [a.raw_data for a in activities if a.raw_data]
    
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
        record.raw_data = data

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
        record.raw_data = data

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
