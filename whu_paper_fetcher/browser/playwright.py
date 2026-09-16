"""Playwright 后端：用 Playwright 驱动本机 Chromium（便携默认，同学用）。

不依赖任何第三方浏览器扩展，pip install 'whu-paper-fetcher[browser]' 即可。

⚠️ 红线（用户 2026-09-16 明确）：**不得弹出界面，必须用户无感** —— 默认
headless=True。CAS 登录用本地 creds 自动填表；若遇到必须人工交互的场景
（MFA/验证码），返回 MFA_REQUIRED 让调用方提示用户，绝不为此弹窗。

 Cloudflare 类挑战页在无头下可能挂起：实测 ARP/SFX 路线不走 Cloudflare
（Elsevier 拦的是直怼原站，SFX/EZproxy 域不设防），所以无头可用。
"""
import json
import threading
from .base import BrowserBackend


class PlaywrightBackend(BrowserBackend):
    def __init__(self, browser_name="chromium", config=None, headless=True):
        self.browser_name = browser_name
        self._display_name = (config.whu.get("display_name", "") if config else "")
        self._headless = headless
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._cdp = None
        self._lock = threading.Lock()
        self._responses = []          # [{id, url, mimeType, status, _resp}]
        self._resp_seq = 0

    # ---- 生命周期 ----
    def _ensure(self):
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = getattr(self._pw, self.browser_name).launch(headless=self._headless)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._page.on("response", self._on_response)
        self._page.on("dialog", self._on_dialog)

    def _on_response(self, response):
        # 记录响应头信息，body 延迟到 network_detail 再读，避免大响应阻塞
        ct = response.headers.get("content-type", "")
        with self._lock:
            self._resp_seq += 1
            rid = self._resp_seq
            self._responses.append({
                "id": rid,
                "url": response.url,
                "mimeType": ct,
                "status": response.status,
                "_resp": response,
            })

    def _on_dialog(self, dialog):
        # WHU 数据库保密协议弹窗会要求输入姓名；自动以配置中的 display_name 接受
        try:
            if dialog.type == "prompt":
                dialog.accept(self._display_name or "")
            else:
                dialog.accept()
        except Exception:
            pass

    # ---- 接口实现 ----
    def open(self, url, new_tab=False):
        self._ensure()
        self._page.goto(url, wait_until="domcontentloaded")
        return {"url": self._page.url}

    def eval_js(self, code, timeout=30):
        self._ensure()
        return self._page.evaluate(code)

    def click(self, selector):
        self._ensure()
        self._page.click(selector, timeout=15000)
        return True

    def fill(self, selector, value):
        self._ensure()
        self._page.fill(selector, value, timeout=15000)
        return True

    def network_start(self):
        # 清空之前的记录，开始新一轮捕获
        with self._lock:
            self._responses.clear()
        return True

    def network_list(self):
        with self._lock:
            return [
                {"url": r["url"], "requestId": r["id"],
                 "mimeType": r["mimeType"], "status": r["status"]}
                for r in self._responses
            ]

    def network_detail(self, request_id):
        with self._lock:
            hit = next((r for r in self._responses if r["id"] == request_id), None)
        if not hit:
            return {}
        try:
            body = hit["_resp"].body()
        except Exception:
            return {}
        # 尝试按 JSON / 文本解析
        ct = hit["mimeType"].lower()
        if "json" in ct:
            try:
                return json.loads(body.decode("utf-8", "replace"))
            except Exception:
                pass
        return body.decode("utf-8", "replace")

    def handle_dialog(self, accept=True, prompt_text=None):
        # Playwright 的 dialog 由事件处理器自动处理；此处作为兼容接口空转
        return True

    def cdp(self, method, params=None):
        self._ensure()
        if self._cdp is None:
            self._cdp = self._page.context.new_cdp_session(self._page)
        return self._cdp.send(method, params or {})

    def save_pdf(self, path, print_background=True):
        self._ensure()
        self._page.pdf(path=path, print_background=print_background)
        return {"path": path}

    def close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._pw = None
