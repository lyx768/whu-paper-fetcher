# 让 AI 帮你下论文（白痴级指南）

本工具能让你的 AI 编程助手（Codex / Claude Code / OpenCode / Qwen Code / Zed / Cursor / GitHub Copilot）直接帮你**找论文、下全文**。

你不用懂原理，照下面做就行。做完之后，以后对 AI 说一句「下这篇论文 DOI xxx」它就会自己跑。

---

## 第 0 步：装好工具（一次性）

打开终端，复制粘贴这一条：

```bash
pip install whu-paper-fetcher
# 或者从源码装（开发者）：
# git clone https://github.com/lyx768/whu-paper-fetcher && cd whu-paper-fetcher && pip install -e .
```

装完验证一下（应该能打印出版本/帮助，不报错就行）：

```bash
whu-paper-fetcher --help
```

> Windows 如果提示「命令找不到」，先装 Python 并勾选 "Add to PATH"，或重开终端。

---

## 第 1 步：告诉工具你的武大账号（一次性）

工具要用你的武大身份去图书馆下载，所以要把学号/密码存到本地（**只存在你自己电脑上，不会上传**）：

```bash
python -m whu_paper_fetcher.scripts.whu_creds_input
# 如果上面不行，从仓库运行：
# python scripts/whu_creds_input.py
```

按提示输入你的武大学号（或 CAS 账号）和密码即可。

---

## 第 2 步：把「下论文」能力接进你用的 AI 工具

**先看你用哪个工具，照对应的一段做：**

### 如果你用 Codex / Claude Code / OpenCode / Qwen Code（这一类都是「能自己跑命令的 AI」）

它们都认同一种 skill 文件，一行命令接好：

```bash
# 进入仓库的 integrations 目录后运行：
#   macOS / Linux:
bash integrations/install.sh
#   Windows (PowerShell):
powershell -ExecutionPolicy Bypass -File integrations/install.ps1
```

这会把 skill 自动链接到对应目录。接完**重启一下你的 AI 工具**让它能读到。

> 手动也行（可选，给爱折腾的人）：
> - Codex → 把 `integrations/skill/` 软链到 `~/.codex/skills/whu-paper-fetcher`
> - Claude Code / OpenCode → 软链到 `~/.claude/skills/whu-paper-fetcher`（OpenCode 会自动读这个目录）
> - Qwen Code → 软链到 `~/.qwen/skills/whu-paper-fetcher`

### 如果你用 Zed / Cursor / GitHub Copilot（这一类是「编辑器里的 AI」）

它们通过 MCP 协议接。先把 MCP server 依赖装上：

```bash
pip install "mcp[cli]"
```

然后按你用的编辑器，把下面这段配置加进去（把 `/绝对路径/到/whu-paper-fetcher/integrations/mcp/server.py` 换成你电脑上这个文件的实际路径）：

**Zed** — 编辑 `~/.config/zed/settings.json`，加：
```json
{
  "context_servers": {
    "whu-paper-fetcher": {
      "command": "python",
      "args": ["/绝对路径/到/whu-paper-fetcher/integrations/mcp/server.py"],
      "env": {}
    }
  }
}
```

**Cursor** — 编辑 `~/.cursor/mcp.json`，加：
```json
{
  "mcpServers": {
    "whu-paper-fetcher": {
      "command": "python",
      "args": ["/绝对路径/到/whu-paper-fetcher/integrations/mcp/server.py"]
    }
  }
}
```

**GitHub Copilot (VS Code)** — 在项目根目录或用户目录放一个 `.mcp.json`，加：
```json
{
  "mcp": {
    "servers": {
      "whu-paper-fetcher": {
        "command": "python",
        "args": ["/绝对路径/到/whu-paper-fetcher/integrations/mcp/server.py"]
      }
    }
  }
}
```
然后重启 VS Code，在 Copilot Chat 里应该能看到 `whu-paper-fetcher` 的工具。

---

## 第 3 步：以后怎么用（最重要的）

接好之后，**直接对 AI 说人话就行**，例如：

- 「帮我下载这篇论文：DOI 10.1016/j.geoderma.2023.116123」
- 「找一下《Deep learning for soil spectroscopy》这篇全文，下给我」
- 「这是一批 DOI，批量下载：[贴一个 DOI 列表]」

AI 会自己：① 把标题解析成 DOI（如果你给的是标题）② 调 `whu-paper-fetcher` 下载 ③ 把文件存到 `~/Downloads/whu-papers/` 并告诉你路径。

---

## 卡住了怎么办（白痴级排查）

| 现象 | 怎么办 |
|---|---|
| 说「遇到 Cloudflare 挑战页 / 需要登录」 | 工具不会绕过验证。**你手动用浏览器登录一次武大图书馆**，再让 AI 重试 |
| 说「whu-paper-fetcher 未安装」 | 回到第 0 步重装；确认终端能跑 `whu-paper-fetcher --help` |
| AI 说「没有下论文的工具」 | 第 2 步没接好，重启 AI 工具；或检查 skill/MCP 路径是否填对 |
| 下载的文件打不开 | 工具已做双重校验；若仍异常，多半是该文不在武大权限内，换 OA 渠道或手动下 |
| 一次下太多被限速 | 工具自带节流；别并行狂刷，等一会儿再试 |

---

## 给 AI 工具开发者 / 想自己接的人

- `integrations/skill/SKILL.md` 是一个标准的 Claude Code 格式 skill，任何认这种格式的 agent（Codex/Claude Code/OpenCode/Qwen Code）直接复用。
- `integrations/mcp/server.py` 是一个 stdio MCP server，包装了 CLI，任何支持 MCP 的客户端都能接。
- 详细安全与合规说明见仓库根目录 `DISCLAIMER.md`。仅限个人学术用途。
