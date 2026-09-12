"""WebBridge 后端：调用本地 Kimi WebBridge daemon（你的私有栈，已实测验证）。

依赖：本机运行 Kimi WebBridge 扩展 + daemon（默认 http://127.0.0.1:10086/command）。
适用：你自己日常使用，复用已登录的 Edge 会话。
"""
import json
import urllib.request
from .base import BrowserBackend


class WebBridgeBackend(BrowserBackend):
    def __init__(self, url, session):
        self.url = url
        self.session = session

    def _call(self, action, args=None, timeout=120):
        body = json.dumps({"action": action, "args": args or {}, "session": self.session}).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _ok(self, resp):
        # daemon 两种返回形态都兼容：{"ok":true,"data":...} 或 裸 data
        if isinstance(resp, dict) and "data" in resp:
            return resp["data"]
        return resp

    def open(self, url, new_tab=False):
        return self._call("navigate", {"url": url, "newTab": new_tab})

    def eval_js(self, code, timeout=30):
        d = self._ok(self._call("evaluate", {"code": code}, timeout=timeout))
        if isinstance(d, dict):
            return d.get("value", d)
        return d

    def click(self, selector):
        return self._call("click", {"selector": selector})

    def fill(self, selector, value):
        return self._call("fill", {"selector": selector, "value": value})

    def network_start(self):
        return self._call("network", {"cmd": "start"})

    def network_list(self):
        d = self._ok(self._call("network", {"cmd": "list"}))
        if isinstance(d, dict):
            return d.get("requests", [])
        return d if isinstance(d, list) else []

    def network_detail(self, request_id):
        return self._ok(self._call("network", {"cmd": "detail", "requestId": request_id}))

    def handle_dialog(self, accept=True, prompt_text=None):
        return self._call("dialog", {"accept": accept, "promptText": prompt_text or ""})

    def cdp(self, method, params=None):
        return self._call("cdp", {"method": method, "params": params or {}})

    def save_pdf(self, path, print_background=True):
        return self._call("save_as_pdf", {"path": path, "print_background": print_background})

    def close(self):
        try:
            self._call("close_session")
        except Exception:
            pass
