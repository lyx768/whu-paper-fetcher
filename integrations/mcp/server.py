#!/usr/bin/env python3
"""WHU Paper Fetcher — MCP server (stdio, pure standard library).

把 `whu-paper-fetcher` CLI 暴露成 MCP 工具，让任何支持 MCP 的客户端
（Zed / Cursor / VS Code GitHub Copilot / Claude Desktop 等）都能让 AI 一句
话下论文。

设计原则：**零第三方依赖**。仅用 Python 标准库实现 MCP stdio 协议的最小子集
（initialize / tools/list / tools/call），所以任何一个 `python` 都能直接启动，
不需要额外 `pip install mcp`。

运行：  python server.py   （stdio 传输，由 harness 配置文件调用）
依赖：  仅要求 `whu-paper-fetcher` 已安装（见主仓库 README）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

PROTOCOL_VERSION = "2024-11-05"


def _resolve_exe() -> list[str]:
    """优先用已安装的 console 入口；否则回退到 `-m` 模块方式。

    若 server 由已安装本包的 python 启动（如 venv 的 python），`sys.executable`
    即可解析到模块，无需 PATH 上有入口名。
    """
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


TOOLS = [
    {
        "name": "fetch_paper",
        "description": (
            "下载单篇论文全文。输入论文的 DOI（例如 10.1016/j.geoderma.2023.123456）。"
            "若是 URL，请先从中提取 DOI 再传入。返回文件绝对路径或错误说明；"
            "文件默认落到配置中的下载目录（默认 ~/Downloads/whu-papers）。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "论文 DOI，例如 10.1016/j.geoderma.2023.123456",
                }
            },
            "required": ["target"],
        },
    },
    {
        "name": "fetch_papers",
        "description": (
            "批量下载论文。输入一个文本文件路径，文件每行一个 DOI。"
            "返回每篇的成功/失败汇总。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文本文件路径，每行一个 DOI",
                }
            },
            "required": ["file_path"],
        },
    },
]


def _read_message() -> dict | None:
    """从 stdin 按 `Content-Length` 帧读取一条 JSON-RPC 消息。"""
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.readline()
        if not line:
            return None  # EOF
        line = line.strip()
        if not line:
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    size = int(headers.get("content-length", "0"))
    if size <= 0:
        return None
    body = sys.stdin.read(size)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _send_message(msg: dict) -> None:
    body = json.dumps(msg, ensure_ascii=False)
    data = body.encode("utf-8")
    sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n")
    sys.stdout.write(body)
    sys.stdout.flush()


def _handle(msg: dict) -> None:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params", {}) or {}

    if method == "initialize":
        _send_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "whu-paper-fetcher", "version": "0.1.0"},
            },
        })
    elif method == "notifications/initialized":
        pass  # 无需回复
    elif method == "tools/list":
        _send_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        })
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        if name == "fetch_paper":
            result = _run(["--doi", arguments.get("target", "")])
        elif name == "fetch_papers":
            result = _run(["--doi-file", arguments.get("file_path", "")])
        else:
            result = f"ERROR: 未知工具 {name}"
        _send_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"content": [{"type": "text", "text": result}], "isError": False},
        })
    else:
        # 未知方法：仅在有 id 时回错误，避免污染无 id 的通知
        if msg_id is not None:
            _send_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })


def main() -> None:
    while True:
        msg = _read_message()
        if msg is None:
            break
        _handle(msg)


if __name__ == "__main__":
    main()
