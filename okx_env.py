# -*- coding: utf-8 -*-
"""OKX 凭证环境加载模块 — 从 .env 文件或环境变量读取，不硬编码。

用法:
    from okx_env import get_okx_env, OKX_API_KEY, OKX_SECRET, OKX_PASSPHRASE

优先级: 系统环境变量 > .env 文件 > 空字符串
.env 文件格式:
    OKX_API_KEY=xxx
    OKX_SECRET_KEY=xxx
    OKX_PASSPHRASE=xxx
"""
import os
from pathlib import Path


def _load_envfile():
    """从同目录下的 .env 文件加载环境变量（不覆盖已存在的）。"""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_envfile()

OKX_API_KEY = os.environ.get("OKX_API_KEY", "")
OKX_SECRET = os.environ.get("OKX_SECRET_KEY", "")
OKX_PASSPHRASE = os.environ.get("OKX_PASSPHRASE", "")


def get_okx_env():
    """返回包含 OKX 凭证的环境变量副本（供 subprocess 使用）。"""
    env = os.environ.copy()
    env.update({
        "OKX_API_KEY": OKX_API_KEY,
        "OKX_SECRET_KEY": OKX_SECRET,
        "OKX_PASSPHRASE": OKX_PASSPHRASE,
    })
    return env
