"""Windows WiFi 切换工具

通过 netsh 命令切换 WiFi 连接，切换后等待网络就绪。
"""

from __future__ import annotations

import asyncio
import subprocess

from utils.log import xiaohongshu_logger


def _run_netsh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["netsh"] + args,
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="replace",
    )


def get_current_wifi() -> str | None:
    """获取当前连接的 WiFi 名称，未连接返回 None。"""
    result = _run_netsh(["wlan", "show", "interfaces"])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("SSID") and "BSSID" not in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                ssid = parts[1].strip()
                if ssid:
                    return ssid
    return None


def disconnect_wifi() -> bool:
    """断开当前 WiFi 连接。"""
    result = _run_netsh(["wlan", "disconnect"])
    return result.returncode == 0


def connect_wifi(ssid: str) -> bool:
    """连接到指定 WiFi（需要已保存的配置文件）。"""
    result = _run_netsh(["wlan", "connect", f"name={ssid}"])
    return result.returncode == 0


async def switch_wifi(target_ssid: str, max_wait: int = 15) -> bool:
    """切换到目标 WiFi，返回是否成功。

    Args:
        target_ssid: 目标 WiFi 名称
        max_wait: 最大等待连接就绪的秒数
    """
    current = get_current_wifi()
    if current == target_ssid:
        xiaohongshu_logger.info(f"当前已连接 WiFi: {target_ssid}，无需切换")
        return True

    xiaohongshu_logger.info(f"正在从 [{current or '未连接'}] 切换到 WiFi: {target_ssid}")

    disconnect_wifi()
    await asyncio.sleep(1)

    if not connect_wifi(target_ssid):
        xiaohongshu_logger.error(f"WiFi 连接命令失败: {target_ssid}，请确认该网络配置文件已保存")
        return False

    # 等待连接就绪
    for i in range(max_wait):
        await asyncio.sleep(1)
        if get_current_wifi() == target_ssid:
            xiaohongshu_logger.info(f"WiFi 切换成功: {target_ssid}，等待 3 秒确保网络稳定...")
            await asyncio.sleep(3)
            return True

    xiaohongshu_logger.error(f"WiFi 切换超时（{max_wait}s）: {target_ssid}")
    return False
