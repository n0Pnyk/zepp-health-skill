"""Analysis pipeline.

Coordinates data fetching, scoring, and report generation.
Optimized with parallel API calls via ThreadPoolExecutor.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _fetch_all_data(
    client: ZeppClient,
    target_date: date,
    *,
    include_extended: bool = False,
) -> dict[str, Any]:
    """Fetch all required raw data in parallel.

    Args:
        client: Zepp API client
        target_date: Date to fetch data for
        include_extended: If True, also fetch 7-day trends (for snapshot)

    Returns:
        Dict with all fetched data, keyed by descriptive names.
    """
    # Define all independent API calls
    tasks: dict[str, Any] = {}

    def _call(key: str, fn, *args, **kwargs):
        """Register a callable under a key."""
        tasks[key] = (fn, args, kwargs)

    # --- Core data (always needed) ---
    _call("daily_today", client.get_daily_data, target_date, target_date)
    _call("readiness_today", client.get_readiness_data, target_date, target_date)
    _call("stress_today", client.get_stress_data, target_date, target_date)
    _call("spo2_today", client.get_spo2_data, target_date, target_date)

    # 60-day readiness baseline
    baseline_start = target_date - timedelta(days=60)
    _call("readiness_baseline", client.get_readiness_data, baseline_start, target_date)

    # 28-day workouts (for training load)
    workout_start_28d = target_date - timedelta(days=28)
    _call("workouts_28d", client.get_workouts, workout_start_28d, target_date)

    # Sport load (optional)
    _call("sport_load", client.get_sport_load, workout_start_28d, target_date)

    # --- Extended data (for snapshot) ---
    if include_extended:
        # Body battery: single call for 7-day range (instead of 7 separate calls)
        bb_start = datetime.combine(target_date - timedelta(days=6), datetime.min.time())
        bb_end = datetime.combine(target_date, datetime.max.time())
        bb_start_ts = int(bb_start.timestamp() * 1000)
        bb_end_ts = int(bb_end.timestamp() * 1000)
        _call("body_battery_7d", client.get_body_battery, bb_start_ts, bb_end_ts)

        # 7-day daily data (for sleep_score trend)
        daily_trend_start = target_date - timedelta(days=6)
        _call("daily_7d", client.get_daily_data, daily_trend_start, target_date)

        # Respiratory rate for today
        resp_start = int(datetime.combine(target_date, datetime.min.time()).timestamp() * 1000)
        resp_end = int(datetime.combine(target_date, datetime.max.time()).timestamp() * 1000)
        _call("respiratory_rate", client.get_respiratory_rate, resp_start, resp_end)

        # HRV RMSSD for 7 days (independent minute-samples, vs readiness sleep_hrv)
        _call("hrv_rmssd_7d", client.get_hrv, bb_start_ts, bb_end_ts, hrv_type="rmssd")

    # Execute all calls in parallel
    results: dict[str, Any] = {}
    errors: set[str] = set()
    meta: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_key = {}
        for key, (fn, args, kwargs) in tasks.items():
            future = executor.submit(fn, *args, **kwargs)
            future_to_key[future] = key

        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                result = future.result()
                results[key] = result
                # Track status per API
                if isinstance(result, list):
                    meta[key] = {"status": "ok" if result else "empty", "items": len(result)}
                elif result is None:
                    meta[key] = {"status": "empty"}
                else:
                    meta[key] = {"status": "ok"}
            except Exception as e:
                errors.add(key)
                results[key] = None
                meta[key] = {"status": "error", "error": str(e)[:200]}

    results["_errors"] = errors
    results["_meta"] = meta
    return results


def generate_daily_report(
    client: ZeppClient,
    target_date: date | None = None,
) -> HealthReport:
    """Generate daily health report.

    Uses parallel API calls for all independent data fetches.
    """
    if target_date is None:
        target_date = date.today()

    # Fetch all data in parallel
    data = _fetch_all_data(client, target_date, include_extended=False)

    # --- Extract today's values ---

    daily_data = data.get("daily_today") or []
    today_activity = daily_data[0] if daily_data else None

    readiness_list = data.get("readiness_today") or []
    today_readiness = readiness_list[-1] if readiness_list else None

    stress_list = data.get("stress_today") or []
    today_stress = stress_list[-1] if stress_list else None

    spo2_list = data.get("spo2_today") or []
    today_spo2 = spo2_list[-1] if spo2_list else None

    # --- Extract baseline history ---

    readiness_history = data.get("readiness_baseline") or []
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

    # --- Workouts ---

    workouts_28d = data.get("workouts_28d") or []
    workouts_7d = [w for w in workouts_28d if (target_date - w.start_time.date()).days <= 7]

    sport_load = None
    if "sport_load" not in data.get("_errors", set()):
        sport_load = data.get("sport_load")

    # --- Today's metric values ---

    today_hrv: int | None = None
    if today_readiness:
        today_hrv = today_readiness.sleep_hrv or today_readiness.hrv_baseline

    today_rhr: int | None = None
    if today_readiness and today_readiness.sleep_rhr:
        today_rhr = today_readiness.sleep_rhr
    elif today_activity and today_activity.sleep and today_activity.sleep.resting_heart_rate:
        today_rhr = today_activity.sleep.resting_heart_rate

    sleep = today_activity.sleep if today_activity else None
    avg_stress = today_stress.avg_stress if today_stress else None

    avg_spo2: int | None = None
    if today_spo2 and today_spo2.readings:
        avg_spo2 = int(sum(r.spo2 for r in today_spo2.readings) / len(today_spo2.readings))

    # --- Compute scores ---

    # 7-day HRV/RHR averages for recovery (more robust than single-day)
    hrv_avg_7d: int | None = None
    rhr_avg_7d: int | None = None
    hrv_recent = [r.sleep_hrv or r.hrv_baseline for r in readiness_history[-7:] if (r.sleep_hrv and r.sleep_hrv > 0) or (r.hrv_baseline and r.hrv_baseline > 0)]
    rhr_recent = [r.sleep_rhr or r.rhr_baseline for r in readiness_history[-7:] if (r.sleep_rhr and r.sleep_rhr > 0) or (r.rhr_baseline and r.rhr_baseline > 0)]
    if hrv_recent:
        hrv_avg_7d = int(sum(hrv_recent) / len(hrv_recent))
    if rhr_recent:
        rhr_avg_7d = int(sum(rhr_recent) / len(rhr_recent))

    # Personalized max HR from 28-day workouts
    from zepp_health.scoring import get_personalized_max_hr
    max_hr = get_personalized_max_hr(workouts_28d)
    resting_hr = rhr_avg_7d or today_rhr or 60

    recovery = compute_recovery(
        today_hrv=today_hrv,
        today_rhr=today_rhr,
        hrv_history=hrv_history,
        rhr_history=rhr_history,
        readiness=today_readiness,
        hrv_avg_7d=hrv_avg_7d,
        rhr_avg_7d=rhr_avg_7d,
    )

    sleep_quality = compute_sleep_quality(sleep)

    exertion = compute_exertion(
        workouts_7d=workouts_7d,
        workouts_28d=workouts_28d,
        sport_load=sport_load,
        resting_hr=resting_hr,
        max_hr=max_hr,
    )

    overall_score = compute_overall(
        recovery=recovery,
        sleep_quality=sleep_quality,
        exertion=exertion,
        avg_stress=avg_stress,
        avg_spo2=avg_spo2,
    )

    recommendations = generate_recommendations(
        recovery=recovery,
        sleep_quality=sleep_quality,
        exertion=exertion,
        avg_stress=avg_stress,
        avg_spo2=avg_spo2,
    )

    # --- Raw metrics ---

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
    """Export complete health data snapshot for LLM analysis.

    Richer than generate_daily_report(), includes 7-day trends.
    Uses a single _fetch_all_data() call to avoid duplicate API requests.
    """
    if target_date is None:
        target_date = date.today()

    # Fetch ALL data in one parallel batch (includes extended data)
    data = _fetch_all_data(client, target_date, include_extended=True)

    # --- Extract today's values (same logic as generate_daily_report) ---

    daily_data = data.get("daily_today") or []
    today_activity = daily_data[0] if daily_data else None

    readiness_list = data.get("readiness_today") or []
    today_readiness = readiness_list[-1] if readiness_list else None

    stress_list = data.get("stress_today") or []
    today_stress = stress_list[-1] if stress_list else None

    spo2_list = data.get("spo2_today") or []
    today_spo2 = spo2_list[-1] if spo2_list else None

    # Baseline history
    readiness_history = data.get("readiness_baseline") or []
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

    # Workouts
    workouts_28d = data.get("workouts_28d") or []
    workouts_7d = [w for w in workouts_28d if (target_date - w.start_time.date()).days <= 7]

    sport_load = None
    if "sport_load" not in data.get("_errors", set()):
        sport_load = data.get("sport_load")

    # Today's metric values
    today_hrv: int | None = None
    if today_readiness:
        today_hrv = today_readiness.sleep_hrv or today_readiness.hrv_baseline

    today_rhr: int | None = None
    if today_readiness and today_readiness.sleep_rhr:
        today_rhr = today_readiness.sleep_rhr
    elif today_activity and today_activity.sleep and today_activity.sleep.resting_heart_rate:
        today_rhr = today_activity.sleep.resting_heart_rate

    sleep = today_activity.sleep if today_activity else None
    avg_stress = today_stress.avg_stress if today_stress else None

    avg_spo2: int | None = None
    if today_spo2 and today_spo2.readings:
        avg_spo2 = int(sum(r.spo2 for r in today_spo2.readings) / len(today_spo2.readings))

    # --- Compute scores ---

    # 7-day HRV/RHR averages for recovery (more robust than single-day)
    hrv_avg_7d: int | None = None
    rhr_avg_7d: int | None = None
    hrv_recent = [r.sleep_hrv or r.hrv_baseline for r in readiness_history[-7:] if (r.sleep_hrv and r.sleep_hrv > 0) or (r.hrv_baseline and r.hrv_baseline > 0)]
    rhr_recent = [r.sleep_rhr or r.rhr_baseline for r in readiness_history[-7:] if (r.sleep_rhr and r.sleep_rhr > 0) or (r.rhr_baseline and r.rhr_baseline > 0)]
    if hrv_recent:
        hrv_avg_7d = int(sum(hrv_recent) / len(hrv_recent))
    if rhr_recent:
        rhr_avg_7d = int(sum(rhr_recent) / len(rhr_recent))

    # Personalized max HR from 28-day workouts
    from zepp_health.scoring import get_personalized_max_hr
    max_hr = get_personalized_max_hr(workouts_28d)
    resting_hr = rhr_avg_7d or today_rhr or 60

    recovery = compute_recovery(
        today_hrv=today_hrv,
        today_rhr=today_rhr,
        hrv_history=hrv_history,
        rhr_history=rhr_history,
        readiness=today_readiness,
        hrv_avg_7d=hrv_avg_7d,
        rhr_avg_7d=rhr_avg_7d,
    )

    # Sleep with SOL and consistency
    sleep_times: list[tuple[int, int]] = []
    daily_7d = data.get("daily_7d") or []
    for d in daily_7d:
        if d.sleep and d.sleep.start_time and d.sleep.end_time:
            sleep_start_min = d.sleep.start_time.hour * 60 + d.sleep.start_time.minute
            wake_end_min = d.sleep.end_time.hour * 60 + d.sleep.end_time.minute
            sleep_times.append((sleep_start_min, wake_end_min))

    sleep_quality = compute_sleep_quality(sleep, sleep_times=sleep_times)

    exertion = compute_exertion(
        workouts_7d=workouts_7d,
        workouts_28d=workouts_28d,
        sport_load=sport_load,
        resting_hr=resting_hr,
        max_hr=max_hr,
    )

    overall_score = compute_overall(
        recovery=recovery,
        sleep_quality=sleep_quality,
        exertion=exertion,
        avg_stress=avg_stress,
        avg_spo2=avg_spo2,
    )

    # --- Build 7-day trends from baseline data (already fetched) ---

    dates = [(target_date - timedelta(days=i)) for i in range(6, -1, -1)]
    date_strs = [d.isoformat() for d in dates]

    # Use baseline data for 7-day trends (60-day fetch already covers this)
    readiness_map = {r.date: r for r in readiness_history}

    # daily_data only has today; fetch 7-day daily data from baseline readiness
    # We need sleep scores from daily data - use readiness data as proxy
    hrv_trend: list[int | None] = []
    rhr_trend: list[int | None] = []
    readiness_trend: list[int | None] = []
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
        sleep_score_trend.append(None)

    # Populate sleep_score_trend from daily data (band_data summary contains sleep_score)
    daily_7d = data.get("daily_7d") or []
    daily_map = {}
    for d in daily_7d:
        if d.date:
            daily_map[d.date] = d
    for i, ds in enumerate(date_strs):
        d = daily_map.get(ds)
        if d and d.sleep and d.sleep.sleep_score is not None:
            sleep_score_trend[i] = d.sleep.sleep_score

    # Fallback: override today's sleep score from daily_today if available
    if today_activity and today_activity.sleep and sleep_score_trend[-1] is None:
        sleep_score_trend[-1] = today_activity.sleep.sleep_score

    # --- Body battery: batch result grouped by date ---

    bb_readings = data.get("body_battery_7d") or []
    bb_by_date: dict[str, int] = {}
    for reading in bb_readings:
        d = reading.timestamp.strftime("%Y-%m-%d")
        # Keep the latest reading per day
        bb_by_date[d] = reading.value

    bb_trend = [bb_by_date.get(ds) for ds in date_strs]

    # --- 7-day workouts (subset of 28-day) ---

    workouts_data = []
    for w in workouts_7d:
        workouts_data.append({
            "date": w.start_time.strftime("%Y-%m-%d"),
            "type": w.workout_name,
            "duration_min": w.duration_seconds // 60,
            "distance_m": int(w.distance_meters),
            "calories": int(w.calories),
            "avg_hr": w.avg_heart_rate,
            "max_hr": w.max_heart_rate,
        })

    # --- Build raw metrics ---

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

    # --- Assemble snapshot ---

    snapshot: dict[str, Any] = {
        "date": target_date.isoformat(),
        "today": {
            "steps": raw_metrics.get("steps"),
            "distance_meters": raw_metrics.get("distance_meters"),
            "calories": raw_metrics.get("calories"),
            "sleep": {
                "total_minutes": raw_metrics.get("sleep_minutes"),
                "deep": raw_metrics.get("deep_sleep_minutes"),
                "light": raw_metrics.get("light_sleep_minutes"),
                "rem": raw_metrics.get("rem_sleep_minutes"),
                "wake_count": None,
                "score": None,
                "resting_hr": raw_metrics.get("resting_heart_rate"),
            },
            "heart_rate": {
                "sleep_hrv": raw_metrics.get("sleep_hrv"),
                "hrv_baseline": raw_metrics.get("hrv_baseline"),
            },
            "stress": {
                "avg": raw_metrics.get("avg_stress"),
            },
            "spo2": {
                "avg": raw_metrics.get("avg_spo2"),
                "odi": raw_metrics.get("spo2_odi"),
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
            "recovery": recovery.score if recovery else None,
            "sleep_quality": sleep_quality.score if sleep_quality else None,
            "exertion": exertion.score if exertion else None,
            "overall": overall_score,
        },
    }

    # Supplement readiness details
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

    # Supplement sleep details
    if today_activity and today_activity.sleep:
        snapshot["today"]["sleep"]["score"] = today_activity.sleep.sleep_score
        snapshot["today"]["sleep"]["wake_count"] = today_activity.sleep.wake_count

    # Supplement body battery
    snapshot["today"]["body_battery"] = bb_trend[-1] if bb_trend else None

    # Supplement respiratory rate
    resp_data = data.get("respiratory_rate")
    if resp_data:
        snapshot["today"]["respiratory_rate"] = resp_data[-1].breaths_per_minute

    # Supplement HRV RMSSD (independent minute-sample data, 7-day)
    hrv_data = data.get("hrv_rmssd_7d") or []
    if hrv_data:
        snapshot["today"]["hrv_rmssd"] = hrv_data[-1].hrv_value
        snapshot["hrv_rmssd_7d"] = [
            {"date": r.timestamp.strftime("%Y-%m-%d"), "rmssd_ms": r.hrv_value}
            for r in hrv_data
        ]

    # Supplement stress details
    if today_stress:
        snapshot["today"]["stress"]["min"] = today_stress.min_stress
        snapshot["today"]["stress"]["max"] = today_stress.max_stress

    # Add warnings for failed API calls
    errors = data.get("_errors", set())
    if errors:
        snapshot["_warnings"] = [f"Failed to fetch: {e}" for e in sorted(errors)]

    # Add per-API status metadata
    api_meta = data.get("_meta", {})
    if api_meta:
        snapshot["_meta"] = api_meta

    return snapshot
