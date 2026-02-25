#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import (
    focus_dir,
    iso_today,
    iso_week,
    load_cfg,
    log_event,
    read_text,
    repo_lock,
    week_file_path,
    week_range,
    write_text,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--week', required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not re.match(r'^\d{4}-W\d{2}$', args.week):
        raise SystemExit('week 参数格式错误，应为 YYYY-Www')

    cfg = load_cfg()
    wpath = week_file_path(cfg)
    archive_dir = focus_dir(cfg) / '_归档'
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f'{args.week}.md'

    with repo_lock():
        content = read_text(wpath)
        if not content.strip():
            content = f"# 本周\n\n归档周次: {args.week}\n"
        write_text(target, content)

        new_week = (
            f"---\ntitle: 本周\nweek: {iso_week()}\ndates: {week_range()}\nstatus: active\ncreated: {iso_today()}\n---\n\n"
            "# 本周\n\n## 原始口述\n\n## 任务清单\n- [ ] 从上周继承任务\n\n"
            "## 参考材料\n\n## 进展记录\n### " + iso_today() + "\n- 完成:\n- 阻塞:\n- 下一步:\n\n"
            "## 本周文档\n| 文档 | 状态 | 位置 | 备注 |\n|---|---|---|---|\n\n"
            "## 待确认\n- 无\n\n## 自动同步记录\n"
        )
        write_text(wpath, new_week)
        log_event(cfg, 'week-archive', f'归档 {args.week} -> {target.name}')

    print(f'已归档: {target}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
