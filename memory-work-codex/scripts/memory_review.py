#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from common import ROOT, iso_today, load_cfg, log_event, read_text, repo_lock, write_text


MEMORY_PATH = ROOT / 'MEMORY.md'
CAND_PATH = ROOT / '.memory-work' / 'candidates.jsonl'


def normalize_hint(text: str) -> str:
    return re.sub(r'\s+', '', text).strip().lower()


def is_same_hint(a: str, b: str) -> bool:
    na = normalize_hint(a)
    nb = normalize_hint(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def is_high_quality_hint(text: str) -> bool:
    if not text:
        return False
    bad_tokens = ('示例', '格式', '说明', '待添加', 'AI 会', '初始化')
    if any(t in text for t in bad_tokens):
        return False
    if len(text.strip()) < 8:
        return False
    return any(k in text for k in ('习惯', '偏好', '每次', '总是', '倾向'))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--from-log', action='store_true')
    p.add_argument('--interactive', choices=['yes', 'no'], default='yes')
    p.add_argument('--approve-all', action='store_true')
    p.add_argument('--min-score', type=float, default=0.35)
    return p.parse_args()


def _safe_json_line(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def load_candidates(from_log: bool) -> list[dict]:
    out: list[dict] = []
    if from_log and CAND_PATH.exists():
        for line in CAND_PATH.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            item = _safe_json_line(line)
            if item:
                out.append(item)

    week = read_text(ROOT / '00 专注区' / '_本周.md')
    heuristic = re.findall(r'(.{0,10}(?:习惯|偏好|每次|总是|倾向).{0,30})', week)
    for idx, h in enumerate(heuristic, 1):
        hint = h.strip()
        if not is_high_quality_hint(hint):
            continue
        out.append(
            {
                'id': f'heuristic-{iso_today()}-{idx}',
                'source': 'weekly-heuristic',
                'date': iso_today(),
                'hint': hint,
                'type': 'dynamic',
            }
        )
    uniq = {}
    seen_hints: list[str] = []
    for c in out:
        hint_key = c.get('hint', '')
        if any(is_same_hint(hint_key, seen) for seen in seen_hints):
            continue
        if hint_key:
            seen_hints.append(hint_key)
        uniq[c['id']] = c
    return list(uniq.values())


def score_candidate(item: dict) -> float:
    score = 0.0
    source = str(item.get('source', ''))
    hint = str(item.get('hint', ''))
    head = str(item.get('content_head', ''))
    mtype = str(item.get('type', 'dynamic'))

    if source == 'weekly-heuristic':
        score += 0.45
    if source == 'sync_focus':
        score += 0.25
    if mtype == 'procedural':
        score += 0.15
    if is_high_quality_hint(hint):
        score += 0.25
    if len(head.strip()) > 40:
        score += 0.15
    if any(k in hint for k in ('总是', '每次', '习惯', '偏好', '倾向')):
        score += 0.2
    if any(k in hint for k in ('示例', '模板', '占位')):
        score -= 0.3

    return max(0.0, min(1.0, score))


def confidence_from_score(score: float) -> int:
    if score >= 0.75:
        return 3
    if score >= 0.5:
        return 2
    return 1


def aggregate_candidates(candidates: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for c in candidates:
        hint = str(c.get('hint', '')).strip()
        if not hint:
            continue
        key = normalize_hint(hint)
        if not key:
            continue
        row = grouped.get(key)
        if row is None:
            row = dict(c)
            row['evidence_count'] = 1
            row['sources'] = {str(c.get('source', 'unknown'))}
            row['score'] = score_candidate(c)
            grouped[key] = row
            continue

        row['evidence_count'] = int(row.get('evidence_count', 1)) + 1
        row['sources'].add(str(c.get('source', 'unknown')))
        row['score'] = max(float(row.get('score', 0.0)), score_candidate(c))
        if len(hint) > len(str(row.get('hint', ''))):
            row['hint'] = hint
        if str(c.get('type', 'dynamic')) == 'procedural':
            row['type'] = 'procedural'

    merged = []
    for key in grouped:
        item = grouped[key]
        item['sources'] = sorted(item['sources'])
        evidence = int(item.get('evidence_count', 1))
        base_score = float(item.get('score', 0.0))
        bump = min(0.3, 0.08 * max(0, evidence - 1))
        total_score = min(1.0, base_score + bump)
        item['score'] = total_score
        item['confidence'] = confidence_from_score(total_score)
        merged.append(item)
    merged.sort(key=lambda x: (float(x.get('score', 0.0)), int(x.get('evidence_count', 1))), reverse=True)
    return merged


def entry_block(item: dict) -> str:
    mtype = item.get('type', 'dynamic')
    title = item.get('hint', item.get('id', '未命名候选'))
    title = title[:80]
    score = float(item.get('score', 0.0))
    evidence = int(item.get('evidence_count', 1))
    confidence = int(item.get('confidence', confidence_from_score(score)))
    sources = item.get('sources', [item.get('source', 'unknown')])
    src_text = ','.join(str(x) for x in sources)
    return (
        f"\n### [{item['id']}] {title}\n"
        f"- type: {mtype}\n"
        f"- evidence_count: {evidence}\n"
        f"- confidence: {confidence}\n"
        f"- score: {score:.2f}\n"
        f"- status: active\n"
        f"- discovered_at: {item.get('date', iso_today())}\n"
        f"- last_activated: {iso_today()}\n"
        f"- source: {src_text}\n"
    )


def write_entries(approved: list[dict]) -> int:
    if not approved:
        return 0
    text = read_text(MEMORY_PATH)
    if '## 动态记忆条目' not in text:
        text += '\n## 动态记忆条目\n'
    if '## 程序记忆条目' not in text:
        text += '\n## 程序记忆条目\n'

    inserted = 0
    for item in approved:
        marker = f"[{item['id']}]"
        if marker in text:
            continue
        block = entry_block(item)
        if item.get('type') == 'procedural':
            text = text.replace('## 程序记忆条目', '## 程序记忆条目' + block, 1)
        else:
            text = text.replace('## 动态记忆条目', '## 动态记忆条目' + block, 1)
        inserted += 1

    write_text(MEMORY_PATH, text)
    return inserted


def main() -> int:
    args = parse_args()
    cfg = load_cfg()

    candidates = load_candidates(args.from_log)
    ranked = [c for c in aggregate_candidates(candidates) if float(c.get('score', 0.0)) >= args.min_score]
    approved: list[dict] = []

    for c in ranked:
        ok = args.approve_all
        if args.interactive == 'yes' and not ok:
            ans = input(
                f"记忆候选: {c['hint']}\n"
                f"score={float(c.get('score', 0.0)):.2f}, evidence={int(c.get('evidence_count', 1))}, "
                f"confidence={int(c.get('confidence', 1))}\n"
                "写入? [y/N]: "
            ).strip().lower()
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
    print(f'达到阈值: {len(ranked)} (min_score={args.min_score:.2f})')
    print(f'写入数: {count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
