#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
用法:
  ./scripts/run.sh <command> [args]

命令:
  init [--lang zh-CN] [--user-name 名字] [--force-templates]
  boot [--mode auto|light|deep]
  sync [light|deep] [--date YYYY-MM-DD]
  review [--from-log] [--interactive yes|no] [--approve-all]
  graduate [--threshold N]
  archive --week YYYY-Www
  export --input <file> --topic <title>
  demo [--workspace /tmp/path]
  check [--strict]
  test
  help
EOF
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  init)
    "$ROOT/scripts/init.sh" "$@"
    ;;
  boot)
    "$ROOT/scripts/boot.sh" "$@"
    ;;
  sync)
    mode="${1:-}"
    if [[ "$mode" == "light" || "$mode" == "deep" ]]; then
      shift
      python3 "$ROOT/scripts/sync_focus.py" --mode "$mode" "$@"
    else
      python3 "$ROOT/scripts/sync_focus.py" "$@"
    fi
    ;;
  review)
    python3 "$ROOT/scripts/memory_review.py" "$@"
    ;;
  graduate)
    python3 "$ROOT/scripts/memory_graduate.py" "$@"
    ;;
  archive)
    python3 "$ROOT/scripts/week_archive.py" "$@"
    ;;
  export)
    python3 "$ROOT/scripts/export_conversation.py" "$@"
    ;;
  demo)
    "$ROOT/scripts/demo_week.sh" "$@"
    ;;
  check)
    python3 "$ROOT/scripts/integrity_check.py" "$@"
    ;;
  test)
    python3 -m unittest discover -s "$ROOT/tests" -p 'test_*.py'
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "未知命令: $cmd" >&2
    usage
    exit 2
    ;;
esac
