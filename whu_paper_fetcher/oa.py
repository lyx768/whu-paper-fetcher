"""OA（开放获取）兜底连接器：先试免费渠道，不碰浏览器。

顺序：Unpaywall → Semantic Scholar → OpenAlex → Europe PMC。
任一返回直链 PDF 即成功。仅做查询，不下载（下载由 fetcher 统一处理）。
"""
import requests

_HEADERS = {"User-Agent": "whu-paper-fetcher/0.1 (+https://github.com/whu-paper-fetcher/whu-paper-fetcher)"}


def _get(url, params=None, timeout=20):
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r
    except Exception:
        pass
    return None


def unpaywall(doi, email):
    if not email:
        return None
    r = _get(f"https://api.unpaywall.org/v2/{doi}", params={"email": email})
    if not r:
        return None
    try:
        d = r.json()
        loc = d.get("best_oa_location") or d.get("oa_location") or {}
        return loc.get("url_for_pdf")
    except Exception:
        return None


def semantic_scholar(doi):
    r = _get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
             params={"fields": "openAccessPdf"})
    if not r:
        return None
    try:
        return (r.json().get("openAccessPdf") or {}).get("url")
    except Exception:
        return None


def openalex(doi):
    r = _get(f"https://api.openalex.org/works/doi:{doi}")
    if not r:
        return None
    try:
        for loc in r.json().get("locations", []):
            u = (loc.get("pdf_url") or "").lower()
            if not u:
                continue
            # 跳过已知的死路链接（出版商代理占位）
            if any(x in u for x in ("sciencedirect", "linkinghub", "elsevier")):
                continue
            return loc["pdf_url"]
    except Exception:
        return None
    return None


def europe_pmc(doi):
    r = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
             params={"query": f'DOI:"{doi}"', "format": "json", "resultType": "core"})
    if not r:
        return None
    try:
        for res in r.json().get("resultList", {}).get("result", []):
            pmcid = res.get("pmcid")
            if pmcid and res.get("isOpenAccess") == "Y":
                rr = _get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/PMC/{pmcid}/fullTextPDF")
                if rr and rr.headers.get("content-type", "").startswith("application/pdf"):
                    return rr.url
    except Exception:
        return None
    return None


def oa_pdf_url(doi, email=""):
    """返回 (source_name, pdf_url) 或 (None, None)。"""
    steps = [
        ("unpaywall", lambda: unpaywall(doi, email)),
        ("semantic_scholar", semantic_scholar),
        ("openalex", openalex),
        ("europe_pmc", europe_pmc),
    ]
    for name, fn in steps:
        try:
            url = fn()
            if url:
                return name, url
        except Exception:
            continue
    return None, None


def download_url(url, path, timeout=60):
    """把 PDF 直链下载到 path。成功返回 True。"""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=timeout, stream=True)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf"):
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False
