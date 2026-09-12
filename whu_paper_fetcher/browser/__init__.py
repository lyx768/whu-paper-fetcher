from .base import BrowserBackend
from .webbridge import WebBridgeBackend
from .playwright import PlaywrightBackend

__all__ = ["BrowserBackend", "WebBridgeBackend", "PlaywrightBackend"]


def get_backend(name, config):
    """按配置返回浏览器后端实例。name 来自 [browser].backend。"""
    b = (name or config.get("browser", "backend", default="playwright")).lower()
    if b == "webbridge":
        return WebBridgeBackend(
            config.get("browser", "webbridge_url", default="http://127.0.0.1:10086/command"),
            config.get("browser", "webbridge_session", default="whu-lib-access"),
        )
    if b == "playwright":
        return PlaywrightBackend(config.get("browser", "playwright_browser", default="chromium"))
    raise ValueError(f"未知浏览器后端: {name!r}（可选 webbridge / playwright）")
