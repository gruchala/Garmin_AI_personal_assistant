"""Modele bazy danych SQLAlchemy"""

import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, JSON, Boolean, Text, inspect, text
from sqlalchemy.schema import CreateColumn
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class DailyMetrics(Base):
    """Metryki dzienne"""
    __tablename__ = 'daily_metrics'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    
    # Podstawowe statystyki
    total_steps = Column(Integer)
    total_distance_meters = Column(Float)
    total_calories = Column(Integer)
    active_calories = Column(Integer)
    
    # Dane treningowe
    moderate_intensity_minutes = Column(Integer)
    vigorous_intensity_minutes = Column(Integer)
    
    # Body Battery
    body_battery_charged = Column(Integer)
    body_battery_drained = Column(Integer)
    body_battery_highest = Column(Integer)
    body_battery_lowest = Column(Integer)
    
    # Stres
    avg_stress_level = Column(Integer)
    max_stress_level = Column(Integer)
    stress_duration_seconds = Column(Integer)
    rest_duration_seconds = Column(Integer)
    low_stress_duration_seconds = Column(Integer)
    medium_stress_duration_seconds = Column(Integer)
    high_stress_duration_seconds = Column(Integer)
    
    # Metadata
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SleepSession(Base):
    """Sesje snu"""
    __tablename__ = 'sleep_sessions'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    
    # Podstawowe informacje
    sleep_start_timestamp = Column(DateTime)
    sleep_end_timestamp = Column(DateTime)
    
    # Czas snu w sekundach
    sleep_time_seconds = Column(Integer)
    nap_time_seconds = Column(Integer)
    
    # Fazy snu w sekundach
    deep_sleep_seconds = Column(Integer)
    light_sleep_seconds = Column(Integer)
    rem_sleep_seconds = Column(Integer)
    awake_seconds = Column(Integer)
    
    # Jakość snu
    sleep_scores = Column(JSON)
    awake_count = Column(Integer)
    avg_sleep_stress = Column(Float)
    
    # Respiracja i SpO2
    avg_respiration_value = Column(Float)
    lowest_respiration_value = Column(Float)
    highest_respiration_value = Column(Float)
    avg_spo2_value = Column(Float)
    lowest_spo2_value = Column(Float)
    
    # Metadata
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HRVData(Base):
    """Dane HRV (Heart Rate Variability)"""
    __tablename__ = 'hrv_data'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    
    # Wartości HRV
    weekly_avg = Column(Float)
    last_night_avg = Column(Float)
    last_night_5_min_high = Column(Float)
    
    # Status
    status = Column(String(50))
    
    # Metadata
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RestingHeartRate(Base):
    """Spoczynkowe tętno"""
    __tablename__ = 'resting_heart_rate'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    
    value = Column(Integer, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Activity(Base):
    """Aktywności treningowe"""
    __tablename__ = 'activities'
    
    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, unique=True, nullable=False, index=True)
    
    # Podstawowe informacje
    activity_name = Column(String(255))
    activity_type = Column(String(100))
    sport_type_id = Column(Integer)
    start_time_local = Column(DateTime, index=True)
    start_time_gmt = Column(DateTime)
    time_zone_id = Column(Integer)
    event_type = Column(String(100))
    device_id = Column(Integer)
    manufacturer = Column(String(100))
    location_name = Column(String(255))
    
    # Metryki
    distance = Column(Float)  # metry
    duration = Column(Float)  # sekundy
    moving_duration = Column(Float)  # sekundy
    elapsed_duration = Column(Float)  # sekundy
    
    # Wysokość
    elevation_gain = Column(Float)
    elevation_loss = Column(Float)
    min_elevation = Column(Float)
    max_elevation = Column(Float)
    avg_elevation = Column(Float)
    
    # Tętno
    average_hr = Column(Integer)
    max_hr = Column(Integer)
    min_hr = Column(Integer)
    recovery_hr = Column(Integer)
    
    # Tempo/prędkość
    average_speed = Column(Float)  # m/s
    max_speed = Column(Float)  # m/s
    avg_grade_adjusted_speed = Column(Float)
    
    # Kalorie
    calories = Column(Integer)
    bmr_calories = Column(Integer)
    steps = Column(Integer)
    
    # Training effect
    aerobic_training_effect = Column(Float)
    anaerobic_training_effect = Column(Float)
    training_effect_label = Column(String(100))
    aerobic_training_effect_message = Column(String(255))
    anaerobic_training_effect_message = Column(String(255))
    activity_training_load = Column(Float)

    # Kadencja i dynamika ruchu
    avg_running_cadence = Column(Float)
    max_running_cadence = Column(Float)
    avg_biking_cadence = Column(Float)
    max_biking_cadence = Column(Float)
    avg_stride_length = Column(Float)
    avg_ground_contact_time = Column(Float)
    avg_ground_contact_balance = Column(Float)
    avg_vertical_oscillation = Column(Float)
    avg_vertical_ratio = Column(Float)

    # Moc
    avg_power = Column(Float)
    max_power = Column(Float)
    normalized_power = Column(Float)
    training_stress_score = Column(Float)
    intensity_factor = Column(Float)
    total_work = Column(Float)

    # Oddech, temperatura, stres i stamina
    avg_respiration_rate = Column(Float)
    min_respiration_rate = Column(Float)
    max_respiration_rate = Column(Float)
    avg_temperature = Column(Float)
    min_temperature = Column(Float)
    max_temperature = Column(Float)
    avg_stress = Column(Float)
    start_stress = Column(Float)
    end_stress = Column(Float)
    max_stress = Column(Float)
    difference_stress = Column(Float)
    difference_body_battery = Column(Integer)
    begin_potential_stamina = Column(Float)
    end_potential_stamina = Column(Float)
    min_available_stamina = Column(Float)

    # Trening siłowy i intensywność
    moderate_intensity_minutes = Column(Integer)
    vigorous_intensity_minutes = Column(Integer)
    active_sets = Column(Integer)
    total_sets = Column(Integer)
    total_reps = Column(Integer)
    lap_count = Column(Integer)

    # Lokalizacja
    start_latitude = Column(Float)
    start_longitude = Column(Float)
    end_latitude = Column(Float)
    end_longitude = Column(Float)
    
    # Metadata
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityDetail(Base):
    """Szczegółowe dane aktywności"""
    __tablename__ = 'activity_details'
    
    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, unique=True, nullable=False, index=True)
    
    # Strefy tętna (czas w sekundach)
    time_in_hr_zone_0 = Column(Integer)
    time_in_hr_zone_1 = Column(Integer)
    time_in_hr_zone_2 = Column(Integer)
    time_in_hr_zone_3 = Column(Integer)
    time_in_hr_zone_4 = Column(Integer)
    time_in_hr_zone_5 = Column(Integer)
    
    # Dodatkowe metryki
    avg_running_cadence = Column(Float)
    max_running_cadence = Column(Float)
    avg_stride_length = Column(Float)
    
    # VO2 Max
    vo2_max_value = Column(Float)
    
    # Metadata
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecoveryMetrics(Base):
    """Obliczone wskaźniki regeneracji"""
    __tablename__ = 'recovery_metrics'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    
    # Wyniki
    readiness_score = Column(Float)
    recovery_score = Column(Float)
    
    # Komponenty
    hrv_score = Column(Float)
    sleep_score = Column(Float)
    rhr_score = Column(Float)
    training_load_score = Column(Float)
    
    # Kategoria i rekomendacje
    category = Column(String(50))
    recommendation = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BodyWeight(Base):
    """Dane o masie ciała i składzie ciała"""
    __tablename__ = 'body_weight'

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)

    weight_grams = Column(Float)      # gramy (API zwraca w gramach)
    bmi = Column(Float)
    body_fat_percent = Column(Float)
    body_water_percent = Column(Float)
    muscle_mass_grams = Column(Float)
    bone_mass_grams = Column(Float)

    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VO2MaxData(Base):
    """Dane VO2max i status treningowy"""
    __tablename__ = 'vo2max_data'

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)

    vo2max_precise = Column(Float)    # np. 47.4
    vo2max_value = Column(Integer)    # zaokrąglona wartość np. 47
    fitness_age = Column(Integer)

    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIInsight(Base):
    """Insighty generowane przez AI"""
    __tablename__ = 'ai_insights'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    
    # Typ insightu
    insight_type = Column(String(100))  # 'daily_summary', 'trend_analysis', 'recommendation', etc.
    
    # Treść
    title = Column(String(255))
    content = Column(Text)
    
    # Priorytet
    priority = Column(String(50))  # 'high', 'medium', 'low'
    
    # Czy przeczytany
    is_read = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)


# Funkcja do inicjalizacji bazy danych
def init_db(database_url: str = "sqlite:///garmin_data.db"):
    """
    Inicjalizuje bazę danych
    
    Args:
        database_url: URL do bazy danych
        
    Returns:
        Tuple (engine, SessionLocal)
    """
    resolved_database_url = os.getenv("DATABASE_URL", database_url)
    engine_kwargs = {"echo": False}

    if resolved_database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(resolved_database_url, **engine_kwargs)
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    return engine, SessionLocal


def _add_missing_columns(engine) -> None:
    """Dodaje nowe, opcjonalne kolumny bez kasowania istniejących danych."""
    schema = inspect(engine)

    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not schema.has_table(table.name):
                continue

            existing = {column["name"] for column in schema.get_columns(table.name)}
            quoted_table = engine.dialect.identifier_preparer.quote(table.name)

            for column in table.columns:
                if column.name in existing:
                    continue

                column_ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
                connection.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {column_ddl}"))
