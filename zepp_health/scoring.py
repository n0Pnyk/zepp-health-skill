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
    HeartRateZone,
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


def get_personalized_max_hr(
    workouts: list[Workout],
    default_age: int = 30,
) -> int:
    """Derive personalized max heart rate from recent workout data.

    Priority:
    1. Actual max HR observed in 28-day workouts
    2. Max HR from HR zone data
    3. Fallback: 220 - age (Fox formula)
    """
    max_hr_values: list[int] = []

    for w in workouts:
        if w.max_heart_rate and w.max_heart_rate > 0:
            max_hr_values.append(w.max_heart_rate)
        if w.hr_zones:
            for z in w.hr_zones:
                if z.max_hr and z.max_hr > 0:
                    max_hr_values.append(z.max_hr)

    if max_hr_values:
        return max(max_hr_values)

    return 220 - default_age


def compute_hr_threshold(
    max_hr: int,
    resting_hr: int,
) -> int:
    """Compute personalized HR threshold for exertion tracking.

    Threshold = RHR + HRR * 0.45 (Karvonen formula at ~45% intensity).
    Athlytic uses a similar approach with personalized thresholds.
    """
    hrr = max_hr - resting_hr
    return int(resting_hr + hrr * 0.45)


def compute_time_above_threshold(
    workouts_7d: list[Workout],
    hr_threshold: int,
) -> float:
    """Compute total minutes spent above HR threshold in 7-day workouts.

    Uses HR zone data when available, falls back to duration-based estimate.
    """
    total_minutes = 0.0

    for w in workouts_7d:
        if not w.duration_seconds or w.duration_seconds <= 0:
            continue

        if w.hr_zones:
            # Sum time in zones where max_hr >= threshold
            above_seconds = sum(
                z.seconds for z in w.hr_zones
                if z.max_hr and z.max_hr >= hr_threshold
            )
            total_minutes += above_seconds / 60
        elif w.avg_heart_rate and w.avg_heart_rate >= hr_threshold:
            # Fallback: if avg HR is above threshold, count full duration
            total_minutes += w.duration_seconds / 60

    return total_minutes


# ============================================================
# Recovery Score
# ============================================================


def compute_recovery(
    today_hrv: Optional[int],
    today_rhr: Optional[int],
    hrv_history: list[int],
    rhr_history: list[int],
    readiness: Optional[ReadinessData] = None,
    hrv_avg_7d: Optional[int] = None,
    rhr_avg_7d: Optional[int] = None,
) -> RecoveryScore:
    """Compute recovery score (0-100).

    Based on comparison of HRV and RHR against 60-day rolling baseline.
    Uses 7-day average vs 60-day baseline (more robust than single-day).
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

    # Use 7-day average for comparison (more robust than single-day)
    compare_hrv = float(hrv_avg_7d) if hrv_avg_7d and hrv_avg_7d > 0 else (float(today_hrv) if today_hrv and today_hrv > 0 else None)
    compare_rhr = float(rhr_avg_7d) if rhr_avg_7d and rhr_avg_7d > 0 else (float(today_rhr) if today_rhr and today_rhr > 0 else None)

    # Compute individual components
    hrv_component: Optional[int] = None
    rhr_component: Optional[int] = None

    if compare_hrv and hrv_mean > 0:
        hrv_component = _z_score_to_100(compare_hrv, hrv_mean, hrv_std)
    elif readiness and readiness.hrv_score is not None:
        hrv_component = readiness.hrv_score

    if compare_rhr and rhr_mean > 0:
        rhr_component = _z_score_to_100(compare_rhr, rhr_mean, rhr_std, invert=True)
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
        hrv_avg_7d=hrv_avg_7d,
        rhr_avg_7d=rhr_avg_7d,
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
    sleep_times: Optional[list[tuple[int, int]]] = None,
) -> Optional[SleepQualityScore]:
    """Compute sleep quality score (0-100).

    Dimensions and weights:
    - Duration (0.20): Target 7-9 hours
    - Deep sleep ratio (0.20): Target 15-20%
    - REM ratio (0.15): Target 20-25%
    - Sleep efficiency (0.12): Target >= 85%
    - Interruption penalty (0.12): Based on wake count and awake duration
    - Onset latency (0.11): 10-20 min normal, >30 min penalty
    - Schedule consistency (0.10): Std dev of sleep/wake times
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
        awake_ratio = (sleep.wake_minutes / (total + sleep.wake_minutes)) if (total + sleep.wake_minutes) > 0 else 0
        efficiency_score = _clamp((1 - awake_ratio) * 100 / 0.85)

    # 5. Interruption penalty
    wake_penalty = sleep.wake_count * 12 + sleep.wake_minutes * 1.5
    interruption_score = _clamp(100 - wake_penalty)

    # 6. Sleep onset latency score (clinical: 10-20 min normal, >30 min = insomnia)
    sol = sleep.sleep_onset_latency
    if sol is not None and sol >= 0:
        if sol <= 20:
            sol_score = 100  # Optimal range
        elif sol <= 30:
            sol_score = _clamp(100 - (sol - 20) * 3)  # Gradual penalty
        else:
            sol_score = _clamp(70 - (sol - 30) * 2)  # Steeper penalty above 30 min
    else:
        sol_score = 75  # Unknown: assume average
        sol = None

    # 7. Sleep schedule consistency (std dev of sleep/wake times across days)
    consistency_score: Optional[int] = None
    if sleep_times and len(sleep_times) >= 3:
        import math

        # Extract sleep start minutes (0-1440, normalize midnight crossings)
        sleep_starts = [s for s, _ in sleep_times]
        wake_ends = [w for _, w in sleep_times]

        def _circ_std(minutes_list: list[int]) -> float:
            """Circular standard deviation for time-of-day in minutes."""
            # Convert to radians on a 24h circle
            radians = [m / 1440 * 2 * math.pi for m in minutes_list]
            sin_sum = sum(math.sin(r) for r in radians)
            cos_sum = sum(math.cos(r) for r in radians)
            n = len(radians)
            r = math.sqrt(sin_sum**2 + cos_sum**2) / n
            # Circular standard deviation
            return math.sqrt(-2 * math.log(r)) * 1440 / (2 * math.pi) if r > 0 else 360

        sleep_std = _circ_std(sleep_starts)
        wake_std = _circ_std(wake_ends)
        avg_std = (sleep_std + wake_std) / 2

        # Map to score: 0 std = 100, 60 min std = 50, 120+ min std = 0
        consistency_score = int(_clamp(100 - avg_std * (100 / 120)))

    # Weighted combination (updated weights)
    score = int(_clamp(
        0.20 * duration_score +
        0.20 * deep_score +
        0.15 * rem_score +
        0.12 * efficiency_score +
        0.12 * interruption_score +
        0.11 * sol_score +
        0.10 * (consistency_score if consistency_score is not None else 75)
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
    if sol is not None:
        if sol <= 20:
            details_parts.append(f"Sleep onset {sol}min (normal)")
        elif sol <= 30:
            details_parts.append(f"Sleep onset {sol}min (slightly slow)")
        else:
            details_parts.append(f"Sleep onset {sol}min (slow, >30min may indicate insomnia)")
    if consistency_score is not None:
        details_parts.append(f"Schedule consistency {consistency_score}/100")

    return SleepQualityScore(
        score=score,
        deep_sleep_pct=round(deep_pct, 1),
        rem_sleep_pct=round(rem_pct, 1),
        efficiency_pct=round(efficiency_score, 1),
        duration_minutes=total,
        onset_latency_minutes=sol,
        consistency_score=consistency_score,
        details="; ".join(details_parts),
    )


# ============================================================
# Exertion Score
# ============================================================


def compute_exertion(
    workouts_7d: list[Workout],
    workouts_28d: list[Workout],
    sport_load: Optional[list[SportLoadRecord]] = None,
    resting_hr: int = 60,
    max_hr: int = 190,
) -> ExertionScore:
    """Compute training load score (0-100).

    Uses Heart Rate Reserve (HRR) method instead of ACWR.
    Threshold = RHR + HRR * 0.45 (Karvonen formula).
    Score based on weekly minutes above threshold vs recommended range.

    Reference: Athlytic exertion model, Karvonen formula.
    ACWR has been widely criticized (Impellizzeri 2019, Wang 2020).
    """
    hr_threshold = compute_hr_threshold(max_hr, resting_hr)
    minutes_above = compute_time_above_threshold(workouts_7d, hr_threshold)

    # Target zone: 150-300 min/week of moderate-to-vigorous activity
    # (WHO guidelines: 150-300 min moderate or 75-150 min vigorous)
    target_low = 150.0
    target_high = 300.0

    # Zone classification based on weekly minutes above threshold
    if minutes_above <= 0:
        zone = "inactive"
        score = 0
    elif minutes_above < target_low * 0.5:
        zone = "detraining"
        score = int(_clamp(minutes_above / (target_low * 0.5) * 30))
    elif minutes_above < target_low:
        zone = "low"
        score = int(_clamp(30 + (minutes_above - target_low * 0.5) / (target_low * 0.5) * 20))
    elif minutes_above <= target_high:
        zone = "productive"
        score = int(_clamp(50 + (minutes_above - target_low) / (target_high - target_low) * 30))
    elif minutes_above <= target_high * 1.5:
        zone = "overreaching"
        score = int(_clamp(80 + (minutes_above - target_high) / (target_high * 0.5) * 15))
    else:
        zone = "high_risk"
        score = int(_clamp(95 + min((minutes_above - target_high * 1.5) / target_high * 5, 5)))

    # Adaptive target zone based on recovery (inverted: lower recovery → lower target)
    # This is a simplified version of Athlytic's Target Exertion Zone
    target_low_adj = int(target_low * 0.5)  # Conservative default
    target_high_adj = int(target_high * 1.0)

    zone_desc = {
        "inactive": "No workout data",
        "detraining": "Undertrained, consider increasing exercise volume",
        "low": "Below recommended range, room to increase",
        "productive": "Effective training volume, in the WHO recommended range",
        "overreaching": "Above recommended range, ensure adequate recovery",
        "high_risk": "Significantly overtrained, schedule rest days",
    }

    details = (
        f"HR threshold {hr_threshold}bpm, "
        f"{minutes_above:.0f} min/week above threshold "
        f"(target {target_low:.0f}-{target_high:.0f} min)"
    )
    if zone in zone_desc:
        details += f" — {zone_desc[zone]}"

    return ExertionScore(
        score=score,
        max_hr_28d=max_hr,
        hr_threshold=hr_threshold,
        minutes_above_threshold=round(minutes_above, 1),
        target_zone_low=target_low_adj,
        target_zone_high=target_high_adj,
        zone=zone,
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
        if sleep_quality.onset_latency_minutes is not None and sleep_quality.onset_latency_minutes > 30:
            recommendations.append("Sleep onset latency >30 minutes may indicate insomnia. Consider CBT-I techniques, limit screen time, and maintain a consistent bedtime.")
        if sleep_quality.consistency_score is not None and sleep_quality.consistency_score < 50:
            recommendations.append("Sleep schedule is irregular. Try to go to bed and wake up at consistent times, even on weekends.")

    # Training load recommendations
    if exertion and exertion.zone != "inactive":
        if exertion.zone == "high_risk":
            recommendations.append("Training load is too high, risk of overtraining! Schedule 2-3 days of active recovery immediately.")
        elif exertion.zone == "overreaching":
            recommendations.append("Training load is on the high side. Consider reducing training volume and increasing recovery time.")
        elif exertion.zone == "detraining":
            recommendations.append("Recent training volume is low. If your goal is to improve fitness, gradually increase exercise volume.")
        elif exertion.zone == "low":
            recommendations.append("Training volume is below WHO recommended range (150-300 min/week). Consider adding more activity.")
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
