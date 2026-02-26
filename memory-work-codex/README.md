# Memory Work Codex（中文）

Codex 适配版的 Memory Work：保留原方法论，替换为 `AGENTS.md + 本地脚本` 执行协议。

## 快速开始（约 15 分钟）

1. 初始化
```bash
cd /Users/zhang/Desktop/Claude/memory-work-codex
./scripts/run.sh init --lang zh-CN --user-name "你的名字"
```

2. 启动工作
```bash
./scripts/run.sh boot --mode auto
```

3. 周中/周末操作
```bash
./scripts/run.sh sync light
./scripts/run.sh sync deep
./scripts/run.sh review --from-log --interactive no
./scripts/run.sh graduate --threshold 3
./scripts/run.sh archive --week 2026-W09
```

4. 完整性检查
```bash
./scripts/run.sh check --strict
```

5. 运行测试
```bash
./scripts/run.sh test
```

## 目录

- `AGENTS.md`：Codex 系统入口
- `SOUL.md` / `USER.md` / `MEMORY.md`：记忆核心文件
- `00 专注区/`：本周工作台、日志、归档
- `scripts/`：自动化命令
  - `run.sh`：统一命令入口（推荐）
- `templates/`：初始化模板
- `.memory-work/config.json`：系统配置

## 三段场景验收

- `scenarios/acceptance.md` 中记录：
1. 首次初始化
2. 日常启动与同步
3. 周末复盘与归档

## Obsidian

可选。直接把 `memory-work-codex` 作为 Vault 打开即可。
