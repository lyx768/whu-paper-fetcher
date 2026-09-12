#!/usr/bin/env python3
"""WHU Paper Fetcher — MCP server (stdio).

Exposes the `whu-paper-fetcher` CLI as MCP tools so any MCP-capable client
(Zed, Cursor, VS Code GitHub Copilot, Claude Desktop, etc.) can fetch papers.

Requires: pip install "mcp[cli]"   (and whu-paper-fetcher installed)

Run: python server.py   (stdio transport, as configured in client settings)
"""
from __future__ import annotations

import shutil
import subprocess
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("whu-paper-fetcher")


def _resolve_exe() -> list[str]:
    """Prefer the installed console entry point; fall back to module run."""
    exe = shutil.which("whu-paper-fetcher")
    if exe:
        return [exe]
    return [sys.executable, "-m", "whu_paper_fetcher.cli"]


def _run(args: list[str]) -> str:
    cmd = _resolve_exe() + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        return (
            "ERROR: whu-paper-fetcher 未安装或不在 PATH。\n"
            "请先执行: pip install whu-paper-fetcher\n"
            "并运行 scripts/whu_creds_input.py 配置武大账号凭证。"
        )
    except subprocess.TimeoutExpired:
        return "ERROR: 下载超时（可能卡在登录/挑战页，请在浏览器手动登录一次后重试）。"
    out = (r.stdout + r.stderr).strip()
    return out or f"exit={r.returncode} (无输出)"


@mcp.tool()
def fetch_paper(target: str) -> str:
    """下载单篇论文全文。

    Args:
        target: 论文的 DOI（如 10.1016/j.geoderma.2023.123456）。若是 URL，请先提取其中的 DOI 再传入。

    Returns:
        下载结果：成功时返回文件绝对路径，失败时返回错误说明。
        文件默认落到配置文件中的下载目录（默认 ~/Downloads/whu-papers）。
    """
    return _run(["--doi", target])


@mcp.tool()
def fetch_papers(file_path: str) -> str:
    """批量下载论文。

    Args:
        file_path: 文本文件路径，每行一个 DOI。

    Returns:
        批量下载汇总（每篇的成功/失败状态）。
    """
    return _run(["--doi-file", file_path])


if __name__ == "__main__":
    mcp.run()
