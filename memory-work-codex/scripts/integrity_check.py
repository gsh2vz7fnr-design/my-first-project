#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import ROOT, load_cfg, read_text


REQUIRED = [
    'AGENTS.md',
    'SOUL.md',
    'USER.md',
    'MEMORY.md',
    'SKILLS.md',
    '.memory-work/config.json',
    '00 专注区/_本周.md',
    '00 专注区/MEMORY_LOG.md',
    '00 专注区/ITERATION_LOG.md',
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--strict', action='store_true')
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_cfg()

    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        print('缺失文件:')
        for p in missing:
            print(f'- {p}')
        return 1

    week = read_text(ROOT / cfg.focus_zone_path / cfg.week_file)
    checks = [
        ('任务清单', '## 任务清单' in week),
        ('进展记录', '## 进展记录' in week),
        ('本周文档', '## 本周文档' in week),
        ('自动同步记录', '## 自动同步记录' in week),
    ]
    bad = [name for name, ok in checks if not ok]
    if bad and args.strict:
        print('周文件结构缺失:')
        for n in bad:
            print(f'- {n}')
        return 1

    print('integrity_check: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
