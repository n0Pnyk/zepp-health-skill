"""输出格式化。

支持三种输出格式：
- JSON: 给 hermes-agent 使用
- Terminal: rich 格式化终端输出
- Morning Briefing: 自然语言早报文本
"""

from __future__ import annotations

from zepp_health.models import HealthReport


def to_json(report: HealthReport, indent: int = 2) -> str:
    """返回 JSON 格式字符串。"""
    return report.model_dump_json(indent=indent)


def to_json_compact(report: HealthReport) -> str:
    """返回紧凑单行 JSON（适合管道传输）。"""
    return report.model_dump_json()


def _score_bar(score: int | None, width: int = 20) -> str:
    """生成文本进度条。"""
    if score is None:
        return "N/A"
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {score}/100"


def _score_emoji(score: int | None) -> str:
    """根据分数返回状态标识。"""
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
    """返回终端友好的文本报告。"""
    lines: list[str] = []

    # 标题
    lines.append(f"═══ 健康报告 {report.date} ═══")
    lines.append("")

    # 综合分
    if report.overall_score is not None:
        emoji = _score_emoji(report.overall_score)
        lines.append(f"综合健康分: {emoji} {report.overall_score}/100")
    else:
        lines.append("综合健康分: N/A")
    lines.append("")

    # 各维度评分
    lines.append("── 评分明细 ──")

    if report.recovery:
        r = report.recovery
        lines.append(f"恢复 {_score_emoji(r.score)} {_score_bar(r.score)}")
        if r.hrv_component is not None:
            lines.append(f"  HRV 分项: {r.hrv_component}/100  RHR 分项: {r.rhr_component or 'N/A'}/100")
        lines.append(f"  趋势: {r.trend}  疲劳信号: {'是' if r.fatigue_signal else '否'}")
        if r.details:
            lines.append(f"  {r.details}")

    if report.sleep_quality:
        sq = report.sleep_quality
        lines.append(f"睡眠 {_score_emoji(sq.score)} {_score_bar(sq.score)}")
        if sq.details:
            lines.append(f"  {sq.details}")

    if report.exertion and report.exertion.zone != "inactive":
        e = report.exertion
        lines.append(f"训练 {_score_emoji(e.score)} {_score_bar(e.score)}")
        lines.append(f"  7天负荷: {e.acute_load_7d:.0f}  28天周均: {e.chronic_load_28d:.0f}  比率: {e.ratio:.2f}")
        lines.append(f"  区间: {e.zone}")

    lines.append("")

    # 原始指标
    if report.raw_metrics:
        lines.append("── 原始指标 ──")
        m = report.raw_metrics
        if "steps" in m:
            lines.append(f"  步数: {m['steps']}  距离: {m.get('distance_meters', 0)}m  卡路里: {m.get('calories', 0)}kcal")
        if "sleep_minutes" in m:
            h = m["sleep_minutes"] // 60
            mins = m["sleep_minutes"] % 60
            lines.append(f"  睡眠: {h}h{mins}m  深睡: {m.get('deep_sleep_minutes', 0)}m  REM: {m.get('rem_sleep_minutes', 0)}m")
        if "resting_heart_rate" in m:
            lines.append(f"  静息心率: {m['resting_heart_rate']}bpm  睡眠HRV: {m.get('sleep_hrv', 'N/A')}ms")
        if "avg_stress" in m:
            lines.append(f"  压力: {m['avg_stress']}/100  血氧: {m.get('avg_spo2', 'N/A')}%")
        lines.append("")

    # 建议
    if report.recommendations:
        lines.append("── 健康建议 ──")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

    lines.append(f"生成时间: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(lines)


def to_morning_briefing(report: HealthReport) -> str:
    """返回自然语言早报文本（适合 hermes-agent 推送）。"""
    lines: list[str] = []

    # 综合分
    if report.overall_score is not None:
        emoji = _score_emoji(report.overall_score)
        lines.append(f"今日健康分: {report.overall_score}/100 {emoji}")
    else:
        lines.append("今日健康分: 数据不足")
    lines.append("")

    # 恢复
    if report.recovery:
        r = report.recovery
        trend_desc = {"improving": "上升", "declining": "下降", "stable": "稳定"}.get(r.trend, r.trend)
        lines.append(f"恢复: {r.score}/100")
        if r.details:
            lines.append(f"  {r.details}")
        lines.append(f"  HRV 趋势: {trend_desc}")
        if r.fatigue_signal:
            lines.append("  ⚠️ 检测到疲劳信号")

    # 睡眠
    if report.sleep_quality:
        sq = report.sleep_quality
        lines.append(f"睡眠: {sq.score}/100")
        if sq.details:
            lines.append(f"  {sq.details}")

    # 训练负荷
    if report.exertion and report.exertion.zone != "inactive":
        e = report.exertion
        lines.append(f"训练负荷: {e.score}/100（{e.zone}）")

    # 压力和血氧
    m = report.raw_metrics
    if "avg_stress" in m:
        lines.append(f"压力: {m['avg_stress']}/100")
    if "avg_spo2" in m:
        lines.append(f"血氧: {m['avg_spo2']}%")

    # 建议
    if report.recommendations:
        lines.append("")
        lines.append("建议:")
        for rec in report.recommendations:
            lines.append(f"  • {rec}")

    return "\n".join(lines)
