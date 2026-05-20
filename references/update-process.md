# Zepp Health 更新流程

## 架构说明

zepp-health 存在两个主要位置：

1. **上游仓库** — `https://github.com/n0pnyk/zepp-health-skill`（git remote: origin）
2. **Hermes skill** — `~/.hermes/skills/smart-home/zepp-health/`（git 仓库，直接 pull）

另外还有一个独立项目：
3. **CLI 项目** — `/root/projects/zepp-health/`（用户自己的版本，有独立 remote）

## 更新流程

### 从上游拉取（推荐方式）

skill 目录本身就是 git 仓库，直接 pull 即可：

```bash
cd ~/.hermes/skills/smart-home/zepp-health
git stash        # 如有本地修改（如 config.json、SKILL.md）
git pull origin main
git stash pop    # 恢复本地修改
```

### 保留不动的文件

| 文件 | 原因 |
|------|------|
| `config.json` | 用户的 API 认证 token |
| `SKILL.md` | 用户改过的中文版 |

### 从 CLI 项目同步（一般不需要）

skill 已直接从 upstream 拉取，通常不需要再从 CLI 项目同步。仅当 CLI 项目有独立的、未合入 upstream 的改动时才需要：
```bash
cd ~/.hermes/skills/smart-home/zepp-health
./sync_from_cli.sh /root/projects/zepp-health
```

## 常见问题

### Q: config.json 过期了怎么办？
A: 登录 app.zepp.com，从浏览器 Cookie 中复制 `apptoken` 和 `userid`，更新 config.json。Zepp 限制单会话：手机 App 登录后服务器 token 会失效。

### Q: 脚本返回全 null 怎么办？
A: 运行 `python3 scripts/health_snapshot.py --check` 检查依赖和配置是否正常。常见原因：token 过期、__pycache__ 缓存旧代码。

### Q: 为什么不直接把 config.json 也 git 管理？
A: config.json 包含敏感 token，不适合 push 到远程仓库。.gitignore 已排除此文件。
