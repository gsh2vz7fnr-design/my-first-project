#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"; shift 2 ;;
    *)
      echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

if [[ "$MODE" == "auto" ]]; then
  DOW="$(date +%u)"
  if (( DOW >= 4 )); then
    MODE="deep"
  else
    MODE="light"
  fi
fi

python3 "$ROOT/scripts/sync_focus.py" --mode "$MODE"

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
week = root / '00 专注区' / '_本周.md'
log = root / '00 专注区' / 'MEMORY_LOG.md'
print('--- 启动摘要 ---')
if week.exists():
    print(f'周文件: {week}')
if log.exists():
    lines = log.read_text(encoding='utf-8').splitlines()[-5:]
    print('近期日志:')
    for line in lines:
        print(f'- {line}')
print('同步模式已完成。')
PY
