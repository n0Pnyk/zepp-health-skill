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

输出 JSON 包含：当日数据、7 天趋势、运动记录、评分明细。

## 配置

需要配置 Zepp API 认证信息，按优先级：
1. `{skill_dir}/config.json` — `{ "app_token": "...", "user_id": "...", "host": "api-mifit-cn3.zepp.com" }`
2. 环境变量 `ZEPP_COOKIE` — cookie 字符串
3. 环境变量 `ZEPP_APP_TOKEN` + `ZEPP_USER_ID`

获取 cookie：登录 app.zepp.com，从浏览器开发者工具复制 Cookie。

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

### 3. 训练负荷（心率储备法）
- inactive: 无运动数据
- detraining: <75 min/week，训练不足
- low: 75-150 min/week，偏低
- productive: 150-300 min/week，WHO 推荐范围
- overreaching: 300-450 min/week，负荷偏高
- high_risk: >450 min/week，过度训练风险

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
