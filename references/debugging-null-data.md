# 数据全为 null 的排查流程

当 health_snapshot.py 返回全 null 时，按以下顺序排查：

## 1. 检查依赖

```bash
python3 {skill_dir}/scripts/health_snapshot.py --check
```

输出应显示所有模块 OK 和 config.json 路径。如果 config.json NOT FOUND，
检查 skill 目录和 CLI 项目是否有 config.json。

## 2. 检查 token 是否有效

最简单的方法：用无效 token 跑一次，看 _meta 字段：

```bash
python3 {skill_dir}/scripts/health_snapshot.py --date 2026-05-19 2>&1 | python3 -c "
import sys,json; d=json.load(sys.stdin)
meta = d.get('_meta',{})
errors = [(k,v) for k,v in meta.items() if v.get('status')=='error']
if errors:
    for k,v in errors: print(f'{k}: {v.get(\"error\",\"\")[:100]}')
else:
    print('All APIs OK')
"
```

如果看到 `401 invalid token`，需要重新获取 token。

## 3. 检查 API 是否真的有数据

有时 API 正常但当天确实没数据（比如还没佩戴手表）。看 _meta 的 status：

- `ok (N items)` — 正常，有 N 条数据
- `empty` — API 正常但没数据（可能当天还没同步）
- `error` — API 报错，看 error 字段

## 4. 清除 Python 缓存

如果代码刚更新过但行为没变，可能是 .pyc 缓存：

```bash
find ~/.hermes/skills/smart-home/zepp-health -name "__pycache__" -type d -exec rm -rf {} +
```

## 5. 直接测试 API

如果以上都正常但还是 null，直接调 API 看原始返回：

```bash
cd ~/.hermes/skills/smart-home/zepp-health && python3 -c "
import sys; sys.path.insert(0,'.')
from zepp_health.config import load_config
from zepp_health.client import ZeppClient
from datetime import date
config = load_config()
with ZeppClient(config) as c:
    data = c.get_band_data(date(2026,5,19), date(2026,5,19))
    print(f'Got {len(data)} days of data')
    if data: print('First item keys:', list(data[0].keys()))
"
```

如果这里能拿到数据但脚本不行，说明是脚本解析问题，不是 API 问题。

## 6. Token 刷新流程

Zepp 限制单会话，手机 App 登录后服务器 token 失效。刷新步骤：

1. 打开 https://user.huami.com/privacy2/index.html
2. 登录（用 Zepp 账号）
3. F12 → Application → Cookies
4. 复制整个 Cookie 字符串（包含 apptoken=xxx 和 userid=xxx）
5. 粘贴给 Hermes，会自动更新 config.json

或者手动更新 config.json：
```json
{
  "app_token": "新的apptoken值",
  "user_id": "1025854709",
  "host": "api-mifit-cn3.zepp.com",
  "timezone": "Asia/Shanghai"
}
```
