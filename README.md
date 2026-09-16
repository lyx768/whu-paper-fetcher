# whu-paper-fetcher

武大专属文献全文获取工具。输入 DOI / 论文 URL，自动拿到全文 PDF 或纯文本。

> ⚠️ 使用本工具前请先阅读 [DISCLAIMER.md](DISCLAIMER.md)（法律与责任声明）。

## ▶ 想让 AI（Codex / Claude Code / OpenCode / Qwen Code / Zed / Cursor / Copilot）帮你下论文？

看 [integrations/README.md](integrations/README.md) —— 一条命令接好 skill / MCP，之后直接对 AI 说「下这篇论文 DOI xxx」它就会自己跑。

核心能力（**武大专属、别处没有**）：

- **武大 CAS 自动登录** —— 本地凭证自动填表，全程无窗无感；仅在触发 MFA/验证码时提示你手动处理
- **`whu.metaersp.cn` 门户 SSO → `ersp.lib.whu.edu.cn` EZproxy** 的完整访问链路
- **全自动无感取全文** —— Playwright 无头只做 SSO，`ersp` 域请求由 curl_cffi（Chrome TLS 指纹）承接，绕过 EZproxy 对自动化浏览器的指纹拦截
- **ScienceDirect ARP 纯文本全文接口** —— 免 TDM API key 直接拿到正文（这是本工具最有价值的部分）
- **OA 四连兜底** —— Unpaywall / Semantic Scholar / OpenAlex / Europe PMC，能白嫖先白嫖

> 设计定位：服务武大同学。你只需 `pip install` + 配个武大账号，给 DOI 就能用。

---

## 与现有开源项目的关系

GitHub 上已有成熟的通用下载工具（如 `paper-fetcher` 38★、`auto-paper-harvester` 27★），
它们覆盖了"OA → 机构 EZproxy → 元数据"的主干管线。本项目的**增量价值**在于上面列出的
**武大专属访问层 + SD ARP 全文接口**，因此我们选择自建一个聚焦武大的轻量仓库，
OA 兜底逻辑内联（约百行），避免同学再装一套通用工具的配置心智负担。

如有兴趣，欢迎把武大访问层反向贡献回上述通用项目。

---

## 安装

```bash
git clone https://github.com/lyx768/whu-paper-fetcher.git
cd whu-paper-fetcher
pip install -e .                       # 核心（OA + WHU 访问）
pip install -e '.[browser]'           # + Playwright 后端 + curl_cffi（同学默认用这个）
pip install -e '.[verify]'            # + pymupdf（下载后做首页文本校验）
```

Playwright 还需装一次浏览器内核：`playwright install chromium`

### macOS 用户

- 建议用 Homebrew 装 Python：`brew install python3`，随后用 `python3 -m pip` 代替 `pip`
- Playwright 的 Chromium 内核跨平台自动下载，无需手动装浏览器
- 配置文件与凭证默认落在标准位置（Windows / Linux / macOS 一致）：
  - 配置：`~/.config/whu-paper-fetcher/config.toml`
  - 凭证：`~/.config/whu-paper-fetcher/creds.json`
  - 下载目录：`~/Downloads/whu-papers`
- 其余用法与 Windows / Linux 完全一致

---

## 配置

1. 复制示例配置并填写：

   ```bash
   cp config.example.toml config.toml
   ```

   关键字段（都在 `config.toml` 里，代码不写死任何个人信息）：

   | 字段 | 含义 |
   |---|---|
   | `whu.username` | 武大学号（留空则读 creds 文件） |
   | `whu.display_name` | 数据库保密协议弹窗要填的真实姓名 |
   | `download.output_dir` | PDF / 全文落盘目录 |
   | `browser.backend` | `playwright`（默认，便携）或 `webbridge`（你的 Kimi WebBridge 栈） |
   | `oa.email` | OA 查询用邮箱（任意邮箱，礼貌池用） |
   | `request.delay_seconds` | 每篇论文之间的间隔秒数（默认 3，越大越温和） |
   | `request.daily_limit` | 每日最多下载篇数（默认 50，防过量触发限速） |

2. 写入 CAS 密码（**本地文件，绝不进仓库**）：

   ```bash
   python scripts/whu_creds_input.py
   ```

   密码存到 `~/.config/whu-paper-fetcher/creds.json`，`.gitignore` 已屏蔽。

---

## 使用

```bash
# 单篇（DOI）
whu-paper-fetcher --doi 10.1016/j.geoderma.2023.116456

# 批量（每行一个 DOI）
whu-paper-fetcher --doi-file dois.txt

# 跳过 OA、直接走武大代理
whu-paper-fetcher --doi 10.xxxx/xxx --skip-oa

# JSON 输出（便于管道处理）
whu-paper-fetcher --doi 10.xxxx/xxx --json
```

命中后产物（在 `output_dir`）：

- `<doi>.pdf` —— 优先来自 OA 直链；否则尽力用页面渲染（PDF 版式非出版社排版件，会标注）
- `<pii>_fulltext.md` —— SD ARP 纯文本全文
- `<pii>_body.json` / `<pii>_doc.html` —— 原始 ARP 响应与文章 HTML（调试用）

---

## 浏览器后端

| 后端 | 适用 | 说明 |
|---|---|---|
| `playwright`（默认） | 同学 | Playwright 无头 Chromium 做 SSO + curl_cffi 承接全文请求，无第三方扩展依赖。本地凭证自动登录，无窗无感 |
| `webbridge` | 你自己 | 复用 Kimi WebBridge 扩展 + 本地 daemon（`127.0.0.1:10086`），复用已登录的 Edge 会话 |

> 注意：ScienceDirect 等站点可能出现人机验证（CAPTCHA / Turnstile）挑战页。
> **本工具不提供绕过验证的方法**；遇到挑战请手动完成后重试。Playwright 后端默认**无头模式**
> （不弹任何窗口），若返回 `MFA_REQUIRED`，说明账号触发了二次验证，需你手动登录一次校内门户再重试。

---

## 安全与隐私

- 你的 CAS 密码只存在本地 `creds.json`，**绝不写入代码、日志或对话**。
- 本工具**仅复用你武大账号已有的真实访问权限**（经学校 EZproxy 授权通道），不是破解付费墙。
- 自动化访问可能触发出版商速率限制 / 二次验证（MFA），此时需你手动过一次。
- 内置请求节流（间隔 + 每日上限），请按默认配置使用，勿为追求速度关闭。
- **使用即代表你已阅读并同意 [DISCLAIMER.md](DISCLAIMER.md) 的全部条款。**

---

## 已知限制

- 武大 EZproxy 会话约 **1 天过期**，过期后重新运行会自动重登（除非触发 MFA）。
- SD ARP 全文为纯文本；附带的 PDF 为页面打印渲染版（版式非出版社排版件，工具会标注）。
- 学校 EZproxy 依赖浏览器指纹策略：UA 伪装 + curl_cffi（Chrome TLS 指纹）已实测通过；
  若学校侧策略升级导致断连，请提 issue 并附 JSON 输出的错误码。
- 非 SD 出版商（Wiley / T&F / Springer 等）走 OA 兜底；未做各家 EZproxy 适配。

---

## License

[MIT](LICENSE)
