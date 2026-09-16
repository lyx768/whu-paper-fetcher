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


def _trace(backend, url):
    """调试辅助：把重定向链上每个落点写本地 trace 文件（不进 stdout/日志，避免刷屏）。"""
    try:
        body = _eval(backend, "(()=>document.body?document.body.innerText.slice(0,200):'')()") or ""
        with open(r"F:\AGENT\work\temp\sfx_trace.log", "a", encoding="utf-8") as f:
            f.write("URL: %s\nBODY: %s\n---\n" % (url[:150], body.replace("\n", " ")[:180]))
    except Exception:
        pass


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


def inject_cookies(backend, cookies):
    """注入从日常 Edge 导出的 cookie，让 headless context 复用已有 SFX/EZproxy 会话
    （手册 IEEE 专节同款手法）。cookies 接受 CDP Network.getAllCookies 的结果：
    [{"name","value","domain","path"}, ...]。前置：backend 已启动（有 _context）。"""
    if isinstance(cookies, dict) and "cookies" in cookies:
        cookies = cookies["cookies"]
    clean = []
    for c in list(cookies or []):
        cc = {k: c[k] for k in ("name", "value", "domain", "path") if k in c}
        if {"name", "value"} <= set(cc) and "domain" in cc:
            cc.setdefault("path", "/")
            clean.append(cc)
    if hasattr(backend, "_ensure"):
        backend._ensure()
    ctx = getattr(backend, "_context", None)
    if ctx is None or not clean:
        return False
    ctx.add_cookies(clean)
    return True


def resolve(doi, backend, wait=6):
    """SFX 解析 DOI 并落地 EZproxy 深链（会话建立）。

    返回 dict：ok / final_url（EZproxy 深链）或 reason。
    任何一步失败都返回 ok=False——调用方自行决定降级（原直连路径）。

    当前状态（2026-09-16 实测）：
      ✅ headless 下 SFX OpenURL 菜单页正常（解析表单、"电子全文"服务都在）
      ✅ 点 "Go"（type=button + onclick=openSFXMenuLink(...,'_blank')，需覆写
         window.open 才能让目标落在主 frame，否则它开新窗）
      ❌ 最后一环：resolver 302 需要 SFX SSO（metaauth/CAS）；全新 headless context
         没有 SFX 会话 cookie，被弹回菜单页。解法二选一：
         a) 从用户日常 Edge 导出 whu-sfx/ersp cookie 注入本 context（手册 IEEE 专节已验证的手法）
         b) 在 headless 里打通 metaauth serviceValidate 全链（工程量大）
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

    # 3) 真实点击 "Go"（与用户手动一致），但先覆写 window.open 把 _blank 目标
    #    重定向到当前 frame —— 红线：不弹任何窗口，用户无感。
    #    Go 按钮 type=button + onclick="openSFXMenuLink(...,'_blank')"，
    #    这解释了 f.submit() 无效与主 frame 永不动。
    r = _eval(backend,
              "(()=>{const f=document.forms['basic1'];if(!f)return 'NOFORM';"
              "window.__origOpen=window.open;"
              "window.open=function(u){if(u){location.href=String(u);}return null;};"
              "const s=f.querySelector('input[type=button],input[type=submit],button');"
              "if(!s)return 'NOBTN'; s.click(); return 'CLICKED';})()")
    if r != "CLICKED":
        out["reason"] = "SFX_NO_GO_BUTTON(%s)" % r
        return out
    time.sleep(4)

    landing = ""
    for _ in range(15):
        time.sleep(2)
        try:
            u = _eval(backend, "(()=>location.href)()")
        except Exception:
            continue                       # 页面正在重定向链中，context 暂不可用
        if u and u != landing:
            landing = u
            _trace(backend, landing)       # 调试：记录每次落点及页面摘要
        if landing and ("ersp.lib.whu.edu.cn" in landing
                        or "lib.whu.edu.cn" in landing
                        or ("sciencedirect" in landing and "exlibrisgroup" not in landing)):
            break
        if landing and "authserver/login" in landing:
            out["reason"] = "CAS_SSO_NOT_PASSED(未登录或 TGT 失效) landing=%s" % landing[:120]
            return out

    out["final_url"] = landing
    if landing and ("ersp.lib.whu.edu.cn" in landing or "lib.whu.edu.cn" in landing
                    or ("sciencedirect" in landing and "exlibrisgroup" not in landing)):
        out["ok"] = True
        out["reason"] = "via SFX sfxresolver"
    else:
        out["reason"] = "landing=%s" % landing[:140]
    return out
