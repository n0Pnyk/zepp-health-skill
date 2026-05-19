"""Health scoring algorithm.

Referencing the Athlytic app scoring logic:
- Recovery: Based on HRV/RHR 60-day rolling baseline comparison
- Sleep Quality: Multi-dimensional sleep quality assessment
- Exertion: Acute/chronic training load ratio
- Overall: Weighted composite health score
"""

from __future__ import annotations

import math
from typing import Optional

from zepp_health.models import (
    ExertionScore,
    HealthReport,
    ReadinessData,
    RecoveryScore,
    SleepData,
    SleepQualityScore,
    SportLoadRecord,
    Workout,
)


def _clamp(value: float, lo: float = 0, hi: float = 100) -> float:
    """Clamp value to the [lo, hi] range."""
    return max(lo, min(hi, value))


def compute_baseline(
    values: list[float],
    window: int = 60,
) -> tuple[float, float]:
    """Compute rolling baseline (mean and standard deviation).

    Returns (mean, std). If insufficient data, std may be 0.
    """
    recent = values[-window:]
    if not recent:
        return 0.0, 0.0
    mean = sum(recent) / len(recent)
    if len(recent) < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in recent) / len(recent)
    std = math.sqrt(variance)
    return mean, std


def _z_score_to_100(value: float, mean: float, std: float, invert: bool = False) -> int:
    """Map z-score to a 0-100 score.

    invert=True reverses direction (lower is better, e.g. RHR).
    Based on z-score from 60-day rolling baseline, linearly mapped to 0-100.
    """
    if std == 0:
        return 50
    if invert:
        z = (mean - value) / std
    else:
        z = (value - mean) / std
    z = _clamp(z, -3, 3)
    score = 50 + (z / 3) * 50
    return int(_clamp(score))


def _detect_fatigue(
    hrv_history: list[float],
    rhr_history: list[float],
    hrv_baseline: float,
    rhr_baseline: float,
    consecutive_days: int = 3,
) -> bool:
    """Detect fatigue signals.

    Returns True if HRV is below baseline for N consecutive days
    and RHR is above baseline for N consecutive days.
    """
    if len(hrv_history) < consecutive_days or len(rhr_history) < consecutive_days:
        return False

    hrv_below = all(v < hrv_baseline for v in hrv_history[-consecutive_days:])
    rhr_above = all(v > rhr_baseline for v in rhr_history[-consecutive_days:])

    return hrv_below and rhr_above


def _compute_trend(values: list[float], window: int = 7) -> str:
    """Compute trend based on 7-day linear regression slope.

    Returns "improving", "declining", or "stable".
    """
    recent = values[-window:]
    if len(recent) < 3:
        return "stable"

    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n

    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(recent))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "stable"

    slope = numerator / denominator

    # Dynamically adjust threshold based on data range
    data_range = max(recent) - min(recent) if recent else 1
    threshold = data_range * 0.05 if data_range > 0 else 0.5

    if slope > threshold:
        return "improving"
    elif slope < -threshold:
        return "declining"
    return "stable"


# ============================================================
# Recovery Score
# ============================================================


def compute_recovery(
    today_hrv: Optional[int],
    today_rhr: Optional[int],
    hrv_history: list[int],
    rhr_history: list[int],
    readiness: Optional[ReadinessData] = None,
) -> RecoveryScore:
    """Compute recovery score (0-100).

    Based on comparison of HRV and RHR against 60-day rolling baseline.
    HRV weight: 0.6, RHR weight: 0.4.

    If insufficient history data, falls back to Zepp's built-in readiness_score.
    """
    # Try computing baseline from historical data
    hrv_floats = [float(v) for v in hrv_history if v > 0]
    rhr_floats = [float(v) for v in rhr_history if v > 0]

    hrv_mean, hrv_std = compute_baseline(hrv_floats)
    rhr_mean, rhr_std = compute_baseline(rhr_floats)

    # If Zepp built-in baseline is available and history is insufficient, use it
    if readiness:
        if hrv_std == 0 and readiness.hrv_baseline:
            hrv_mean = float(readiness.hrv_baseline)
            hrv_std = hrv_mean * 0.15  # Estimate standard deviation
        if rhr_std == 0 and readiness.rhr_baseline:
            rhr_mean = float(readiness.rhr_baseline)
            rhr_std = rhr_mean * 0.08

    # Compute individual components
    hrv_component: Optional[int] = None
    rhr_component: Optional[int] = None

    if today_hrv and today_hrv > 0 and hrv_mean > 0:
        hrv_component = _z_score_to_100(float(today_hrv), hrv_mean, hrv_std)
    elif readiness and readiness.hrv_score is not None:
        hrv_component = readiness.hrv_score

    if today_rhr and today_rhr > 0 and rhr_mean > 0:
        rhr_component = _z_score_to_100(float(today_rhr), rhr_mean, rhr_std, invert=True)
    elif readiness and readiness.rhr_score is not None:
        rhr_component = readiness.rhr_score

    # Weighted combination
    if hrv_component is not None and rhr_component is not None:
        score = int(_clamp(0.6 * hrv_component + 0.4 * rhr_component))
    elif hrv_component is not None:
        score = hrv_component
    elif rhr_component is not None:
        score = rhr_component
    elif readiness and readiness.readiness_score is not None:
        # Fully fall back to Zepp built-in score
        score = readiness.readiness_score
    else:
        score = 0

    # Fatigue detection
    fatigue = _detect_fatigue(hrv_floats, rhr_floats, hrv_mean, rhr_mean)

    # Trend computation
    trend = _compute_trend(hrv_floats) if len(hrv_floats) >= 3 else "stable"

    # Generate description
    details_parts = []
    if today_hrv and hrv_mean > 0:
        diff_pct = (today_hrv - hrv_mean) / hrv_mean * 100
        direction = "above" if diff_pct > 0 else "below"
        details_parts.append(f"HRV {today_hrv}ms ({direction} baseline by {abs(diff_pct):.0f}%)")
    if today_rhr and rhr_mean > 0:
        diff = today_rhr - rhr_mean
        direction = "above" if diff > 0 else "below"
        details_parts.append(f"RHR {today_rhr}bpm ({direction} baseline by {abs(diff):.0f}bpm)")
    if fatigue:
        details_parts.append("Fatigue signal detected: HRV consistently low and RHR consistently high")

    return RecoveryScore(
        score=score,
        hrv_component=hrv_component,
        rhr_component=rhr_component,
        trend=trend,
        fatigue_signal=fatigue,
        details="; ".join(details_parts) if details_parts else "Insufficient data, using device built-in score",
    )


# ============================================================
# Sleep Quality Score
# ============================================================


def compute_sleep_quality(
    sleep: Optional[SleepData],
    age: int = 30,
) -> Optional[SleepQualityScore]:
    """Compute sleep quality score (0-100).

    Dimensions and weights:
    - Duration (0.25): Target 7-9 hours
    - Deep sleep ratio (0.25): Target 15-20%
    - REM ratio (0.20): Target 20-25%
    - Sleep efficiency (0.15): Target >= 85%
    - Interruption penalty (0.15): Based on wake count and awake duration
    """
    if not sleep or sleep.total_minutes == 0:
        return None

    total = sleep.total_minutes

    # 1. Duration score
    if age < 18:
        target_min, target_max = 480, 600  # 8-10 hours
    elif age < 65:
        target_min, target_max = 420, 540  # 7-9 hours
    else:
        target_min, target_max = 390, 510  # 6.5-8.5 hours

    if total < target_min:
        duration_score = _clamp((total / target_min) * 100)
    elif total > target_max:
        # Oversleeping also incurs a penalty
        over = total - target_max
        duration_score = _clamp(100 - over * 0.5)
    else:
        duration_score = 100

    # 2. Deep sleep ratio score
    deep_pct = (sleep.deep_sleep_minutes / total * 100) if total > 0 else 0
    deep_score = _clamp(deep_pct / 17.5 * 100)  # Target 17.5%

    # 3. REM ratio score
    rem_pct = (sleep.rem_sleep_minutes / total * 100) if total > 0 else 0
    rem_score = _clamp(rem_pct / 22.5 * 100)  # Target 22.5%

    # 4. Sleep efficiency
    if sleep.total_bed_time and sleep.total_bed_time > 0:
        efficiency = (total / sleep.total_bed_time) * 100
        efficiency_score = _clamp(efficiency / 85 * 100)
    else:
        # When no time-in-bed data is available, estimate from awake duration
        awake_ratio = (sleep.wake_minutes / (total + sleep.wake_minutes)) if (total + sleep.wake_minutes) > 0 else 0
        efficiency_score = _clamp((1 - awake_ratio) * 100 / 0.85)

    # 5. Interruption penalty
    wake_penalty = sleep.wake_count * 12 + sleep.wake_minutes * 1.5
    interruption_score = _clamp(100 - wake_penalty)

    # Weighted combination
    score = int(_clamp(
        0.25 * duration_score +
        0.25 * deep_score +
        0.20 * rem_score +
        0.15 * efficiency_score +
        0.15 * interruption_score
    ))

    # Generate description
    details_parts = []
    hours = total // 60
    mins = total % 60
    details_parts.append(f"Total duration {hours}h{mins}m")

    if deep_pct > 0:
        details_parts.append(f"Deep sleep {deep_pct:.0f}%{' (on target)' if 15 <= deep_pct <= 20 else ' (below target)'}")
    if rem_pct > 0:
        details_parts.append(f"REM {rem_pct:.0f}%{' (on target)' if 20 <= rem_pct <= 25 else ' (below target)'}")
    if sleep.wake_count > 0:
        details_parts.append(f"Woke up {sleep.wake_count} time(s)")

    return SleepQualityScore(
        score=score,
        deep_sleep_pct=round(deep_pct, 1),
        rem_sleep_pct=round(rem_pct, 1),
        efficiency_pct=round(efficiency_score, 1),
        duration_minutes=total,
        details="; ".join(details_parts),
    )


# ============================================================
# Exertion Score
# ============================================================


def compute_exertion(
    workouts_7d: list[Workout],
    workouts_28d: list[Workout],
    sport_load: Optional[list[SportLoadRecord]] = None,
) -> ExertionScore:
    """Compute training load score (0-100).

    Based on acute (7-day) / chronic (28-day) training load ratio.
    """
    # Compute acute load (7 days)
    acute_load = 0.0
    for w in workouts_7d:
        if w.exercise_load and w.exercise_load > 0:
            acute_load += w.exercise_load
        elif w.duration_seconds > 0 and w.avg_heart_rate:
            # Estimate load: duration (minutes) * heart rate intensity
            duration_min = w.duration_seconds / 60
            hr_intensity = w.avg_heart_rate / 190  # Assume max HR of 190
            acute_load += duration_min * hr_intensity * 10

    # If no workout data, try using sport_load
    if acute_load == 0 and sport_load:
        for sl in sport_load[-7:]:
            if sl.wtl_sum:
                acute_load += sl.wtl_sum

    # Compute chronic load (28-day weekly average)
    chronic_weekly = 0.0
    if workouts_28d:
        total_load = 0.0
        for w in workouts_28d:
            if w.exercise_load and w.exercise_load > 0:
                total_load += w.exercise_load
            elif w.duration_seconds > 0 and w.avg_heart_rate:
                duration_min = w.duration_seconds / 60
                hr_intensity = w.avg_heart_rate / 190
                total_load += duration_min * hr_intensity * 10
        chronic_weekly = total_load / 4  # 4-week average
    elif sport_load and len(sport_load) >= 7:
        total = sum(sl.wtl_sum or 0 for sl in sport_load[-28:])
        chronic_weekly = total / 4

    # Compute ratio
    if chronic_weekly > 0:
        ratio = acute_load / chronic_weekly
    else:
        ratio = 0

    # Zone mapping
    if ratio < 0.8:
        zone = "detraining"
        score = int(_clamp(ratio / 0.8 * 40))
    elif ratio < 1.0:
        zone = "maintaining"
        score = int(_clamp(40 + (ratio - 0.8) / 0.2 * 20))
    elif ratio < 1.3:
        zone = "productive"
        score = int(_clamp(60 + (ratio - 1.0) / 0.3 * 20))
    elif ratio < 1.5:
        zone = "overreaching"
        score = int(_clamp(80 + (ratio - 1.3) / 0.2 * 10))
    else:
        zone = "high_risk"
        score = int(_clamp(90 + min((ratio - 1.5) / 0.5 * 10, 10)))

    # Generate description
    zone_desc = {
        "detraining": "Undertrained, consider increasing exercise volume",
        "maintaining": "Maintaining, moderate training volume",
        "productive": "Effective improvement, good training response",
        "overreaching": "Load is high, pay attention to recovery",
        "high_risk": "Risk of overtraining, consider rest days",
        "inactive": "No workout data",
    }

    details = f"7-day load {acute_load:.0f}, 28-day weekly avg {chronic_weekly:.0f}, ratio {ratio:.2f}"
    if zone in zone_desc:
        details += f" ({zone_desc[zone]})"

    return ExertionScore(
        score=score if acute_load > 0 else 0,
        acute_load_7d=round(acute_load, 1),
        chronic_load_28d=round(chronic_weekly, 1),
        ratio=round(ratio, 2),
        zone=zone if acute_load > 0 else "inactive",
        details=details,
    )


# ============================================================
# Overall Score
# ============================================================


def compute_overall(
    recovery: Optional[RecoveryScore],
    sleep_quality: Optional[SleepQualityScore],
    exertion: Optional[ExertionScore],
    avg_stress: Optional[int] = None,
    avg_spo2: Optional[int] = None,
) -> Optional[int]:
    """Compute overall health score (0-100).

    Weights:
    - Recovery: 0.35
    - Sleep Quality: 0.30
    - Exertion: 0.15
    - Stress (inverted): 0.10
    - SpO2: 0.10
    """
    components: list[tuple[float, float]] = []  # (weight, score)

    if recovery:
        components.append((0.35, recovery.score))
    if sleep_quality:
        components.append((0.30, sleep_quality.score))
    if exertion and exertion.zone != "inactive":
        components.append((0.15, exertion.score))
    if avg_stress is not None:
        # Invert stress: lower stress = higher score
        stress_score = int(_clamp(100 - avg_stress))
        components.append((0.10, stress_score))
    if avg_spo2 is not None:
        # Normalize SpO2: 90% -> 0, 100% -> 100
        spo2_score = int(_clamp((avg_spo2 - 90) / 10 * 100))
        components.append((0.10, spo2_score))

    if not components:
        return None

    # Redistribute weights proportionally
    total_weight = sum(w for w, _ in components)
    if total_weight == 0:
        return None

    score = sum(w / total_weight * s for w, s in components)
    return int(_clamp(score))


# ============================================================
# Recommendation Generation
# ============================================================


def generate_recommendations(
    recovery: Optional[RecoveryScore],
    sleep_quality: Optional[SleepQualityScore],
    exertion: Optional[ExertionScore],
    avg_stress: Optional[int] = None,
    avg_spo2: Optional[int] = None,
) -> list[str]:
    """Generate health recommendations based on individual scores."""
    recommendations: list[str] = []

    # Recovery recommendations
    if recovery:
        if recovery.fatigue_signal:
            recommendations.append("Persistent fatigue signal detected (low HRV + high RHR). Consider scheduling rest days and ensuring adequate sleep.")
        elif recovery.score < 40:
            recommendations.append("Recovery level is low. Your body may not have fully recovered from previous training. Consider reducing today's exercise intensity.")
        elif recovery.score >= 75:
            recommendations.append("Recovery status is good. Suitable for moderate to high intensity training.")
        if recovery.trend == "declining":
            recommendations.append("HRV shows a declining trend. Check your sleep quality and life stress levels.")

    # Sleep recommendations
    if sleep_quality:
        if sleep_quality.score < 60:
            recommendations.append("Sleep quality is poor. Consider improving sleep habits: maintain a consistent schedule, reduce screen time before bed.")
        if sleep_quality.deep_sleep_pct is not None and sleep_quality.deep_sleep_pct < 15:
            recommendations.append("Deep sleep ratio is low. Avoid alcohol and caffeine before bed, keep the bedroom cool.")
        if sleep_quality.rem_sleep_pct is not None and sleep_quality.rem_sleep_pct < 18:
            recommendations.append("REM sleep is insufficient, which may affect memory and emotional regulation. Maintain a regular sleep schedule.")
        if sleep_quality.duration_minutes and sleep_quality.duration_minutes < 360:
            recommendations.append("Sleep duration is under 6 hours. Chronic sleep deprivation affects health and athletic performance.")

    # Training load recommendations
    if exertion and exertion.zone != "inactive":
        if exertion.zone == "high_risk":
            recommendations.append("Training load is too high, risk of overtraining! Schedule 2-3 days of active recovery immediately.")
        elif exertion.zone == "overreaching":
            recommendations.append("Training load is on the high side. Consider reducing training volume and increasing recovery time.")
        elif exertion.zone == "detraining":
            recommendations.append("Recent training volume is low. If your goal is to improve fitness, gradually increase exercise volume.")
        elif exertion.zone == "productive":
            recommendations.append("Training load is in the effective improvement zone. Maintain your current pace.")

    # Stress recommendations
    if avg_stress is not None:
        if avg_stress > 60:
            recommendations.append("Stress level is high. Consider relaxation activities: deep breathing, meditation, or a light walk.")
        elif avg_stress > 40:
            recommendations.append("Stress is moderate. Take appropriate breaks and relaxation.")

    # SpO2 recommendations
    if avg_spo2 is not None:
        if avg_spo2 < 93:
            recommendations.append("Blood oxygen saturation is low (<93%). Pay attention to respiratory health and seek medical attention if necessary.")
        elif avg_spo2 < 95:
            recommendations.append("Blood oxygen saturation is slightly below normal range. Check for snoring or breathing difficulties.")

    if not recommendations:
        recommendations.append("All indicators are normal. Maintain your current lifestyle.")

    return recommendations
