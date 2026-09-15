"""ScienceDirect 全文获取（经武大 ersp EZproxy + ARP 接口）。

为什么走 ARP：SD 文章页只是外壳，正文由前端异步请求
/sdfe/arp/pii/<PII>/body?entitledToken=<token> 拉取。EZproxy 重写 HTML 的 href，
但 JS 拼出的 ARP 地址绕过了代理前缀，导致正文请求失败、页面只剩摘要。
本模块手工补回该请求，直接取纯文本全文（无需 TDM API key）。

注意：武大 EZproxy 会话最稳的入口是 whu.metaersp.cn 门户 SSO，
再站内跳转 ersp（直接 navigate ersp 会被 CAS 拦回登录页）。
"""
import json
import os
import re
import time

INLINE = {
    "italic", "bold", "sup", "sub", "small-caps", "monospace", "underline",
    "ce:italic", "ce:bold", "ce:sup", "ce:sub", "mml:math", "math",
    "cross-ref", "xref", "link", "span", "ce:span", "inf",
}
BLOCK_SKIP = {"footnotes", "attachments", "affiliations", "correspondences"}


def _clean(s):
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _node_text(n):
    if isinstance(n, str):
        return n
    if isinstance(n, list):
        return "".join(_node_text(x) for x in n)
    if not isinstance(n, dict):
        return ""
    out = ""
    if "_" in n and isinstance(n["_"], (str, int, float)):
        out += str(n["_"])
    kids = n.get("$$")
    if kids:
        out += "".join(_node_text(k) for k in kids)
    return out


def _first_named(n, name):
    for k in n.get("$$", []) if isinstance(n, dict) else []:
        if isinstance(k, dict) and k.get("#name") == name:
            return k
    return None


def _walk_float(n, out):
    items = n.get("$$") if isinstance(n, dict) else None
    if not items:
        return
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("#name") == "float":
            _walk_float(it, out)
            continue
        lbl = _first_named(it, "label")
        cap = _first_named(it, "caption")
        label = _clean(_node_text(lbl)) if lbl else ""
        text = _clean(_node_text(cap)) if cap else ""
        if text:
            prefix = "Figure" if it.get("#name") == "figure" else "Table"
            out.append(("fig", "%s %s. %s" % (prefix, label, text)))


def _walk(n, depth, out):
    if isinstance(n, list):
        for x in n:
            _walk(x, depth, out)
        return
    if not isinstance(n, dict):
        return
    name = n.get("#name", "")
    if name in BLOCK_SKIP:
        return
    if name == "section":
        title = ""
        for k in n.get("$$", []):
            if isinstance(k, dict) and k.get("#name") == "section-title":
                title = _clean(_node_text(k))
        if title:
            out.append(("h%d" % min(depth + 1, 4), title))
        for k in n.get("$$", []):
            if isinstance(k, dict) and k.get("#name") in ("section-title", "label"):
                continue
            _walk(k, depth + 1, out)
        return
    if name in ("float", "floats"):
        _walk_float(n, out)
        return
    if name in ("section-title", "title"):
        t = _clean(_node_text(n))
        if t:
            out.append(("h%d" % min(depth, 4), t))
        return
    if name in ("para", "simple-para"):
        t = _clean(_node_text(n))
        if t:
            out.append(("p", t))
        return
    if name == "list":
        for k in n.get("$$", []):
            if isinstance(k, dict) and k.get("#name") == "list-item":
                t = _clean(_node_text(k))
                if t:
                    out.append(("li", t))
        return
    if name == "abstract":
        for k in n.get("$$", []):
            _walk(k, depth + 1, out)
        return
    kids = n.get("$$")
    if kids:
        for k in kids:
            _walk(k, depth, out)
        return
    t = _clean(_node_text(n))
    if t and len(t) > 40:
        out.append(("p", t))


def parse_arp_body(payload):
    """把 ARP body（SD 内容模型树）解析为 Markdown 文本。"""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return payload
    out = []
    _walk(payload.get("content", payload), 1, out)
    if isinstance(payload, dict) and payload.get("floats"):
        out.append(("h2", "Figure and table captions"))
        _walk_float(payload["floats"], out)

    lines = []
    for kind, text in out:
        if kind.startswith("h"):
            lvl = int(kind[1])
            lines.append("")
            lines.append("#" * lvl + " " + text)
            lines.append("")
        elif kind == "li":
            lines.append("- " + text)
        elif kind == "fig":
            lines.append("")
            lines.append("> **" + text + "**")
            lines.append("")
        else:
            lines.append(text)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def fetch_fulltext(backend, pii, config, out_dir, tag=None, display_name=""):
    """抓取 SD 纯文本全文。返回 (paths_dict, error_or_None)。"""
    ersp_sd = config.get("whu", "ersp_sd")
    metaersp = config.get("whu", "metaersp")
    article_url = "%s/science/article/pii/%s" % (ersp_sd, pii)

    backend.network_start()
    # 1) 经 metaersp 门户建立 SSO 会话（避免直接 navigate ersp 被 CAS 拦截）
    backend.open(metaersp)
    time.sleep(4)
    # 2) 站内跳转到文章页，复用 metaersp 的 SSO cookie
    backend.eval_js("location.href=%s" % json.dumps(article_url))
    time.sleep(13)
    # 清掉可能弹出的"请输入姓名"保密协议对话框
    try:
        backend.handle_dialog(accept=True, prompt_text=display_name)
    except Exception:
        pass

    def _detail_body(request_id):
        """取 network detail 的响应体。
        注意：daemon 的 detail 常返回 {"body": "<html>", ...}。若直接对整字典 json.dumps，
        内层引号会被转义成 \\"，后面的 entitledToken 正则必然失配（2026-09-15 实测）。"""
        raw = backend.network_detail(request_id)
        if isinstance(raw, dict) and isinstance(raw.get("body"), (str, dict)):
            return raw["body"]
        return raw

    def _token_of(s):
        if not isinstance(s, str):
            return None
        m = re.search(r'"entitledToken":"([A-Fa-f0-9]+)"', s)
        return m.group(1) if m else None

    reqs = backend.network_list()
    hit = next((r for r in reqs
                if ("/pii/%s" % pii) in r.get("url", "")
                and (r.get("mimeType") or "").startswith("text/html")), None)
    html = ""
    if hit:
        raw = _detail_body(hit["requestId"])
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        if isinstance(raw, str):
            html = raw

    token = _token_of(html)
    if not token:
        # 回退：文章页命中浏览器缓存时不会产生新的网络请求，network 必然捕不到响应。
        # 直接从页面 DOM 取完整 HTML（实测 daemon 可完整回传 ~2MB outerHTML）。
        try:
            dom = backend.eval_js("document.documentElement.outerHTML")
        except Exception:
            dom = None
        if isinstance(dom, str):
            token = _token_of(dom)
            if token:
                html = dom
    if not token:
        if not html:
            return None, "未捕获到文章 HTML 响应，且 DOM 回退也未取到（可能 SSO 未建立或网络拦截）"
        return None, "HTML 中无 entitledToken（可能未授权或页面结构变化）"

    # 3) 补回 ARP body 请求
    arp_url = "%s/sdfe/arp/pii/%s/body?entitledToken=%s" % (ersp_sd, pii, token)
    backend.open(arp_url)
    time.sleep(8)
    reqs2 = backend.network_list()
    body_hit = next((r for r in reqs2
                     if "/body?" in r.get("url", "")
                     and "json" in (r.get("mimeType") or "")), None)
    payload = None
    if body_hit:
        payload = _detail_body(body_hit["requestId"])
        # daemon detail 可能返回 {"ok":false,"error":{...}}（如响应体已被浏览器回收，
        # 报 "No resource with given identifier found"）——这种一律视为取不到，走下面的回退。
        if isinstance(payload, dict) and payload.get("ok") is False and "error" in payload:
            payload = None
    if payload is None:
        # 回退：ARP 端点是 application/json，浏览器会把它渲染成文本页，
        # 直接取 body.innerText 即为完整 JSON（实测 2026-09-15 生效）。
        try:
            txt = backend.eval_js("document.body ? document.body.innerText : ''")
        except Exception:
            txt = None
        if isinstance(txt, str) and txt.strip().startswith("{"):
            try:
                payload = json.loads(txt)
            except Exception:
                payload = None
    if not payload:
        return None, "ARP body 为空（network detail 与页面 innerText 两条路都失败）"

    os.makedirs(out_dir, exist_ok=True)
    tag = tag or pii
    doc_path = os.path.join(out_dir, "%s_doc.html" % tag)
    body_path = os.path.join(out_dir, "%s_body.json" % tag)
    md_path = os.path.join(out_dir, "%s_fulltext.md" % tag)
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    md = parse_arp_body(payload)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    return {"html": doc_path, "body": body_path, "markdown": md_path}, None


def save_article_pdf(backend, pii, config, pdf_path):
    """尽力而为：把文章页渲染为 PDF（Cloudflare 挑战页可能挂起，失败不致命）。"""
    ersp_sd = config.get("whu", "ersp_sd")
    metaersp = config.get("whu", "metaersp")
    article_url = "%s/science/article/pii/%s" % (ersp_sd, pii)
    try:
        backend.open(metaersp)
        time.sleep(3)
        backend.eval_js("location.href=%s" % json.dumps(article_url))
        time.sleep(10)
        # 切前台再渲染，有头模式下更稳
        try:
            backend.cdp("Page.bringToFront")
        except Exception:
            pass
        backend.save_pdf(pdf_path)
        return True
    except Exception as e:
        return False
