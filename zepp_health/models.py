"""Zepp 健康数据模型。

包含从 API 获取的原始数据模型和分析输出模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 原始数据模型（API 返回的数据结构）
# ============================================================


class StepData(BaseModel):
    """步数数据。"""

    timestamp: datetime
    steps: int = 0
    distance_meters: int = Field(default=0, description="距离（米）")
    calories: int = Field(default=0, description="消耗卡路里")
    run_distance: int = Field(default=0, description="跑步距离（米）")
    walking_minutes: int = Field(default=0, description="步行时长（分钟）")
    running_calories: int = Field(default=0, description="跑步卡路里")
    running_steps: int = Field(default=0, description="跑步步数")


class SleepPhase(BaseModel):
    """单个睡眠阶段。"""

    start: datetime
    end: datetime
    phase_type: str = Field(description="阶段类型: deep/light/rem/awake")
    duration_minutes: int


class SleepData(BaseModel):
    """睡眠数据。"""

    date: str
    start_time: datetime
    end_time: datetime
    total_minutes: int
    deep_sleep_minutes: int
    light_sleep_minutes: int
    rem_sleep_minutes: int = 0
    awake_minutes: int = 0
    sleep_score: Optional[int] = Field(default=None, description="睡眠质量分 (0-100)")
    resting_heart_rate: Optional[int] = Field(default=None, description="睡眠期间静息心率")
    sleep_onset_latency: Optional[int] = Field(default=None, description="入睡时间（分钟）")
    wake_count: int = Field(default=0, description="醒来次数")
    wake_minutes: int = Field(default=0, description="清醒时长（分钟）")
    total_bed_time: Optional[int] = Field(default=None, description="总卧床时间（分钟）")
    out_of_bed_time: Optional[int] = Field(default=None, description="离床时间（分钟）")
    interruption_score: Optional[int] = Field(default=None, description="中断评分")
    phases: list[SleepPhase] = Field(default_factory=list)


class HeartRateData(BaseModel):
    """心率数据。"""

    timestamp: datetime
    bpm: int
    activity_type: Optional[str] = None


class ActivitySummary(BaseModel):
    """活动摘要。"""

    start: datetime
    end: datetime
    mode: int = Field(description="活动模式代码")
    mode_name: str = Field(description="活动模式名称")
    steps: int = 0
    distance: int = 0
    calories: int = 0


class ActivityData(BaseModel):
    """每日活动数据（包含步数、睡眠、心率）。"""

    date: str
    steps: Optional[StepData] = None
    sleep: Optional[SleepData] = None
    heart_rates: list[HeartRateData] = Field(default_factory=list)
    activities: list[ActivitySummary] = Field(default_factory=list)


class StressReading(BaseModel):
    """单次压力读数。"""

    timestamp: datetime
    value: int = Field(description="压力值 (0-100)")


class StressData(BaseModel):
    """每日压力数据。"""

    date: str
    min_stress: int = 0
    max_stress: int = 0
    avg_stress: int = 0
    relax_proportion: int = Field(default=0, description="放松状态占比 (%)")
    normal_proportion: int = Field(default=0, description="正常状态占比 (%)")
    medium_proportion: int = Field(default=0, description="中等压力占比 (%)")
    high_proportion: int = Field(default=0, description="高压力占比 (%)")
    readings: list[StressReading] = Field(default_factory=list)


class SpO2Reading(BaseModel):
    """单次血氧读数。"""

    timestamp: datetime
    spo2: int = Field(description="血氧百分比 (0-100)")
    reading_type: str = Field(default="auto", description="auto 或 manual")


class OSAEvent(BaseModel):
    """睡眠呼吸暂停事件。"""

    timestamp: datetime
    spo2_decrease: Optional[int] = Field(default=None, description="最低血氧值")
    spo2_samples: list[int] = Field(default_factory=list)
    hr_samples: list[int] = Field(default_factory=list)


class SpO2Data(BaseModel):
    """每日血氧数据。"""

    date: str
    odi: Optional[float] = Field(default=None, description="氧减指数")
    odi_count: int = Field(default=0, description="氧减事件次数")
    sleep_score: Optional[int] = Field(default=None, description="睡眠呼吸评分")
    readings: list[SpO2Reading] = Field(default_factory=list)
    osa_events: list[OSAEvent] = Field(default_factory=list)


class PAIData(BaseModel):
    """PAI（个人活动智能）数据。"""

    date: str
    total_pai: float = Field(default=0, description="7天滚动 PAI 分")
    daily_pai: float = Field(default=0, description="当日 PAI 分")
    resting_hr: Optional[int] = None
    max_hr: Optional[int] = None
    low_zone_minutes: int = 0
    medium_zone_minutes: int = 0
    high_zone_minutes: int = 0


class HeartRateZone(BaseModel):
    """心率区间。"""

    zone: int = Field(description="区间编号 (1-6)")
    zone_name: str
    seconds: int = Field(description="该区间停留时间（秒）")
    max_hr: int


# 运动类型代码映射
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
    """运动记录。"""

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
    avg_pace: Optional[float] = Field(default=None, description="配速 (min/km)")
    total_steps: int = 0
    training_effect: Optional[float] = Field(default=None, description="有氧训练效果 (1-5)")
    anaerobic_te: Optional[float] = Field(default=None, description="无氧训练效果 (1-5)")
    vo2_max: Optional[int] = None
    exercise_load: Optional[int] = Field(default=None, description="运动负荷")
    avg_cadence: Optional[int] = None
    hr_zones: list[HeartRateZone] = Field(default_factory=list)


class ReadinessData(BaseModel):
    """每日准备度/恢复数据（含 HRV 和体温）。"""

    date: str
    readiness_score: Optional[int] = Field(default=None, description="综合准备度分 (0-100)")
    readiness_insight: Optional[int] = None
    rhr_score: Optional[int] = Field(default=None, description="静息心率评分 (0-100)")
    rhr_baseline: Optional[int] = Field(default=None, description="个人 RHR 基线 (bpm)")
    sleep_rhr: Optional[int] = Field(default=None, description="睡眠期间 RHR (bpm)")
    hrv_score: Optional[int] = Field(default=None, description="HRV 评分 (0-100)")
    hrv_baseline: Optional[int] = Field(default=None, description="个人 HRV 基线 (ms)")
    sleep_hrv: Optional[int] = Field(default=None, description="睡眠期间 HRV (ms)")
    skin_temp_score: Optional[int] = Field(default=None, description="体温评分 (0-100)")
    skin_temp_baseline: Optional[float] = None
    skin_temp_calibrated: Optional[float] = None
    mental_score: Optional[int] = Field(default=None, description="心理状态评分 (0-100)")
    mental_baseline: Optional[int] = None
    physical_score: Optional[int] = Field(default=None, description="身体状态评分 (0-100)")
    physical_baseline: Optional[int] = None
    ahi_score: Optional[int] = Field(default=None, description="呼吸暂停评分")
    ahi_baseline: Optional[float] = None
    afib_score: Optional[int] = Field(default=None, description="房颤评分")
    afib_baseline: Optional[int] = None


class DaySummary(BaseModel):
    """每日汇总。"""

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
# 新增数据模型（来自 zepp-health-cli 的额外端点）
# ============================================================


class VO2MaxRecord(BaseModel):
    """最大摄氧量记录。"""

    date: str
    vo2_max: int = Field(description="VO2 max (ml/kg/min)")
    device_id: Optional[str] = None


class WeightRecord(BaseModel):
    """体重记录。"""

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
    """血压记录。"""

    timestamp: datetime
    systolic: int = Field(description="收缩压 (mmHg)")
    diastolic: int = Field(description="舒张压 (mmHg)")
    pulse: Optional[int] = None
    source: Optional[str] = None


class BodyBatteryReading(BaseModel):
    """身体电量读数。"""

    timestamp: datetime
    value: int = Field(description="身体电量 (0-100)")


class HRVReading(BaseModel):
    """HRV 读数。"""

    timestamp: datetime
    hrv_value: int = Field(description="HRV 值 (ms)")
    reading_type: str = Field(default="sdnn", description="sdnn 或 rmssd")


class RespiratoryRateReading(BaseModel):
    """呼吸频率读数。"""

    timestamp: datetime
    breaths_per_minute: float


class SportLoadRecord(BaseModel):
    """运动负荷记录。"""

    date: str
    wtl_sum: Optional[float] = Field(default=None, description="每日训练负荷总和")
    current_day_train_load: Optional[float] = None


# ============================================================
# 分析输出模型
# ============================================================


class RecoveryScore(BaseModel):
    """恢复评分。"""

    score: int = Field(description="恢复分 (0-100)")
    hrv_component: Optional[int] = Field(default=None, description="HRV 分项分")
    rhr_component: Optional[int] = Field(default=None, description="RHR 分项分")
    trend: str = Field(default="stable", description="趋势: improving/declining/stable")
    fatigue_signal: bool = Field(default=False, description="是否检测到疲劳信号")
    details: str = ""


class SleepQualityScore(BaseModel):
    """睡眠质量评分。"""

    score: int = Field(description="睡眠质量分 (0-100)")
    deep_sleep_pct: Optional[float] = Field(default=None, description="深睡占比 (%)")
    rem_sleep_pct: Optional[float] = Field(default=None, description="REM 占比 (%)")
    efficiency_pct: Optional[float] = Field(default=None, description="睡眠效率 (%)")
    duration_minutes: Optional[int] = None
    details: str = ""


class ExertionScore(BaseModel):
    """训练负荷评分。"""

    score: int = Field(description="训练负荷分 (0-100)")
    acute_load_7d: float = Field(default=0, description="7天急性负荷")
    chronic_load_28d: float = Field(default=0, description="28天慢性负荷")
    ratio: float = Field(default=0, description="急性/慢性比率")
    zone: str = Field(default="inactive", description="负荷区间")
    details: str = ""


class HealthReport(BaseModel):
    """完整健康报告。"""

    date: str
    generated_at: datetime
    overall_score: Optional[int] = Field(default=None, description="综合健康分 (0-100)")
    recovery: Optional[RecoveryScore] = None
    sleep_quality: Optional[SleepQualityScore] = None
    exertion: Optional[ExertionScore] = None
    raw_metrics: dict = Field(default_factory=dict, description="原始指标数据")
    recommendations: list[str] = Field(default_factory=list, description="健康建议")
