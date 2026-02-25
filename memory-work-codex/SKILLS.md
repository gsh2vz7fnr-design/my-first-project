# SKILLS.md

本仓库的“技能”以脚本命令形式提供，避免依赖特定模型运行时。

| 触发意图 | 技能占位 | 命令 |
|---|---|---|
| 会话启动时间校准 | datetime-check | `./scripts/boot.sh --mode auto` |
| 周工作台同步 | focus-zone-sync | `python3 scripts/sync_focus.py --mode light|deep` |
| 记忆复盘 | memory-review | `python3 scripts/memory_review.py --from-log --interactive no` |
| 记忆毕业 | memory-graduate | `python3 scripts/memory_graduate.py --threshold 3` |
| 会话导出 | save-conversation | `python3 scripts/export_conversation.py --input <file> --topic <title>` |
| 周归档 | week-archive | `python3 scripts/week_archive.py --week YYYY-Www` |

说明：
- 技能名称保持与 Memory Work 概念对齐。
- 实际执行入口统一为本地脚本，便于 Codex/CLI 复用。
