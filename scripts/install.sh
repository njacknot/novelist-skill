#!/usr/bin/env bash
# 跨工具一键安装脚本：把 novelist skill 安装到 Codex / Gemini / Claude Code / OpenCode / Antigravity
set -euo pipefail

TOOL=""
DEST=""
FORCE="0"

usage() {
  cat <<'USAGE'
用法：
  install.sh --tool <codex|gemini|claude-code|opencode|antigravity> [--dest <目录>] [--force]

示例：
  install.sh --tool codex
  install.sh --tool gemini --force
  install.sh --tool claude-code --dest ~/.claude/skills/novelist

参数：
  --tool    目标工具名（必填）
  --dest    自定义安装目录（可选，默认使用工具标准路径）
  --force   覆盖已有安装
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool) TOOL="${2:-}"; shift 2 ;;
    --dest) DEST="${2:-}"; shift 2 ;;
    --force) FORCE="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$TOOL" ]]; then
  echo "缺少 --tool 参数" >&2
  usage
  exit 2
fi

# 源目录：本脚本所在目录的上一级
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

default_dest() {
  case "$1" in
    codex)       echo "$HOME/.codex/skills/novelist" ;;
    gemini)      echo "$HOME/.gemini/skills/novelist" ;;
    claude-code) echo "$HOME/.claude/skills/novelist" ;;
    opencode)    echo "$HOME/.opencode/skills/novelist" ;;
    antigravity) echo "$HOME/.antigravity/skills/novelist" ;;
    *) echo "不支持的工具: $1" >&2; exit 2 ;;
  esac
}

is_protected_dest() {
  local raw="$1"
  local trimmed="${raw%/}"
  # 禁止根目录 / 家目录 / 空路径 / 当前目录
  if [[ -z "$trimmed" || "$trimmed" == "/" || "$trimmed" == "$HOME" || "$trimmed" == "." ]]; then
    return 0
  fi
  return 1
}

if [[ -z "$DEST" ]]; then
  DEST="$(default_dest "$TOOL")"
fi

if is_protected_dest "$DEST"; then
  echo "目标目录被保护（根目录 / 家目录 / 空）: $DEST" >&2
  exit 2
fi

if [[ -e "$DEST" ]]; then
  if [[ "$FORCE" != "1" ]]; then
    echo "目标目录已存在: $DEST（加 --force 覆盖）" >&2
    exit 2
  fi
  echo "[info] 覆盖已有安装: $DEST"
  rm -rf "$DEST"
fi

mkdir -p "$(dirname "$DEST")"

# 使用 rsync 如果可用，否则 cp
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude='.git' --exclude='node_modules' --exclude='.flow' "$SRC_DIR/" "$DEST/"
else
  cp -r "$SRC_DIR" "$DEST"
  rm -rf "$DEST/.git" 2>/dev/null || true
fi

echo "[ok] novelist skill 已安装到: $DEST"
echo "[tip] 在 $TOOL 里试着说：「用 novelist 帮我写一部悬疑小说」"
