# 三段场景验收记录

日期：2026-02-25
目录：`/Users/zhang/Desktop/Claude/memory-work-codex`

## 场景 1：首次初始化
命令：
```bash
./scripts/init.sh --lang zh-CN --user-name "Zhang" --force-templates
```
结果：
- `integrity_check: OK`
- 初始化完成，核心文件与目录存在

## 场景 2：日常启动 + 深度同步
命令：
```bash
./scripts/boot.sh --mode auto
python3 scripts/sync_focus.py --mode deep
```
准备：新增 `00 专注区/需求梳理.md`

结果：
- 启动轻同步可运行（周三自动进入 light）
- 深度同步识别新增文件并补录到 `_本周.md`
- 自动写入候选记忆到 `.memory-work/candidates.jsonl`

## 场景 3：周末复盘 + 归档
命令：
```bash
python3 scripts/memory_review.py --from-log --interactive no --approve-all
python3 scripts/memory_graduate.py --threshold 1
python3 scripts/week_archive.py --week 2026-W09
python3 scripts/integrity_check.py --strict
```
结果：
- 记忆复盘：`候选数: 1`，`写入数: 1`
- 记忆毕业：`毕业条目数: 1`
- 周归档成功，生成 `_归档/2026-W09.md`
- 完整性检查通过：`integrity_check: OK`

## 附加：会话导出占位能力
命令：
```bash
python3 scripts/export_conversation.py --input /tmp/demo_conversation.md --topic 复盘示例
```
结果：
- 成功导出到 `01 你的项目/会话沉淀/` 目录

## 验收结论
- 通过：初始化、启动同步、记忆复盘/毕业、周归档、完整性检查、会话导出均可执行。
- 备注：`memory_graduate.py` 在验收时使用阈值 `--threshold 1` 以便演示流程，默认建议保持 `3`。
