#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re

from common import ROOT, iso_today, load_cfg, log_event, read_text, repo_lock, write_text


MEMORY_PATH = ROOT / 'MEMORY.md'
USER_PATH = ROOT / 'USER.md'


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--threshold', type=int, default=None)
    return p.parse_args()


def parse_blocks(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r'(### \[[^\]]+\].*?)(?=\n### \[|\Z)', re.S)
    items = []
    for m in pattern.finditer(text):
        block = m.group(1)
        id_match = re.search(r'### \[([^\]]+)\]', block)
        if not id_match:
            continue
        items.append((id_match.group(1), block))
    return items


def get_num(block: str, key: str, default: int = 0) -> int:
    m = re.search(rf'- {re.escape(key)}:\s*(\d+)', block)
    return int(m.group(1)) if m else default


def get_status(block: str) -> str:
    m = re.search(r'- status:\s*(\S+)', block)
    return m.group(1) if m else 'active'


def set_status(block: str, status: str) -> str:
    if re.search(r'- status:\s*\S+', block):
        return re.sub(r'- status:\s*\S+', f'- status: {status}', block, count=1)
    return block + f"\n- status: {status}\n"


def main() -> int:
    args = parse_args()
    cfg = load_cfg()
    threshold = args.threshold or cfg.graduation_threshold

    with repo_lock():
        mtext = read_text(MEMORY_PATH)
        utext = read_text(USER_PATH)

        blocks = parse_blocks(mtext)
        graduated = []
        for mid, block in blocks:
            if get_status(block) != 'active':
                continue
            conf = get_num(block, 'confidence', 0)
            ev = get_num(block, 'evidence_count', 0)
            if conf >= threshold and ev >= threshold:
                graduated.append((mid, block))

        if not graduated:
            print('无可毕业条目')
            return 0

        if '## 稳定特征（毕业区）' not in utext:
            utext += '\n## 稳定特征（毕业区）\n'

        for mid, block in graduated:
            if f'来自记忆: {mid}' not in utext:
                title = re.search(r'### \[[^\]]+\]\s*(.+)', block)
                desc = title.group(1).strip() if title else mid
                utext = utext.replace(
                    '## 稳定特征（毕业区）',
                    f'## 稳定特征（毕业区）\n- 来自记忆: {mid} | {desc} | 毕业日期: {iso_today()}',
                    1,
                )
            mtext = mtext.replace(block, set_status(block, 'graduated'))

        write_text(USER_PATH, utext)
        write_text(MEMORY_PATH, mtext)
        log_event(cfg, 'memory-graduate', f'毕业 {len(graduated)} 条')

    print(f'毕业条目数: {len(graduated)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
