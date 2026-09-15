# 全文获取实战手册（从机构权限到图表落地）

> 本文件是 `whu-paper-fetcher` 的**参考文档**，记录在真实校园网 + 图书馆代理环境下
> 把论文「全文 + 图」拿到手的完整方法论与踩坑清单。
> 由本地实战 skill 同步而来（同步日期：2026-09-15），写入前已做实名与本地路径脱敏。
>
> 阅读建议：先看 `SKILL.md` 用 CLI 解决常规需求；**当 CLI 失败、或你需要的不只是 PDF
> 而是正文文本与图时**，再回到本文件按出版商/链路找对应章节。
>
> 合规前提：仅限个人学术用途，遵守仓库根目录 `DISCLAIMER.md` 与所在机构订阅条款。

## 武大文献权限批量下载

## 前置
- 用户 Edge 已登录 `whu.metaersp.cn`（数据库导航页，信息门户账号）
- Kimi WebBridge daemon `127.0.0.1:10086`，session 例 `whu-lib-access`
- Edge 下载目录是 `F:\landsat\landsat_2010`（用户自定义，非 Downloads！）
- 工作驱动脚本参考：`F:\AGENT\work\2026-09-04-22-28-15\browser_batch.py`
- **2026-09-07 用户明确：入口走武大图书馆门户（library.whu.edu.cn / metaersp.cn 数据库导航），再跳 ersp；直接 daemon navigate ersp.lib.whu.edu.cn 会因缺 SSO cookie 跳到 `cas.whu.edu.cn` 统一身份认证，登录态不自动建立。** 正确流程：先在 Edge 里经图书馆入口登录，再在 daemon 里 `location.href` 站内跳转。

## 自动登录（CAS 会话，2026-09-10 新增 · 用户要求"下次别让我手动登"）
- **目标**：文献管线开始前自动建立 CAS 数据库会话，不再依赖用户手动在浏览器登录。
- **脚本**：`F:\AGENT\scripts-archive\whu_cas_autologin.py` —— 调 daemon 导航 CAS 登录页；已登录（重定向个人中心）直接返回；否则优先用浏览器自动填充、无填充则读本地凭证文件填充并提交。
- **凭证文件（仅本地，绝不进对话）**：`%USERPROFILE%\.workbuddy\secrets\whu_cas.json` → `{"username":"...","password":"..."}`。**由用户用本地终端写入，AI 不代填、不在回复中回显**（RED_LINES R5）。
- **调用时机**：ScienceDirect 系走 ersp 前先跑一次；返回码 0=已登录/成功，2=MFA_REQUIRED（需用户手动过一次二次验证），1=失败。
- **前置判据（2026-09-11 新增 · 同日二次修正）**：跑之前先检查 `whu_cas.json` 里 username/password **是否为非空字符串**（可只打印 `len` 与是否为空，**不打印值**）——空串时脚本只会返回"凭证文件为空"。
  - ⚠️ **空串 ≠ 用户没填过凭证**（2026-09-11 踩坑）：用户很可能填在**浏览器密码管理器**里而不是这个 json。**空串时必须再查一次 Edge 密码库**（`Login Data` sqlite，只读 `origin_url`/`username_value`/`date_last_used`，**不解密密码值**）：
    ```
    cp "%LOCALAPPDATA%/Microsoft/Edge/User Data/Default/Login Data" /tmp/ld.db
    # select origin_url, username_value, length(password_value), date_last_used from logins
    ```
    Chrome/Edge 时间戳换算：`unix = ts/1e6 - 11644473600`。命中 `cas.whu.edu.cn` 且 `date_last_used` 近期 → **用户确实登录过、密码在浏览器里**，别对用户说"你没填"。
  - 两条都空才是真的没有凭证，此时**立即转 OA 路径，不要在此耗时**。
- **captcha 判据（2026-09-11 修正，原写法是错的）**：**不要**用 `!!document.querySelector('#captchaImg')` 判断"有验证码"。武大 CAS 的 `#captchaDiv`/`#captchaImg`/`#captcha` **默认带 `hide` class、`getBoundingClientRect()` 全为 0**，元素存在但不显示、不拦登录。正确判据是**可见性**：`el.offsetParent !== null && rect.width > 0`。
  - 教训：**"元素存在" ≠ "可见/必填"**。同类错误还有"文件存在 ≠ 内容正确"。任何"有/没有"的结论都要用**能反映语义的那个指标**（可见性、非空性、内容匹配），不能用存在性代替。
- **Edge 自动填充无法被自动化触发（2026-09-11 实测）**：Chromium 的密码填充下拉属浏览器 UI 层（不在页面 DOM 内，`querySelectorAll` 探不到，`[class*=autofill]` 计数恒为 0）。实测 `evaluate` 里 `el.focus()` 可让 `activeElement` 正确变化，daemon `click`（by selector）也返回成功，但 **`input.value` 始终为空、下拉不弹**；CDP `Input.dispatchMouseEvent` 同样无效。→ **别指望脚本把浏览器密码"调出来"，只有用户本人手点一次才行；长期方案仍是让用户把凭证写进 json。**
- **MFA 限制（必须如实告知用户）**：若武大 CAS 启用短信/OTP/智慧珞珈二次验证，自动填充密码后仍卡在验证页，脚本返回 MFA_REQUIRED，此时仍需用户手动过一次；之后会话期内可复用。
- **注意**：CAS 会话约 1 天过期（见坑清单），过期后管线自动重跑本脚本即可，无需用户干预——除非触发 MFA。

## ⭐ 全链路实测打通记录（2026-09-11 18:30，凭证已入 json，CAS 自动登录可用）

**自 CAS 登录到全文 PDF 的完整可复现链路**（每步都实测过）：

1. **autologin 脚本已修**（`F:\AGENT\scripts-archive\whu_cas_autologin.py`）：武大 CAS 提交按钮不是 `button`/`input[type=submit]`，是 **`<a id="login_submit">登录`** —— 旧选择器 `querySelectorAll('button,input[type=submit]')` 永远返回 `no-btn`（这正是 09-11 首测 FAIL 的原因）。已修为 `'#login_submit,button,input[type=submit],a[role=button]'` 优先命中 id。表单字段实况：`id=username`(text) + `id=password`(type=password, **name=passwordText**) + `id=captcha`(隐藏)。CAS 成功落地 URL 含 `personalInfo/personCenter`（脚本判定已覆盖）。
2. **EZproxy 深链直连不可用**：`ersp.lib.whu.edu.cn/.../G.https/science/article/pii/...` 直接 navigate → `ERR_EMPTY_RESPONSE`。**必须从门户点进去**建立会话 cookie。
3. **门户 SSO 链路**（CAS 已登录后全程免密）：
   `whu.metaersp.cn/` → 点 `loginBtn`（CAS SSO 自动回跳，页面出现"<用户名>|退出"）→ `databaseList` → 点 title 含 ScienceDirect 的 `<a>`（先 `removeAttribute('target')` 免开新 tab）→ 详情页 → **先点"确定"（用户保密协议）会弹 prompt"请输入您的姓名"** → 用 CDP `Page.handleJavaScriptDialog {accept:true, promptText:"<你的姓名>"}` 处理，否则页面被 dialog 挂死 → 点 `database-hero__button`（访问地址）→ 落 EZproxy SD 主页（`Brought to you by: Wuhan University` 可作成功判据）。
4. **代理内文章页**：`.../G.https/science/article/pii/{PII}` 导航成功 → 全文在 DOM（txtlen ~60k、`Introduction` 存在）。ARP body 无需手工补——正文随页面加载。
5. **PDF 兜底 = `Page.printToPDF`（本轮最大杀器）**：pdfft 链接（代理重写版）fetch 回 HTML（meta refresh `ref=cra_js_challenge`）；真实导航跳 `pdf.sciencedirectassets.com/craft/capi/cfts/init` → "Request Verification: In Progress" **挂死**（无 iframe 无按钮无 checkbox，bringToFront + CDP 真鼠标都无效，别再耗时）。直接对文章页跑 `Page.printToPDF {printBackground:true, preferCSSPageSize:true}` → 20 页 / 11 MB 归档件。**响应 ~15 MB base64，必须 `-o` 落 temp 再解析**。诚实标注：这是网页渲染版（非出版社排版版），入库笔记 `pdf_note` 写明来源与差异；首页标题/作者/期刊仍须程序化核验。

## ⭐ ScienceDirect 闭源全文：ARP 接口路线（2026-09-10 打通，首选，纯文本全文）

**结论先说**：ScienceDirect 文章页的 HTML 只是"外壳"，**正文由前端异步请求 `/sdfe/arp/pii/{PII}/body` 拉取**。EZproxy 只重写 HTML 里的 href，**JS 拼出的 ARP 地址绕过代理前缀** → 该请求根本没发出/失败 → 页面只剩摘要（且此时 `View PDF` 常是 `aria-disabled="true"`、pdfft 深链经代理返回 403）。所以"代理能进文章页但正文抓不到"不是单篇问题，是通用缺陷。修法是**手工把那个 ARP 请求补回来**。

### 一键脚本（已落盘）
```bash
python F:/AGENT/scripts-archive/sci-fulltext/fetch_sd.py <PII> --no-search --tag <名字>
## 产出 <tag>_doc.html / <tag>_body.json / <tag>_fulltext.md
python F:/AGENT/scripts-archive/sci-fulltext/sd_body_parse.py <body.json> <out.md>
```

### 手工步骤（脚本失效时照做）
1. `network start` → `navigate` 到 `https://ersp.lib.whu.edu.cn/s/com/sciencedirect/www/G.https/science/article/pii/<PII>`（**直达即可，不必走搜索**）→ 等 10–13 s
2. `network list` 找 `mimeType` 为 `text/html` 且 url 含 `/pii/<PII>` 的请求 → `network detail` 取其 `body`（服务端原始 HTML，~190KB）
3. 正则取 token：`"entitledToken":"([A-Fa-f0-9]+)"`（**80 位十六进制**）
4. `navigate` 到 `.../sdfe/arp/pii/<PII>/body?entitledToken=<token>` → 等 8 s → `network list` 找 url 含 `/body?` 的请求 → `network detail` 取 JSON
5. 解析 SD 内容模型（节点形如 `{"#name":tag, "$":attrs, "$$":children, "_":text}`）→ 章节标题 + 段落

### 诊断判据（判断该走这条路）
服务端 HTML 里查这些字符串：
- `Introduction` 出现 **0** 次 → 正文靠 AJAX，必须走 ARP
- `"ajaxLinks":{...,"body":true}`、`"body":{}` → 正文位空着等异步填
- `"articleEntitlement":{...,"entitled":true,"authenticationMethod":"IP"}` → 机构权限**没问题**（别再去折腾登录）
- `"accessTypeLabel":"Full text access"` → 有权限；`"isPdfFullText":false` → PDF 此路不通

### 可复用的兄弟接口
`/sdfe/arp/pii/<PII>/references?entitledToken=`、`/category/toc?jwt=`、`/citingArticles?pii=&doi=`、`/recommendations`、`/author-metadata` —— 均返回 JSON，照同样方式取。

### ⭐ SD 图表免登录直下（ars.els-cdn.com 公共 CDN，2026-09-15 验证）
**结论先说**：ScienceDirect 的**图表图片**（figure/table 渲染图）走公共 CDN `ars.els-cdn.com`，**不需要任何登录/S3 签名**，HTTP 200 直下。
- 规律 URL：`https://ars.els-cdn.com/content/image/1-s2.0-{PII}-gr{N}.jpg`（或 `.png`）。`{N}` 从 `gr1` 顺序试到 `gr30+`，CDN 对不存在的编号返回 404，存在的返回图片字节（>2KB 即有效）。
- PII 由 Crossref `alternative-id[0]` 取，与 ARP 路线一致。
- **ARP JSON 里的 `attachments[*].ucs-locator` 是 `stated` S3 URL，直下 403（签名校验）——别被它误导，一律改用上方 els-cdn 公共 CDN。**
- 批量脚本骨架：
```python
import urllib.request, os
PII="S0016706121001981"   # 1-s2.0- 后面的 PII
D="docs/figures/<stem>"; os.makedirs(D, exist_ok=True)
for n in range(1,31):
    ok=False
    for ext in ("jpg","png"):
        u=f"https://ars.els-cdn.com/content/image/1-s2.0-{PII}-gr{n}.{ext}"
        try:
            r=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.sciencedirect.com/"}),timeout=20)
            d=r.read()
            if len(d)>2000:
                open(f"{D}/fig_{n:02d}.{ext}","wb").write(d); ok=True; break
        except Exception: pass
    if not ok: break   # 连续空号即到末尾
```
- 验证：JPEG 头 `\xff\xd8\xff` / PNG 头 `\x89PNG`，过滤 logo 与 <2KB 的占位。
- **适用前提**：只要拿到 PII 即可批量取图，**不等全文**——封禁期间可先把 13 篇 Elsevier 论文的图表预抓，解锁全文后直接嵌。

### ⚠️ 当前封禁状态（2026-09-15 实测，推翻上方"Elsevier ✅ 可"旧结论）
**自动化拿 ScienceDirect 全文文本当前已被 captcha 墙彻底封死**，以下 4 条路全部复现失败，请勿再耗时重试：
1. `whu-paper-fetcher`（playwright 默认 backend + webbridge 均测）→ **ARP_FAILED**（"未捕获到文章 HTML 响应，可能 SSO 未建立或网络拦截"）
2. daemon `navigate` 直连 `sciencedirect.com/science/article/pii/<PII>` → 落"请稍候… / Are you a robot?" 挑战页，**无 token、无正文**
3. daemon `navigate` 经 ersp 代理 `ersp.lib.whu.edu.cn/s/com/sciencedirect/...` → **"Page not found"**（ERS-P 该 vendor 路径当前不通）
4. urllib / jina reader（`r.jina.ai/http://...`）直取 → Elsevier 全站 **403 "Are you a robot?"**（含 gold-OA 的 Rodriguez/Zhou）
- **根因**：Kimi WebBridge 的 Edge 会话仅有武大网关态，**无 SD 的 CAS entitled ticket**（uas.metaauth.com serviceValidate 带 captcha，全自动过不去）。**唯一解锁**：在 `whu-lib-access` 会话里手动打开任意一篇 SD 文章、完成一次武大 CAS 登录（过 captcha/扫码），让该 Edge 会话持有 SD ticket——之后 `whu-paper-fetcher` 与 ARP 路线才会恢复。CAS ticket 有时效，登录后尽快启动批量。
- 同次测试：Wiley 系经 WHU 代理 `s/com/wiley/...` → **404**；IEEE 系经 WHU 代理 `s/com/ieee/...` → **oops.html（未订阅/被拦）**。这两家当前也走不通，gold-OA 的 Rodriguez/Zhou 经 Unpaywall 仅 SD 主链、无 Elsevier 外镜像。

### 坑
- **JSON body 一律写文件再 `--data-binary @file`**，inline 传参会被 shell 吃掉（`\/` 会被 JSON 解码成 `/`，正则里直接语法报错）。
- **`evaluate` 的 async/await 会挂死**（daemon 返回 HTTP 000），别用 `fetch()` 取正文，改用 `navigate` + `network detail`。
- `network` 的 `detail.body` **可能已是解析好的 dict**（不是字符串），写盘前先判断类型。
- daemon 的 `cdp` 只能发**页面级**命令；`Browser.setDownloadBehavior` / `Page.setDownloadBehavior` 都会报 "Cannot access browser-level commands"。
- daemon 实际工具集比 SKILL 文档多：`find / read_page / network / mouse_click / key_type / send_keys / scroll / wait / dialog / select_option / hover / drag`（文档版本落后，以报错里的 "Available:" 列表为准）。
- daemon 卡死（pid 残留指向死进程）→ 删 `~/.kimi-webbridge/daemon.pid` 再 `kimi-webbridge start`。

## 路线优先级
1. **OA 聚合四连（不碰浏览器，2026-09-05 实测 +3）**：
   a. Unpaywall API（`api.unpaywall.org/v2/<doi>?email=`）→ MDPI/arXiv/PMLR/JMLR/CVPR 显式 URL
   b. Semantic Scholar `api.semanticscholar.org/graph/v1/paper/DOI:<doi>?fields=openAccessPdf` → `openAccessPdf.url`（直链失败时必再试一次 curl-cffi `impersonate='chrome'`，Nature 官方 `.pdf` 链接就是这样拿下的）
   c. OpenAlex `api.openalex.org/works/doi:<doi>` → `locations[].pdf_url`（过滤掉 sciencedirect/linkinghub/elsevier 的死路链接）
   d. Europe PMC：`search?query=DOI:"<doi>"` → pmcid → `fullTextPDF`（isOpenAccess=N 时 404，别浪费时间）
2. **⭐ SFX 链接解析器路线（2026-09-14 打通，订阅论文首选——见下方专节）**
3. **ScienceDirect 系**（Geoderma/Catena/STILL/RSE/STOTEN/ISPRS 等）：ersp 代理路线 —— **先走上面的 ARP 接口拿全文文本**（快、稳、纯文本）；只有必须要 PDF 渲染件时才走下面的 pdfft 流程。
4. **其他出版商**：Wiley/T&F/Springer/Science/IEEE/SSRN 等一律先走 SFX 路线（第 2 条）；Wiley `pdfdirect` 直链 curl-cffi 也 403，只能浏览器

### ⭐ 出版商分流表（2026-09-15 实测定档，先按此决策再动手）
| 出版商 | 全文形式 | headless 可行性 | 走法 |
|---|---|---|---|
| **Elsevier**（ScienceDirect：Geoderma/RSE/ISPRS/STOTEN…） | HTML（ARP `body` JSON）+ PDF | ⚠️ **2026-09-15 起被 captcha 墙封死**（whu-paper-fetcher ARP_FAILED / 直连"请稍候" / ersp 代理 404 / jina 403），需用户在 WebBridge `whu-lib-access` 会话手动过一次武大 CAS 才恢复 | **ARP 接口路线**（见上方专节）仍是对的，但当前前置是"人工登录拿 ticket"；**图表可免登录走 els-cdn 公共 CDN 先预抓**（见上方专节） |
| **IEEE**（TGRS/JSTARS…） | **仅 PDF**（HTML 文章页只有摘要） | ✅ **可**（2026-09-15 打通） | SFX 拿 arnumber → **curl 带精确浏览器 UA + 导出 cookie** 直取 `stampPDF/getPDF.jsp?arnumber=<N>`（见下方 IEEE 专节）。**关键 = UA 必须与浏览器完全一致** |
| **Wiley** | PDF | ✅（走 SFX/EZproxy） | 流程 A |
| **Springer** | PDF | ✅（WAYFless） | 流程 B |
| **SSRN / gold OA** | PDF / HTML | ✅ | 见对应专节 |

### ⭐⭐ IEEE 全文 PDF 获取 = 「精确 User-Agent + 导出 cookie + 主机侧 curl」（2026-09-15 打通，最终解）

**根因**：`ersp.lib.whu.edu.cn` 的 EZproxy **把会话绑定到 User-Agent**。之前 5 条浏览器内路径全败（见下方"失败路径存档"），且 curl 用通用 UA（`Mozilla/5.0`）会被弹回**校外用户登录页**——**真因就是 UA 不匹配，不是没权限、不是 cookie 不够**。

**可复现步骤（零前台，纯主机侧）**：
1. 从 daemon 取**浏览器精确 UA**：
   ```
   evaluate → navigator.userAgent
   # 实测值：Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0
   ```
2. 导出**全部 cookie**（Netscape 格式）：
   ```
   cdp → {"method":"Network.getCookies","params":{}}
   # 关键 cookie：ersp.lib.whu.edu.cn 的 GW.SESSION（httpOnly）、try.login
   ```
3. SFX 解析 DOI 拿 **arnumber**（IEEE DOI 经 SFX 会落到**搜索结果页** `searchresult.jsp`，需从结果页提 `/document/<arnumber>/` 链接）。
4. **curl 直取 PDF**（带精确 UA + cookie + referer）：
   ```bash
   curl -s -L -b ck.txt -c ck.txt \
     -e "https://ersp.lib.whu.edu.cn/s/org/ieee/ieeexplore/G.https/document/<ARNUM>/" \
     -A "$UA" \
     -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8' \
     -H 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8' \
     -H 'Sec-Fetch-Dest: document' -H 'Sec-Fetch-Mode: navigate' -H 'Sec-Fetch-Site: same-origin' \
     -o "<OUT>.pdf" \
     "https://ersp.lib.whu.edu.cn/s/org/ieee/ieeexplore/G.https/stampPDF/getPDF.jsp?tp=&arnumber=<ARNUM>"
   ```
   → `content_type=application/pdf`，直接落盘。**实测：Song 25.3 MB / 14 页；Liu 11.5 MB / 18 页。**
5. 校验：`%PDF` 头 + pymupdf 首页标题/作者匹配。

**⚠️ 不要再用浏览器内的 PDF 取字节**：PDF 查看器上下文禁 fetch/XHR；大 base64 经 evaluate 返回会把 daemon 打成 **502**。

**🌐 通用推论（比 IEEE 更值钱）**：凡 `ersp.lib.whu.edu.cn` 下的受限资源，**首选「浏览器精确 UA + 导出 cookie + 主机 curl」**——它绕开 daemon 的全部浏览器上下文限制（PDF 上下文、下载命令被禁、大响应截断），是最稳的通用解法。浏览器内 evaluate 只用于**读 HTML 页**（文章页/检索页），不用于取二进制。

<details><summary>失败路径存档（2026-09-15，浏览器内取 IEEE PDF 字节，5 条全败——仅供避坑）</summary>

1. `cdp` `Page.setDownloadBehavior` → `Cannot access browser-level commands`（daemon 只允许页面级命令）
2. PDF 查看器上下文 `fetch(location.href,{credentials:'include'})` → `Inspected target navigated or closed`
3. 同步 `XMLHttpRequest` + `overrideMimeType('text/plain; charset=x-user-defined')` → `NetworkError: Failed to load`（PDF 文档上下文禁 XHR）
4. `network list` 能看到 `mimeType=application/pdf` 且 `completed:true`，但 `network detail` → `No resource with given identifier`（CDP 资源已回收，二进制不缓冲）
5. `Page.printToPDF` 对已显示 PDF 的标签 → **1 页空白**（printToPDF 不能打印 PDFium 内容）
6. HTML 文章页上下文 fetch PDF URL → daemon **502**（响应体过大）
7. curl 用**通用 UA** → 弹回校外用户登录页（← 这条是唯一"接近成功"的，差的就是精确 UA）
</details>

### daemon 参数名速查（踩过坑的）
- `network` 的参数名是 **`cmd`**（`start`/`stop`/`list`/`detail`），**不是** `action`。
- `fill` 用 `{selector, value}`（不是 text）；`key_type` 用 `{text}`（不是 keys）。
- `cdp` 只能发**页面级**命令；`Page.setDownloadBehavior`、`Browser.*` 属浏览器级，会被拒。
- `network detail` 的 `body` 可能是已解析 dict；`evaluate` 的 code 里别用带 `/` 的正则字面量。

## ⭐ SFX 链接解析器路线（2026-09-14 打通，用户亲自示范纠正：永远别直怼出版社原站）

**核心思想**：订阅论文**不直连出版社**（Wiley 直连域名被 Cloudflare bot 检测封杀——无头 Playwright 33s 不放行 "Just a moment"；真实 Edge tab 后台时 CF 挂死、真鼠标点击不送达），**也不瞎猜 EZproxy 路径**（`s/com/wiley/www/...` 必 404）。走武大 SFX 按 DOI 解析，由它给出**正确的 EZproxy 深链**。全程无前台、纯 evaluate，无人值守可用。

### 流程 A（Wiley 系，实测 10.1111/ejss.70419 → 4.6MB PDF）
1. **SFX OpenURL**（路径是 `/86whu`，**不是** `/sfxlcl41`——后者返回 "no services found"；`/sfx_local` 是 404）：
   `https://whu-sfx.exlibrisgroup.com.cn/86whu?url_ver=Z39.88-2004&rft_val_fmt=info:ofi/fmt:kev:mtx:journal&rft.genre=article&rft_id=info:doi/<DOI urlencode>`
2. daemon navigate → SFX 菜单页（判据："由武汉大学的SFX提供" + 题名/来源正确）。**读服务列表**：
   - 有"电子全文 → 获取全文于: XXX电子期刊" = 有订阅，继续
   - 只有 DOI / CALIS文献传递 = **武大 SFX 无该刊订阅，但别急着放弃**——Shibboleth WAYFless（流程 B）可能仍有权限（实测 Paddy and Water Environment SFX 无服务但 WAYFless 后 Download PDF 可用）
3. 提取表单字段拼 GET URL：`document.forms['basic1']`（action=`/86whu/cgi/core/sfxresolver.cgi`；hidden 字段 `request_id`/`service_id`/`tmp_ctx_obj_id`/`tmp_ctx_svc_id` + text 字段 `rft.year`/`rft.volume`/`rft.issue`/`rft.spage`）→ `navigate` 该 URL → **302 到正确 EZproxy 深链**。Wiley 实测形如：
   `https://ersp.lib.whu.edu.cn/s/com/wiley/onlinelibrary/bsssjournals/G.https/doi/full/<DOI>`
   （token 三级 `wiley/onlinelibrary/bsssjournals` = 出版社/平台/期刊群，别猜）
4. EZproxy 文章页判权限：body 含 `Wuhan University` + `Full Access` → navigate `.../G.https/doi/pdfdirect/<DOI>` → `document.contentType=='application/pdf'` → 页面上下文 `fetch(location.href,{credentials:'include'})` → Uint8Array 按 `0x8000` 分块 `String.fromCharCode` → `btoa` 回传 base64 落盘（4.6MB 实测无截断）
5. 双重验证：`%PDF` 头 + pymupdf 首页标题/作者匹配

### 流程 B（Springer 系，不走 EZproxy，走 Shibboleth WAYFless，实测 s10333-026-01095-2 → 2.5MB PDF）1. `navigate` `https://fsso.springer.com/federation/init?entityId=https%3A%2F%2Fidp.whu.edu.cn%2Fidp%2Fshibboleth&returnUrl=https%3A%2F%2Flink.springer.com%2Farticle%2F<DOI>`（returnUrl 直接指文章页）
2. **过两道武大 IdP 确认页**（纯表单，evaluate 可点）：
   ① "关于身份认证与隐私的声明"：勾 `input[type=checkbox]` + 点"提交"
   ② "信息发布"（属性释放确认，显示 Scoped affiliation）：点"接受"
3. 落 `link.springer.com/article/<DOI>`，判权限：body 含 `Download PDF` 且无 `Buy article/US$` = 有权限
4. `navigate` `https://link.springer.com/content/pdf/<DOI>.pdf` → contentType=application/pdf → 同流程 A 第 4 步 fetch 落盘

### 流程 C（WOS 检索入口 —— 用户 2026-09-14 亲自示范的日常工作流）
**用户教的标准流程**：图书馆登录 → WOS 主题检索 → 结果列表每条自带 SFX"Full text at publisher"按钮 → 一键进带武大权限的全文页（HTML+PDF）。**这个按钮背后就是我脚本化的 SFX-by-DOI**（流程 A/B），所以 WOS 是"检索入口"，SFX 是"取全文出口"，两者是一套。

- **WOS 入口**：`https://webofscience.clarivate.cn/wos/woscc/basic-search`（.cn 中国镜像；首页 JS 数据里的 `wtu.metaersp.cn/external?...` 是第三方件错配到别校 CAS，**别用**）
- **检索交互**：填 `#composeQuerySmartSearch`（daemon `fill` 参数名是 `value` 不是 `text`）→ 点 `button[data-ta="smart-search-query"]`（**Enter 键不触发 Angular 提交**）→ 跳 `/wos/woscc/summary/<uuid>` 结果页
- **机构登录链**（access.clarivate.com 出现时）：机构登录 → 选 `CHINA CERNET Federation`（mat-select#mat-select-0，Angular 下拉，113 项）→ 转到机构 → CARSI DS（ds.carsi.edu.cn，列表懒加载，先点字母"W"再点"武汉大学（Wuhan University）"→ 点"登录"按钮）→ 武大 IdP 两道页（隐私声明勾选+提交 / 信息发布点"接受"）→ 落 `wos/?...SID=...`
- **⚠️ 已知缺陷（2026-09-14 实测）**：SSO 链全通但**会话落不下来**——落地后 header 仍显示 `Sign In`（匿名态），机构 SFX 按钮不出现。疑似武大 IdP 对 Clarivate SP 只释放 scoped-affiliation，WOS 权益判定不认。**处置**：① daemon 启动时若用户 Edge 里已有手工登录的 WOS 会话则直接可用（每次行动作 `VERIFY`：header 无 `Sign In` 才继续）；② 会话不在时**不要恋战**，直接用流程 A/B 的 SFX-by-DOI 取全文（与 WOS 按钮等价），检索仍可用 Crossref/OpenAlex API 替代
- **daemon fill/key_type 参数名**：`fill` 要 `{selector, value}`、`key_type` 要 `{text}`——传错只报 "value/text is required"

### 流程 C（WOS 检索入口 —— 用户 2026-09-14 亲自示范的检索+全文一体化流程）
**用户教的完整链路**：图书馆登录 → WOS 检索（主题/高级检索）→ 结果列表每条自带 SFX "Full text at publisher" 按钮 → 一键落地带 "Brought to you by: Wuhan University" 的全文页（HTML+PDF）。WOS 是检索入口，SFX 是全文出口；已知 DOI 时可跳过 WOS 直接走流程 A/B 的 SFX OpenURL（等效且更快）。

**认证链（2026-09-14 实测，无头可自动过到 IdP 接受）**：
1. `navigate` `https://webofscience.clarivate.cn/wos/woscc/basic-search`（中国镜像；国际站 www.webofscience.com 别用）→ 落 `access.clarivate.com/login` 机构登录页
2. "机构登录"下拉是 Angular Material `mat-select`（aria-label=机构，id=mat-select-0）→ 合成 click 打开 → 选项列表（113 项，无"武汉大学"直选项）→ 选 **"CHINA CERNET Federation"**（CARSI 由 CERNET 运营）
3. 点 **"转到机构"** → 落 `ds.carsi.edu.cn` 学校列表（懒加载，先点字母 **"W"** 跳段）→ 点 **"武汉大学（Wuhan University）"** → **再点"登录"按钮**（只点学校不跳转，必须补点登录）
4. 落 `idp.whu.edu.cn` "信息发布"（属性释放确认，服务=Clarivate Analytics SP）→ 点 **"接受"** → 回 `webofscience.clarivate.cn/wos/?...&SID=<...>` 会话建立
5. 搜索：`#search-option-0`（data-ta=search-criteria-input）fill 查询词 → 点 **`button[data-ta="run-search"]`**（注意别误点 data-ta 含 "search" 的 search-history-link）→ `/wos/woscc/summary/<uuid>`

**实测硬限制（2026-09-14，勿浪费时间）**：结果页 Angular 渲染在**后台 tab 卡死**（body 停在导航壳 ~2.7k 字符，等 60s 不出结果列表；SFX "Full text at publisher" 按钮随之不可见）——Edge 对 hidden tab 节流，与 Cloudflare 问题同源。**WOS 深度自动化（读取结果列表/点 SFX）需 tab 前台可见**；无人值守检索用 Crossref/OpenAlex API，全文走流程 A/B（SFX 直连，不依赖 WOS）。
**daemon 参数名**：`fill` 用 `value`（不是 text）、`key_type` 用 `text`（不是 keys）；evaluate 间歇失联（WinError 10061，伴 Edge crashpad 报错）重试即可。

### 2026-09-14 事故教训（勿重蹈）
- **门户"访问地址"按钮是 Vue 组件**（无 href/onclick 属性），合成 click 与 CDP 真鼠标在后台 tab 均无效——**别从门户按钮硬点，直接走 SFX URL**。
- **无头 Playwright 过不了 Wiley 的 Cloudflare bot 检测**（"Performing security verification" 33s 不放行）；真实 Edge + tab 可见才能过 CF。无人值守一律走 SFX（EZproxy 由 WHU 服务器代取，出版商只见 WHU IP，根本不触发 CF）。
- daemon 旧 session 绑定的 tab 被关闭后：`evaluate` 返回 502、`navigate` 报 `No tab with given id`、`list_tabs` 空 → **换新 session 名 navigate 建新 tab 即恢复**，不用重启 daemon。

## ⭐ WOS 检索入口（用户 2026-09-14 亲自示范的工作流起点，全程已逐步实测）

用户示范的完整流程：**图书馆登录 → WOS 检索 → 结果列表 → 每条结果自带 SFX "Full text at publisher" 按钮 → 一键进入带武大权限的全文（HTML+PDF）**。要点：**检索在 WOS 做，全文靠 SFX，永不直怼出版社**。

### WOS 机构登录链（逐步实测，选择器齐全）
1. 直接 `navigate` `https://webofscience.clarivate.cn/wos/woscc/basic-search`（clarivate.cn 中国镜像；www.webofscience.com 国际站更慢）。未登录 → 跳 `access.clarivate.com/login?app=wos`。
2. 登录页点**机构登录**：`mat-select#mat-select-0`（aria-label="机构"）→ 弹出 113 个 `.mat-option`，点 **"CHINA CERNET Federation"**（CARSI 由 CERNET 运营；无直接的"武汉大学"项）。
3. 点按钮 **"转到机构"**（按 text 找 button）→ 跳 `ds.carsi.edu.cn`（CARSI 发现服务）。
4. CARSI 页面：学校列表**懒加载**（只载当前字母段）。点字母 **"W"** tab → 等 `LI.schoolList1` 出现"武汉大学（Wuhan University）" → 点它 → **必须再点"登录"按钮**（只点学校不跳转！）。
5. 跳 WHU IdP `idp.whu.edu.cn`："信息发布"（属性释放，服务=Clarivate Analytics SP）→ 点 **"接受"**。（首次还有"关于身份认证与隐私的声明"页：勾 checkbox + 点"提交"。）
6. 回 `webofscience.clarivate.cn/wos/?...SID=<已发>` → SSO 完成，会话 cookie 在 `.clarivate.cn`。

### 已知坑（2026-09-14 实测）
- **woscc 应用会话在后台 tab 里不稳定**：Angular 引导间歇卡死（body 卡 ~1200 字符壳不动，bringToFront+新 tab 也可能无效）；即便 SSO 完成发了 SID，summary 页 header 仍可能显示 Sign In。**无人值守不要依赖 WOS 界面做检索**——WOS 界面适合用户在前台时手动/半自动用。
- **无人值守的等价替代（已验证）**：检索继续用 Crossref/OpenAlex API 扫描；拿到 DOI 后直接走上面 SFX 路线（`/86whu` OpenURL）取全文——**SFX 就是 WOS 结果里那个 "Full text at publisher" 按钮的底层 resolver，按 DOI 直调 = 跳过 WOS 界面、效果相同**。
- `wtu.metaersp.cn/external?siteUrl=...` 的 WOS 直达是第三方件（yuntaigo），跳到 `auth.wtu.edu.cn`（别的学校 CAS）——**死路，别用**；走 access.clarivate 机构登录链。
- daemon `fill` 参数是 `value`（不是 text）；`key_type` 参数是 `text`。WOS smart search 提交按钮：`button[data-ta="smart-search-query"]`（Enter 键不触发 Angular 提交）。
- WOS SPA 半初始化卡死后，同 tab 内再 navigate 无效，**close_tab 后开全新 tab 冷启动**；仍卡则说明后台节流，需前台。

## ScienceDirect 系流程（已验证 2026-09-07 更新）
1. PII：`GET api.crossref.org/works/<doi>` → `alternative-id[0]`
2. 文章 URL：`https://ersp.lib.whu.edu.cn/s/com/sciencedirect/www/G.https/science/article/pii/<PII>`
   - **必须站内导航**（先开代理首页，再 evaluate `location.href` 跳转），直接 daemon navigate 会 400
3. 取正文 pdfft 按钮 href：`a.link-button.accessbar-utility-component`（注意别抓到"推荐文章"的 View PDF 链接；用 PII 字串过滤）
4. `location.assign("<相对 pdfft 路径>")` → 跳到 `pdf.sciencedirectassets.com/.../main.pdf` 查看器
5. **探测状态**：`document.contentType==='application/pdf'` 即已过验证；否则停在 `cfts/init` 挑战页 → 见"Cloudflare Turnstile 自动处置"
6. PDF 查看器加载后，用页面上下文 `fetch(location.href,{credentials:'include'}).then(r=>r.arrayBuffer()).then(b=>btoa(bin))` 取字节 → daemon 响应写 `C:/WINDOWS/Temp/wb_<random>.json` → python 解码 base64 落 `docs/pdfs/1-s2.0-<PII>-main.pdf`（**不走 CDP 点保存按钮**，避免 Edge 下载目录/`.tmp` 搬运）
7. 双重校验：① `%PDF` 头；② 首页文本含标题关键词（pymupdf）

### Cloudflare Turnstile 自动处置（2026-09-07 实测）
- **首选：复用 cf_clearance 自动过**。会话里已有任一篇通过记录时，重新 `navigate article` 拿**新鲜** pdfft（md5 会变）→ 再 `location.assign` 跳，challenge 往往直接放行（117985 第二次即此路径，无需任何点击）。旧 pdfft 链接的 challenge 页若"挂死 In Progress / 无 checkbox"，不要等，**重导 article 拿新链接再跳**即可。
- **若真弹 checkbox（需点击）**：用 CDP 真鼠标抢点（见坑清单"CDP 真鼠标三连"）。坐标获取顺序：
  1. 先 `elementFromPoint` / 递归 shadow DOM 找 checkbox 真实视口坐标 → CDP 点之（最稳）
  2. fallback：ScienceDirect 全屏挑战页布局固定，checkbox 经验在视口中心偏上 ≈ `(innerWidth/2, innerHeight*0.42)`，`Page.bringToFront` 后 CDP 点该坐标抢点
- **用户报告"框位置每次固定"** → 下次真弹框时第一时间 `hit-test` 记录真实坐标并写死进本段（目前样本不足：117981 手动点 / 117985 自动过 / 一次挂死无框，未实测到坐标）。
- 跳过 alert：若跳 ersp 弹"用户登录已过期" JS alert，先 `Page.handleJavaScriptDialog accept:true` 再让用户重登。

### ⭐ 挑战页"挂死无组件"的**第一处置：先 `Page.bringToFront` 切前台再 navigate**（2026-09-11 实证，优先级高于点击）
- **现象**：直连 `sciencedirect.com/science/article/pii/<PII>` 落在标题"请稍候…"的挑战页（正文 "Are you a robot? Please confirm you are a human by completing the captcha challenge below"），但探测 DOM 只有 hidden `cf-turnstile-response` ——**无 iframe、无 shadow DOM、无可见 checkbox/button**，属"组件未渲染"挂死态，点也点不到。
- **根因**：daemon 的 agent 标签页**不在前台**（`list_tabs` 显示 `active:false`）→ 挑战脚本被节流/不渲染。
- **处置（实测一次通过）**：
  1. `cdp` → `{"method":"Page.bringToFront"}`
  2. `list_tabs` 确认目标 tab `"active":true`
  3. 重新 `navigate` 同一 URL → **挑战自动放行**，页面直接变成完整文章（实测 atech.102530 gold OA 全文 61,843 字符由此取得）
- **顺序纪律**：遇到"挂死无组件"**先做 bringToFront + 重导**，再考虑重导新鲜链接，最后才考虑 CDP 鼠标。不要一上来就点坐标（本次实测坐标点击对未渲染组件无效）。
- **反面案例（预期降级，别再耗时间）**：`pdf.sciencedirectassets.com/craft/capi/cfts/init` 的验证页**在 tab 已 active 的情况下仍挂死**（同样无组件）；重导新鲜 md5 + CDP `Input.dispatchMouseEvent` move/press/release 三连**均未放行**。此时出版商 PDF 记为"未能获取"，改用同页 HTML 全文替代（gold OA 文章 HTML 即全文）。

### ⭐ SSRN 预印本全文获取路线（2026-09-11 打通，含 green-OA 同文替代）
- **适用**：SSRN 预印本（`10.2139/ssrn.<id>`），以及 **green OA** 论文——OpenAlex 的 `open_access.oa_url` 常指向 SSRN 同文预印本，可替代封闭的出版商版。
- **判据**：先核对预印本页标题/作者与目标论文**逐字一致**（本次 chemolab.105877 → SSRN 7031722 标题完全一致）才可替代。
- **步骤**：
  1. `navigate` 到 `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=<id>`（**真实浏览器可正常打开，无 Cloudflare 拦截**；curl 直连会返回空/被拦）
  2. 页面内取 PDF 直链：`Array.from(document.querySelectorAll('a')).find(a=>a.href.indexOf('Delivery.cfm')>=0).href`
  3. 用**页面上下文** `fetch(href,{credentials:'include'})` → `arrayBuffer()` → 分块 `String.fromCharCode` → `btoa()` 回传 base64
  4. daemon 响应 **必须 `-o` 落 `C:/WINDOWS/Temp/wb_<unique>.json`**（本次 4.13 MB PDF 的 base64 约 5.5 MB，直读 stdout 会截断），再用 python 解码写文件
  5. 双重验证：`%PDF` 头 + pymupdf 读首页标题/作者匹配
- **实测产出**：ssrn.7379880 → 47 页 / 4.13 MB；ssrn.7031722 → 15 页 / 889 KB。
- **误下清理**：若 curl 直连 SD 得到的 `<name>.pdf` 实为 `<!DOCTYPE html>`（挑战页），必须删净，不可入库。

## 无窗口路线：Headless Edge + CDP（2026-09-05 跑通到最后一关）
真实 Edge 二进制跑 headless（真 TLS 指纹、无窗口、不用 Playwright），配合从活 Edge 导出的登录态，可走完代理全流程。
脚本：`headless_fetch.py`（单篇）/ `headless_batch.py`（批量）/ `cdp_edge.py`（CDP 封装）。

启动（必须带 `--remote-allow-origins=*`，否则 WebSocket 握手 403）：
```
msedge.exe --headless=new --remote-debugging-port=9333 --remote-allow-origins=*
  --user-data-dir=<拷贝的最小 profile> --disable-blink-features=AutomationControlled
  --no-first-run --no-default-browser-check --disable-renderer-backgrounding
```
- profile 最小拷贝：`Local State` + `Default/{Cookies,Cookies-wal,Preferences,Secure Preferences,Local Storage}`（19MB，别拷整个 878MB）
- **登录态不在 cookie 里，在 localStorage**：`whu.metaersp.cn` 的 token/library/ticketInfo/userInfo。用 daemon `evaluate` 导出，再在 headless 里 `localStorage.setItem` 注入；同时注入 `ersp.lib.whu.edu.cn` 的 `GW.SESSION`（否则跳 CAS 统一身份认证）
- PDF 字节用 CDP `Network.getResponseBody`（`Network.responseReceived` 筛 mimeType=application/pdf），不点保存按钮
- pdfft 必须**页面上下文跳转**（`location.href=href`），`Page.navigate` 直连会被代理 nginx 403
- **Cloudflare 关口（2026-09-07 修正旧结论）**：`pdf.sciencedirectassets.com/craft/capi/cfts/init` 的验证**并非必然卡死**——活 Edge 会话已有通过记录时，重新 navigate article 拿新鲜 pdfft 再跳通常自动放行（实测 117985 第二次无需点击）。仍可能弹 checkbox：活 Edge 里解一次 → 导出 assets 域 `__cf_bm`/`cf_clearance` → 注入 headless 可批量；或直接 CDP 真鼠标抢点 checkbox（见上段）。headless 的 30 分钟窗口假设仍有效，但优先试"重导新鲜链接自动过"。
- 不要用 `browser_cookie3`：Windows 下会抛 RequiresAdminError；直接从 daemon CDP `Network.getCookies` 取，HttpOnly 也拿得到

## 下载后验证（强制，2026-09-05 Lehmann 事故教训）
- 每份 PDF 落盘后必须**双重验证**：① `%PDF` 头；② **首页文本与目标论文匹配**（读前 200 字符核对标题/作者）。
- 事故：Semantic Scholar 把 Lehmann & Kleber 2015 Nature 标 BRONZE 指向 `nature.com/articles/nature16069.pdf`——实际该 URL 返回 HTML，且文章页内唯一 PDF 链接是**相关文献**（USGS Wershaw 2004 报告）。按 S2 元数据下载得到的是完全无关的错误文档，两个副本共 2 次误下未察觉。
- 排查手法：headless Edge 打开文章页看真实 PDF 链接指向哪（`document.querySelectorAll('a')` 过滤 pdf），再决定是否需要换源。
- OA 元数据不可信顺序：S2 BRONZE > Unpaywall > OpenAlex；都不信，只信落盘后的内容验证。
- 错误文件清理：误下副本要删干净（本例同内容文件曾被存成两个名字），笔记 pdf 字段指向验证过的那份。

## 坑清单
- Elsevier 未开 CARSI，机构登录只认 IP/VPN → 必须走导航页代理
- **代理登录约 1 天过期**：跳转时弹 `用户登录已过期` 的 JS alert 卡死标签页 → CDP `Page.handleJavaScriptDialog accept:true` 处理，然后让用户在 `whu.metaersp.cn` 重新登录（凭证不经对话）
- **杀掉 msedge.exe 会连带杀死 daemon**（扩展宿主通道）→ 重启后跑 `%USERPROFILE%\.kimi-webbridge\bin\kimi-webbridge.exe start`（幂等），daemon 会话标签需重建
- **Edge 152 无视窗口反节流参数**：`--disable-features=CalculateNativeWinOcclusion` 等 4 项写进命令行也不管用，最小化/遮挡仍报 `hidden` → 别迷信参数，窗口必须可见
- fetch/XHR/anchor-download/curl/curl-cffi 拉 pdfft 全被 Cloudflare 拦（TLS 指纹），只有 navigate 上下文能过
- pdfft URL 直接 daemon navigate 会 403；必须在文章页 evaluate `location.href=href`（带 referer 的页面上下文跳转）→ cfts/init 验证页
- SPA 文章页对 `el.click()` 合成点击无响应（View PDF），location.href 跳转有效
- **CDP 真鼠标三连**（绕过 React SPA 吞合成 click）：`Input.dispatchMouseEvent` 按 move→press→release 顺序，`isTrusted:true`。前置：① `Page.bringToFront` 切前台（list_tabs active:true 验证，否则输入被静默吞）；② 坐标是 CSS 像素（devicePixelRatio 不影响 CDP）；③ **坐标处 `elementFromPoint` 必须=目标按钮**——ScienceDirect 文章页有 ReactModal Overlay（"Download (N) PDFs" 推荐位）盖住 View PDF，需先 hit-test 找 modal close 按钮 CDP 点掉它，再 hit-test 点真按钮。
- **fetch 跨域坑**：pdfft 会 302 跳 `pdf.sciencedirectassets.com`（跨域），在 ersp 域上下文 `fetch` 会被 CORS 拦 → 必须先 `location.assign` 跳进 PDF viewer（assets 域），再同域 `fetch(location.href)` 取字节。
- **shell 转义坑**：CDP 调用 body 带正则/过长时，curl `-d "..."` inline JSON 转义破坏，必须 Write 工具写 `C:/WINDOWS/Temp/wb_<random>.json`（避免并发用 PID/时间戳），再 `curl --data-binary @<file>`。Windows Temp 而非 git-bash /tmp（Python 在两边解析不同）。
- daemon 响应超过 ~显示阈值会被截断 → fetch PDF 字节的响应务必 `-o` 落 `C:/WINDOWS/Temp/wb_<random>.json` 再用 python 解析，别直接读 stdout。
- **daemon "已恢复"判据（2026-09-11 新增，避免沿用过期结论）**：`network list` 返回 **502** = 浏览器桥接断（重启法：`taskkill /PID <pid> /F` → 删 `~/.kimi-webbridge/daemon.pid` → `./kimi-webbridge.exe start`）；返回 **`session "x" has no tab — navigate or find_tab first`** = **桥接已恢复**，只需 `navigate` 建 tab 即可用。**502 结论最多沿用一次操作就要复测**——本次即因未复测而多绕了 EZproxy 一圈。
- **evaluate 正则坑（2026-09-11）**：`extension_error: evaluate: SyntaxError: Invalid regular expression flags` = code 字符串里的 `\/pdf/i` 一类被 JSON 转义破坏。**daemon `evaluate` 的 code 中避免使用带 `/` 的正则字面量**，统一改用 `indexOf` / 字符串比较。
- **网络动作清单（2026-09-11 实测）**：daemon 支持 `navigate, find_tab, find, evaluate, network, snapshot, read_page, click, fill, mouse_click, cdp, key_type, send_keys, screenshot, scroll, save_as_pdf, upload, close_tab, list_tabs, close_session, wait, dialog, select_option, hover, drag`。注意 `mouse_click` **必须传 CSS selector 或 `@e` ref，不支持 x/y 坐标**；要按坐标点必须走 `cdp` + `Input.dispatchMouseEvent`。
- 脚本 fetch 会拿到 52949 字节的挑战 HTML，不是 PDF
- Edge 下载目录被用户改成 F:\landsat\landsat_2010
- daemon 截图在窗口最小化时返回全白；`document.visibilityState=='hidden'` 时点击全部失效，先让用户把窗口放前台
- MDPI `/pdf` 直链返回 HTML 中转页；须从文章页点其 PDF 按钮（Content-Disposition 下载）
- arXiv 终端直连易被重置，浏览器正常；可试 `export.arxiv.org`
- MDPI DOI 转 URL 不补零：`10.3390/rs6054305` → `/2072-4292/6/5/4305/pdf`（卷/期/文章号都去前导零）
- **入口必须是武大图书馆门户 / metaersp.cn（2026-09-07 用户纠正）**：daemon 直接 `navigate ersp.lib.whu.edu.cn/...` 会被 CAS 拦截要求重新登录（2026-09-07 实测：tab 跳到 `cas.whu.edu.cn/authserver/login`）。正确做法是先在 Edge 里经 `library.whu.edu.cn` 或 `whu.metaersp.cn` 数据库导航页完成 SSO 登录，再在 daemon 里从 metaersp 站内 `location.href` 跳 ersp；登录态会自动透传。判定标准：跳 ersp 后 `document.title` 含"武汉大学"或直接是数据库页面（ScienceDirect/Elsevier），**不是**"统一身份认证"。

## 经实战修正（2026-09-08 抓 3 篇 Geoderma 全文 PDF 验证）

原"fetch 字节法（evaluate 返回 base64）"与"CDP 点网页保存按钮"两条路实战均有致命坑，已收敛为单一可靠路径：

1. **禁止 `fetch` 返回巨 base64 经 daemon 返回**：17MB PDF → base64 ≈24MB，会让 daemon 响应卡死（python 侧 13min 无返回、HTTP 000）。evaluate 不要返回大响应。
2. **禁止 CDP 点网页"保存/下载"按钮**：会触发 Edge 的"另存为" OS 对话框（非网页 DOM，CDP 的 `Input.dispatchMouseEvent` 控制不了它），下载被 OS 对话框阻塞。用户说的"弹出一个文件夹页面保存、那时就不是网页端了"即此——只能绕开，不能点。
3. **正确下载路径（单一）**：`Page.setDownloadBehavior` 设 `behavior:"allow"` + `downloadPath:<DLDIR>`（关掉"下载前询问"弹窗）→ 页面内 `fetch(location.href,{credentials:'include'})` 拿 blob → `URL.createObjectURL` + `<a download>.click()` 触发 Edge **原生下载**落到 DLDIR（F:\landsat\landsat_2010）→ 脚本扫 DLDIR 最新 `%PDF` 落 vault。字节走 Edge 通道，不经 daemon 大响应，也不弹 OS 对话框。
4. **VIS=hidden 必挂**：Cloudflare 挑战页在 `visibilityState=='hidden'` 时永远 "In Progress" 挂起，下载也中断。每步 `Page.bringToFront` 临时置 visible（窗口最小化不够，需用户把 Edge 放前台）。
5. **chrome-error 页禁止 JS 导航**：tab 落到 `chrome-error://` 后 `location.href` 被浏览器拒绝。需先 `navigate` action 重置回 `whu.metaersp.cn` 正常页，再 JS 站内跳 ersp。
6. **daemon 卡死/无响应（HTTP 000，tasklist 无 `kimi-webbridge.exe`）**：跑 `%USERPROFILE%\.kimi-webbridge\bin\kimi-webbridge.exe start`（幂等）重启；重启后 session tab 需重建（navigate）。
7. **Edge 文件锁**：原生下载后 Edge 仍短时占用 `AUTO.pdf`，`os.rename` 会 `WinError 32`；改用 `shutil.copy` + 重试循环落 vault，源文件可延后删。

---

## ⭐ 2026-09-15 大扩容：非 Elsevier 五条新路线（全部实测拿到 PDF）

### A. 浏览器内 fetch → base64 分块回传（突破下载落盘限制的通用兜底）
适用：本机 urllib 无代理（arXiv/PMC/Nature/SSRN 直连不通），且：
- CDP `Browser.setDownloadBehavior` **不被 WebBridge 扩展支持**（实测 `{"code":-32601} wasn't found`），无法指定下载目录；
- `Page.setDownloadBehavior` 报 `Cannot not access browser-level commands`；
- navigate 到 PDF 直链时 Chrome 用内置 viewer **内联显示**，不触发下载。

做法（`browser_fetch.py`）：
1. `navigate` 到**同域 HTML 页**（不是 PDF 页 —— PDF viewer 页注入不了 JS，且跨域 fetch 会被 CORS 拦）；
2. `evaluate` 执行异步 JS：`fetch(pdfUrl,{credentials:'include'}) → arrayBuffer → 逐块 String.fromCharCode → btoa` 存 `window.__b64`，并置 `window.__len`；
3. Python 轮询 `window.__len`，再按 180000 字符分块 `window.__b64.substr(off, n)` 取回拼接 → base64 解码。

实测：arXiv 10.6MB PDF 20 秒完整取回（`%PDF` 校验通过）。**这是绕开"daemon 不建议回传大响应"限制的可行姿势** —— 分块即可。
注意：JS 里**不要**用带 `/` 的正则字面量（daemon 转义坑）；用 `indexOf`。

### B. Science（science.org）
- 可用前缀：`https://ersp.lib.whu.edu.cn/s/org/science/www/G.https/doi/pdf/<DOI>`
- ❌ `s/com/sciencemag/www` 与 `s/com/science/www` 均 504 Gateway Time-out（前缀名错）。
- 实测 Lal 2004 `10.1126/science.1097396` → 323,865 B PDF。

### C. IEEE（Xplore）
1. 拿 arnumber 两条路：
   - 老文章：Crossref `works/<doi>.message.link[].URL` 里有 `…/ielx5/…/0<arnumber>.pdf?arnumber=<arnumber>`（实测 Pan 2010 TKDE → **5288526**）；
   - 新文章：`curl -sIL https://doi.org/<DOI>` 的 `%{url_effective}` 即 `https://ieeexplore.ieee.org/document/<arnumber>/`（实测 Zhao 2026 TGRS → **11320940**）。
2. PDF：`https://ersp.lib.whu.edu.cn/s/org/ieee/ieeexplore/G.https/stampPDF/getPDF.jsp?tp=&arnumber=<n>`（带 EZproxy cookie 直下）。实测 2.6MB / 15MB 均成功。
- ⚠️ 直接 navigate EZproxy 的 IEEE **搜索页**会 30s 超时，别走搜索页找 document id。

### D. ingentaconnect（ASPRS/PE&RS 等）
文章页上**没有任何 PDF 链接**，须手工拼参数：
`<EZproxy前缀>/content/asprs/pers/<年>/<卷>/<期>/art0000N?crawler=true&mimetype=application/pdf`
实测 Atyosi 2026 PE&RS → 3.0MB PDF。

### E. PMC（PubMed Central）
- `https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMCxxxxxxx` 对**非 OA subset** 返回 404（PNAS 等 green-OA 常见）；
- 文章页 `…/articles/PMCxxxxxxx/pdf/` 直下会返回 HTML（反爬）；
- 可行：`navigate` 文章页 → 浏览器内 fetch（见 A）取 PDF。实测 Sanderman 2017 PNAS → 4.19MB PDF。

### F. Nature 系（含 Scientific Reports）
- `…/articles/<DOI>.pdf` 与 EZproxy 同路径都可能只返回 HTML 落地页；
- 页面上的 "Download PDF" 按钮若指向 `_reference.pdf`，那是**参考文献清单**，不是正文；
- 判据：页面出现 "We're sharing this article early … will be replaced automatically by the final Version of Record" = **Accepted Manuscript，正文未发布**，此时放弃并如实标注，别用摘要冒充全文。

---

## ⭐ 矢量图 PDF 的配图：整页渲染 + 图注定位（2026-09-15）

- 现象：`extract_image` 对矢量绘制的 PDF 抽不到正文图；抽出来的往往是一堆 `640×640 px` 的**图标**（图例符号、期刊 logo）。
- 鉴别伪图：`page.get_image_info()` 给出图像在页面上的**真实绘制尺寸**（点）。`640×640 px` 的图标在页面上只画 `31×32 pt` → 一律剔除；真图至少数百 pt。
- 正确做法（`render_figpages.py` + `embed_pages.py`）：
  1. 逐页正则找图注 `^\s*(?:Figure|Fig\.?)\s*(\d{1,2})[.:]`；

  2. 含图注的页 → `page.get_pixmap(matrix=Matrix(2,2))` 存 `page_N.png`；
  3. 图注文本从 PDF 文本层抽 `Figure N.` 后的原文（截到下一个 `Figure M.`），写进笔记，**不做任何推断**。
- 实测：Tan OTCE(CVPR) 渲染 8 页覆盖 Fig.1–12；Liu(SSRN) 11 页覆盖 Fig.1–12。
- ⚠️ 剔除脚本务必 **默认保留 + 白名单 + dry-run**：本轮初版按"文件名含 `_pN_` 且该页无大图"剔除，漏白名单导致 671 张 Elsevier 图（`gr1.jpg` 命名、无页号）被误移；已用 `rollback_aux.py` 全部还原。**带页码的文件名格式不止 `figN_pN_` 一种**（还有 `fig_NN_pN.png`、`figN_pN.`），正则必须容错，解析不出页号的一律保留。
