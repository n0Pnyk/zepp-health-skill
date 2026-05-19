"""Zepp Health API client.

Merges endpoints from amazfit-cli and zepp-health-cli reference projects.
Uses httpx as the HTTP client with context manager support.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from zepp_health.config import AppConfig
from zepp_health.models import (
    ActivityData,
    ActivitySummary,
    BodyBatteryReading,
    BloodPressureRecord,
    DaySummary,
    HeartRateData,
    HeartRateZone,
    HRVReading,
    OSAEvent,
    PAIData,
    ReadinessData,
    RespiratoryRateReading,
    SleepData,
    SleepPhase,
    SpO2Data,
    SpO2Reading,
    SportLoadRecord,
    StepData,
    StressData,
    StressReading,
    VO2MaxRecord,
    WeightRecord,
    Workout,
    WORKOUT_TYPES,
)

# API base URL
BAND_DATA_PATH = "/v1/data/band_data.json"
EVENTS_PATH = "/users/{user_id}/events"
EVENTS_V2_PATH = "/v2/users/me/events"
WORKOUT_HISTORY_PATH = "/v1/sport/run/history.json"
HEART_RATE_PATH = "/users/{user_id}/heartRate"
WEIGHT_PATH = "/users/{user_id}/members/-1/weightRecords"
BLOOD_PRESSURE_PATH = "/users/me/bloodPressure"
SPORT_STATS_PATH = "/v2/watch/users/{user_id}/WatchSportStatistics/{stat_type}"

# Activity mode codes
ACTIVITY_MODES = {
    1: "slow_walking",
    3: "fast_walking",
    4: "light_sleep",
    5: "deep_sleep",
    6: "running",
    7: "normal_activity",
    9: "cycling",
    11: "rem_sleep",
    80: "outdoor_running",
    81: "walking",
    82: "hiking",
    83: "treadmill",
    84: "cycling",
    85: "stationary_bike",
}


class ZeppClientError(Exception):
    """API client error."""
    pass


class ZeppClient:
    """Zepp Health API client."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._user_id = config.user_id
        self._http = httpx.Client(
            base_url=f"https://{config.host}",
            timeout=30.0,
            follow_redirects=False,
        )
        self._http.headers.update({
            "apptoken": config.app_token,
            "appname": "com.huami.midong",
            "appplatform": config.app_platform,
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "v": "2.0",
            "vn": "10.2.5",
            "lang": config.lang,
            "country": config.country,
            "timezone": config.timezone,
            "user-agent": "Zepp/10.2.5 (iPhone; iOS 26.3.1; Scale/3.00)",
        })

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the HTTP client."""
        self._http.close()

    # ----------------------------------------------------------
    # Internal utility methods
    # ----------------------------------------------------------

    @staticmethod
    def _r() -> str:
        """Generate a random UUID for cache busting."""
        return str(uuid.uuid4()).upper()

    @staticmethod
    def _normalize_timestamp(ts: int | float | None) -> float:
        """Convert a millisecond timestamp to seconds."""
        if not ts:
            return 0
        if ts > 1e12:
            return ts / 1000
        return float(ts)

    @staticmethod
    def _date_str_from_ts(ts: int | float) -> str:
        """Get a YYYY-MM-DD date string from a timestamp."""
        return datetime.fromtimestamp(
            ZeppClient._normalize_timestamp(ts)
        ).strftime("%Y-%m-%d")

    @staticmethod
    def _safe_json_loads(raw: str | None, default: Any = None) -> Any:
        """Safely parse JSON."""
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def _decode_summary(summary_b64: str) -> Optional[dict]:
        """Decode base64-encoded summary data."""
        try:
            decoded = base64.b64decode(summary_b64)
            data = json.loads(decoded)
            if isinstance(data, list):
                return data[0] if data else None
            if isinstance(data, dict):
                return data
        except Exception:
            return None

    @staticmethod
    def _date_range_to_ms(start: datetime, end: datetime) -> tuple[int, int]:
        """Convert a date range to millisecond timestamps."""
        start_ts = int(datetime.combine(start, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(end, datetime.max.time()).timestamp())
        return start_ts * 1000, end_ts * 1000

    def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        """Send a GET request and return the JSON response."""
        params["r"] = self._r()
        response = self._http.get(path, params=params)
        if response.status_code != 200:
            raise ZeppClientError(
                f"API request failed: {response.status_code} - {response.text[:200]}"
            )
        return response.json()

    def _get_events(
        self,
        event_type: str,
        start_date: datetime,
        end_date: datetime,
        *,
        sub_type: Optional[str] = None,
        extra_params: Optional[dict] = None,
    ) -> list[dict]:
        """Fetch event data with pagination."""
        url = EVENTS_PATH.format(user_id=self._user_id)
        start_ms, end_ms = self._date_range_to_ms(start_date, end_date)

        params: dict[str, Any] = {
            "eventType": event_type,
            "limit": 1000,
        }
        if sub_type:
            params["subType"] = sub_type
        if extra_params:
            params.update(extra_params)

        items: list[dict] = []
        cursor = start_ms

        while cursor <= end_ms:
            params["from"] = str(cursor)
            params["to"] = str(end_ms)

            result = self._get_json(url, params)
            batch = result.get("items", [])
            if not batch:
                break

            items.extend(batch)

            if len(batch) < params["limit"]:
                break

            # Advance cursor to the last timestamp
            max_ts = 0
            for item in batch:
                ts = self._normalize_timestamp(item.get("timestamp", 0))
                if ts:
                    max_ts = max(max_ts, int(ts * 1000))

            if max_ts <= cursor or max_ts >= end_ms:
                break

            cursor = max_ts + 1

        return items

    def _get_v2_events(
        self,
        event_type: str,
        sub_type: str,
        start_ts: int,
        end_ts: int,
        *,
        limit: int = 200,
    ) -> list[dict]:
        """Fetch data from the v2 events endpoint."""
        params: dict[str, Any] = {
            "eventType": event_type,
            "subType": sub_type,
            "from": start_ts,
            "to": end_ts,
            "limit": limit,
            "reverse": 1,
        }
        result = self._get_json(EVENTS_V2_PATH, params)
        return result.get("items", [])

    # ----------------------------------------------------------
    # Band Data (steps, sleep, heart rate summaries)
    # ----------------------------------------------------------

    def get_band_data(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Get raw band data."""
        params = {
            "query_type": "summary",
            "device_type": "ios_phone",
            "userid": self._user_id,
            "from_date": start_date.isoformat(),
            "to_date": end_date.isoformat(),
        }
        result = self._get_json(BAND_DATA_PATH, params)
        if result.get("code") != 1:
            raise ZeppClientError(f"API error: {result.get('message', 'Unknown error')}")
        return result.get("data", [])

    def get_daily_data(
        self,
        start_date: date,
        end_date: date,
    ) -> list[ActivityData]:
        """Get parsed daily activity data."""
        raw_data = self.get_band_data(start_date, end_date)
        return [self._parse_day_data(day) for day in raw_data]

    def _parse_day_data(self, raw: dict) -> ActivityData:
        """Parse raw band data into ActivityData."""
        date_str = raw.get("date_time", raw.get("dateTime", ""))
        activity = ActivityData(date=date_str)

        summary_b64 = raw.get("summary", "")
        summary = self._decode_summary(summary_b64) if summary_b64 else None
        if summary:
            activity.steps = self._parse_step_summary(summary, date_str)
            activity.sleep = self._parse_sleep_from_summary(summary, date_str)
            activity.activities = self._parse_activities_from_summary(summary, date_str)
            activity.heart_rates = self._parse_hr_from_summary(summary, date_str)

        return activity

    def _parse_step_summary(self, summary: dict, date_str: str) -> Optional[StepData]:
        """Parse step data from summary."""
        try:
            stp = summary.get("stp", {})
            if isinstance(stp, dict):
                base_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
                return StepData(
                    timestamp=base_date,
                    steps=stp.get("ttl", 0),
                    distance_meters=stp.get("dis", 0),
                    calories=stp.get("cal", 0),
                    run_distance=stp.get("runDist", 0),
                    walking_minutes=stp.get("wk", 0),
                    running_calories=stp.get("runCal", 0),
                    running_steps=stp.get("rn", 0),
                )
        except Exception:
            pass
        return None

    def _parse_sleep_from_summary(self, summary: dict, date_str: str) -> Optional[SleepData]:
        """Parse sleep data from summary."""
        try:
            slp = summary.get("slp", {})
            if not slp or not isinstance(slp, dict):
                return None

            deep_sleep = slp.get("dp", 0)
            light_sleep = slp.get("lt", 0)
            rem_sleep = slp.get("dt", 0)
            total = deep_sleep + light_sleep + rem_sleep

            if total == 0:
                return None

            start_ts = slp.get("st", 0)
            end_ts = slp.get("ed", 0)
            base_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()

            if start_ts > 1e9:
                start_time = datetime.fromtimestamp(start_ts)
                end_time = datetime.fromtimestamp(end_ts)
            else:
                start_time = base_date + timedelta(minutes=start_ts)
                end_time = base_date + timedelta(minutes=end_ts)

            # Parse sleep phases
            phases = []
            for stage in slp.get("stage", []):
                phase_start = stage.get("start", 0)
                phase_end = stage.get("stop", phase_start)
                mode = stage.get("mode", 4)
                phase_start_dt = base_date + timedelta(minutes=phase_start)
                phase_end_dt = base_date + timedelta(minutes=phase_end)
                phase_type = {
                    4: "light", 5: "deep", 8: "rem", 11: "rem",
                }.get(mode, "awake")
                phases.append(SleepPhase(
                    start=phase_start_dt,
                    end=phase_end_dt,
                    phase_type=phase_type,
                    duration_minutes=phase_end - phase_start,
                ))

            return SleepData(
                date=date_str,
                start_time=start_time,
                end_time=end_time,
                total_minutes=total,
                deep_sleep_minutes=deep_sleep,
                light_sleep_minutes=light_sleep,
                rem_sleep_minutes=rem_sleep,
                sleep_score=slp.get("ss"),
                resting_heart_rate=slp.get("rhr"),
                sleep_onset_latency=slp.get("lb") or None,
                wake_count=slp.get("wc", 0),
                wake_minutes=slp.get("wk", 0),
                total_bed_time=slp.get("ebt") or None,
                out_of_bed_time=slp.get("obt") or None,
                interruption_score=slp.get("is") or None,
                phases=phases,
            )
        except Exception:
            return None

    def _parse_hr_from_summary(self, summary: dict, date_str: str) -> list[HeartRateData]:
        """Parse heart rate data from summary."""
        heart_rates = []
        try:
            base_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()

            hr_data = summary.get("hr", {})
            max_hr = hr_data.get("maxHr", {})
            if max_hr and max_hr.get("hr", 0) > 0:
                hr_ts = max_hr.get("ts", 0)
                hr_time = datetime.fromtimestamp(hr_ts) if hr_ts > 1e9 else base_date
                heart_rates.append(HeartRateData(
                    timestamp=hr_time, bpm=max_hr["hr"], activity_type="max",
                ))

            slp = summary.get("slp", {})
            rhr = slp.get("rhr", 0)
            if rhr > 0:
                heart_rates.append(HeartRateData(
                    timestamp=base_date, bpm=rhr, activity_type="resting",
                ))
        except Exception:
            pass

        return heart_rates

    def _parse_activities_from_summary(self, summary: dict, date_str: str) -> list[ActivitySummary]:
        """Parse activity phases from summary."""
        activities = []
        try:
            stp = summary.get("stp", {})
            if not isinstance(stp, dict):
                return activities

            base_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()

            for stage in stp.get("stage", []):
                start = stage.get("start", 0)
                stop = stage.get("stop", start)
                mode = stage.get("mode", 0)
                activities.append(ActivitySummary(
                    start=base_date + timedelta(minutes=start),
                    end=base_date + timedelta(minutes=stop),
                    mode=mode,
                    mode_name=ACTIVITY_MODES.get(mode, f"unknown_{mode}"),
                    steps=stage.get("step", 0),
                    distance=stage.get("dis", 0),
                    calories=stage.get("cal", 0),
                ))
        except Exception:
            pass

        return activities

    # ----------------------------------------------------------
    # Daily summaries
    # ----------------------------------------------------------

    def get_summary(
        self,
        start_date: date,
        end_date: date,
    ) -> list[DaySummary]:
        """Get daily summary data."""
        daily_data = self.get_daily_data(start_date, end_date)
        summaries = []

        for day in daily_data:
            resting_hr = None
            max_hr = None
            for hr in day.heart_rates:
                if hr.activity_type == "resting":
                    resting_hr = hr.bpm
                elif hr.activity_type == "max":
                    max_hr = hr.bpm

            if not resting_hr and day.sleep and day.sleep.resting_heart_rate:
                resting_hr = day.sleep.resting_heart_rate

            summaries.append(DaySummary(
                date=day.date,
                total_steps=day.steps.steps if day.steps else 0,
                total_distance_meters=day.steps.distance_meters if day.steps else 0,
                total_calories=day.steps.calories if day.steps else 0,
                sleep_minutes=day.sleep.total_minutes if day.sleep else 0,
                deep_sleep_minutes=day.sleep.deep_sleep_minutes if day.sleep else 0,
                light_sleep_minutes=day.sleep.light_sleep_minutes if day.sleep else 0,
                rem_sleep_minutes=day.sleep.rem_sleep_minutes if day.sleep else 0,
                resting_heart_rate=resting_hr,
                max_heart_rate=max_hr,
                min_heart_rate=resting_hr,
            ))

        return summaries

    # ----------------------------------------------------------
    # Events endpoints (stress, SpO2, PAI, readiness)
    # ----------------------------------------------------------

    def get_stress_data(
        self,
        start_date: date,
        end_date: date,
    ) -> list[StressData]:
        """Get stress data."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        items = self._get_events("all_day_stress", start_dt, end_dt)

        stress_list = []
        for item in items:
            date_str = self._date_str_from_ts(item.get("timestamp", 0))
            readings = []
            data_points = self._safe_json_loads(item.get("data", "[]"), [])
            if isinstance(data_points, list):
                for point in data_points:
                    point_ts = self._normalize_timestamp(point.get("time", 0))
                    readings.append(StressReading(
                        timestamp=datetime.fromtimestamp(point_ts),
                        value=point.get("value", 0),
                    ))

            stress_list.append(StressData(
                date=date_str,
                min_stress=int(item.get("minStress", 0)),
                max_stress=int(item.get("maxStress", 0)),
                avg_stress=int(item.get("avgStress", 0)),
                relax_proportion=int(item.get("relaxProportion", 0)),
                normal_proportion=int(item.get("normalProportion", 0)),
                medium_proportion=int(item.get("mediumProportion", 0)),
                high_proportion=int(item.get("highProportion", 0)),
                readings=readings,
            ))

        return stress_list

    def get_spo2_data(
        self,
        start_date: date,
        end_date: date,
    ) -> list[SpO2Data]:
        """Get blood oxygen (SpO2) data."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        items = self._get_events(
            "blood_oxygen", start_dt, end_dt,
            extra_params={"timeZone": self._config.timezone},
        )

        daily_data: dict[str, SpO2Data] = {}

        for item in items:
            subtype = item.get("subType", "")

            if subtype == "odi":
                ts = self._normalize_timestamp(item.get("timestamp", 0))
                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                if date_str not in daily_data:
                    daily_data[date_str] = SpO2Data(date=date_str)
                daily_data[date_str].odi = float(item.get("odi", 0))
                daily_data[date_str].odi_count = int(item.get("odiNum", 0))
                score = item.get("score")
                if score and int(score) > 0:
                    daily_data[date_str].sleep_score = int(score)

            elif subtype == "click":
                extra_raw = item.get("extra")
                extra = self._safe_json_loads(extra_raw, {}) if isinstance(extra_raw, str) else (extra_raw or {})
                if not isinstance(extra, dict):
                    extra = {}

                spo2_val = item.get("spo2", item.get("value", 0)) or extra.get("spo2")
                if not spo2_val:
                    history = extra.get("spo2History")
                    if isinstance(history, list):
                        for val in reversed(history):
                            if val:
                                spo2_val = val
                                break

                reading_ts = extra.get("timestamp", item.get("timestamp", 0))
                reading_ts = self._normalize_timestamp(reading_ts)
                date_str = datetime.fromtimestamp(reading_ts).strftime("%Y-%m-%d")

                if date_str not in daily_data:
                    daily_data[date_str] = SpO2Data(date=date_str)

                if spo2_val:
                    reading_type = "auto" if extra.get("isAuto") else "manual"
                    daily_data[date_str].readings.append(SpO2Reading(
                        timestamp=datetime.fromtimestamp(reading_ts),
                        spo2=int(spo2_val),
                        reading_type=reading_type,
                    ))

            elif subtype == "osa_event":
                extra_raw = item.get("extra")
                extra = self._safe_json_loads(extra_raw, {}) if isinstance(extra_raw, str) else (extra_raw or {})
                if not isinstance(extra, dict):
                    extra = {}

                event_ts = self._normalize_timestamp(
                    extra.get("timestamp", item.get("timestamp", 0))
                )
                date_str = datetime.fromtimestamp(event_ts).strftime("%Y-%m-%d")

                if date_str not in daily_data:
                    daily_data[date_str] = SpO2Data(date=date_str)

                daily_data[date_str].osa_events.append(OSAEvent(
                    timestamp=datetime.fromtimestamp(event_ts),
                    spo2_decrease=int(extra["spo2_decrease"]) if extra.get("spo2_decrease") is not None else None,
                    spo2_samples=[int(v) for v in (extra.get("spo2") or []) if v is not None],
                    hr_samples=[int(v) for v in (extra.get("hr") or []) if v is not None],
                ))

        return list(daily_data.values())

    def get_pai_data(
        self,
        start_date: date,
        end_date: date,
    ) -> list[PAIData]:
        """Get PAI data."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        items = self._get_events("PaiHealthInfo", start_dt, end_dt)

        pai_list = []
        for item in items:
            date_str = self._date_str_from_ts(item.get("timestamp", 0))
            pai_list.append(PAIData(
                date=date_str,
                total_pai=float(item.get("totalPai", 0)),
                daily_pai=float(item.get("dailyPai", 0)),
                resting_hr=int(item.get("restHr", 0)) or None,
                max_hr=int(item.get("maxHr", 0)) or None,
                low_zone_minutes=int(item.get("lowZoneMinutes", 0)),
                medium_zone_minutes=int(item.get("mediumZoneMinutes", 0)),
                high_zone_minutes=int(item.get("highZoneMinutes", 0)),
            ))

        return pai_list

    def get_readiness_data(
        self,
        start_date: date,
        end_date: date,
    ) -> list[ReadinessData]:
        """Get readiness/recovery data."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        items = self._get_events("readiness", start_dt, end_dt)

        daily_data: dict[str, ReadinessData] = {}

        def _int(val: Any) -> Optional[int]:
            if val is None or val == "" or val == "255":
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        def _float(val: Any) -> Optional[float]:
            if val is None or val == "":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        for item in items:
            if item.get("subType") != "watch_score":
                continue

            ts = self._normalize_timestamp(int(item.get("timestamp", 0)))
            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

            readiness = ReadinessData(
                date=date_str,
                readiness_score=_int(item.get("rdnsScore")),
                readiness_insight=_int(item.get("rdnsInsight")),
                rhr_score=_int(item.get("rhrScore")),
                rhr_baseline=_int(item.get("rhrBaseline")),
                sleep_rhr=_int(item.get("sleepRHR")),
                hrv_score=_int(item.get("hrvScore")),
                hrv_baseline=_int(item.get("hrvBaseline")),
                sleep_hrv=_int(item.get("sleepHRV")),
                skin_temp_score=_int(item.get("skinTempScore")),
                skin_temp_baseline=_float(item.get("skinTempBaseLine")),
                skin_temp_calibrated=_float(item.get("skinTempCalibrated")),
                mental_score=_int(item.get("mentScore")),
                mental_baseline=_int(item.get("mentBaseLine")),
                physical_score=_int(item.get("phyScore")),
                physical_baseline=_int(item.get("phyBaseline")),
                ahi_score=_int(item.get("ahiScore")),
                ahi_baseline=_float(item.get("ahiBaseline")),
                afib_score=_int(item.get("afibScore")),
                afib_baseline=_int(item.get("afibBaseLine")),
            )

            # Keep the record with the most complete data per day
            if date_str not in daily_data:
                daily_data[date_str] = readiness
            else:
                existing = daily_data[date_str]
                existing_count = sum(1 for v in existing.model_dump().values() if v is not None)
                new_count = sum(1 for v in readiness.model_dump().values() if v is not None)
                if new_count > existing_count:
                    daily_data[date_str] = readiness

        return sorted(daily_data.values(), key=lambda x: x.date)

    # ----------------------------------------------------------
    # Workout data
    # ----------------------------------------------------------

    def get_workouts(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[Workout]:
        """Get workout history."""
        params: dict[str, Any] = {}
        workouts: list[Workout] = []
        seen_track_ids: set[str] = set()
        next_track_id = None

        while True:
            if next_track_id:
                params["stopTrackId"] = str(next_track_id)

            result = self._get_json(WORKOUT_HISTORY_PATH, params)

            if result.get("code") != 1:
                raise ZeppClientError(f"API error: {result.get('message', 'Unknown error')}")

            data = result.get("data", {})
            summary_list = data.get("summary", [])
            new_items = 0

            for item in summary_list:
                track_id = str(item.get("trackid", ""))
                if track_id and track_id in seen_track_ids:
                    continue
                if track_id:
                    seen_track_ids.add(track_id)
                new_items += 1

                try:
                    end_ts = int(item.get("end_time", 0))
                    duration = int(item.get("run_time", 0))
                    start_ts = end_ts - duration
                    start_time = datetime.fromtimestamp(start_ts)
                    end_time = datetime.fromtimestamp(end_ts)

                    if start_date and start_time.date() < start_date:
                        continue
                    if end_date and start_time.date() > end_date:
                        continue

                    workout_type = int(item.get("type", 0))
                    te = item.get("te")
                    training_effect = te / 10.0 if te and te > 0 else None

                    avg_hr = item.get("avg_heart_rate")
                    max_hr = item.get("max_heart_rate")
                    min_hr = item.get("min_heart_rate")

                    vo2 = item.get("VO2_max")
                    vo2_max = int(vo2) if vo2 and int(vo2) > 0 else None

                    load = item.get("exercise_load")
                    exercise_load = int(load) if load and int(load) > 0 else None

                    # Parse heart rate zones
                    hr_zones = []
                    hr_range = item.get("heart_range", "")
                    if hr_range:
                        zone_names = ["Very Light", "Light", "Moderate", "Hard", "Maximum", "Extreme"]
                        for i, zone_str in enumerate(hr_range.split(";")):
                            if zone_str:
                                parts = zone_str.split(",")
                                if len(parts) == 2:
                                    try:
                                        seconds = int(parts[0])
                                        max_hr_zone = int(parts[1])
                                        if seconds > 0:
                                            hr_zones.append(HeartRateZone(
                                                zone=i + 1,
                                                zone_name=zone_names[i] if i < len(zone_names) else f"Zone {i+1}",
                                                seconds=seconds,
                                                max_hr=max_hr_zone,
                                            ))
                                    except (ValueError, TypeError):
                                        pass

                    workouts.append(Workout(
                        track_id=track_id or "",
                        workout_type=workout_type,
                        workout_name=WORKOUT_TYPES.get(workout_type, f"unknown_{workout_type}"),
                        start_time=start_time,
                        end_time=end_time,
                        duration_seconds=duration,
                        distance_meters=float(item.get("dis", 0) or 0),
                        calories=float(item.get("calorie", 0) or 0),
                        avg_heart_rate=int(float(avg_hr)) if avg_hr else None,
                        max_heart_rate=int(float(max_hr)) if max_hr else None,
                        min_heart_rate=int(float(min_hr)) if min_hr else None,
                        avg_pace=float(item.get("avg_pace", 0) or 0) or None,
                        total_steps=int(float(item.get("total_step", 0) or 0)),
                        training_effect=training_effect,
                        vo2_max=vo2_max,
                        exercise_load=exercise_load,
                        hr_zones=hr_zones,
                    ))
                except (ValueError, TypeError):
                    continue

            next_track_id = data.get("next")
            if next_track_id in (None, "", 0, -1, "0", "-1"):
                break
            if str(next_track_id) in seen_track_ids:
                break
            if new_items == 0:
                break

        return workouts

    # ----------------------------------------------------------
    # Additional endpoints (from zepp-health-cli)
    # ----------------------------------------------------------

    def get_sport_load(
        self,
        start_date: date,
        end_date: date,
    ) -> list[SportLoadRecord]:
        """Get sport load data."""
        path = SPORT_STATS_PATH.format(user_id=self._user_id, stat_type="SPORT_LOAD")
        params = {
            "startDay": start_date.isoformat(),
            "endDay": end_date.isoformat(),
            "limit": 900,
            "isReverse": "true",
        }
        result = self._get_json(path, params)
        items = result.get("items", [])

        records = []
        for item in items:
            records.append(SportLoadRecord(
                date=item.get("dayId", ""),
                wtl_sum=item.get("wtlSum"),
                current_day_train_load=item.get("currnetDayTrainLoad"),
            ))
        return records

    def get_vo2_max(
        self,
        start_date: date,
        end_date: date,
    ) -> list[VO2MaxRecord]:
        """Get VO2 max data."""
        path = SPORT_STATS_PATH.format(user_id=self._user_id, stat_type="VO2_MAX")
        params = {
            "startDay": start_date.isoformat(),
            "endDay": end_date.isoformat(),
            "limit": 900,
            "isReverse": "true",
        }
        result = self._get_json(path, params)
        items = result.get("items", [])

        records = []
        for item in items:
            vo2 = item.get("vo2Max")
            if vo2 and int(vo2) > 0:
                records.append(VO2MaxRecord(
                    date=item.get("dayId", ""),
                    vo2_max=int(vo2),
                    device_id=item.get("deviceId"),
                ))
        return records

    def get_heart_rate_samples(
        self,
        start_ts: int,
        end_ts: int,
        *,
        limit: int = 1000,
    ) -> list[HeartRateData]:
        """Get heart rate sample data."""
        params = {
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": limit,
            "type": 2,
        }
        result = self._get_json(
            HEART_RATE_PATH.format(user_id=self._user_id), params
        )
        items = result.get("items", [])

        readings = []
        for item in items:
            ts = self._normalize_timestamp(item.get("timestamp", item.get("time", 0)))
            bpm = item.get("heartRate", item.get("hr", 0))
            if ts and bpm:
                readings.append(HeartRateData(
                    timestamp=datetime.fromtimestamp(ts),
                    bpm=int(bpm),
                ))
        return readings

    def get_weight_records(
        self,
        start_ts: int,
        end_ts: int,
        *,
        limit: int = 300,
    ) -> list[WeightRecord]:
        """Get weight records."""
        params = {
            "fromTime": start_ts,
            "toTime": end_ts,
            "limit": limit,
            "isForward": 0,
        }
        result = self._get_json(
            WEIGHT_PATH.format(user_id=self._user_id), params
        )
        items = result.get("items", [])

        records = []
        for item in items:
            ts = self._normalize_timestamp(item.get("timestamp", 0))
            weight = item.get("weight", 0)
            if ts and weight:
                records.append(WeightRecord(
                    timestamp=datetime.fromtimestamp(ts),
                    weight_kg=float(weight) / 1000 if weight > 100 else float(weight),
                    bmi=item.get("bmi"),
                    body_fat_pct=item.get("fat"),
                    muscle_mass=item.get("muscle"),
                ))
        return records

    def get_blood_pressure(
        self,
        *,
        days: int = 7,
        to_date: Optional[date] = None,
    ) -> list[BloodPressureRecord]:
        """Get blood pressure data."""
        td = to_date or date.today()
        params = {
            "days": days,
            "sourceArrayStr": "com.huami.midong.associated,com.huami.midong",
            "toDate": td.isoformat(),
        }
        result = self._get_json(BLOOD_PRESSURE_PATH, params)
        items = result.get("items", [])

        records = []
        for item in items:
            ts = self._normalize_timestamp(item.get("timestamp", 0))
            systolic = item.get("systolic", item.get("sbp", 0))
            diastolic = item.get("diastolic", item.get("dbp", 0))
            if ts and systolic and diastolic:
                records.append(BloodPressureRecord(
                    timestamp=datetime.fromtimestamp(ts),
                    systolic=int(systolic),
                    diastolic=int(diastolic),
                    pulse=item.get("pulse"),
                ))
        return records

    def get_body_battery(
        self,
        start_ts: int,
        end_ts: int,
    ) -> list[BodyBatteryReading]:
        """Get body battery data.

        The value structure is a dict containing a samples array.
        Each sample: {s: offset_ms, total: total_charge, mental: mental_charge, physical: physical_charge}
        """
        items = self._get_v2_events(
            "Charge", "real_data", start_ts, end_ts,
        )
        readings = []
        for item in items:
            ts = self._normalize_timestamp(item.get("timestamp", 0))
            value = item.get("value", 0)

            if not ts:
                continue

            # value may be a dict (containing samples) or a plain number
            if isinstance(value, dict):
                samples = value.get("samples", [])
                if samples:
                    # Take the first valid sample (total != 255; 255 means invalid)
                    valid_sample = None
                    for s in samples:
                        t = s.get("total", 255)
                        if t != 255 and t > 0:
                            valid_sample = s
                            break
                    if not valid_sample:
                        valid_sample = samples[0]
                    total = valid_sample.get("total", 0)
                    # The API returns total with a -3 offset; the app adds 3 to restore it
                    display_value = int(total) + 3 if total != 255 else 0
                    readings.append(BodyBatteryReading(
                        timestamp=datetime.fromtimestamp(ts),
                        value=display_value,
                    ))
            elif isinstance(value, (int, float)):
                readings.append(BodyBatteryReading(
                    timestamp=datetime.fromtimestamp(ts),
                    value=int(value),
                ))
        return readings

    def get_hrv(
        self,
        start_ts: int,
        end_ts: int,
        *,
        hrv_type: str = "sdnn",
    ) -> list[HRVReading]:
        """Get HRV data.

        hrv_type: "sdnn" or "rmssd"
        """
        event_type = "hrv_sdnn" if hrv_type == "sdnn" else "HRVRMSSD"
        items = self._get_v2_events(
            event_type, "real_data", start_ts, end_ts,
        )
        readings = []
        for item in items:
            ts = self._normalize_timestamp(item.get("timestamp", 0))
            value = item.get("value", 0)
            if not ts or not value:
                continue
            # value may be a dict or a number
            if isinstance(value, dict):
                # Try extracting from common fields
                v = value.get("value") or value.get("hrv") or value.get("total", 0)
            else:
                v = value
            if v:
                readings.append(HRVReading(
                    timestamp=datetime.fromtimestamp(ts),
                    hrv_value=int(float(v)),
                    reading_type=hrv_type,
                ))
        return readings

    def get_respiratory_rate(
        self,
        start_ts: int,
        end_ts: int,
    ) -> list[RespiratoryRateReading]:
        """Get respiratory rate data."""
        items = self._get_v2_events(
            "RespiratoryRate", "real_data", start_ts, end_ts,
        )
        readings = []
        for item in items:
            ts = self._normalize_timestamp(item.get("timestamp", 0))
            value = item.get("value", 0)
            if not ts or not value:
                continue
            # value may be a dict (containing measurements) or a number
            if isinstance(value, dict):
                v = value.get("value") or value.get("rpm") or value.get("total", 0)
            else:
                v = value
            if v:
                readings.append(RespiratoryRateReading(
                    timestamp=datetime.fromtimestamp(ts),
                    breaths_per_minute=float(v),
                ))
        return readings
