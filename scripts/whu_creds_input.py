#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""武大 CAS 凭证写入工具（在用户本地终端交互运行，凭证不经过任何 AI 对话）。

用法：
    python scripts/whu_creds_input.py
    python scripts/whu_creds_input.py --path ~/.config/whu-paper-fetcher/creds.json

写入后凭证存于本地配置文件（.gitignore 已屏蔽，不会上传）。
AI 只读该文件用于自动填充 CAS 登录表单，不在任何回复中回显密码。
"""
import json
import getpass
import os
import argparse

DEFAULT_PATH = os.path.expanduser("~/.config/whu-paper-fetcher/creds.json")
NOTE = "由用户通过本地终端写入，严禁在对话窗口中输入密码。"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=DEFAULT_PATH, help="凭证文件保存路径")
    a = ap.parse_args()

    print("== 武大 CAS 凭证写入（输入密码时不回显）==")
    username = input("学号: ").strip()
    if not username:
        print("学号为空，退出。")
        return 1
    password = getpass.getpass("密码: ")
    if not password:
        print("密码为空，退出。")
        return 2

    data = {"username": username, "password": password, "note": NOTE}
    os.makedirs(os.path.dirname(a.path) or ".", exist_ok=True)
    with open(a.path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 验证：只报长度，不回显内容
    with open(a.path, "r", encoding="utf-8") as f:
        check = json.load(f)
    print("写入成功:", a.path)
    print("  username 长度:", len(check.get("username", "")))
    print("  password 长度:", len(check.get("password", "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
