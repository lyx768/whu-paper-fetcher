# whu-paper-fetcher

武大专属文献全文获取工具。输入 DOI / 论文 URL，自动拿到全文 PDF 或纯文本。

核心能力（**武大专属、别处没有**）：

- **武大 CAS 自动登录** —— 经浏览器后端复用你的武大账号会话，无需每次手填
- **`whu.metaersp.cn` 门户 SSO → `ersp.lib.whu.edu.cn` EZproxy** 的完整访问链路
- **ScienceDirect ARP 纯文本全文接口** —— 免 TDM API key 直接拿到正文（这是本工具最有价值的部分）
- **Cloudflare Turnstile** 挑战页的处置经验（切前台 + 站内跳新链接）
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
git clone https://github.com/<你的账号>/whu-paper-fetcher.git
cd whu-paper-fetcher
pip install -e .                       # 核心（OA + WHU 访问）
pip install -e '.[browser]'           # + Playwright 后端（同学默认用这个）
pip install -e '.[verify]'            # + pymupdf（下载后做首页文本校验）
```

Playwright 还需装一次浏览器内核：`playwright install chromium`

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
| `playwright`（默认） | 同学 | 用 Playwright 驱动本机 Chromium，无第三方依赖。首次需手动过一次武大 SSO，之后由 creds 自动登录 |
| `webbridge` | 你自己 | 复用 Kimi WebBridge 扩展 + 本地 daemon（`127.0.0.1:10086`），复用已登录的 Edge 会话 |

> 注意：ScienceDirect 的 Cloudflare 挑战页在**隐藏/无头窗口**下可能挂起。
> Playwright 后端默认以有头模式启动；若遇到挑战页卡死，把浏览器窗口放到前台再重试。

---

## 安全与隐私

- 你的 CAS 密码只存在本地 `creds.json`，**绝不写入代码、日志或对话**。
- 本工具**仅复用你武大账号已有的真实访问权限**，不是破解付费墙；下载请遵守出版商与学校使用条款。
- 自动化访问可能触发出版商速率限制 / 二次验证（MFA），此时需你手动过一次。

---

## 已知限制

- 武大 EZproxy 会话约 **1 天过期**，过期后重新运行会自动重登（除非触发 MFA）。
- SD ARP 全文为纯文本；若需出版社排版版 PDF，走页面渲染兜底（版式非官方）。
- Playwright 后端（同学默认路径）尚未在真实武大账号下完整回归测试，如遇 SSO / 挑战页选择器变化，请提 issue。
- 非 SD 出版商（Wiley / T&F / Springer 等）走 OA 兜底；未做各家 EZproxy 适配。

---

## License

[MIT](LICENSE)
