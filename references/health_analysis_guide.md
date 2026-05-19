# Health Data Analysis Guide

This document provides a reference framework for LLM-driven health data analysis.

## Metric Interpretation

### HRV (Heart Rate Variability)

- **Meaning**: Reflects autonomic nervous system status; a core indicator of recovery and stress
- **Normal range**: Highly individual, 20-100ms can all be normal
- **Key**: Compare against personal baseline; trends matter more than absolute values
- **Above baseline**: Good recovery, parasympathetic activity dominant
- **Below baseline**: Stress, fatigue, illness precursor, alcohol effects, etc.
- **3+ consecutive days below baseline by 10%+**: Needs attention

### Resting Heart Rate (RHR)

- **Meaning**: Heart rate at rest, reflects cardiovascular efficiency
- **Normal range**: 40-100 bpm, athletes may be lower
- **Below baseline**: Good cardiovascular efficiency, good recovery
- **Above baseline**: Fatigue, stress, illness, overtraining
- **3+ consecutive days above baseline by 5bpm+**: Needs attention

### Sleep

| Metric | Normal Range | Too Low | Too High |
|--------|-------------|---------|----------|
| Total duration | 7-9 hours | Sleep deprivation | Possible hypersomnia |
| Deep sleep % | 15-20% | Insufficient recovery | — |
| REM % | 20-25% | Memory/mood impact | — |
| Wake count | <3 | — | Sleep fragmentation |
| Sleep efficiency | >85% | Difficulty falling asleep | — |

### Body Battery

- 0-100 scale
- >70: Suitable for moderate-to-high intensity activity
- 30-70: Moderate, light activity
- <30: Needs rest and recovery

### Stress

- 0-100 scale
- <40: Low stress, predominantly relaxed
- 40-60: Moderate stress
- >60: High stress, needs attention to relaxation

### SpO2 (Blood Oxygen)

- Normal: 95-100%
- 93-95%: Slightly low, monitor breathing
- <93%: Recommend medical consultation
- ODI (Oxygen Desaturation Index): >5 events/hour needs attention

### Training Load

| Zone | Acute:Chronic Ratio | Meaning |
|------|---------------------|---------|
| detraining | <0.8 | Under-training |
| maintaining | 0.8-1.0 | Maintaining fitness |
| productive | 1.0-1.3 | Effective progression |
| overreaching | 1.3-1.5 | High load |
| high_risk | >1.5 | Overtraining risk |

## Cross-Analysis Patterns

### Overtraining Signal
- HRV persistently down + RHR persistently up + sleep quality down + training load up
- Action: Schedule 2-3 days of active recovery immediately

### Illness Precursor
- HRV sudden large drop (>20%) + RHR elevated + body battery low
- Action: Rest and monitor symptoms

### Alcohol Impact
- Deep sleep proportion down + REM down + HRV down + RHR up (day after drinking)
- Action: Reduce alcohol intake, especially before sleep

### Jet Lag / Schedule Disruption
- Sleep efficiency down + sleep onset latency up + HRV highly variable
- Action: Establish consistent sleep/wake schedule

### Good Recovery
- HRV above baseline + RHR below baseline + body battery high + sleep quality good
- Action: Suitable for high-intensity training

## Recommendation Principles

1. **Specific and actionable**: "Go to bed before 10pm tonight" > "Get more sleep"
2. **Severity grading**: Urgent (seek medical attention), Important (adjust immediately), General (daily advice)
3. **No repetition**: Mention each issue only once
4. **Consider trends**: A single-day anomaly may be coincidence; consecutive anomalies need attention
5. **Personalize**: Adjust recommendations based on user's exercise habits and goals
6. **Positive reinforcement**: Give positive feedback when metrics are good

## Output Structure Template

```
## Data Overview
[Key metrics summary table]

## 7-Day Trends
[Trend changes and anomaly markers]

## Cross-Analysis
[Multi-metric correlation analysis]

## Personalized Recommendations
1. [Most important recommendation]
2. [Secondary recommendation]
3. ...

## Today's Actions
[Concrete action items based on current state]
```
