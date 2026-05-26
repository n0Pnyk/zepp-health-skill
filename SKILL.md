---
name: zepp-health
description: >
  This skill should be used when the user asks about their health data,
  wants a health analysis, health report, sleep analysis, recovery status,
  training readiness, body battery, stress level, or says "健康", "身体",
  "睡眠", "恢复", "训练", "运动", "心率", "HRV", "压力", "血氧".
---

# Zepp Health Analysis Skill

Fetch health data from the Zepp/Amazfit API and provide personalized analysis and recommendations.

## Data Fetching

Run the following command to get a structured health data snapshot:

```bash
python3 {skill_dir}/scripts/health_snapshot.py
```

Specify a date:

```bash
python3 {skill_dir}/scripts/health_snapshot.py --date YYYY-MM-DD
```

Output is JSON containing: today's data, 7-day trends, workout records, and score breakdowns.

## Configuration

Configure Zepp API authentication (by priority):
1. `{skill_dir}/config.json` — `{ "app_token": "...", "user_id": "...", "host": "api-mifit-cn3.zepp.com" }`
2. Environment variable `ZEPP_COOKIE` — cookie string
3. Environment variables `ZEPP_APP_TOKEN` + `ZEPP_USER_ID`

Get cookie: visit https://user.huami.com/privacy2/#/confirmExportData, log in, open DevTools (F12) → Network, refresh, find a request to `api-mifit*.zepp.com`, copy `apptoken` from headers and `userid` from URL/params.

## Analysis Framework

After fetching data, reference `{skill_dir}/references/health_analysis_guide.md` for analysis.

Core analysis dimensions:

### 1. Recovery Status
- HRV vs personal baseline (trends matter more than absolute values)
- RHR vs personal baseline
- 3 consecutive days of HRV down + RHR up = fatigue signal

### 2. Sleep Quality
- Deep sleep 15-20%, REM 20-25% is normal
- Wake count <3 is ideal
- Sleep efficiency >85% is ideal

### 3. Training Load
- Acute:chronic ratio 0.8-1.3 is healthy
- >1.5 indicates overtraining risk

### 4. Body Battery
- >70 suitable for training, <30 needs rest

### 5. Stress & SpO2
- Average stress <40 is low, >60 needs attention
- SpO2 <93% should recommend medical consultation

## Output Format

Structure the analysis as follows:

1. **Data Overview** — Key metrics summary
2. **Trend Analysis** — 7-day changes and anomalies
3. **Cross-Analysis** — Multi-metric correlation
4. **Personalized Recommendations** — Specific, actionable advice
5. **Today's Actions** — Concrete actions based on current state

## Safety Boundaries

Must recommend seeking medical attention (without diagnosing) when:
- SpO2 < 90%
- Resting heart rate anomaly exceeds 20% above baseline
- HRV persistently low (30%+ below baseline)
- User describes chest pain, breathing difficulty, or other symptoms

Always stay within health advisory scope. Never provide medical diagnoses.
