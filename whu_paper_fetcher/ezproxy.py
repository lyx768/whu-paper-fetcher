"""出版社无关通用 EZproxy 全文路由（2026-09-17 突破并固化）。

适用：Wiley / Springer / T&F 等**无 ScienceDirect PII** 的出版商。
SD（Elsevier）走 pure_fetch 的 ARP 接口；其余走本模块。

路线（与 pure_fetch 同源，复用其 curl_cffi 指纹会话）：
  1) playwright CAS 登录已在 autologin 完成
  2) metaersp middle?url=doi.org/<DOI> 建 EZproxy 会话 cookie（SSO）
  3) 导出 cookie -> curl_cffi(impersonate="chrome") 抓文章页 + 抽 PDF
  4) 深链构造：出版社原文 URL 翻成
       https://host/path -> https://ersp.lib.whu.edu.cn/s/com/<sld>/<sub>/G.https<path>
     （WHU EZproxy 的 G.https 前缀：把 https:// 换成 G.https，并在前面加 s/com/<sld>/<sub>/）

与 SD 路线区别：通用路线直接抓出版社文章页 HTML（SD 走 ARP JSON 纯文本接口）。
Wiley 的 PDF 走 token 化重定向（非直链），故 PDF 尽力而为；文章页全文即满足"全文级"铁律。
"""
import os
import re
import time

from curl_cffi import requests as cr
from .pure_fetch import curl_session_from

MIDDLE = "https://whu.metaersp.cn/middle?url=https://doi.org/{doi}"
EZPROXY_BASE = "https://ersp.lib.whu.edu.cn/s/com"

_EDGE_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0")

_HEAD_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+\n|\n[ \t]+|\n{2,}")


def _ezproxy_deeplink(article_url):
    """出版社原文 URL -> WHU EZproxy 深链。无法解析返回 None。"""
    m = re.match(r"https?://([^/]+)(/.*)?$", article_url)
    if not m:
        return None
    host, path = m.group(1), (m.group(2) or "/")
    parts = host.split(".")
    if len(parts) >= 3:
        sld, sub = parts[-2], parts[-3]
    elif len(parts) == 2:
        sld, sub = parts[0], ""
    else:
        return None
    if sub:
        return f"{EZPROXY_BASE}/{sld}/{sub}/G.https{path}"
    return f"{EZPROXY_BASE}/{sld}/G.https{path}"


def _resolve_publisher_url(s, doi):
    """用 curl_cffi 跟 doi.org 303（不跟随），拿出版商文章页原文 URL。失败返回 None。"""
    try:
        r = s.get(f"https://doi.org/{doi}", allow_redirects=False, timeout=30,
                  headers={"User-Agent": _EDGE_UA})
        loc = r.headers.get("Location", "")
        if loc and loc.startswith("http"):
            return loc
    except Exception:
        pass
    return None


def _html_to_text(html):
    txt = _HEAD_RE.sub("\n", html)
    txt = _WS_RE.sub("\n", txt)
    return txt.strip()


def _get(s, url, timeout=90):
    try:
        r = s.get(url, allow_redirects=True, timeout=timeout, headers={"User-Agent": _EDGE_UA})
        return r, None
    except Exception as e:
        return None, str(e)[:80]


def _try_save_pdf(s, url, out_path):
    """若 url 返回 %PDF 则落盘返回路径，否则返回 None。"""
    r, err = _get(s, url)
    if err or not r:
        return None
    if r.content[:4] == b"%PDF":
        with open(out_path, "wb") as f:
            f.write(r.content)
        return out_path
    return None


def fetch_generic(backend, doi, config, out_dir, tag=None, display_name=""):
    """通用 EZproxy 取全文。返回 (paths|None, err|None)。"""
    tag = tag or re.sub(r"[^A-Za-z0-9._-]", "_", doi)
    os.makedirs(out_dir, exist_ok=True)

    # 1) SSO：metaersp middle 建 EZproxy 会话 cookie
    landing = None
    try:
        backend.open(MIDDLE.format(doi=doi))
        for _ in range(12):
            time.sleep(2)
            try:
                u = backend.eval_js("(()=>location.href)()")
            except Exception:
                u = None
            if u and "ersp.lib.whu.edu.cn" in u:
                landing = u
                break
            if u and str(u).startswith("chrome-error"):
                # 出版商 Cloudflare 拦 headless 导航；但 ersp cookie 已在重定向链中落下，
                # 下面用 curl_cffi 直取深链即可（无需再走浏览器）
                break
    except Exception as e:
        return None, "SSO_NAV_FAILED:%s" % str(e)[:120]

    s = curl_session_from(backend)
    if not list(s.cookies.jar):
        return None, "NO_COOKIES_EXPORTED"

    # 2) 解析文章页 EZproxy 深链
    if landing and "ersp.lib.whu.edu.cn" in landing:
        article_ez = landing
    else:
        pub = _resolve_publisher_url(s, doi)
        article_ez = _ezproxy_deeplink(pub) if pub else None
    if not article_ez:
        return None, "NO_ARTICLE_DEEPLINK"

    # 3) 抓文章页
    article_path = os.path.join(out_dir, "%s_article.html" % tag)
    r, err = _get(s, article_ez)
    if err:
        return None, "ARTICLE_FAILED:%s" % err
    if r.status_code != 200 or len(r.text) < 500:
        return None, "ARTICLE_EMPTY(status=%s len=%d url=%s)" % (
            r.status_code, len(r.text), r.url[:100])
    with open(article_path, "w", encoding="utf-8") as f:
        f.write(r.text)

    paths = {"html": article_path}

    # 4) 抽全文文本
    txt = _html_to_text(r.text)
    if txt:
        tp = os.path.join(out_dir, "%s_fulltext.txt" % tag)
        with open(tp, "w", encoding="utf-8") as f:
            f.write(txt)
        paths["fulltext_txt"] = tp

    # 5) 抽 PDF（尽力而为；Wiley 等 token 化重定向可能只返回 HTML）
    pdf_path = os.path.join(out_dir, "%s.pdf" % tag)
    candidates = list(re.findall(r'href=["\']([^"\']+)["\']', r.text))
    if pub:
        base = re.sub(r"/abstract$|/full$|/pdf$", "", pub)
        dl = _ezproxy_deeplink(base + "/pdf")
        if dl:
            candidates.append(dl)
    seen = set()
    for c in candidates:
        if c in seen or "pdf" not in c.lower():
            continue
        seen.add(c)
        if c.startswith("//"):
            c = "https:" + c
        elif c.startswith("/"):
            c = "https://ersp.lib.whu.edu.cn" + c
        elif not c.startswith("http"):
            continue
        got = _try_save_pdf(s, c, pdf_path)
        if got:
            paths["pdf"] = got
            break
    return paths, None
