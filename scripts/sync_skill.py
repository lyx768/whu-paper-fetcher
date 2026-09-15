#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把本地 runtime skill 同步进本仓库（自动脱敏）。

背景：作者本地有一份持续迭代的「武大文献权限获取方法论」skill
（`~/.workbuddy/skills/whu-literature-download/SKILL.md`，纯文本、无版本管理），
本仓库的 `integrations/skill/` 是给外部用户的标准 skill 入口。
本脚本把前者同步为后者的参考文档，并在写入前做实名/路径脱敏 —— 因为本仓库是公开的。

用法：
    python scripts/sync_skill.py            # 同步（写入仓库）
    python scripts/sync_skill.py --check    # 只比对差异，不写文件，有差异时退出码 1
"""
import argparse
import os
import re
import sys
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(REPO, "integrations", "skill", "references", "fulltext-playbook.md")

# 本地 runtime skill 的位置。默认走 WorkBuddy 目录，可用环境变量覆盖。
SRC = os.environ.get(
    "WHU_SKILL_SRC",
    os.path.join(os.path.expanduser("~"), ".workbuddy", "skills",
                 "whu-literature-download", "SKILL.md"),
)

HEADER = """# 全文获取实战手册（从机构权限到图表落地）

> 本文件是 `whu-paper-fetcher` 的**参考文档**，记录在真实校园网 + 图书馆代理环境下
> 把论文「全文 + 图」拿到手的完整方法论与踩坑清单。
> 由本地实战 skill 同步而来（同步日期：{today}），写入前已做实名与本地路径脱敏。
>
> 阅读建议：先看 `SKILL.md` 用 CLI 解决常规需求；**当 CLI 失败、或你需要的不只是 PDF
> 而是正文文本与图时**，再回到本文件按出版商/链路找对应章节。
>
> 合规前提：仅限个人学术用途，遵守仓库根目录 `DISCLAIMER.md` 与所在机构订阅条款。

"""

# 脱敏规则：顺序有意义，先处理更具体的路径形态。
SCRUBS = [
    # C:\Users\<name>\AppData\Local\... -> %LOCALAPPDATA%\...
    (re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'`]+[\\/]AppData[\\/]Local", re.I),
     "%LOCALAPPDATA%"),
    # C:\Users\<name>\... -> %USERPROFILE%\...
    (re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'`]+", re.I), "%USERPROFILE%"),
    # /c/Users/<name>/... (Git Bash 形态)
    (re.compile(r"/[a-z]/Users/[^/\s\"'`]+", re.I), "%USERPROFILE%"),
    # CAS 保密协议弹窗要填姓名：promptText:"张三" -> 占位符
    (re.compile(r'(promptText\s*:\s*)"[^"]{1,12}"'), r'\1"<你的姓名>"'),
    # 页面上的登录态文案："李*翔|退出"
    (re.compile(r'"[\u4e00-\u9fa5]\*[\u4e00-\u9fa5]\|退出"'), '"<用户名>|退出"'),
]

# 额外兜底：若脚本作者本机用户名/姓名以明文出现，逐条抹掉。
# 通过环境变量注入，避免把实名写进公开仓库。
EXTRA_NAMES = [n for n in os.environ.get("WHU_SCRUB_NAMES", "").split(",") if n.strip()]


def scrub(text):
    hits = []
    for pat, repl in SCRUBS:
        text, n = pat.subn(repl, text)
        if n:
            hits.append("%s x%d" % (pat.pattern[:34], n))
    for name in EXTRA_NAMES:
        if name in text:
            hits.append("literal:%s x%d" % (name, text.count(name)))
            text = text.replace(name, "<已脱敏>")
    return text, hits


def strip_frontmatter(text):
    """去掉 YAML frontmatter（runtime skill 有 name/description，参考文档不需要）。"""
    if text.lstrip().startswith("---"):
        m = re.match(r"\s*---\s*\n.*?\n---\s*\n", text, re.S)
        if m:
            return text[m.end():]
    return text


def build():
    if not os.path.isfile(SRC):
        sys.exit("找不到源文件：%s\n（可用环境变量 WHU_SKILL_SRC 指定）" % SRC)
    with open(SRC, encoding="utf-8") as f:
        raw = f.read()

    body = strip_frontmatter(raw).lstrip("\n")
    body, hits = scrub(body)

    # 正文里出现的一级标题降一级，让本文件自身的 H1 唯一
    body = re.sub(r"(?m)^# (?!#)", "## ", body)

    out = HEADER.format(today=date.today().isoformat()) + body.rstrip() + "\n"
    return out, hits, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写入")
    args = ap.parse_args()

    out, hits, raw = build()

    old = ""
    if os.path.isfile(DEST):
        with open(DEST, encoding="utf-8") as f:
            old = f.read()

    if args.check:
        if old == out:
            print("同步一致，无需更新。")
            return 0
        print("有差异：本地 %d 字符 / 仓库 %d 字符" % (len(out), len(old)))
        return 1

    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    with open(DEST, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)

    rel = os.path.relpath(DEST, REPO).replace("\\", "/")
    print("已写入 %s" % rel)
    print("  源：%s（%d 字符）" % (SRC, len(raw)))
    print("  出：%d 字符" % len(out))
    print("  脱敏命中：%s" % ("; ".join(hits) if hits else "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
