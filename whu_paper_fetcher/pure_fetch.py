"""无感全自动取 Elsevier 全文（playwright SSO + curl_cffi 承接）——2026-09-16 全链实测。

分工（为什么是混合）：
  playwright headless —— 只负责 SSO：CAS creds 自动登录 → metaersp middle 链
    （CAS TGT / metaauth 会话 cookie 全部落进 context，全程无窗、用户无感）
  curl_cffi(impersonate="chrome") —— 承接 ersp 域的页面/接口请求。
    原因：ersp 的 WAF 在 **TLS/HTTP2 指纹层**掐 chromium（UA 伪装成真 Edge 也被断连，
    ERR_EMPTY_RESPONSE；同 URL curl 直连反而 404 放行）——UA 修不掉，指纹才修得掉。

关键路径（勿改，裸路径必 404/403）：
  入口  https://ersp.lib.whu.edu.cn/s/com/sciencedirect/G.https/science/article/pii/<PII>
        （昨天 17 篇成功页面的同款 EZproxy 前缀；比 linkinghub 签名链稳，
         那条链的 articleSelectSinglePerm 会回 "Your request cannot be processed"）
  token 页面内 entitledToken（一次性）
  body  https://ersp.lib.whu.edu.cn/s/com/sciencedirect/www/G.https/sdfe/arp/pii/<PII>/body?entitledToken=<tok>
        ⚠️ ARP 必须带 EZproxy 前缀，裸 /sdfe/arp/ 404（文献服务网关页）。

对外入口：
  fetch_fulltext_curlcffi(backend, doi, pii, config, out_dir, tag, display_name)
    backend 已跑完 autologin；本函数再走一次 middle 完成 metaauth SSO，然后
    导出 cookie 交给 curl_cffi。返回与 sd_arp.fetch_fulltext 同构的 paths 字典。
"""
import json
import os
import re
import time

from curl_cffi import requests as cr

MIDDLE = "https://whu.metaersp.cn/middle?url=https://doi.org/{doi}"
ARTICLE = "https://ersp.lib.whu.edu.cn/s/com/sciencedirect/G.https/science/article/pii/{pii}"
ARP = ("https://ersp.lib.whu.edu.cn/s/com/sciencedirect/www/G.https/"
       "sdfe/arp/pii/{pii}/body?entitledToken={tok}")
TOKEN_RE = re.compile(r"entitledToken[\"\':= ]+([A-Za-z0-9\-_]{16,})")


def _export_cookies(backend):
    ctx = getattr(backend, "_context", None)
    if ctx is None:
        return []
    return ctx.cookies()


def curl_session_from(backend):
    """从 playwright context 导出 cookie，建同指纹的 curl_cffi 会话。"""
    s = cr.Session(impersonate="chrome")
    for c in _export_cookies(backend):
        s.cookies.set(c["name"], c["value"],
                      domain=c["domain"].lstrip("."), path=c.get("path", "/"))
    return s


def fetch_fulltext_curlcffi(backend, doi, pii, config, out_dir, tag=None, display_name=""):
    """SSO(playwright) + 全文(curl_cffi)。返回 (paths|None, err|None)。"""
    if not pii:
        return None, "NO_PII"
    tag = tag or pii

    # 1) SSO：metaersp middle 会把 CAS TGT 换成 metaauth/ersp 会话 cookie
    try:
        backend.open(MIDDLE.format(doi=doi))
        time.sleep(6)          # middle 是 SPA，JS 跳 ersp /o/ 再 302 链，等它跑完
    except Exception as e:
        return None, "SSO_NAV_FAILED: %s" % str(e)[:120]

    s = curl_session_from(backend)
    if not list(s.cookies.jar):
        return None, "NO_COOKIES_EXPORTED"

    # 2) 文章页（curl_cffi 指纹过 WAF）
    try:
        r = s.get(ARTICLE.format(pii=pii), allow_redirects=True, timeout=90)
    except Exception as e:
        return None, "ARTICLE_FAILED: %s" % str(e)[:120]
    if r.status_code != 200 or "entitledToken" not in r.text:
        return None, "ARTICLE_NO_TOKEN(status=%s len=%d url=%s)" % (
            r.status_code, len(r.text), r.url[:100])
    tok = TOKEN_RE.search(r.text).group(1)

    # 3) ARP body（带 EZproxy 前缀）
    try:
        r3 = s.get(ARP.format(pii=pii, tok=tok), timeout=90)
    except Exception as e:
        return None, "ARP_FAILED: %s" % str(e)[:120]
    if r3.status_code != 200 or not r3.text.strip().startswith("{"):
        return None, "ARP_BAD(status=%s len=%d)" % (r3.status_code, len(r3.text))
    payload = json.loads(r3.text)

    # 4) 解析 + 落盘（复用 sd_arp 的解析器，文件三件套与 daemon 路线完全同构）
    from .sd_arp import parse_arp_body
    os.makedirs(out_dir, exist_ok=True)
    doc_path = os.path.join(out_dir, "%s_doc.html" % tag)
    body_path = os.path.join(out_dir, "%s_body.json" % tag)
    md_path = os.path.join(out_dir, "%s_fulltext.md" % tag)
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(r.text)
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(parse_arp_body(payload))
    return {"html": doc_path, "body": body_path, "markdown": md_path}, None
