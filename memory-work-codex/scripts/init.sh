#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LANG="zh-CN"
USER_NAME="未命名用户"
FORCE_TEMPLATES="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang)
      LANG="$2"; shift 2 ;;
    --user-name)
      USER_NAME="$2"; shift 2 ;;
    --force-templates)
      FORCE_TEMPLATES="true"; shift 1 ;;
    *)
      echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$ROOT/.memory-work" "$ROOT/00 专注区/_归档" "$ROOT/01 你的项目" "$ROOT/02 你的阅读" "$ROOT/03 你的写作" "$ROOT/06 Skills"

TODAY="$(date +%F)"
WEEK_ID="$(date +%G-W%V)"
WEEK_START="$(date -v-monday +%F)"
WEEK_END="$(date -v+sunday +%F)"
WEEK_RANGE="$WEEK_START ~ $WEEK_END"

render() {
  local tpl="$1"
  local out="$2"
  if [[ -f "$out" && "$FORCE_TEMPLATES" != "true" ]]; then
    return
  fi
  sed \
    -e "s/{{today}}/$TODAY/g" \
    -e "s/{{week_id}}/$WEEK_ID/g" \
    -e "s/{{week_range}}/$WEEK_RANGE/g" \
    -e "s/{{timezone}}/Asia\/Shanghai/g" \
    -e "s/{{user_name}}/$USER_NAME/g" \
    "$tpl" > "$out"
}

render "$ROOT/templates/SOUL.md.template" "$ROOT/SOUL.md"
render "$ROOT/templates/USER.md.template" "$ROOT/USER.md"
render "$ROOT/templates/MEMORY.md.template" "$ROOT/MEMORY.md"
render "$ROOT/templates/_本周.md.template" "$ROOT/00 专注区/_本周.md"
render "$ROOT/templates/MEMORY_LOG.md.template" "$ROOT/00 专注区/MEMORY_LOG.md"

[[ -f "$ROOT/00 专注区/ITERATION_LOG.md" ]] || cat > "$ROOT/00 专注区/ITERATION_LOG.md" <<EOF
# ITERATION_LOG.md

$TODAY | init | 初始化 codex 版 memory work
EOF

[[ -f "$ROOT/00 专注区/00.专注区_agent.md" ]] || cp "$ROOT/templates/zone_agent.template.md" "$ROOT/00 专注区/00.专注区_agent.md"
[[ -f "$ROOT/01 你的项目/00.项目区_agent.md" ]] || cp "$ROOT/templates/zone_agent.template.md" "$ROOT/01 你的项目/00.项目区_agent.md"
[[ -f "$ROOT/02 你的阅读/00.阅读区_agent.md" ]] || cp "$ROOT/templates/zone_agent.template.md" "$ROOT/02 你的阅读/00.阅读区_agent.md"
[[ -f "$ROOT/03 你的写作/00.写作区_agent.md" ]] || cp "$ROOT/templates/zone_agent.template.md" "$ROOT/03 你的写作/00.写作区_agent.md"
[[ -f "$ROOT/06 Skills/00.skills_agent.md" ]] || cp "$ROOT/templates/zone_agent.template.md" "$ROOT/06 Skills/00.skills_agent.md"

python3 "$ROOT/scripts/integrity_check.py"

echo "初始化完成: $ROOT"
