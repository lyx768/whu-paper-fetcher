"""武大 SFX 链接解析器 —— 建立 EZproxy 会话的权威路径（用户 2026-09-14 亲自示范）。

核心思想（用户原话级教训）：订阅论文**不直怼出版社原站**（Elsevier craft challenge /
Wiley Cloudflare 都会拦），**也不瞎猜 EZproxy 路径**（`s/com/wiley/www/...` 必 404）。
走武大 SFX 按 DOI 解析，由它 302 出**正确的 EZproxy 深链**——导航这个深链顺带把
ersp 会话建立起来，这正是 ARP / 浏览器全文路线的前置条件。

已知 DOI 时，这与 WOS 检索结果列表里的 "Full text at publisher"（SFX）按钮**完全等价**
——WOS 只是检索入口，SFX 是取全文出口，两者是一套（见 integrations/skill/references/
fulltext-playbook.md 流程 A/C）。

关键实测参数（勿改）：
  - SFX OpenURL 路径是 `/86whu`，**不是** `/sfxlcl41`（返回 no services found）、
    `/sfx_local` 是 404；
  - 解析表单 `document.forms['basic1']`，action=`/86whu/cgi/core/sfxresolver.cgi`，
    hidden 字段 request_id / service_id / tmp_ctx_obj_id / tmp_ctx_svc_id，
    text 字段 rft.year / rft.volume / rft.issue / rft.spage。
"""
import json
import time
import urllib.parse

SFX_BASE = "https://whu-sfx.exlibrisgroup.com.cn/86whu"

_MENU_MARK = "由武汉大学的SFX提供"


def sfx_openurl(doi):
    q = urllib.parse.quote(doi, safe="")
    return (SFX_BASE + "?url_ver=Z39.88-2004"
            "&rft_val_fmt=info:ofi/fmt:kev:mtx:journal"
            "&rft.genre=article&rft_id=info:doi/" + q)


def _eval(backend, code, timeout=30):
    try:
        d = backend.eval_js(code, timeout=timeout)
    except Exception:
        return ""
    if isinstance(d, dict):
        return d.get("value", d)
    return d if isinstance(d, str) else json.dumps(d, ensure_ascii=False) if d else ""


def resolve(doi, backend, wait=6):
    """SFX 解析 DOI 并落地 EZproxy 深链（会话建立）。

    返回 dict：ok / final_url（EZproxy 深链）或 reason。
    任何一步失败都返回 ok=False——调用方自行决定降级（原直连路径）。
    """
    out = {"ok": False, "final_url": "", "reason": ""}
    backend.open(sfx_openurl(doi))
    time.sleep(wait)

    # 1) 确认落在 SFX 菜单页
    chk = _eval(backend,
                "(()=>JSON.stringify({t:document.title,"
                "m:document.body.innerText.includes('%s'),"
                "u:location.href}))()" % _MENU_MARK)
    try:
        chk = json.loads(chk) if isinstance(chk, str) else (chk or {})
    except Exception:
        chk = {}
    if not chk.get("m"):
        out["reason"] = "SFX_MENU_NOT_FOUND(可能无订阅服务或页面变化) url=%s" % (chk.get("u", "")[:120])
        return out

    # 2) 读解析表单字段（无表单 = 只有 DOI/CALIS 服务，无直接全文）
    form = _eval(backend,
                 "(()=>{const f=document.forms['basic1'];if(!f)return 'null';"
                 "const o={action:f.action};"
                 "for(const el of f.elements){if(el.name)o[el.name]=el.value||'';}"
                 "return JSON.stringify(o);})()")
    try:
        form = json.loads(form) if isinstance(form, str) else None
    except Exception:
        form = None
    if not form or "action" not in form:
        out["reason"] = "SFX_NO_RESOLVER_FORM(可能只有DOI/CALIS文献传递服务)"
        return out

    # 3) 拼 sfxresolver.cgi GET → navigate → 302 落 EZproxy 深链
    action = form.pop("action")
    qs = urllib.parse.urlencode({k: v for k, v in form.items() if v})
    sep = "&" if "?" in action else "?"
    resolver_url = action if action.startswith("http") else (
        SFX_BASE + (action if action.startswith("/") else "/" + action) + sep + qs)
    backend.open(resolver_url)
    time.sleep(5)

    landing = _eval(backend, "(()=>location.href)()")
    out["final_url"] = (landing or "").strip()
    if "ersp.lib.whu.edu.cn" in out["final_url"] or "EZproxy" in out["final_url"]:
        out["ok"] = True
        out["reason"] = "via SFX sfxresolver"
    else:
        out["reason"] = "landing=%s" % out["final_url"][:140]
    return out
