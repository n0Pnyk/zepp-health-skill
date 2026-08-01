# Zepp API 端点实测参考（2026-08-01）

实测环境：api-mifit-cn3.zepp.com，apptoken 认证，appname=com.huami.midong，v=2.0，vn=10.2.5。

## 端点状态总表

| 端点 | 数据 | 状态 |
|------|------|------|
| `/v1/data/band_data.json`（步数/睡眠/RHR摘要） | 7天✅ | ✅ |
| `/users/{uid}/events` all_day_stress | 7天✅ | ✅ |
| `/users/{uid}/events` blood_oxygen | 7天✅ | ✅ |
| `/users/{uid}/events` PaiHealthInfo | 6天✅ | ✅ |
| `/users/{uid}/events` readiness | 7天✅ | ✅（HRV/RHR/皮温数据源） |
| `/v1/sport/run/history.json`（运动记录） | ✅ | ✅ |
| `/v2/watch/users/{uid}/WatchSportStatistics/SPORT_LOAD` | ✅ | ✅ |
| `/v2/users/me/events` Charge（身体电量） | 7天✅ | ✅ |
| `/users/me/bloodPressure` | 空 | ⚠️ 返回**裸 list** `[]`，不是 `{"items":[]}`（已修复 client） |
| `/v2/users/me/events` RespiratoryRate | 7天✅ | ⚠️ value=base64 measurements（已修复 client） |
| `/users/{uid}/heartRate` | 空 | ⚠️ 任意 type 都空，疑似失效 |
| `/v2/users/me/events` hrv_sdnn 等 | 空 | ⚠️ 失效，HRV 只能从 readiness 事件拿 |
| `/v2/watch/users/{uid}/WatchSportStatistics/VO2_MAX` | 空 | ⚪ 真无数据（需跑步才估算） |
| `/users/{uid}/members/-1/weightRecords` | 空 | ⚪ 无体重记录，参数正常 |

## 关键结构（踩坑记录）

### RespiratoryRate（v2 events）
```json
{"value": {"measurements": "<base64>", "timeZone": "Asia/Shanghai"}}
```
- measurements 解码 = 1440 字节（一天每分钟 1 字节）
- 每字节 = 呼吸次数/分钟（12-16 正常，0 = 无效）
- 修复：b64decode → 过滤 0 → 平均 → 每日一条记录
- client.get_respiratory_rate 已按此实现（2026-08-01）

### bloodPressure
```json
// 空时直接返回裸数组，不是 dict！
[]
// 有数据时是数组元素，字段: timestamp/systolic/diastolic/pulse
```
- 修复：`items = result if isinstance(result, list) else result.get("items", [])`
- 注意：实测该用户 0 条记录（无血压设备数据）

### body_battery（v2 events Charge）
```json
{"value": {"samples": [{"s": 偏移ms, "total": 81, "mental": 77.7, "physical": 83.5}], ...}}
```
- total 有 -3 偏移，App 端 +3 还原（client 已处理）
- 每条 value 含全天样本（1440 个/天），取第一个有效 total!=255

### readiness（v1 events, subType=watch_score）
- **HRV/RHR/皮温的主要数据源**（单独 hrv endpoint 已失效）
- 字段：rdnsScore, rhrScore, rhrBaseline, sleepRHR, hrvScore, hrvBaseline, sleepHRV, skinTempScore 等

## 数据滞后说明

- 设备数据通常滞后 1 天（当天 08:00 前的数据要次日才全）
- "今天"查询 respiratory_rate 可能为空，查 7 天范围一定有（7-25..7-31 实测 7 条）

### WORKOUT_TYPES 运动类型映射（2026-08-01 修正）

来源：H3llK33p3r/zepp-fit-extractor ActivityType 枚举 + 用户数据特征验证。

| type | 名称 | 数据特征验证 |
|------|------|-------------|
| 1 | outdoor_running | ✅ 40条：HR136/pace0.36 |
| 2 | walking | - |
| 3 | cycling | - |
| 4 | treadmill | - |
| 5 | indoor_cycling | - |
| **6** | **walking**（原错误为 elliptical） | ✅ 29条：HR95/步数2721/pace1.23=散步 |
| 7 | climbing | - |
| 8 | treadmill（原 trail_running） | ✅ 2条：有GPS距离3000/4000m |
| 9 | outdoor_cycling（原 skiing） | ✅ 7条：步数≈132=骑行 |
| 10 | snowboarding | ❓ 用户1条 dis=0/steps=1420 存疑 |
| 14 | indoor_swimming | 补充 |
| 16-22 | 游泳/瑜伽/划船等 | - |
| 64 | strength_training | - |
| 128 | hiit | - |
| 192 | outdoor_running | ✅ 2条：HR151-170/步数4583-4969 |
| 223 | other | - |

**踩坑要点：**
- type 6 旧代码误标 elliptical，用户 29 条散步记录全显示错——数据特征（低HR+高步数+慢pace）才是判定依据
- type 9 步数≈0 是骑行铁证（骑行不产生步数）
- 所有运动类型都从 /v1/sport/run/history.json 返回，其他 sport 段（/walking /ride 等）404
- detail 端点 /v1/sport/run/detail.json 需要 trackid + source 双参数（只传 trackid 会 400）

## 验证脚本

```bash
python3 /tmp/zepp_probe.py        # 全端点状态探测
python3 /tmp/zepp_raw_probe.py    # 原始 HTTP 响应
python3 /tmp/zepp_verify_fix.py   # 修复验证
```
