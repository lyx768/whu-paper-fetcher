---
name: whu-paper-fetcher
description: 下载学术论文全文。当用户想获取/下载某篇论文的 PDF 或全文、给了 DOI/URL/标题，或说"下论文/找论文/获取全文/帮我搞到这篇"时使用。支持武大机构权限（ScienceDirect 等 Elsevier 系）与 OA 开放获取兜底。仅限个人学术用途。
---

# WHU Paper Fetcher

通过 `whu-paper-fetcher` CLI 获取论文全文（PDF 或纯文本）。该工具封装了武大机构访问链路（CAS 登录 → ersp EZproxy → ScienceDirect ARP 全文接口）与 OA 四连兜底（Unpaywall / Semantic Scholar / OpenAlex / Europe PMC）。

## 何时使用
- 用户给了 DOI、论文 URL，或论文标题想下载
- 用户说"下这篇论文"、"找全文"、"获取 PDF"、"帮我把这篇搞到"
- 批量：用户给了一串 DOI/URL，或一段参考文献列表

## 前置条件（首次使用需确认）
- 已安装：`pip install whu-paper-fetcher`（或从仓库 `pip install -e .`）
- 已配置武大账号凭证：`python scripts/whu_creds_input.py` 写入本地凭证文件（默认 `~/.config/whu-paper-fetcher/creds.json`，不进仓库）
- 浏览器后端默认 Playwright（同学装好即可用）；作者本机用 WebBridge 栈（`browser.backend = "webbridge"`）
- 仅学术个人用途，遵守仓库 DISCLAIMER

## 工作流程
1. **解析目标为 DOI**：若用户给的是标题而非 DOI/URL，先用 web 搜索或 Crossref API（`https://api.crossref.org/works?query=<title>&rows=1`）解析出真实 DOI。**不要瞎编或猜测 DOI**，解析后向用户复述确认的 DOI 再下载。
2. **单篇下载**：
   ```
   whu-paper-fetcher --doi "<DOI>"
   ```
   （若用户给的是 URL，先从中提取出 DOI 再作为 --doi 参数传入）
3. **批量下载**：把每行一个 DOI 写入文本文件，然后：
   ```
   whu-paper-fetcher --doi-file list.txt
   ```
4. **结果**：默认落到 `~/Downloads/whu-papers/`，返回绝对路径。工具内置请求节流（间隔 + 每日上限），不要并行狂刷。

## 失败处理
- 若工具报"遇到 Cloudflare 挑战页"之类，说明需要用户在真实浏览器登录一次（手动过一次验证）——此时提示用户手动操作，本工具不提供绕过验证的方法。
- 若 OA 与机构通道都失败，如实告知用户该文暂无法自动获取，不要伪造下载结果。

## 注意事项
- 全文仅供个人学术使用，不得对外分发
- 遵守请求节流，避免触发出版社或学校风控
- 不要伪造 DOI、不要谎报下载成功
