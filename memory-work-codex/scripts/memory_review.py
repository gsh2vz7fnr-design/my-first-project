#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import ROOT, iso_today, load_cfg, log_event, read_text, repo_lock, write_text


MEMORY_PATH = ROOT / 'MEMORY.md'
CAND_PATH = ROOT / '.memory-work' / 'candidates.jsonl'


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--from-log', action='store_true')
    p.add_argument('--interactive', choices=['yes', 'no'], default='yes')
    p.add_argument('--approve-all', action='store_true')
    return p.parse_args()


def load_candidates(from_log: bool) -> list[dict]:
    out: list[dict] = []
    if from_log and CAND_PATH.exists():
        for line in CAND_PATH.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            out.append(json.loads(line))

    week = read_text(ROOT / '00 专注区' / '_本周.md')
    heuristic = re.findall(r'(.{0,10}(?:习惯|偏好|每次|总是|倾向).{0,30})', week)
    for idx, h in enumerate(heuristic, 1):
        out.append(
            {
                'id': f'heuristic-{iso_today()}-{idx}',
                'source': 'weekly-heuristic',
                'date': iso_today(),
                'hint': h.strip(),
                'type': 'dynamic',
            }
        )
    uniq = {}
    for c in out:
        uniq[c['id']] = c
    return list(uniq.values())


def entry_block(item: dict, confidence: int = 1) -> str:
    mtype = item.get('type', 'dynamic')
    title = item.get('hint', item.get('id', '未命名候选'))
    title = title[:80]
    return (
        f"\n### [{item['id']}] {title}\n"
        f"- type: {mtype}\n"
        f"- evidence_count: 1\n"
        f"- confidence: {confidence}\n"
        f"- status: active\n"
        f"- discovered_at: {item.get('date', iso_today())}\n"
        f"- last_activated: {iso_today()}\n"
        f"- source: {item.get('source', 'unknown')}\n"
    )


def write_entries(approved: list[dict]) -> int:
    if not approved:
        return 0
    text = read_text(MEMORY_PATH)
    if '## 动态记忆条目' not in text:
        text += '\n## 动态记忆条目\n'
    if '## 程序记忆条目' not in text:
        text += '\n## 程序记忆条目\n'

    for item in approved:
        marker = f"[{item['id']}]"
        if marker in text:
            continue
        block = entry_block(item)
        if item.get('type') == 'procedural':
            text = text.replace('## 程序记忆条目', '## 程序记忆条目' + block, 1)
        else:
            text = text.replace('## 动态记忆条目', '## 动态记忆条目' + block, 1)

    write_text(MEMORY_PATH, text)
    return len(approved)


def main() -> int:
    args = parse_args()
    cfg = load_cfg()

    candidates = load_candidates(args.from_log)
    approved: list[dict] = []

    for c in candidates:
        ok = args.approve_all
        if args.interactive == 'yes' and not ok:
            ans = input(f"记忆候选: {c['hint']}\n写入? [y/N]: ").strip().lower()
            ok = ans in {'y', 'yes'}
        if args.interactive == 'no' and not args.approve_all:
            ok = False
        if ok:
            approved.append(c)

    with repo_lock():
        count = write_entries(approved)
        if count:
            log_event(cfg, 'memory-review', f'新增记忆 {count} 条')

    print(f'候选数: {len(candidates)}')
    print(f'写入数: {len(approved)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
