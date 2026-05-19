"""健康评分算法。

参考 Athlytic app 的评分逻辑：
- Recovery: 基于 HRV/RHR 的 60 天滚动基线对比
- Sleep Quality: 多维度睡眠质量评估
- Exertion: 急性/慢性训练负荷比率
- Overall: 加权综合健康分
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
    """将值限制在 [lo, hi] 范围内。"""
    return max(lo, min(hi, value))


def compute_baseline(
    values: list[float],
    window: int = 60,
) -> tuple[float, float]:
    """计算滚动基线（均值和标准差）。

    返回 (mean, std)。如果数据不足，std 可能为 0。
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
    """将 z-score 映射到 0-100 分。

    invert=True 时反转方向（值越低越好，如 RHR）。
    基于 60 天滚动基线的 z-score，线性映射到 0-100。
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
    """检测疲劳信号。

    如果 HRV 连续 N 天低于基线且 RHR 连续 N 天高于基线，返回 True。
    """
    if len(hrv_history) < consecutive_days or len(rhr_history) < consecutive_days:
        return False

    hrv_below = all(v < hrv_baseline for v in hrv_history[-consecutive_days:])
    rhr_above = all(v > rhr_baseline for v in rhr_history[-consecutive_days:])

    return hrv_below and rhr_above


def _compute_trend(values: list[float], window: int = 7) -> str:
    """计算趋势（基于 7 天线性回归斜率）。

    返回 "improving"、"declining" 或 "stable"。
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

    # 根据数据范围动态调整阈值
    data_range = max(recent) - min(recent) if recent else 1
    threshold = data_range * 0.05 if data_range > 0 else 0.5

    if slope > threshold:
        return "improving"
    elif slope < -threshold:
        return "declining"
    return "stable"


# ============================================================
# Recovery Score（恢复评分）
# ============================================================


def compute_recovery(
    today_hrv: Optional[int],
    today_rhr: Optional[int],
    hrv_history: list[int],
    rhr_history: list[int],
    readiness: Optional[ReadinessData] = None,
) -> RecoveryScore:
    """计算恢复评分 (0-100)。

    基于 HRV 和 RHR 与 60 天滚动基线的对比。
    HRV 权重 0.6，RHR 权重 0.4。

    如果没有足够的历史数据，使用 Zepp 内置的 readiness_score 作为回退。
    """
    # 尝试从历史数据计算基线
    hrv_floats = [float(v) for v in hrv_history if v > 0]
    rhr_floats = [float(v) for v in rhr_history if v > 0]

    hrv_mean, hrv_std = compute_baseline(hrv_floats)
    rhr_mean, rhr_std = compute_baseline(rhr_floats)

    # 如果有 Zepp 内置基线且历史数据不足，使用内置基线
    if readiness:
        if hrv_std == 0 and readiness.hrv_baseline:
            hrv_mean = float(readiness.hrv_baseline)
            hrv_std = hrv_mean * 0.15  # 估算标准差
        if rhr_std == 0 and readiness.rhr_baseline:
            rhr_mean = float(readiness.rhr_baseline)
            rhr_std = rhr_mean * 0.08

    # 计算各分项
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

    # 加权组合
    if hrv_component is not None and rhr_component is not None:
        score = int(_clamp(0.6 * hrv_component + 0.4 * rhr_component))
    elif hrv_component is not None:
        score = hrv_component
    elif rhr_component is not None:
        score = rhr_component
    elif readiness and readiness.readiness_score is not None:
        # 完全回退到 Zepp 内置评分
        score = readiness.readiness_score
    else:
        score = 0

    # 疲劳检测
    fatigue = _detect_fatigue(hrv_floats, rhr_floats, hrv_mean, rhr_mean)

    # 趋势计算
    trend = _compute_trend(hrv_floats) if len(hrv_floats) >= 3 else "stable"

    # 生成描述
    details_parts = []
    if today_hrv and hrv_mean > 0:
        diff_pct = (today_hrv - hrv_mean) / hrv_mean * 100
        direction = "高于" if diff_pct > 0 else "低于"
        details_parts.append(f"HRV {today_hrv}ms（{direction}基线 {abs(diff_pct):.0f}%）")
    if today_rhr and rhr_mean > 0:
        diff = today_rhr - rhr_mean
        direction = "高于" if diff > 0 else "低于"
        details_parts.append(f"RHR {today_rhr}bpm（{direction}基线 {abs(diff):.0f}bpm）")
    if fatigue:
        details_parts.append("检测到疲劳信号：HRV 持续偏低且 RHR 持续偏高")

    return RecoveryScore(
        score=score,
        hrv_component=hrv_component,
        rhr_component=rhr_component,
        trend=trend,
        fatigue_signal=fatigue,
        details="；".join(details_parts) if details_parts else "数据不足，使用设备内置评分",
    )


# ============================================================
# Sleep Quality Score（睡眠质量评分）
# ============================================================


def compute_sleep_quality(
    sleep: Optional[SleepData],
    age: int = 30,
) -> Optional[SleepQualityScore]:
    """计算睡眠质量评分 (0-100)。

    维度和权重：
    - 时长 (0.25): 目标 7-9 小时
    - 深睡占比 (0.25): 目标 15-20%
    - REM 占比 (0.20): 目标 20-25%
    - 睡眠效率 (0.15): 目标 ≥85%
    - 中断惩罚 (0.15): 基于醒来次数和清醒时长
    """
    if not sleep or sleep.total_minutes == 0:
        return None

    total = sleep.total_minutes

    # 1. 时长评分
    if age < 18:
        target_min, target_max = 480, 600  # 8-10 小时
    elif age < 65:
        target_min, target_max = 420, 540  # 7-9 小时
    else:
        target_min, target_max = 390, 510  # 6.5-8.5 小时

    if total < target_min:
        duration_score = _clamp((total / target_min) * 100)
    elif total > target_max:
        # 超时也扣分
        over = total - target_max
        duration_score = _clamp(100 - over * 0.5)
    else:
        duration_score = 100

    # 2. 深睡占比评分
    deep_pct = (sleep.deep_sleep_minutes / total * 100) if total > 0 else 0
    deep_score = _clamp(deep_pct / 17.5 * 100)  # 目标 17.5%

    # 3. REM 占比评分
    rem_pct = (sleep.rem_sleep_minutes / total * 100) if total > 0 else 0
    rem_score = _clamp(rem_pct / 22.5 * 100)  # 目标 22.5%

    # 4. 睡眠效率
    if sleep.total_bed_time and sleep.total_bed_time > 0:
        efficiency = (total / sleep.total_bed_time) * 100
        efficiency_score = _clamp(efficiency / 85 * 100)
    else:
        # 没有卧床时间数据时，用清醒时长估算
        awake_ratio = (sleep.wake_minutes / (total + sleep.wake_minutes)) if (total + sleep.wake_minutes) > 0 else 0
        efficiency_score = _clamp((1 - awake_ratio) * 100 / 0.85)

    # 5. 中断惩罚
    wake_penalty = sleep.wake_count * 12 + sleep.wake_minutes * 1.5
    interruption_score = _clamp(100 - wake_penalty)

    # 加权组合
    score = int(_clamp(
        0.25 * duration_score +
        0.25 * deep_score +
        0.20 * rem_score +
        0.15 * efficiency_score +
        0.15 * interruption_score
    ))

    # 生成描述
    details_parts = []
    hours = total // 60
    mins = total % 60
    details_parts.append(f"总时长 {hours}h{mins}m")

    if deep_pct > 0:
        details_parts.append(f"深睡 {deep_pct:.0f}%{'（达标）' if 15 <= deep_pct <= 20 else '（偏低）'}")
    if rem_pct > 0:
        details_parts.append(f"REM {rem_pct:.0f}%{'（达标）' if 20 <= rem_pct <= 25 else '（偏低）'}")
    if sleep.wake_count > 0:
        details_parts.append(f"醒来 {sleep.wake_count} 次")

    return SleepQualityScore(
        score=score,
        deep_sleep_pct=round(deep_pct, 1),
        rem_sleep_pct=round(rem_pct, 1),
        efficiency_pct=round(efficiency_score, 1),
        duration_minutes=total,
        details="；".join(details_parts),
    )


# ============================================================
# Exertion Score（训练负荷评分）
# ============================================================


def compute_exertion(
    workouts_7d: list[Workout],
    workouts_28d: list[Workout],
    sport_load: Optional[list[SportLoadRecord]] = None,
) -> ExertionScore:
    """计算训练负荷评分 (0-100)。

    基于急性（7天）/ 慢性（28天）训练负荷比率。
    """
    # 计算急性负荷（7天）
    acute_load = 0.0
    for w in workouts_7d:
        if w.exercise_load and w.exercise_load > 0:
            acute_load += w.exercise_load
        elif w.duration_seconds > 0 and w.avg_heart_rate:
            # 估算负荷：时长(分钟) * 心率强度
            duration_min = w.duration_seconds / 60
            hr_intensity = w.avg_heart_rate / 190  # 假设最大心率 190
            acute_load += duration_min * hr_intensity * 10

    # 如果没有运动数据，尝试用 sport_load
    if acute_load == 0 and sport_load:
        for sl in sport_load[-7:]:
            if sl.wtl_sum:
                acute_load += sl.wtl_sum

    # 计算慢性负荷（28天平均每周）
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
        chronic_weekly = total_load / 4  # 4 周平均
    elif sport_load and len(sport_load) >= 7:
        total = sum(sl.wtl_sum or 0 for sl in sport_load[-28:])
        chronic_weekly = total / 4

    # 计算比率
    if chronic_weekly > 0:
        ratio = acute_load / chronic_weekly
    else:
        ratio = 0

    # 区间映射
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

    # 生成描述
    zone_desc = {
        "detraining": "训练不足，建议增加运动量",
        "maintaining": "维持状态，训练量适中",
        "productive": "有效提升，训练效果良好",
        "overreaching": "负荷偏高，注意恢复",
        "high_risk": "过度训练风险，建议休息",
        "inactive": "无运动数据",
    }

    details = f"7天负荷 {acute_load:.0f}，28天周均 {chronic_weekly:.0f}，比率 {ratio:.2f}"
    if zone in zone_desc:
        details += f"（{zone_desc[zone]}）"

    return ExertionScore(
        score=score if acute_load > 0 else 0,
        acute_load_7d=round(acute_load, 1),
        chronic_load_28d=round(chronic_weekly, 1),
        ratio=round(ratio, 2),
        zone=zone if acute_load > 0 else "inactive",
        details=details,
    )


# ============================================================
# Overall Score（综合健康分）
# ============================================================


def compute_overall(
    recovery: Optional[RecoveryScore],
    sleep_quality: Optional[SleepQualityScore],
    exertion: Optional[ExertionScore],
    avg_stress: Optional[int] = None,
    avg_spo2: Optional[int] = None,
) -> Optional[int]:
    """计算综合健康分 (0-100)。

    权重：
    - Recovery: 0.35
    - Sleep Quality: 0.30
    - Exertion: 0.15
    - Stress (反转): 0.10
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
        # 压力反转：低压力 = 高分
        stress_score = int(_clamp(100 - avg_stress))
        components.append((0.10, stress_score))
    if avg_spo2 is not None:
        # 血氧归一化：90% -> 0, 100% -> 100
        spo2_score = int(_clamp((avg_spo2 - 90) / 10 * 100))
        components.append((0.10, spo2_score))

    if not components:
        return None

    # 按比例重分配权重
    total_weight = sum(w for w, _ in components)
    if total_weight == 0:
        return None

    score = sum(w / total_weight * s for w, s in components)
    return int(_clamp(score))


# ============================================================
# 建议生成
# ============================================================


def generate_recommendations(
    recovery: Optional[RecoveryScore],
    sleep_quality: Optional[SleepQualityScore],
    exertion: Optional[ExertionScore],
    avg_stress: Optional[int] = None,
    avg_spo2: Optional[int] = None,
) -> list[str]:
    """根据各项评分生成健康建议。"""
    recommendations: list[str] = []

    # 恢复建议
    if recovery:
        if recovery.fatigue_signal:
            recommendations.append("检测到持续疲劳信号（HRV 偏低 + RHR 偏高），建议安排休息日，保证充足睡眠。")
        elif recovery.score < 40:
            recommendations.append("恢复水平较低，身体可能尚未从之前的训练中恢复，建议降低今日运动强度。")
        elif recovery.score >= 75:
            recommendations.append("恢复状态良好，适合进行中高强度训练。")
        if recovery.trend == "declining":
            recommendations.append("HRV 呈下降趋势，注意检查睡眠质量和生活压力。")

    # 睡眠建议
    if sleep_quality:
        if sleep_quality.score < 60:
            recommendations.append("睡眠质量不佳，建议关注睡眠习惯：固定作息时间、减少睡前屏幕使用。")
        if sleep_quality.deep_sleep_pct is not None and sleep_quality.deep_sleep_pct < 15:
            recommendations.append("深睡比例偏低，建议睡前避免酒精和咖啡因，保持卧室凉爽。")
        if sleep_quality.rem_sleep_pct is not None and sleep_quality.rem_sleep_pct < 18:
            recommendations.append("REM 睡眠不足，可能影响记忆和情绪调节，建议保持规律作息。")
        if sleep_quality.duration_minutes and sleep_quality.duration_minutes < 360:
            recommendations.append("睡眠时长不足 6 小时，长期睡眠不足会影响健康和运动表现。")

    # 训练负荷建议
    if exertion and exertion.zone != "inactive":
        if exertion.zone == "high_risk":
            recommendations.append("训练负荷过高，存在过度训练风险！建议立即安排 2-3 天的主动恢复。")
        elif exertion.zone == "overreaching":
            recommendations.append("训练负荷偏高，建议适当降低训练量，增加恢复时间。")
        elif exertion.zone == "detraining":
            recommendations.append("近期训练量偏低，如果目标是提升体能，建议逐步增加运动量。")
        elif exertion.zone == "productive":
            recommendations.append("训练负荷在有效提升区间，保持当前节奏。")

    # 压力建议
    if avg_stress is not None:
        if avg_stress > 60:
            recommendations.append("压力水平偏高，建议进行放松活动：深呼吸、冥想或轻度散步。")
        elif avg_stress > 40:
            recommendations.append("压力中等，注意适当休息和放松。")

    # 血氧建议
    if avg_spo2 is not None:
        if avg_spo2 < 93:
            recommendations.append("血氧饱和度偏低（<93%），建议关注呼吸健康，必要时就医检查。")
        elif avg_spo2 < 95:
            recommendations.append("血氧饱和度略低于正常范围，注意是否有打鼾或呼吸不畅的情况。")

    if not recommendations:
        recommendations.append("各项指标正常，保持当前的生活方式。")

    return recommendations
