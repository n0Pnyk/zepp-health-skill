"""Output formatting.

Supports three output formats:
- JSON: for hermes-agent consumption
- Terminal: rich-formatted terminal output
- Morning Briefing: natural language morning report text
"""

from __future__ import annotations

from zepp_health.models import HealthReport


def to_json(report: HealthReport, indent: int = 2) -> str:
    """Return JSON formatted string."""
    return report.model_dump_json(indent=indent)


def to_json_compact(report: HealthReport) -> str:
    """Return compact single-line JSON (suitable for piping)."""
    return report.model_dump_json()


def _score_bar(score: int | None, width: int = 20) -> str:
    """Generate a text progress bar."""
    if score is None:
        return "N/A"
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {score}/100"


def _score_emoji(score: int | None) -> str:
    """Return a status indicator based on score."""
    if score is None:
        return "⚪"
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    elif score >= 40:
        return "🟠"
    return "🔴"


def to_terminal(report: HealthReport) -> str:
    """Return a terminal-friendly text report."""
    lines: list[str] = []

    # Title
    lines.append(f"═══ Health Report {report.date} ═══")
    lines.append("")

    # Overall score
    if report.overall_score is not None:
        emoji = _score_emoji(report.overall_score)
        lines.append(f"Overall Health Score: {emoji} {report.overall_score}/100")
    else:
        lines.append("Overall Health Score: N/A")
    lines.append("")

    # Dimension scores
    lines.append("── Score Breakdown ──")

    if report.recovery:
        r = report.recovery
        lines.append(f"Recovery {_score_emoji(r.score)} {_score_bar(r.score)}")
        if r.hrv_component is not None:
            lines.append(f"  HRV Component: {r.hrv_component}/100  RHR Component: {r.rhr_component or 'N/A'}/100")
        lines.append(f"  Trend: {r.trend}  Fatigue Signal: {'Yes' if r.fatigue_signal else 'No'}")
        if r.details:
            lines.append(f"  {r.details}")

    if report.sleep_quality:
        sq = report.sleep_quality
        lines.append(f"Sleep {_score_emoji(sq.score)} {_score_bar(sq.score)}")
        if sq.details:
            lines.append(f"  {sq.details}")

    if report.exertion and report.exertion.zone != "inactive":
        e = report.exertion
        lines.append(f"Training {_score_emoji(e.score)} {_score_bar(e.score)}")
        lines.append(f"  7-Day Load: {e.acute_load_7d:.0f}  28-Day Weekly Avg: {e.chronic_load_28d:.0f}  Ratio: {e.ratio:.2f}")
        lines.append(f"  Zone: {e.zone}")

    lines.append("")

    # Raw metrics
    if report.raw_metrics:
        lines.append("── Raw Metrics ──")
        m = report.raw_metrics
        if "steps" in m:
            lines.append(f"  Steps: {m['steps']}  Distance: {m.get('distance_meters', 0)}m  Calories: {m.get('calories', 0)}kcal")
        if "sleep_minutes" in m:
            h = m["sleep_minutes"] // 60
            mins = m["sleep_minutes"] % 60
            lines.append(f"  Sleep: {h}h{mins}m  Deep Sleep: {m.get('deep_sleep_minutes', 0)}m  REM: {m.get('rem_sleep_minutes', 0)}m")
        if "resting_heart_rate" in m:
            lines.append(f"  Resting HR: {m['resting_heart_rate']}bpm  Sleep HRV: {m.get('sleep_hrv', 'N/A')}ms")
        if "avg_stress" in m:
            lines.append(f"  Stress: {m['avg_stress']}/100  SpO2: {m.get('avg_spo2', 'N/A')}%")
        lines.append("")

    # Recommendations
    if report.recommendations:
        lines.append("── Recommendations ──")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

    lines.append(f"Generated at: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(lines)


def to_morning_briefing(report: HealthReport) -> str:
    """Return a natural language morning briefing (suitable for hermes-agent push)."""
    lines: list[str] = []

    # Overall score
    if report.overall_score is not None:
        emoji = _score_emoji(report.overall_score)
        lines.append(f"Today's Health Score: {report.overall_score}/100 {emoji}")
    else:
        lines.append("Today's Health Score: Insufficient Data")
    lines.append("")

    # Recovery
    if report.recovery:
        r = report.recovery
        trend_desc = {"improving": "Rising", "declining": "Falling", "stable": "Stable"}.get(r.trend, r.trend)
        lines.append(f"Recovery: {r.score}/100")
        if r.details:
            lines.append(f"  {r.details}")
        lines.append(f"  HRV Trend: {trend_desc}")
        if r.fatigue_signal:
            lines.append("  ⚠️ Fatigue signal detected")

    # Sleep
    if report.sleep_quality:
        sq = report.sleep_quality
        lines.append(f"Sleep: {sq.score}/100")
        if sq.details:
            lines.append(f"  {sq.details}")

    # Training load
    if report.exertion and report.exertion.zone != "inactive":
        e = report.exertion
        lines.append(f"Training Load: {e.score}/100 ({e.zone})")

    # Stress and SpO2
    m = report.raw_metrics
    if "avg_stress" in m:
        lines.append(f"Stress: {m['avg_stress']}/100")
    if "avg_spo2" in m:
        lines.append(f"SpO2: {m['avg_spo2']}%")

    # Recommendations
    if report.recommendations:
        lines.append("")
        lines.append("Recommendations:")
        for rec in report.recommendations:
            lines.append(f"  • {rec}")

    return "\n".join(lines)
