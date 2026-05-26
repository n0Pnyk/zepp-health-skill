# Zepp Health Skill

[English](#english) | [中文](#中文)

---

## English

Claude Code Skill for LLM-driven analysis of Zepp/Amazfit health data with personalized recommendations.

Works with [OpenClaw](https://github.com/anthropics/openclaw) or hermes-agent.

### Quick Start

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

Get your cookie: visit [user.huami.com/privacy2](https://user.huami.com/privacy2/#/confirmExportData), log in, open browser DevTools (F12) → Network tab, refresh the page, find a request to `api-mifit*.zepp.com`, and copy `apptoken` from request headers and `userid` from the URL or query parameters.

> **Note:** `app.zepp.com` is no longer accessible. The correct URL is `user.huami.com/privacy2`. Also, `apptoken` and `userid` are injected via the Zepp App's JSBridge (KeepAlive SDK) only when opened inside the Zepp mobile app's WebView. If you open the page in a regular desktop browser, the token will be empty. Use the method above — open DevTools on the `user.huami.com` page directly in your desktop browser to capture the token from API requests.

### Usage

Say any of these in OpenClaw or hermes-agent:

- "Analyze my health data"
- "How did I sleep last night?"
- "What's my recovery status?"
- "Check my training load"

The LLM will automatically call `scripts/health_snapshot.py` to fetch data and reference `references/health_analysis_guide.md` for analysis.

### Contents

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill definition, triggers, and analysis framework |
| `scripts/health_snapshot.py` | Data fetch script, outputs JSON |
| `references/health_analysis_guide.md` | LLM analysis reference guide |
| `zepp_health/` | Core library (data fetching, normalization, scoring) |

### Manual Testing

```bash
python3 scripts/health_snapshot.py                  # Today's data
python3 scripts/health_snapshot.py --date 2026-05-18 # Specific date
```

### CLI vs Skill

| Mode | Recommendations | Personalization | Dependencies |
|------|----------------|-----------------|--------------|
| [zepp-health CLI](https://github.com/n0Pnyk/zepp-health) | Rule engine | Generic | Python |
| zepp-health-skill | LLM analysis | Highly personalized | LLM service |

### Syncing Core Library

When the CLI repo updates the core library:

```bash
./sync_from_cli.sh
```

### Safety Boundaries

The LLM will recommend seeking medical attention (without diagnosing) when:
- SpO2 < 90%
- Resting heart rate anomaly exceeds 20% above baseline
- HRV persistently low (30%+ below baseline)

### Disclaimer

This tool is for informational purposes only and does not constitute medical advice. Consult a healthcare professional for any health concerns.

### License

[MIT License](LICENSE)

---

## 中文

Claude Code Skill，让 LLM 分析你的 Zepp/Amazfit 健康数据并给出个性化建议。

配合 [OpenClaw](https://github.com/anthropics/openclaw) 或 hermes-agent 使用。

### 快速部署

```bash
git clone https://github.com/n0Pnyk/zepp-health-skill.git
cd zepp-health-skill

# 安装依赖
pip install httpx pydantic rich python-dotenv

# 配置认证（选一种）
cp config.example.json config.json
# 编辑 config.json，填入 app_token 和 user_id

# 或用环境变量
export ZEPP_COOKIE="userid=xxx; apptoken=xxx; region=1"
```

获取 cookie：访问 [user.huami.com/privacy2](https://user.huami.com/privacy2/#/confirmExportData)，登录后打开浏览器 DevTools（F12）→ Network 标签，刷新页面，找到发往 `api-mifit*.zepp.com` 的请求，从请求头复制 `apptoken`，从 URL 或参数中复制 `userid`。

> **注意：** `app.zepp.com` 已不可访问，正确地址是 `user.huami.com/privacy2`。另外，`apptoken` 和 `userid` 由 Zepp App 的 JSBridge（KeepAlive SDK）注入，只有在手机 Zepp App 内置 WebView 中打开时才会自动带上。用普通桌面浏览器打开这个页面时 token 是空的。正确做法：在桌面浏览器直接打开 `user.huami.com` 页面，登录后在 DevTools 的 Network 中抓取 API 请求里的 token。

### 使用

在 OpenClaw 或 hermes-agent 中说：

- 「分析我的健康数据」
- 「今天睡眠怎么样」
- 「我的恢复状态如何」
- 「帮我看看训练负荷」

LLM 会自动调用 `scripts/health_snapshot.py` 获取数据，参考 `references/health_analysis_guide.md` 进行分析。

### 包含内容

| 文件 | 用途 |
|------|------|
| `SKILL.md` | Skill 定义，触发条件和分析框架 |
| `scripts/health_snapshot.py` | 数据获取脚本，输出 JSON |
| `references/health_analysis_guide.md` | LLM 分析参考指南 |
| `zepp_health/` | 核心库（数据拉取、归一化、评分） |

### 手动测试

```bash
python3 scripts/health_snapshot.py                  # 今日数据
python3 scripts/health_snapshot.py --date 2026-05-18  # 指定日期
```

### 与 CLI 的区别

| 模式 | 建议来源 | 个性化程度 | 依赖 |
|------|----------|------------|------|
| [zepp-health CLI](https://github.com/n0Pnyk/zepp-health) | 规则引擎 | 通用 | Python |
| zepp-health-skill | LLM 分析 | 高度个性化 | LLM 服务 |

### 同步核心库

当 CLI 仓库更新核心库后，运行同步脚本：

```bash
./sync_from_cli.sh
```

### 安全边界

以下情况会建议就医，不做诊断：
- SpO2 < 90%
- 静息心率异常升高超过基线 20%
- HRV 持续异常偏低（低于基线 30%+）

### 免责声明

本工具仅供健康数据参考，不构成医疗建议。如有健康问题请咨询专业医生。

### 许可证

[MIT License](LICENSE)
