"""编排器：DOI -> PII -> OA 兜底 -> 武大 ersp -> SD ARP 全文 / PDF。

入口函数：
- fetch_by_doi：单篇，自带浏览器会话
- fetch_many：批量，复用同一浏览器会话（只登录一次）
"""
import os
import re
import time
import datetime
import requests

from .config import load_config, load_creds
from .browser import get_backend
from .oa import oa_pdf_url, download_url
from .whu_auth import autologin
from .sd_arp import fetch_fulltext, save_article_pdf
from .validate import verify_pdf_matches
from . import sfx


def _establish_session(backend, doi):
    """SFX-by-DOI 建立 EZproxy 会话（用户 2026-09-14 教的权威路径）。
    失败只记 note，不阻断——旧直连路径仍可尝试。"""
    try:
        r = sfx.resolve(doi, backend)
        if r.get("ok"):
            return {"sfx": "ok", "final_url": r.get("final_url", "")[:160]}
        return {"sfx": "skip", "note": r.get("reason", "")[:160]}
    except Exception as e:
        return {"sfx": "skip", "note": str(e)[:160]}

_HEADERS = {"User-Agent": "whu-paper-fetcher/0.1 (+https://github.com/whu-paper-fetcher/whu-paper-fetcher)"}

# 请求节流：避免对出版商/学校服务器造成负担，也降低触发限速或账号风控的概率。
_daily_count = {}


def _throttle(config):
    delay = config.get("request", "delay_seconds", default=3)
    if delay:
        time.sleep(delay)
    today = datetime.date.today().isoformat()
    _daily_count[today] = _daily_count.get(today, 0) + 1
    limit = config.get("request", "daily_limit", default=50)
    if limit and _daily_count[today] > limit:
        raise RuntimeError(
            "已达每日下载上限 %d，已停止以避免触发出版商/学校限速。明日自动重置。" % limit
        )


def _sanitize(doi):
    return re.sub(r"[^A-Za-z0-9._-]", "_", doi)


def resolve_doi(doi):
    """返回 (pii, title)。pii 解析不到、或解析到的 alternative-id 实为 DOI 本身时返回 (None, title)。"""
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", headers=_HEADERS, timeout=20)
        if r.status_code == 200:
            msg = r.json().get("message", {})
            pii = (msg.get("alternative-id") or [None])[0]
            title = ""
            if msg.get("title"):
                title = msg["title"][0] if isinstance(msg["title"], list) else msg["title"]
            # 真实 SD PII 形如 S0038-0717(21)00234-5，绝不以 "10." 开头；
            # Wiley/Springer 等会把 DOI 本身塞进 alternative-id，需剔除，否则误走 SD 路线
            if pii and pii.startswith("10."):
                pii = None
            return pii, title
    except Exception:
        pass
    return None, ""


def _keywords(title):
    if not title:
        return []
    return [w.lower() for w in re.split(r"\s+", title) if len(w) > 3]


def try_oa(doi, email, out_dir, tag, verify):
    src, url = oa_pdf_url(doi, email)
    if not url:
        return None
    pdf_path = os.path.join(out_dir, f"{tag}.pdf")
    if not download_url(url, pdf_path):
        return None
    rec = {"source": src, "url": url, "pdf": pdf_path}
    if verify:
        _, title = resolve_doi(doi)
        ok, note = verify_pdf_matches(pdf_path, _keywords(title))
        rec["verified"] = ok
        rec["note"] = note
    return rec


def fetch_whu(backend, doi, pii, config, out_dir, tag, display_name):
    """走武大 ersp 代理取全文。backend 必须已登录 CAS。
    - 有 PII（Elsevier/ScienceDirect）：走 SD ARP 纯文本接口（pure_fetch）。
    - 无 PII（Wiley / Springer / T&F 等）：走通用 EZproxy 路由（ezproxy）。
    """
    if pii:
        return _fetch_whu_sd(backend, doi, pii, config, out_dir, tag, display_name)

    # 通用 EZproxy（出版社无关，2026-09-17 突破并固化）
    try:
        from .ezproxy import fetch_generic
        paths, err = fetch_generic(backend, doi, config, out_dir,
                                   tag=tag, display_name=display_name)
        if err:
            return {"error": "EZPROXY_FAILED", "note": err, "via": "curl_cffi_generic"}
        rec = {"html": paths["html"], "via": "curl_cffi_generic"}
        if paths.get("fulltext_txt"):
            rec["fulltext_txt"] = paths["fulltext_txt"]
        if paths.get("pdf"):
            rec["pdf"] = paths["pdf"]
        return rec
    except ImportError:
        return {"error": "NO_PII", "note": "无 PII；通用 EZproxy 路由需 curl_cffi"
                                      "（pip install -e '.[browser]'）"}


def _fetch_whu_sd(backend, doi, pii, config, out_dir, tag, display_name):
    """SD（Elsevier）专用：走 ersp EZproxy + SD ARP 全文接口。"""
    # 首选：无感全自动链路（2026-09-16 打通）——playwright 只做 SSO，
    # ersp 域请求交给 curl_cffi（chromium TLS 指纹被 ersp WAF 掐，UA 伪装救不了）
    try:
        from .pure_fetch import fetch_fulltext_curlcffi
        paths, err = fetch_fulltext_curlcffi(backend, doi, pii, config,
                                             out_dir, tag=tag, display_name=display_name)
        if err:
            return {"error": "ARP_FAILED", "note": err, "via": "curl_cffi"}
        rec = {"fulltext_md": paths["markdown"], "body_json": paths["body"],
               "html": paths["html"], "via": "curl_cffi"}
        pdf_path = os.path.join(out_dir, f"{tag}.pdf")
        if save_article_pdf(backend, pii, config, pdf_path):
            rec["pdf"] = pdf_path
        return rec
    except ImportError:
        pass  # 环境没装 curl_cffi 时退回旧路径

    # 旧路径：daemon/浏览器捕获 ARP 响应（要求真实 Edge TLS 指纹，headless 常被掐）
    paths, err = fetch_fulltext(backend, pii, config, out_dir, tag=tag, display_name=display_name)
    if err:
        return {"error": "ARP_FAILED", "note": err}
    rec = {"fulltext_md": paths["markdown"], "body_json": paths["body"], "html": paths["html"]}
    pdf_path = os.path.join(out_dir, f"{tag}.pdf")
    if save_article_pdf(backend, pii, config, pdf_path):
        rec["pdf"] = pdf_path
    return rec


def fetch_by_doi(doi, config=None, backend_name=None, verify=None):
    """单篇抓取（自建浏览器会话）。返回结果字典。"""
    config = config or load_config()
    email = config.get("oa", "email", default="")
    skip_oa = config.get("oa", "skip_oa", default=False)
    out_dir = os.path.expanduser(config.get("download", "output_dir", default="~/Downloads/whu-papers"))
    do_verify = verify if verify is not None else config.get("download", "verify", default=True)
    os.makedirs(out_dir, exist_ok=True)
    tag = _sanitize(doi)

    pii, _ = resolve_doi(doi)
    result = {"doi": doi, "pii": pii, "oa": None, "whu": None, "pdf": None}

    _throttle(config)
    if not skip_oa:
        oa = try_oa(doi, email, out_dir, tag, do_verify)
        if oa:
            result["oa"] = oa
            result["pdf"] = oa["pdf"]
            return result

    backend = get_backend(backend_name, config)
    creds = load_creds(config)
    rc = autologin(backend, config, creds)
    if rc == 2:
        backend.close()
        result["whu"] = {"error": "MFA_REQUIRED", "note": "需手动过一次二次验证后重试"}
        return result
    if rc == 1:
        backend.close()
        result["whu"] = {"error": "LOGIN_FAILED", "note": "CAS 登录失败（凭证缺失或表单变化）"}
        return result
    sfxr = _establish_session(backend, doi)
    result["whu"] = fetch_whu(backend, doi, pii, config, out_dir, tag,
                              config.get("whu", "display_name", default=""))
    if isinstance(result["whu"], dict):
        result["whu"]["sfx"] = sfxr.get("sfx")
        if sfxr.get("note"):
            result["whu"]["sfx_note"] = sfxr["note"]
    if result["whu"] and result["whu"].get("pdf"):
        result["pdf"] = result["whu"]["pdf"]
    backend.close()
    return result


def fetch_many(dois, config=None, backend_name=None, verify=None):
    """批量抓取：复用同一浏览器会话（只登录一次 CAS）。"""
    config = config or load_config()
    email = config.get("oa", "email", default="")
    skip_oa = config.get("oa", "skip_oa", default=False)
    out_dir = os.path.expanduser(config.get("download", "output_dir", default="~/Downloads/whu-papers"))
    do_verify = verify if verify is not None else config.get("download", "verify", default=True)
    os.makedirs(out_dir, exist_ok=True)

    results = []
    backend = None
    logged_in = False
    for doi in dois:
        _throttle(config)
        tag = _sanitize(doi)
        pii, _ = resolve_doi(doi)
        res = {"doi": doi, "pii": pii, "oa": None, "whu": None, "pdf": None}

        if not skip_oa:
            oa = try_oa(doi, email, out_dir, tag, do_verify)
            if oa:
                res["oa"] = oa
                res["pdf"] = oa["pdf"]
                results.append(res)
                continue

        if backend is None:
            backend = get_backend(backend_name, config)
        if not logged_in:
            rc = autologin(backend, config, load_creds(config))
            if rc == 2:
                res["whu"] = {"error": "MFA_REQUIRED", "note": "需手动过一次二次验证"}
                results.append(res)
                backend.close()
                backend = None
                continue
            if rc == 1:
                res["whu"] = {"error": "LOGIN_FAILED", "note": "CAS 登录失败"}
                results.append(res)
                backend.close()
                backend = None
                continue
            logged_in = True

        sfxr = _establish_session(backend, doi)
        res["whu"] = fetch_whu(backend, doi, pii, config, out_dir, tag,
                               config.get("whu", "display_name", default=""))
        if isinstance(res["whu"], dict):
            res["whu"]["sfx"] = sfxr.get("sfx")
            if sfxr.get("note"):
                res["whu"]["sfx_note"] = sfxr["note"]
        if res["whu"] and res["whu"].get("pdf"):
            res["pdf"] = res["whu"]["pdf"]
        results.append(res)

    if backend is not None:
        backend.close()
    return results
