"""管线逻辑端到端测试（不依赖武大账号 / 不访问真实网络）。

用 FakeBackend 模拟浏览器后端，验证：
- SD ARP 响应 -> Markdown 解析 -> 落盘命名 -> 产物存在且内容正确
"""
import os
import re
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whu_paper_fetcher.browser.base import BrowserBackend
from whu_paper_fetcher import sd_arp
from whu_paper_fetcher.config import load_config


class FakeBackend(BrowserBackend):
    """内存版浏览器后端，按 URL 模式回放预设响应，不启动任何真实浏览器。"""

    def __init__(self, arp_payload):
        self._arp = arp_payload
        self._reqs = []
        self._resp = {}
        self._opened = []

    def open(self, url, new_tab=False):
        self._opened.append(url)
        rid = len(self._reqs) + 1
        if "science/article/pii/" in url:
            content = '<html><body>{"entitledToken":"ABC123DEF456"}</body></html>'
            mt = "text/html"
        elif "/body?" in url:
            content = self._arp
            mt = "application/json"
        else:
            content = ""
            mt = "text/html"
        self._reqs.append({"requestId": rid, "url": url, "mimeType": mt, "status": 200, "_resp": None})
        self._resp[rid] = content
        return {"url": url}

    def eval_js(self, code, timeout=30):
        m = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", code)
        if m:
            self.open(m.group(1))
        return None

    def click(self, selector):
        return True

    def fill(self, selector, value):
        return True

    def network_start(self):
        self._reqs = []
        self._resp = {}

    def network_list(self):
        return self._reqs

    def network_detail(self, request_id):
        return self._resp.get(request_id, "")

    def handle_dialog(self, accept=True, prompt_text=None):
        return True

    def cdp(self, method, params=None):
        return {}

    def save_pdf(self, path, print_background=True):
        return {"path": path}

    def close(self):
        pass


SAMPLE_ARP = {
    "content": {"$$": [
        {"#name": "section", "$$": [
            {"#name": "section-title", "_": "Introduction"},
            {"#name": "para", "_": "Soil organic carbon is important for climate."},
        ]}
    ]}
}


def test_fulltext_pipeline():
    b = FakeBackend(SAMPLE_ARP)
    cfg = load_config()
    out = tempfile.mkdtemp()
    paths, err = sd_arp.fetch_fulltext(
        b, "S1234567890", cfg, out, tag="testpaper", display_name=""
    )
    assert err is None, err
    for k in ("markdown", "body", "html"):
        assert os.path.exists(paths[k]), k
    with open(paths["markdown"], encoding="utf-8") as f:
        md = f.read()
    assert "Introduction" in md, md
    assert "Soil organic carbon" in md, md
    with open(paths["body"], encoding="utf-8") as f:
        json.load(f)
    print("PIPELINE_MOCK_OK")


if __name__ == "__main__":
    test_fulltext_pipeline()
