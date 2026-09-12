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
    """返回 (pii, title)。pii 解析不到时返回 (None, title)。"""
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", headers=_HEADERS, timeout=20)
        if r.status_code == 200:
            msg = r.json().get("message", {})
            pii = (msg.get("alternative-id") or [None])[0]
            title = ""
            if msg.get("title"):
                title = msg["title"][0] if isinstance(msg["title"], list) else msg["title"]
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
    """走武大 ersp 代理取 SD 全文。backend 必须已登录 CAS。"""
    if not pii:
        return {"error": "NO_PII", "note": "Crossref 未解析到 PII，无法走 SD 全文接口"}
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
    result["whu"] = fetch_whu(backend, doi, pii, config, out_dir, tag,
                              config.get("whu", "display_name", default=""))
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

        res["whu"] = fetch_whu(backend, doi, pii, config, out_dir, tag,
                               config.get("whu", "display_name", default=""))
        if res["whu"] and res["whu"].get("pdf"):
            res["pdf"] = res["whu"]["pdf"]
        results.append(res)

    if backend is not None:
        backend.close()
    return results
