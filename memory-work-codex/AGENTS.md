# AGENTS.md

## 目标
这是 Codex 版 Memory Work 的系统入口。目标：在不打断用户心流的前提下，自动完成周工作台同步和长期记忆维护。

## 启动触发词
- `启动`
- `开始工作`
- `boot`
- `initialize`

## 启动顺序（每次会话）
1. 读取本文件。
2. 运行 `./scripts/boot.sh --mode auto`。
3. 启动后以搭档语气汇报：
- 当前周文件状态
- 新发现产出
- 待确认项

## 启动脚本职责
`boot.sh` 内部执行：
1. 日期判断（周一到周三=light，周四到周日=deep）
2. 读取 `00 专注区/_本周.md`
3. 读取 `00 专注区/MEMORY_LOG.md` 尾部
4. 读取 `SOUL.md`
5. 调用 `sync_focus.py` 执行同步

## 四层记忆
- 持久层：`SOUL.md`、`USER.md`
- 工作层：`00 专注区/_本周.md`
- 动态层：`MEMORY.md`（`## 动态记忆条目`）
- 程序层：`MEMORY.md`（`## 程序记忆条目`）

## 记忆触发协议（惊奇度）
高惊奇信号：
1. 修正既有认知
2. 补全关键空白
3. 形成重复模式（>=2 次）

低惊奇信号：
1. 单次事务执行
2. 仅进度更新
3. 与既有记忆一致且无新增信息

## 记忆写入规则
- 执行期：只记录候选，不打断用户。
- 复盘期：`memory_review.py` 批量确认后写入 `MEMORY.md`。
- 身份层更新（写入 `USER.md`）必须逐条确认。

## Zone Agent 规则
- 进入任意分区前先读取 `00.*_agent.md`。
- 分区规则与全局冲突时，采用更严格规则。
- 多分区协同时，应用所有相关规则并取最严格约束。

## 常用命令
- 初始化：`./scripts/init.sh --lang zh-CN --user-name "你的名字"`
- 启动：`./scripts/boot.sh --mode auto`
- 轻/深同步：`python3 scripts/sync_focus.py --mode light|deep`
- 记忆复盘：`python3 scripts/memory_review.py --from-log --interactive no`
- 记忆毕业：`python3 scripts/memory_graduate.py --threshold 3`
- 周归档：`python3 scripts/week_archive.py --week YYYY-Www`
- 完整性检查：`python3 scripts/integrity_check.py --strict`

## 安全边界
- 不修改 `_归档/` 下历史文件。
- 不对敏感目录执行自动写入（除非用户明确确认）。
- 所有脚本写入动作需要记录到 `00 专注区/MEMORY_LOG.md`。
