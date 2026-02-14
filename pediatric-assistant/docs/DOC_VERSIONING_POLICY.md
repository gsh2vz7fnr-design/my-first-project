# 文档版本管理规范

最后更新: 2026-02-14

## 目标
将以下三类核心文档按“版本号 + 分类目录”管理，确保每次变更都有可追溯记录：
- 需求文档 (PRD)
- 开发文档 (DEV GUIDE)
- Bug 修复文档 (FIX PLAN)

## 目录约定
每个发布版本必须建立如下结构：

```text
versions/<version>/
  requirements/
  development/
  bugfix/
```

示例（本次）：
- `versions/v4.1/requirements/PRD_v4.1_2026-02-14.md`
- `versions/v4.1/development/DEV_GUIDE_v1.1_2026-02-14.md`
- `versions/v4.1/bugfix/TODO_FIX_PLAN_v2.2_2026-02-14.md`

## 维护规则
1. 根目录的 `PRD_UPDATED.md`、`DEV_GUIDE.md`、`docs/TODO_FIX_PLAN.md` 作为“最新工作副本”。
2. 每次这三类文档发生有效变更时，必须在 `versions/<version>/` 下新增一组版本快照文件。
3. 文件名必须包含: 文档类型 + 文档版本号 + 日期（`YYYY-MM-DD`）。
4. 不覆盖历史版本；历史版本只追加，不回写。
5. 提交代码时，若涉及三类文档任一变更，必须同时提交对应版本快照。

## 建议流程
1. 先修改最新工作副本。
2. 确认版本号（例如 `v4.2`）。
3. 创建三目录并复制快照。
4. 提交时在 commit message 说明文档版本。
