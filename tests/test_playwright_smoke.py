"""真实启动 Chromium，验证 Playwright 后端能起来并基本工作。

前置：pip install 'whu-paper-fetcher[browser]' && playwright install chromium
无需武大账号、无需联网即可验证后端可用性（用的是 data: URL 本地页面）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whu_paper_fetcher.browser import PlaywrightBackend


def test_playwright_launch_and_goto():
    b = PlaywrightBackend("chromium")
    try:
        b.open("data:text/html,<h1 id=x>hi</h1>")
        title = b.eval_js("document.getElementById('x').textContent")
        assert title == "hi", repr(title)
        # CDP 通道可用（ARP 拦截 / PDF 渲染依赖）
        b.cdp("Page.bringToFront")
        print("PLAYWRIGHT_SMOKE_OK")
    finally:
        b.close()


if __name__ == "__main__":
    test_playwright_launch_and_goto()
