# Zepp Health Skill

Claude Code Skill，让 LLM 分析你的 Zepp/Amazfit 健康数据并给出个性化建议。

配合 [OpenClaw](https://github.com/anthropics/openclaw) 或 hermes-agent 使用。

## 快速部署

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

获取 cookie：登录 [app.zepp.com](https://app.zepp.com)，从浏览器开发者工具（F12 → Network）复制 Cookie。

## 使用

在 OpenClaw 或 hermes-agent 中说：

- 「分析我的健康数据」
- 「今天睡眠怎么样」
- 「我的恢复状态如何」
- 「帮我看看训练负荷」

LLM 会自动调用 `scripts/health_snapshot.py` 获取数据，参考 `references/health_analysis_guide.md` 进行分析。

## 包含内容

| 文件 | 用途 |
|------|------|
| `SKILL.md` | Skill 定义，触发条件和分析框架 |
| `scripts/health_snapshot.py` | 数据获取脚本，输出 JSON |
| `references/health_analysis_guide.md` | LLM 分析参考指南 |
| `zepp_health/` | 核心库（数据拉取、归一化、评分） |

## 手动测试

```bash
python3 scripts/health_snapshot.py            # 今日数据
python3 scripts/health_snapshot.py --date 2026-05-18  # 指定日期
```

## 与 CLI 的区别

| 模式 | 建议来源 | 个性化程度 | 依赖 |
|------|----------|------------|------|
| [zepp-health CLI](https://github.com/n0Pnyk/zepp-health) | 规则引擎 | 通用 | Python |
| zepp-health-skill | LLM 分析 | 高度个性化 | LLM 服务 |

## 同步核心库

当 CLI 仓库更新核心库后，运行同步脚本：

```bash
./sync_from_cli.sh
```

## 安全边界

以下情况会建议就医，不做诊断：
- SpO2 < 90%
- 静息心率异常升高超过基线 20%
- HRV 持续异常偏低（低于基线 30%+）
