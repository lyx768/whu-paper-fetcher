"""武大 CAS 自动登录（经浏览器后端）。

返回码：0=成功/已登录, 1=失败（凭证错误/表单变化）, 2=需要人工过 MFA。
凭证只从本地 creds 文件读取，绝不在日志/对话中回显。
"""
import json
import time

CAS_LOGIN = "https://cas.whu.edu.cn/authserver/login"


def _state(backend):
    try:
        st = backend.eval_js("(()=>JSON.stringify({url:location.href,title:document.title}))()")
        if isinstance(st, str):
            try:
                return json.loads(st)
            except Exception:
                return {}
        return st or {}
    except Exception:
        return {}


def _is_logged_in(url, title):
    u = (url or "").lower()
    return "personcenter" in u or "personalinfo" in u or "个人中心" in (title or "")


def _needs_mfa(url):
    u = (url or "").lower()
    return any(k in u for k in ["mfa", "verify", "otp", "sms", "authcode", "dynamic"])


def autologin(backend, config, creds):
    """建立武大 CAS 会话。成功返回 0，MFA 返回 2，失败返回 1。"""
    backend.open(CAS_LOGIN)
    time.sleep(5)

    st = _state(backend)
    if _is_logged_in(st.get("url", ""), st.get("title", "")):
        return 0

    # 先探测浏览器是否已自动填充（你的私有 WebBridge 会话通常已填充）
    pf = backend.eval_js(
        "(()=>{const u=document.querySelector('input#username,input[name=username]');"
        "const p=document.querySelector('input#password,input[name=password],input[type=password]');"
        "return JSON.stringify({u:(u&&u.value||'').length,p:(p&&p.value||'').length});})()"
    )
    try:
        pfd = json.loads(pf) if isinstance(pf, str) else (pf or {})
        filled = pfd.get("u", 0) > 0 and pfd.get("p", 0) > 0
    except Exception:
        filled = False

    if not filled:
        user = creds.get("username") or config.get("whu", "username", default="")
        pwd = creds.get("password", "")
        if not user or not pwd:
            return 1
        backend.fill("input#username", user)
        backend.fill("input#password", pwd)

    # 提交按钮是 <a id="login_submit">（不是 button/input）
    backend.click("#login_submit")
    time.sleep(7)

    st2 = _state(backend)
    url2 = (st2.get("url", "") or "").lower()
    title2 = st2.get("title", "")
    if _is_logged_in(url2, title2):
        return 0
    if _needs_mfa(url2):
        return 2
    return 1
