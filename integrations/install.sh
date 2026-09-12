#!/usr/bin/env bash
# 把通用 SKILL.md 软链到各 agentic CLI harness 的 skills 目录。
# 覆盖：Codex (~/.codex/skills)、Claude Code + OpenCode (~/.claude/skills)、Qwen Code (~/.qwen/skills)
# Zed / Cursor / Copilot 走 MCP，见 README。
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$HERE/skill"

link() {
  local dst="$1"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    echo "skip (exists): $dst"
  else
    ln -s "$SKILL_SRC" "$dst"
    echo "linked: $dst"
  fi
}

link "$HOME/.codex/skills/whu-paper-fetcher"
link "$HOME/.claude/skills/whu-paper-fetcher"
link "$HOME/.qwen/skills/whu-paper-fetcher"

echo ""
echo "Skill 已链接。MCP server 配置（Zed/Cursor/Copilot）见 integrations/README.md"
