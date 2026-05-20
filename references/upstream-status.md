# Zepp Health 上游仓库状态

## 仓库地址
- GitHub: https://github.com/n0pnyk/zepp-health-skill
- 本地克隆: /root/projects/zepp-health-skill

## 本地项目（用户自己的）
- /root/projects/zepp-health — 无 git remote，独立维护

## 最后同步检查: 2026-05-19

### 上游最新提交
| Commit | Date | Message |
|--------|------|---------|
| 53357b8 | 2026-05-19 | optimize API calls: parallel execution, batch body_battery, deduplicate |
| 2ab4937 | 2026-05-19 | bilingual README (English + Chinese) |
| c2555bc | 2026-05-19 | translate all source code comments and user-facing text to English |
| da879ea | 2026-05-19 | docs: translate all documentation to English |
| 181c783 | 2026-05-19 | 添加 MIT 许可证和健康数据免责声明 |

### 本地落后情况
- /root/projects/zepp-health-skill: 仅 2 个旧提交(ad1ec42, e733e77)，落后上游 5 个提交
- ~/.hermes/skills/smart-home/zepp-health/: 非 git 仓库，需手动同步

## 检查上游更新的方法
```bash
curl -s "https://api.github.com/repos/n0pnyk/zepp-health-skill/commits?per_page=5" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for c in data:
    print(c['sha'][:7], c['commit']['author']['date'][:10], c['commit']['message'][:80])
"
```
