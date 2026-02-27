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
./scripts/run.sh review --from-log --interactive no --min-score 0.35
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

6. 一键演示完整一周（不污染当前目录）
```bash
./scripts/run.sh demo
```

7. 打开前端控制台
```bash
./scripts/run.sh ui 4173
```
浏览器访问：`http://127.0.0.1:4173`

## 目录

- `AGENTS.md`：Codex 系统入口
- `SOUL.md` / `USER.md` / `MEMORY.md`：记忆核心文件
- `00 专注区/`：本周工作台、日志、归档
- `scripts/`：自动化命令
  - `run.sh`：统一命令入口（推荐）
- `templates/`：初始化模板
- `.memory-work/config.json`：系统配置
- `frontend/`：可视化控制台（纯静态页面）

## 三段场景验收

- `scenarios/acceptance.md` 中记录：
1. 首次初始化
2. 日常启动与同步
3. 周末复盘与归档

## 真实一周示例

- 示例输入在 [sample_week/README.md](/Users/zhang/Desktop/Claude/memory-work-codex/sample_week/README.md)
- 你可以直接执行：
```bash
./scripts/run.sh demo
```
- 演示脚本会在 `/tmp` 创建临时工作目录，自动跑：
  - 初始化
  - 深同步
  - 记忆复盘
  - 记忆毕业
  - 周归档
  - 完整性检查

记忆评分说明：
- `review` 新增 `--min-score`（0~1），用于过滤低质量候选。
- 分数由来源、语义信号、证据次数综合计算，写入时会带 `score / evidence_count / confidence`。

## Obsidian

可选。直接把 `memory-work-codex` 作为 Vault 打开即可。
