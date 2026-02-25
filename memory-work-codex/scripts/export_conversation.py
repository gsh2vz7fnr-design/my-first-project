#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import ROOT, iso_now, load_cfg, log_event


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--topic', required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_cfg()
    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f'输入文件不存在: {src}')

    out_dir = ROOT / '01 你的项目' / '会话沉淀'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{iso_now().replace(':', '-')}_{args.topic}.md"
    out.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
    log_event(cfg, 'conversation-export', f'导出会话 -> {out.name}')
    print(str(out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
