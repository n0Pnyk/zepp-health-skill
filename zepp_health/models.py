"""Zepp health data models.

Contains raw data models fetched from the API and analysis output models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Raw data models (data structures returned by the API)
# ============================================================


class StepData(BaseModel):
    """Step count data."""

    timestamp: datetime
    steps: int = 0
    distance_meters: int = Field(default=0, description="Distance in meters")
    calories: int = Field(default=0, description="Calories burned")
    run_distance: int = Field(default=0, description="Running distance in meters")
    walking_minutes: int = Field(default=0, description="Walking duration in minutes")
    running_calories: int = Field(default=0, description="Running calories")
    running_steps: int = Field(default=0, description="Running steps")


class SleepPhase(BaseModel):
    """Individual sleep phase."""

    start: datetime
    end: datetime
    phase_type: str = Field(description="Phase type: deep/light/rem/awake")
    duration_minutes: int


class SleepData(BaseModel):
    """Sleep data."""

    date: str
    start_time: datetime
    end_time: datetime
    total_minutes: int
    deep_sleep_minutes: int
    light_sleep_minutes: int
    rem_sleep_minutes: int = 0
    awake_minutes: int = 0
    sleep_score: Optional[int] = Field(default=None, description="Sleep quality score (0-100)")
    resting_heart_rate: Optional[int] = Field(default=None, description="Resting heart rate during sleep")
    sleep_onset_latency: Optional[int] = Field(default=None, description="Sleep onset latency in minutes")
    wake_count: int = Field(default=0, description="Number of awakenings")
    wake_minutes: int = Field(default=0, description="Awake duration in minutes")
    total_bed_time: Optional[int] = Field(default=None, description="Total time in bed in minutes")
    out_of_bed_time: Optional[int] = Field(default=None, description="Time out of bed in minutes")
    interruption_score: Optional[int] = Field(default=None, description="Interruption score")
    phases: list[SleepPhase] = Field(default_factory=list)


class HeartRateData(BaseModel):
    """Heart rate data."""

    timestamp: datetime
    bpm: int
    activity_type: Optional[str] = None


class ActivitySummary(BaseModel):
    """Activity summary."""

    start: datetime
    end: datetime
    mode: int = Field(description="Activity mode code")
    mode_name: str = Field(description="Activity mode name")
    steps: int = 0
    distance: int = 0
    calories: int = 0


class ActivityData(BaseModel):
    """Daily activity data (includes steps, sleep, heart rate)."""

    date: str
    steps: Optional[StepData] = None
    sleep: Optional[SleepData] = None
    heart_rates: list[HeartRateData] = Field(default_factory=list)
    activities: list[ActivitySummary] = Field(default_factory=list)


class StressReading(BaseModel):
    """Individual stress reading."""

    timestamp: datetime
    value: int = Field(description="Stress value (0-100)")


class StressData(BaseModel):
    """Daily stress data."""

    date: str
    min_stress: int = 0
    max_stress: int = 0
    avg_stress: int = 0
    relax_proportion: int = Field(default=0, description="Relaxed state proportion (%)")
    normal_proportion: int = Field(default=0, description="Normal state proportion (%)")
    medium_proportion: int = Field(default=0, description="Medium stress proportion (%)")
    high_proportion: int = Field(default=0, description="High stress proportion (%)")
    readings: list[StressReading] = Field(default_factory=list)


class SpO2Reading(BaseModel):
    """Individual SpO2 reading."""

    timestamp: datetime
    spo2: int = Field(description="Blood oxygen percentage (0-100)")
    reading_type: str = Field(default="auto", description="auto or manual")


class OSAEvent(BaseModel):
    """Sleep apnea event."""

    timestamp: datetime
    spo2_decrease: Optional[int] = Field(default=None, description="Minimum SpO2 value")
    spo2_samples: list[int] = Field(default_factory=list)
    hr_samples: list[int] = Field(default_factory=list)


class SpO2Data(BaseModel):
    """Daily SpO2 data."""

    date: str
    odi: Optional[float] = Field(default=None, description="Oxygen desaturation index")
    odi_count: int = Field(default=0, description="Number of oxygen desaturation events")
    sleep_score: Optional[int] = Field(default=None, description="Sleep breathing score")
    readings: list[SpO2Reading] = Field(default_factory=list)
    osa_events: list[OSAEvent] = Field(default_factory=list)


class PAIData(BaseModel):
    """PAI (Personal Activity Intelligence) data."""

    date: str
    total_pai: float = Field(default=0, description="7-day rolling PAI score")
    daily_pai: float = Field(default=0, description="Daily PAI score")
    resting_hr: Optional[int] = None
    max_hr: Optional[int] = None
    low_zone_minutes: int = 0
    medium_zone_minutes: int = 0
    high_zone_minutes: int = 0


class HeartRateZone(BaseModel):
    """Heart rate zone."""

    zone: int = Field(description="Zone number (1-6)")
    zone_name: str
    seconds: int = Field(description="Time spent in this zone in seconds")
    max_hr: int


# Workout type code mapping
WORKOUT_TYPES = {
    1: "outdoor_running",
    2: "walking",
    3: "cycling",
    4: "treadmill",
    5: "indoor_cycling",
    6: "elliptical",
    7: "climbing",
    8: "trail_running",
    9: "skiing",
    10: "snowboarding",
    16: "freestyle",
    17: "swimming",
    18: "indoor_swimming",
    19: "open_water_swimming",
    20: "yoga",
    21: "rowing",
    22: "indoor_rowing",
    64: "strength_training",
    128: "hiit",
    223: "other",
}


class Workout(BaseModel):
    """Workout record."""

    track_id: str
    workout_type: int
    workout_name: str = ""
    start_time: datetime
    end_time: datetime
    duration_seconds: int = 0
    distance_meters: float = 0
    calories: float = 0
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    min_heart_rate: Optional[int] = None
    avg_pace: Optional[float] = Field(default=None, description="Pace (min/km)")
    total_steps: int = 0
    training_effect: Optional[float] = Field(default=None, description="Aerobic training effect (1-5)")
    anaerobic_te: Optional[float] = Field(default=None, description="Anaerobic training effect (1-5)")
    vo2_max: Optional[int] = None
    exercise_load: Optional[int] = Field(default=None, description="Exercise load")
    avg_cadence: Optional[int] = None
    hr_zones: list[HeartRateZone] = Field(default_factory=list)


class ReadinessData(BaseModel):
    """Daily readiness/recovery data (including HRV and body temperature)."""

    date: str
    readiness_score: Optional[int] = Field(default=None, description="Overall readiness score (0-100)")
    readiness_insight: Optional[int] = None
    rhr_score: Optional[int] = Field(default=None, description="Resting heart rate score (0-100)")
    rhr_baseline: Optional[int] = Field(default=None, description="Personal RHR baseline (bpm)")
    sleep_rhr: Optional[int] = Field(default=None, description="RHR during sleep (bpm)")
    hrv_score: Optional[int] = Field(default=None, description="HRV score (0-100)")
    hrv_baseline: Optional[int] = Field(default=None, description="Personal HRV baseline (ms)")
    sleep_hrv: Optional[int] = Field(default=None, description="HRV during sleep (ms)")
    skin_temp_score: Optional[int] = Field(default=None, description="Body temperature score (0-100)")
    skin_temp_baseline: Optional[float] = None
    skin_temp_calibrated: Optional[float] = None
    mental_score: Optional[int] = Field(default=None, description="Mental state score (0-100)")
    mental_baseline: Optional[int] = None
    physical_score: Optional[int] = Field(default=None, description="Physical state score (0-100)")
    physical_baseline: Optional[int] = None
    ahi_score: Optional[int] = Field(default=None, description="Apnea score")
    ahi_baseline: Optional[float] = None
    afib_score: Optional[int] = Field(default=None, description="Atrial fibrillation score")
    afib_baseline: Optional[int] = None


class DaySummary(BaseModel):
    """Daily summary."""

    date: str
    total_steps: int = 0
    total_distance_meters: int = 0
    total_calories: int = 0
    sleep_minutes: int = 0
    deep_sleep_minutes: int = 0
    light_sleep_minutes: int = 0
    rem_sleep_minutes: int = 0
    resting_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    min_heart_rate: Optional[int] = None
    avg_stress: Optional[int] = None
    avg_spo2: Optional[int] = None
    total_pai: Optional[float] = None


# ============================================================
# Additional data models (extra endpoints from zepp-health-cli)
# ============================================================


class VO2MaxRecord(BaseModel):
    """VO2 max record."""

    date: str
    vo2_max: int = Field(description="VO2 max (ml/kg/min)")
    device_id: Optional[str] = None


class WeightRecord(BaseModel):
    """Weight record."""

    timestamp: datetime
    weight_kg: float
    bmi: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass: Optional[float] = None
    bone_mass: Optional[float] = None
    visceral_fat: Optional[float] = None
    body_water_pct: Optional[float] = None
    basal_metabolism: Optional[int] = None


class BloodPressureRecord(BaseModel):
    """Blood pressure record."""

    timestamp: datetime
    systolic: int = Field(description="Systolic pressure (mmHg)")
    diastolic: int = Field(description="Diastolic pressure (mmHg)")
    pulse: Optional[int] = None
    source: Optional[str] = None


class BodyBatteryReading(BaseModel):
    """Body battery reading."""

    timestamp: datetime
    value: int = Field(description="Body battery (0-100)")


class HRVReading(BaseModel):
    """HRV reading."""

    timestamp: datetime
    hrv_value: int = Field(description="HRV value (ms)")
    reading_type: str = Field(default="sdnn", description="sdnn or rmssd")


class RespiratoryRateReading(BaseModel):
    """Respiratory rate reading."""

    timestamp: datetime
    breaths_per_minute: float


class SportLoadRecord(BaseModel):
    """Sport load record."""

    date: str
    wtl_sum: Optional[float] = Field(default=None, description="Daily training load sum")
    current_day_train_load: Optional[float] = None


# ============================================================
# Analysis output models
# ============================================================


class RecoveryScore(BaseModel):
    """Recovery score."""

    score: int = Field(description="Recovery score (0-100)")
    hrv_component: Optional[int] = Field(default=None, description="HRV component score")
    rhr_component: Optional[int] = Field(default=None, description="RHR component score")
    trend: str = Field(default="stable", description="Trend: improving/declining/stable")
    fatigue_signal: bool = Field(default=False, description="Whether fatigue signal is detected")
    details: str = ""


class SleepQualityScore(BaseModel):
    """Sleep quality score."""

    score: int = Field(description="Sleep quality score (0-100)")
    deep_sleep_pct: Optional[float] = Field(default=None, description="Deep sleep percentage (%)")
    rem_sleep_pct: Optional[float] = Field(default=None, description="REM sleep percentage (%)")
    efficiency_pct: Optional[float] = Field(default=None, description="Sleep efficiency (%)")
    duration_minutes: Optional[int] = None
    details: str = ""


class ExertionScore(BaseModel):
    """Training load score."""

    score: int = Field(description="Training load score (0-100)")
    acute_load_7d: float = Field(default=0, description="7-day acute load")
    chronic_load_28d: float = Field(default=0, description="28-day chronic load")
    ratio: float = Field(default=0, description="Acute/chronic ratio")
    zone: str = Field(default="inactive", description="Load zone")
    details: str = ""


class HealthReport(BaseModel):
    """Complete health report."""

    date: str
    generated_at: datetime
    overall_score: Optional[int] = Field(default=None, description="Overall health score (0-100)")
    recovery: Optional[RecoveryScore] = None
    sleep_quality: Optional[SleepQualityScore] = None
    exertion: Optional[ExertionScore] = None
    raw_metrics: dict = Field(default_factory=dict, description="Raw metrics data")
    recommendations: list[str] = Field(default_factory=list, description="Health recommendations")
