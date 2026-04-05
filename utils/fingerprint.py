"""浏览器指纹随机化工具

每次浏览器会话调用 generate_fingerprint() 生成一组随机但内部一致的指纹参数，
配合 get_launch_args() 和 get_context_options() 应用到 chromium.launch / browser.new_context。
"""

from __future__ import annotations

import random
from typing import Any


# ---------- 随机池 ----------

VIEWPORTS: list[dict[str, int]] = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
    {"width": 1600, "height": 900},
    {"width": 1680, "height": 1050},
    {"width": 2560, "height": 1440},
]

USER_AGENTS: list[str] = [
    # Windows 10 / Chrome 120-126
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # macOS / Chrome 120-126
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

DEVICE_SCALE_FACTORS: list[float] = [1.0, 1.25, 1.5]

COLOR_SCHEMES: list[str] = ["light", "dark"]

TIMEZONES: list[str] = ["Asia/Shanghai", "Asia/Chongqing", "Asia/Harbin", "Asia/Urumqi"]

ANTI_DETECTION_ARGS: list[str] = [
    "--disable-blink-features=AutomationControlled",
    "--lang=zh-CN",
    "--disable-infobars",
    "--no-sandbox",
]


# ---------- 公开函数 ----------

def generate_fingerprint() -> dict[str, Any]:
    """生成一组随机浏览器指纹参数，每次浏览器会话调用一次。"""
    return {
        "viewport": random.choice(VIEWPORTS),
        "user_agent": random.choice(USER_AGENTS),
        "locale": "zh-CN",
        "timezone_id": random.choice(TIMEZONES),
        "device_scale_factor": random.choice(DEVICE_SCALE_FACTORS),
        "color_scheme": random.choice(COLOR_SCHEMES),
    }


def get_launch_args(extra_args: list[str] | None = None) -> list[str]:
    """返回 chromium 反检测启动参数列表。"""
    args = list(ANTI_DETECTION_ARGS)
    if extra_args:
        args.extend(extra_args)
    return args


def get_context_options(
    fingerprint: dict[str, Any],
    *,
    storage_state: str | None = None,
    permissions: list[str] | None = None,
) -> dict[str, Any]:
    """将指纹参数组装为 browser.new_context(**options) 的 kwargs。"""
    options: dict[str, Any] = {
        "viewport": fingerprint["viewport"],
        "user_agent": fingerprint["user_agent"],
        "locale": fingerprint["locale"],
        "timezone_id": fingerprint["timezone_id"],
        "device_scale_factor": fingerprint["device_scale_factor"],
        "color_scheme": fingerprint["color_scheme"],
    }
    if storage_state:
        options["storage_state"] = storage_state
    if permissions:
        options["permissions"] = permissions
    return options
