"""分析流水线。

协调数据获取、评分计算和报告生成。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from zepp_health.client import ZeppClient
from zepp_health.models import HealthReport
from zepp_health.scoring import (
    compute_exertion,
    compute_overall,
    compute_recovery,
    compute_sleep_quality,
    generate_recommendations,
)


def generate_daily_report(
    client: ZeppClient,
    target_date: date | None = None,
) -> HealthReport:
    """生成每日健康报告。

    流程：
    1. 拉取当天数据（band_data, readiness, stress, spo2）
    2. 拉取历史数据（28 天运动, 60 天 readiness 用于基线）
    3. 调用评分函数
    4. 生成建议
    5. 返回 HealthReport
    """
    if target_date is None:
        target_date = date.today()

    # ----------------------------------------------------------
    # 1. 拉取当天数据
    # ----------------------------------------------------------

    # Band data（步数、睡眠、心率摘要）
    daily_data = client.get_daily_data(target_date, target_date)
    today_activity = daily_data[0] if daily_data else None

    # Readiness（HRV、RHR、准备度）
    readiness_list = client.get_readiness_data(target_date, target_date)
    today_readiness = readiness_list[-1] if readiness_list else None

    # Stress
    stress_list = client.get_stress_data(target_date, target_date)
    today_stress = stress_list[-1] if stress_list else None

    # SpO2
    spo2_list = client.get_spo2_data(target_date, target_date)
    today_spo2 = spo2_list[-1] if spo2_list else None

    # ----------------------------------------------------------
    # 2. 拉取历史数据用于基线和训练负荷
    # ----------------------------------------------------------

    # 60 天 readiness 历史（用于 HRV/RHR 基线）
    baseline_start = target_date - timedelta(days=60)
    readiness_history = client.get_readiness_data(baseline_start, target_date)

    # 提取 HRV 和 RHR 历史序列
    hrv_history: list[int] = []
    rhr_history: list[int] = []
    for r in readiness_history:
        if r.sleep_hrv and r.sleep_hrv > 0:
            hrv_history.append(r.sleep_hrv)
        elif r.hrv_baseline and r.hrv_baseline > 0:
            hrv_history.append(r.hrv_baseline)
        if r.sleep_rhr and r.sleep_rhr > 0:
            rhr_history.append(r.sleep_rhr)
        elif r.rhr_baseline and r.rhr_baseline > 0:
            rhr_history.append(r.rhr_baseline)

    # 28 天运动历史（用于训练负荷）
    workout_start = target_date - timedelta(days=28)
    workouts_28d = client.get_workouts(workout_start, target_date)
    workouts_7d = [w for w in workouts_28d if (target_date - w.start_time.date()).days <= 7]

    # Sport load（可选）
    sport_load = None
    try:
        sport_load = client.get_sport_load(workout_start, target_date)
    except Exception:
        pass  # sport_load 端点可能不可用

    # ----------------------------------------------------------
    # 3. 提取当天指标值
    # ----------------------------------------------------------

    # HRV：优先用 sleep_hrv，其次用 hrv_baseline
    today_hrv: int | None = None
    if today_readiness:
        today_hrv = today_readiness.sleep_hrv or today_readiness.hrv_baseline

    # RHR：优先用 sleep_rhr，其次用 band_data 中的 resting_heart_rate
    today_rhr: int | None = None
    if today_readiness and today_readiness.sleep_rhr:
        today_rhr = today_readiness.sleep_rhr
    elif today_activity and today_activity.sleep and today_activity.sleep.resting_heart_rate:
        today_rhr = today_activity.sleep.resting_heart_rate

    # 睡眠数据
    sleep = today_activity.sleep if today_activity else None

    # 平均压力
    avg_stress = today_stress.avg_stress if today_stress else None

    # 平均血氧
    avg_spo2: int | None = None
    if today_spo2 and today_spo2.readings:
        avg_spo2 = int(sum(r.spo2 for r in today_spo2.readings) / len(today_spo2.readings))

    # ----------------------------------------------------------
    # 4. 计算评分
    # ----------------------------------------------------------

    recovery = compute_recovery(
        today_hrv=today_hrv,
        today_rhr=today_rhr,
        hrv_history=hrv_history,
        rhr_history=rhr_history,
        readiness=today_readiness,
    )

    sleep_quality = compute_sleep_quality(sleep)

    exertion = compute_exertion(
        workouts_7d=workouts_7d,
        workouts_28d=workouts_28d,
        sport_load=sport_load,
    )

    overall_score = compute_overall(
        recovery=recovery,
        sleep_quality=sleep_quality,
        exertion=exertion,
        avg_stress=avg_stress,
        avg_spo2=avg_spo2,
    )

    # ----------------------------------------------------------
    # 5. 生成建议
    # ----------------------------------------------------------

    recommendations = generate_recommendations(
        recovery=recovery,
        sleep_quality=sleep_quality,
        exertion=exertion,
        avg_stress=avg_stress,
        avg_spo2=avg_spo2,
    )

    # ----------------------------------------------------------
    # 6. 组装原始指标
    # ----------------------------------------------------------

    raw_metrics: dict = {}
    if today_activity:
        if today_activity.steps:
            raw_metrics["steps"] = today_activity.steps.steps
            raw_metrics["distance_meters"] = today_activity.steps.distance_meters
            raw_metrics["calories"] = today_activity.steps.calories
        if today_activity.sleep:
            raw_metrics["sleep_minutes"] = today_activity.sleep.total_minutes
            raw_metrics["deep_sleep_minutes"] = today_activity.sleep.deep_sleep_minutes
            raw_metrics["light_sleep_minutes"] = today_activity.sleep.light_sleep_minutes
            raw_metrics["rem_sleep_minutes"] = today_activity.sleep.rem_sleep_minutes
            raw_metrics["resting_heart_rate"] = today_activity.sleep.resting_heart_rate
    if today_hrv:
        raw_metrics["sleep_hrv"] = today_hrv
    if today_readiness and today_readiness.hrv_baseline:
        raw_metrics["hrv_baseline"] = today_readiness.hrv_baseline
    if avg_stress is not None:
        raw_metrics["avg_stress"] = avg_stress
    if avg_spo2 is not None:
        raw_metrics["avg_spo2"] = avg_spo2
    if today_spo2 and today_spo2.odi is not None:
        raw_metrics["spo2_odi"] = today_spo2.odi

    # ----------------------------------------------------------
    # 7. 返回报告
    # ----------------------------------------------------------

    return HealthReport(
        date=target_date.isoformat(),
        generated_at=datetime.now(),
        overall_score=overall_score,
        recovery=recovery,
        sleep_quality=sleep_quality,
        exertion=exertion,
        raw_metrics=raw_metrics,
        recommendations=recommendations,
    )


def generate_snapshot(
    client: ZeppClient,
    target_date: date | None = None,
) -> dict[str, Any]:
    """导出 LLM 分析用的完整数据快照。

    比 generate_daily_report() 更丰富，包含 7 天趋势数据。
    输出为 dict，可直接 JSON 序列化。
    """
    if target_date is None:
        target_date = date.today()

    # 当天报告
    report = generate_daily_report(client, target_date)

    # 7 天趋势
    trend_start = target_date - timedelta(days=6)
    readiness_7d = client.get_readiness_data(trend_start, target_date)
    daily_7d = client.get_daily_data(trend_start, target_date)

    # 构建日期索引
    readiness_map = {r.date: r for r in readiness_7d}
    daily_map = {d.date: d for d in daily_7d}

    dates = [(target_date - timedelta(days=i)) for i in range(6, -1, -1)]
    date_strs = [d.isoformat() for d in dates]

    hrv_trend: list[int | None] = []
    rhr_trend: list[int | None] = []
    readiness_trend: list[int | None] = []
    bb_trend: list[int | None] = []
    sleep_score_trend: list[int | None] = []

    for ds in date_strs:
        r = readiness_map.get(ds)
        if r:
            hrv_trend.append(r.sleep_hrv)
            rhr_trend.append(r.sleep_rhr)
            readiness_trend.append(r.readiness_score)
        else:
            hrv_trend.append(None)
            rhr_trend.append(None)
            readiness_trend.append(None)

        day = daily_map.get(ds)
        if day and day.sleep:
            sleep_score_trend.append(day.sleep.sleep_score)
        else:
            sleep_score_trend.append(None)

    # 身体电量 7 天
    for d in dates:
        start_ts = int(datetime.combine(d, datetime.min.time()).timestamp() * 1000)
        end_ts = int(datetime.combine(d, datetime.max.time()).timestamp() * 1000)
        try:
            bb_readings = client.get_body_battery(start_ts, end_ts)
            bb_trend.append(bb_readings[0].value if bb_readings else None)
        except Exception:
            bb_trend.append(None)

    # 7 天运动
    workout_start = target_date - timedelta(days=6)
    workouts = client.get_workouts(workout_start, target_date)
    workouts_data = []
    for w in workouts:
        workouts_data.append({
            "date": w.start_time.strftime("%Y-%m-%d"),
            "type": w.workout_name,
            "duration_min": w.duration_seconds // 60,
            "distance_m": int(w.distance_meters),
            "calories": int(w.calories),
            "avg_hr": w.avg_heart_rate,
            "max_hr": w.max_heart_rate,
        })

    # 组装快照
    today = report.raw_metrics
    snapshot: dict[str, Any] = {
        "date": target_date.isoformat(),
        "today": {
            "steps": today.get("steps"),
            "distance_meters": today.get("distance_meters"),
            "calories": today.get("calories"),
            "sleep": {
                "total_minutes": today.get("sleep_minutes"),
                "deep": today.get("deep_sleep_minutes"),
                "light": today.get("light_sleep_minutes"),
                "rem": today.get("rem_sleep_minutes"),
                "wake_count": report.sleep_quality and report.sleep_quality.duration_minutes,
                "score": None,
                "resting_hr": today.get("resting_heart_rate"),
            },
            "heart_rate": {
                "sleep_hrv": today.get("sleep_hrv"),
                "hrv_baseline": today.get("hrv_baseline"),
            },
            "stress": {
                "avg": today.get("avg_stress"),
            },
            "spo2": {
                "avg": today.get("avg_spo2"),
                "odi": today.get("spo2_odi"),
            },
            "readiness": {},
        },
        "trends_7d": {
            "hrv": hrv_trend,
            "rhr": rhr_trend,
            "readiness": readiness_trend,
            "body_battery": bb_trend,
            "sleep_score": sleep_score_trend,
        },
        "workouts_7d": workouts_data,
        "scores": {
            "recovery": report.recovery.score if report.recovery else None,
            "sleep_quality": report.sleep_quality.score if report.sleep_quality else None,
            "exertion": report.exertion.score if report.exertion else None,
            "overall": report.overall_score,
        },
    }

    # 补充 readiness 详细数据
    today_readiness = readiness_map.get(target_date.isoformat())
    if today_readiness:
        skin_delta = None
        if today_readiness.skin_temp_calibrated is not None:
            skin_delta = round(today_readiness.skin_temp_calibrated / 100, 1)
        snapshot["today"]["readiness"] = {
            "score": today_readiness.readiness_score,
            "hrv_score": today_readiness.hrv_score,
            "rhr_score": today_readiness.rhr_score,
            "skin_temp_delta": skin_delta,
        }

    # 补充睡眠评分
    today_daily = daily_map.get(target_date.isoformat())
    if today_daily and today_daily.sleep:
        snapshot["today"]["sleep"]["score"] = today_daily.sleep.sleep_score
        snapshot["today"]["sleep"]["wake_count"] = today_daily.sleep.wake_count

    # 补充身体电量
    snapshot["today"]["body_battery"] = bb_trend[-1] if bb_trend else None

    # 补充呼吸频率
    try:
        resp_ts_start = int(datetime.combine(target_date, datetime.min.time()).timestamp() * 1000)
        resp_ts_end = int(datetime.combine(target_date, datetime.max.time()).timestamp() * 1000)
        resp = client.get_respiratory_rate(resp_ts_start, resp_ts_end)
        if resp:
            snapshot["today"]["respiratory_rate"] = resp[-1].breaths_per_minute
    except Exception:
        pass

    # 补充压力详情
    stress_list = client.get_stress_data(target_date, target_date)
    if stress_list:
        st = stress_list[-1]
        snapshot["today"]["stress"]["min"] = st.min_stress
        snapshot["today"]["stress"]["max"] = st.max_stress

    return snapshot
