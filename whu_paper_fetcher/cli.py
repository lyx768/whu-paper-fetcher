#!/usr/bin/env python3
"""whu-paper-fetcher 命令行入口。"""
import argparse
import json
import sys

from .config import load_config
from .fetcher import fetch_by_doi, fetch_many


def _print_result(res):
    doi = res.get("doi", "")
    print(f"\n=== {doi} ===")
    if res.get("oa"):
        oa = res["oa"]
        v = "✓" if oa.get("verified", True) else "✗"
        print(f"  [OA] {oa['source']}: {oa['pdf']}  {v} {oa.get('note','')}")
        return
    if res.get("whu"):
        whu = res["whu"]
        if whu.get("error"):
            print(f"  [WHU] 失败: {whu['error']} - {whu.get('note','')}")
        else:
            print(f"  [WHU] 全文: {whu.get('fulltext_md')}")
            if whu.get("pdf"):
                print(f"        PDF:  {whu['pdf']}")
        return
    print("  [!] 未获取到任何全文（OA 与 WHU 均未命中）")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="whu-paper-fetcher",
        description="武大专属文献全文获取：CAS 自动登录 + ersp EZproxy + SD ARP 全文接口，OA 兜底。",
    )
    ap.add_argument("--doi", help="单个 DOI")
    ap.add_argument("--doi-file", help="DOI 列表文件（每行一个）")
    ap.add_argument("--backend", default=None, help="浏览器后端：playwright（默认）/ webbridge")
    ap.add_argument("--skip-oa", action="store_true", help="跳过 OA 兜底，直接走武大代理")
    ap.add_argument("--no-verify", action="store_true", help="下载后不做 PDF 校验")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    a = ap.parse_args(argv)

    if not a.doi and not a.doi_file:
        ap.error("必须提供 --doi 或 --doi-file")

    config = load_config()
    if a.skip_oa:
        # 临时覆盖（不改配置文件）
        config._d.setdefault("oa", {})["skip_oa"] = True
    verify = not a.no_verify

    if a.doi:
        res = fetch_by_doi(a.doi, config=config, backend_name=a.backend, verify=verify)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            _print_result(res)
        return 0

    dois = []
    with open(a.doi_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                dois.append(line)
    results = fetch_many(dois, config=config, backend_name=a.backend, verify=verify)
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            _print_result(r)
        ok = sum(1 for r in results if r.get("oa") or (r.get("whu") and not r["whu"].get("error")))
        print(f"\n完成：{ok}/{len(results)} 命中")
    return 0


if __name__ == "__main__":
    sys.exit(main())
