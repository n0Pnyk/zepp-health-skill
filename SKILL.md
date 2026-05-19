---
name: zepp-health
description: >
  This skill should be used when the user asks about their health data,
  wants a health analysis, health report, sleep analysis, recovery status,
  training readiness, body battery, stress level, or says "健康", "身体",
  "睡眠", "恢复", "训练", "运动", "心率", "HRV", "压力", "血氧".
---

# Zepp Health Analysis Skill

通过 Zepp/Amazfit API 获取用户的健康数据，进行个性化分析和建议。

## 数据获取

运行以下命令获取结构化健康数据快照：

```bash
python3 {skill_dir}/scripts/health_snapshot.py
```

可指定日期：

```bash
python3 {skill_dir}/scripts/health_snapshot.py --date YYYY-MM-DD
```

检查依赖是否完整：

```bash
python3 {skill_dir}/scripts/health_snapshot.py --check
```

输出 JSON 包含：当日数据、7 天趋势、运动记录、评分明细、`_warnings`（API 错误）、`_meta`（各接口状态）。

## 配置

需要配置 Zepp API 认证信息，按优先级：
1. `{skill_dir}/config.json` — `{ "app_token": "...", "user_id": "...", "host": "api-mifit-cn3.zepp.com" }`
2. 环境变量 `ZEPP_COOKIE` — cookie 字符串
3. 环境变量 `ZEPP_APP_TOKEN` + `ZEPP_USER_ID`

### 获取认证信息

1. 打开 Zepp 隐私数据页面并登录：
   ```
   https://user.huami.com/privacy2/index.html?loginPlatform=web&platform_app=com.xiaomi.hm.health
   ```
2. 打开浏览器开发者工具（F12）→ Network 标签
3. 刷新页面，找到发往 `api-mifit*.zepp.com` 的请求
4. 从请求头复制 `apptoken`，从 URL/参数复制 `userid`

> Token 约 30 天过期，手机 App 登录后服务器 token 会失效，需重新获取。

## 分析框架

拿到数据后，参考 `{skill_dir}/references/health_analysis_guide.md` 进行分析。

核心分析维度：

### 1. 恢复状态
- HRV 与个人基线对比（趋势比绝对值重要）
- RHR 与个人基线对比
- 连续 3 天 HRV↓ + RHR↑ = 疲劳信号

### 2. 睡眠质量
- 深睡占比 15-20%、REM 占比 20-25% 为正常
- 醒来次数 <3 次为佳
- 睡眠效率 >85% 为佳

### 3. 训练负荷
- 急慢性比 0.8-1.3 为健康区间
- >1.5 存在过度训练风险

### 4. 身体电量
- >70 适合训练，<30 需要休息

### 5. 压力与血氧
- 压力均值 <40 为低压力，>60 需关注
- 血氧 <93% 需建议就医

## 输出格式

按以下结构组织分析结果：

1. **数据概览** — 关键指标摘要
2. **趋势分析** — 7 天变化趋势和异常
3. **交叉分析** — 多指标关联判断
4. **个性化建议** — 具体、可执行的行动建议
5. **今日行动** — 根据当前状态给出当天建议

## 安全边界

以下情况必须建议就医，不做诊断：
- SpO2 < 90%
- 静息心率异常升高超过基线 20% 以上
- HRV 持续异常偏低（低于基线 30%+）
- 用户描述胸痛、呼吸困难等症状

始终保持在健康建议范围内，不提供医疗诊断。

## 注意事项

1. **Token 会过期** — Zepp 限制单会话，手机 App 登录后服务器 token 立即失效。数据返回 null 或 401 时，重新从隐私数据页面提取 token 并更新 config.json。

2. **间歇性 401** — 即使 config 正确，Zepp API 有时仍返回 401。直接重试即可。

3. **指标缺失** — snapshot JSON 的 `_meta` 字段记录每个 API 的请求状态（ok/empty/error），可据此判断是数据未同步还是 API 故障。

4. **建议来源区别** — 此 skill 用 LLM 分析（个性化），CLI 的 `zepp-health briefing` 用固定规则（通用）。

## 更新方法

skill 目录是 git 仓库，直接 pull：

```bash
cd ~/.hermes/skills/smart-home/zepp-health
git pull
```

`config.json` 在 .gitignore 中不会被覆盖。`SKILL.md` 有本地修改时 git 会提示冲突，保留本地版本即可。

## 上游仓库

GitHub: https://github.com/n0Pnyk/zepp-health-skill
