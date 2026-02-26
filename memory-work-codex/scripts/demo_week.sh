#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace)
      WORKSPACE="$2"; shift 2 ;;
    *)
      echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$WORKSPACE" ]]; then
  WORKSPACE="$(mktemp -d /tmp/memory-work-codex-demo.XXXXXX)"
fi

mkdir -p "$WORKSPACE"
cp -R "$ROOT"/. "$WORKSPACE"/
rm -rf "$WORKSPACE/.git" "$WORKSPACE/scripts/__pycache__" "$WORKSPACE/tests/__pycache__" "$WORKSPACE/.memory-work/.lock" || true

cd "$WORKSPACE"
./scripts/run.sh init --lang zh-CN --user-name "DemoUser" --force-templates
cp sample_week/*.md "00 专注区/"

./scripts/run.sh sync deep --date 2026-02-27
./scripts/run.sh review --from-log --interactive no --approve-all
./scripts/run.sh graduate --threshold 1
./scripts/run.sh archive --week 2026-W09
./scripts/run.sh check --strict

cat <<EOF

演示完成。
工作目录: $WORKSPACE
关键结果:
- 归档文件: $WORKSPACE/00 专注区/_归档/2026-W09.md
- 当前周文件: $WORKSPACE/00 专注区/_本周.md
- 记忆文件: $WORKSPACE/MEMORY.md
- 验证: integrity_check: OK
EOF
