"""配置加载：config.toml + 环境变量 + 本地 creds 文件。

设计原则：代码内部不写死任何个人信息（学号、姓名、下载目录、密钥路径）。
所有可变项都从配置文件读取，配置默认值不含真实数据。
"""
import os
import json

try:
    import tomllib

    def _load_toml(path):
        with open(path, "rb") as f:
            return tomllib.load(f)
except ModuleNotFoundError:  # Python 3.10
    import toml

    def _load_toml(path):
        with open(path, "r", encoding="utf-8") as f:
            return toml.load(f)


DEFAULTS = {
    "whu": {
        "username": "",
        "display_name": "",
        "metaersp": "https://whu.metaersp.cn/",
        "ersp_sd": "https://ersp.lib.whu.edu.cn/s/com/sciencedirect/www/G.https",
    },
    "download": {
        "output_dir": "~/Downloads/whu-papers",
        "verify": True,
    },
    "browser": {
        "backend": "playwright",
        "playwright_browser": "chromium",
        "webbridge_url": "http://127.0.0.1:10086/command",
        "webbridge_session": "whu-lib-access",
    },
    "oa": {
        "email": "",
        "skip_oa": False,
    },
    "creds": {
        "path": "~/.config/whu-paper-fetcher/creds.json",
    },
}


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _config_candidates():
    env = os.environ.get("WHU_PF_CONFIG")
    cands = []
    if env:
        cands.append(env)
    cands.append(os.path.expanduser("~/.config/whu-paper-fetcher/config.toml"))
    cands.append(os.path.join(os.getcwd(), "config.toml"))
    return cands


class Config:
    def __init__(self, data):
        self._d = data

    def get(self, *keys, default=None):
        cur = self._d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    @property
    def whu(self):
        return self._d.get("whu", {})

    @property
    def download(self):
        return self._d.get("download", {})

    @property
    def browser(self):
        return self._d.get("browser", {})

    @property
    def oa(self):
        return self._d.get("oa", {})

    @property
    def creds(self):
        return self._d.get("creds", {})


def load_config():
    data = DEFAULTS
    for p in _config_candidates():
        if p and os.path.exists(p):
            try:
                data = _deep_merge(DEFAULTS, _load_toml(p))
            except Exception:
                pass
            break
    return Config(data)


def load_creds(config: Config):
    """读取本地 creds 文件（gitignore 屏蔽，绝不进仓库）。返回 {username,password}。"""
    path = os.path.expanduser(config.get("creds", "path",
                                         default="~/.config/whu-paper-fetcher/creds.json"))
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
