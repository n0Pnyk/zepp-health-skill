# Zepp Health Skill

Claude Code Skill for LLM-driven analysis of Zepp/Amazfit health data with personalized recommendations.

Works with [OpenClaw](https://github.com/anthropics/openclaw) or hermes-agent.

## Quick Start

```bash
git clone https://github.com/n0Pnyk/zepp-health-skill.git
cd zepp-health-skill

# Install dependencies
pip install httpx pydantic rich python-dotenv

# Configure authentication (choose one)
cp config.example.json config.json
# Edit config.json with your app_token and user_id

# Or use environment variables
export ZEPP_COOKIE="userid=xxx; apptoken=xxx; region=1"
```

Get your cookie: log in to [app.zepp.com](https://app.zepp.com), copy the Cookie from browser developer tools (F12 → Network).

## Usage

Say any of these in OpenClaw or hermes-agent:

- "Analyze my health data"
- "How did I sleep last night?"
- "What's my recovery status?"
- "Check my training load"

The LLM will automatically call `scripts/health_snapshot.py` to fetch data and reference `references/health_analysis_guide.md` for analysis.

## Contents

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill definition, triggers, and analysis framework |
| `scripts/health_snapshot.py` | Data fetch script, outputs JSON |
| `references/health_analysis_guide.md` | LLM analysis reference guide |
| `zepp_health/` | Core library (data fetching, normalization, scoring) |

## Manual Testing

```bash
python3 scripts/health_snapshot.py                  # Today's data
python3 scripts/health_snapshot.py --date 2026-05-18 # Specific date
```

## CLI vs Skill

| Mode | Recommendations | Personalization | Dependencies |
|------|----------------|-----------------|--------------|
| [zepp-health CLI](https://github.com/n0Pnyk/zepp-health) | Rule engine | Generic | Python |
| zepp-health-skill | LLM analysis | Highly personalized | LLM service |

## Syncing Core Library

When the CLI repo updates the core library:

```bash
./sync_from_cli.sh
```

## Safety Boundaries

The LLM will recommend seeking medical attention (without diagnosing) when:
- SpO2 < 90%
- Resting heart rate anomaly exceeds 20% above baseline
- HRV persistently low (30%+ below baseline)

## Disclaimer

This tool is for informational purposes only and does not constitute medical advice. Consult a healthcare professional for any health concerns.

## License

[MIT License](LICENSE)
