#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from common import (
    ROOT,
    iso_today,
    list_focus_files,
    load_cfg,
    log_event,
    read_text,
    relative_to_root,
    repo_lock,
    week_file_path,
    write_text,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['light', 'deep'], required=True)
    p.add_argument('--date', default=iso_today())
    return p.parse_args()


def mentioned_names(week_text: str) -> set[str]:
    names = set(re.findall(r'`([^`]+)`', week_text))
    for m in re.findall(r'\|\s*([^|]+?)\s*\|\s*(?:草稿|进行中|完成|已归档)', week_text):
        names.add(m.strip())
    return names


def add_sync_section(text: str, heading: str, lines: list[str]) -> str:
    block = f"\n### {heading}\n" + "\n".join(f"- {ln}" for ln in lines) + "\n"
    if '## 自动同步记录' not in text:
        text += '\n## 自动同步记录\n'
    return text + block


def ensure_today_progress(text: str, date_s: str) -> str:
    if f'### {date_s}' in text:
        return text
    anchor = '## 进展记录'
    section = f"\n### {date_s}\n- 完成:\n- 阻塞:\n- 下一步:\n"
    if anchor in text:
        return text.replace(anchor, anchor + section, 1)
    return text + '\n' + anchor + section


def append_outputs_table(text: str, rel_paths: list[str]) -> str:
    for rp in rel_paths:
        name = Path(rp).name
        row = f"| {name} | 进行中 | {rp} | 自动发现 |"
        if row in text:
            continue
        table_hdr = '| 文档 | 状态 | 位置 | 备注 |'
        table_sep = '|---|---|---|---|'
        if table_sep in text:
            text = text.replace(table_sep, table_sep + '\n' + row, 1)
        elif table_hdr in text:
            text = text.replace(table_hdr, table_hdr + '\n' + table_sep + '\n' + row, 1)
        else:
            text += '\n## 本周文档\n| 文档 | 状态 | 位置 | 备注 |\n|---|---|---|---|\n' + row + '\n'
    return text


def mark_tasks(text: str, rel_paths: list[str]) -> str:
    updated = text
    for rp in rel_paths:
        stem = Path(rp).stem
        updated = re.sub(
            rf'^- \[ \] (.*{re.escape(stem)}.*)$',
            r'- [x] \1',
            updated,
            flags=re.MULTILINE,
        )
    return updated


def append_candidates(new_files: list[Path], date_s: str) -> int:
    if not new_files:
        return 0
    cpath = ROOT / '.memory-work' / 'candidates.jsonl'
    cpath.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with cpath.open('a', encoding='utf-8') as f:
        for p in new_files:
            head = '\n'.join(read_text(p).splitlines()[:20])
            rec = {
                'id': f'auto-{date_s}-{p.name}',
                'source': 'sync_focus',
                'date': date_s,
                'file': relative_to_root(p),
                'hint': f'本周新增产出 {p.name}',
                'content_head': head,
                'type': 'dynamic',
            }
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            count += 1
    return count


def main() -> int:
    args = parse_args()
    date_s = args.date
    dt.date.fromisoformat(date_s)

    cfg = load_cfg()
    week = week_file_path(cfg)
    with repo_lock():
        text = read_text(week)
        refs = mentioned_names(text)
        files = list_focus_files(cfg)
        new_files = [p for p in files if p.name not in refs and relative_to_root(p) not in refs]

        summary = [f"扫描文件数: {len(files)}", f"新增未登记文件: {len(new_files)}"]
        if args.mode == 'deep' and new_files:
            rels = [relative_to_root(p) for p in new_files]
            text = ensure_today_progress(text, date_s)
            text = append_outputs_table(text, rels)
            text = mark_tasks(text, rels)
            inspect_lines = []
            for p in new_files:
                first = (read_text(p).splitlines()[:1] or [''])[0]
                inspect_lines.append(f"{relative_to_root(p)} | 首行: {first[:80]}")
            text = add_sync_section(text, f"{date_s} 深度回溯", summary + inspect_lines)
            wrote = append_candidates(new_files, date_s)
            summary.append(f"候选记忆新增: {wrote}")
        else:
            text = add_sync_section(text, f"{date_s} 轻量同步", summary)

        write_text(week, text)
        log_event(cfg, f'focus-sync-{args.mode}', ' ; '.join(summary))

    print('\n'.join(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
