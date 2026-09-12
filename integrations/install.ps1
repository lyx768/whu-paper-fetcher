# 把通用 SKILL.md 软链(目录联结)到各 agentic CLI harness 的 skills 目录（Windows）。
# 覆盖：Codex、Claude Code + OpenCode（共用 .claude/skills）、Qwen Code。
# Zed / Cursor / Copilot 走 MCP，见 README。
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillSrc = Join-Path $Here "skill"

function Link($dst) {
  $dir = Split-Path $dst
  if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  if (Test-Path $dst) { Write-Host "skip (exists): $dst"; return }
  # 跨盘用 Junction（reparse point），本机实证可用
  New-Item -ItemType Junction -Path $dst -Target $SkillSrc | Out-Null
  Write-Host "linked: $dst"
}

Link "$env:USERPROFILE\.codex\skills\whu-paper-fetcher"
Link "$env:USERPROFILE\.claude\skills\whu-paper-fetcher"
Link "$env:USERPROFILE\.qwen\skills\whu-paper-fetcher"

Write-Host ""
Write-Host "Skill 已链接。MCP server 配置（Zed/Cursor/Copilot）见 integrations/README.md"
