---
name: whu-paper-fetcher
description: 下载学术论文全文。当用户想获取/下载某篇论文的 PDF 或全文、给了 DOI/URL/标题，或说"下论文/找论文/获取全文/帮我搞到这篇"时使用。支持武大机构权限（ScienceDirect 等 Elsevier 系）与 OA 开放获取兜底；CLI 覆盖不到的出版商、或你要的是正文文本与配图而非 PDF 时，按 references 里的实战手册走。仅限个人学术用途。
---

# WHU Paper Fetcher

通过 `whu-paper-fetcher` CLI 获取论文全文（PDF 或纯文本）。工具封装了武大机构访问链路（CAS 登录 → ersp EZproxy → ScienceDirect ARP 全文接口）与 OA 四连兜底（Unpaywall / Semantic Scholar / OpenAlex / Europe PMC）。

## 何时使用

- 用户给了 DOI、论文 URL，或论文标题想下载
- 用户说"下这篇论文"、"找全文"、"获取 PDF"、"帮我把这篇搞到"
- 批量：用户给了一串 DOI/URL，或一段参考文献列表

## 走哪条路径

**A. 先跑 CLI —— 默认选择。** 覆盖绝大多数 Elsevier 系论文与 OA 渠道，一条命令的事。

**B. CLI 覆盖不到，或你要的不只是 PDF —— 读 `references/fulltext-playbook.md`。**
那份手册记录了在真实校园网 + 图书馆代理环境下把「全文 + 图」拿到手的完整方法，适用场景：

| 你要的 | 手册里看哪部分 |
|---|---|
| 非 Elsevier 出版商（Wiley / T&F / Springer / Nature / PNAS / IEEE / PE&RS …） | 各出版商的代理落点与 PDF 直链规律 |
| **正文文本 + 配图**（比 PDF 更适合喂给 AI 精读） | ARP 全文接口、出版社公共 CDN 取图 |
| 图是矢量图，抽不出来 | 整页渲染 + 图注定位 |
| 被拦住了（Cloudflare / 跳登录 / 文件被占用 / 一直转圈） | 处置与已知坑清单 |

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

- **不要把「手动登录」当默认答案。** 凭证一次录入后，CAS 会话应当自动完成 —— 这正是本工具存在的意义。遇到登录类报错，先确认凭证文件是否存在且字段非空（可只打印长度、**不要回显密码**），再重试。
- 只有当平台弹出**人机验证**、工具明确无法自动通过时，才请用户手动过一次验证。本工具不提供绕过验证的方法。
- 若 OA 与机构通道都失败，如实告知用户该文暂无法自动获取，不要伪造下载结果。
- 需要更细的链路排查（某个出版商拿不下、图取不下来、要正文而非 PDF），查 `references/fulltext-playbook.md`，不要凭猜测硬怼出版社原站。

## 注意事项

- 全文仅供个人学术使用，不得对外分发
- 遵守请求节流，避免触发出版社或学校风控
- 不要伪造 DOI、不要谎报下载成功
