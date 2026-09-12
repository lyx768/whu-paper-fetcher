"""浏览器后端抽象接口。

两种实现：
- WebBridgeBackend：调用本地 Kimi WebBridge daemon（你的私有栈，已验证）
- PlaywrightBackend：用 Playwright 驱动本机 Chromium（便携默认，同学用）

WHU 访问逻辑（whu_auth / sd_arp）只依赖本接口，不关心底层是哪套后端。
"""
from abc import ABC, abstractmethod


class BrowserBackend(ABC):
    @abstractmethod
    def open(self, url, new_tab=False):
        """导航到 url。"""
        ...

    @abstractmethod
    def eval_js(self, code, timeout=30):
        """执行 JS 表达式，返回 Python 值。"""
        ...

    @abstractmethod
    def click(self, selector):
        ...

    @abstractmethod
    def fill(self, selector, value):
        ...

    @abstractmethod
    def network_start(self):
        """开始记录网络请求。"""
        ...

    @abstractmethod
    def network_list(self):
        """返回 [{url, requestId, mimeType, status}, ...]。"""
        ...

    @abstractmethod
    def network_detail(self, request_id):
        """返回该请求的响应体（str 或 dict）。"""
        ...

    @abstractmethod
    def handle_dialog(self, accept=True, prompt_text=None):
        """处理 JS 弹窗（alert/confirm/prompt）。prompt_text 用于 prompt 输入。"""
        ...

    @abstractmethod
    def cdp(self, method, params=None):
        """发送原始 CDP 命令（如 Page.bringToFront / Input.dispatchMouseEvent）。"""
        ...

    @abstractmethod
    def save_pdf(self, path, print_background=True):
        """把当前页渲染为 PDF 落盘。"""
        ...

    @abstractmethod
    def close(self):
        ...
