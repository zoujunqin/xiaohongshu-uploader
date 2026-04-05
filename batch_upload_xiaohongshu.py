"""
小红书多账号批量定时发布视频脚本

从 multiple_account_config.json 读取多账号配置，
遍历每个账号的 xiaohongshu_video_upload_dir_path 目录，
按视频文件创建日期从早到晚排序，依次定时发布。

视频文件名约定：
    前缀_标题_[标签1][标签2].mp4
    - 标题：按 _ 分割后取第二段
    - 标签：提取所有 [] 中的内容

发布规则：
    - 默认定时发布，一次发布 days_per_time 天
    - 每天最多发布 count_per_day 条（上限 2）
    - 定时时间在 10:00~22:00 之间随机生成
    - 同一天两条发布时间间隔不少于 4 小时
    - 已发布的视频记录到 SQLite，下次运行自动跳过
"""

import asyncio
import json
import os
import random
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from conf import BASE_DIR
from uploader.xiaohongshu_uploader.main import (
    XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
    XiaoHongShuVideo,
    xiaohongshu_setup,
)
from utils.log import xiaohongshu_logger
from utils.wifi_switch import switch_wifi

# ---------- 配置 ----------
CONFIG_PATH = Path.home() / "Desktop" / "douyin-downloader" / "multiple_account_config.json"
DB_PATH = Path(BASE_DIR) / "db" / "database.db"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv"}
SCHEDULE_HOUR_MIN = 10   # 定时发布最早时刻（含）
SCHEDULE_HOUR_MAX = 22   # 定时发布最晚时刻（含）
MIN_GAP_HOURS = 4        # 同一天两条之间的最小间隔（小时）
DEFAULT_DAYS_PER_TIME = 3   # 默认一次发布天数
MAX_DAYS_PER_TIME = 3       # 一次发布天数上限


# ---------- 数据库 ----------
def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xiaohongshu_publish_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT NOT NULL,
            video_path TEXT NOT NULL,
            title TEXT,
            publish_time TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account, video_path)
        )
    """)
    conn.commit()
    conn.close()


def is_video_published(account: str, video_path: str) -> bool:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM xiaohongshu_publish_log WHERE account = ? AND video_path = ?",
        (account, video_path),
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def get_published_count_by_date(account: str, date_str: str) -> int:
    """查询某账号在某天（格式 YYYY-MM-DD）已定时发布的视频数量"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM xiaohongshu_publish_log WHERE account = ? AND publish_time LIKE ?",
        (account, f"{date_str}%"),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_last_publish_date(account: str) -> str | None:
    """查询某账号最后一条发布记录的定时日期（YYYY-MM-DD），无记录返回 None"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT publish_time FROM xiaohongshu_publish_log WHERE account = ? ORDER BY publish_time DESC LIMIT 1",
        (account,),
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0][:10]  # 取 YYYY-MM-DD 部分
    return None


def record_published_video(account: str, video_path: str, title: str, publish_time: str):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO xiaohongshu_publish_log (account, video_path, title, publish_time) VALUES (?, ?, ?, ?)",
        (account, video_path, title, publish_time),
    )
    conn.commit()
    conn.close()


# ---------- 视频文件解析 ----------
def get_video_files(dir_path: str) -> list[Path]:
    """获取目录下所有视频文件，按创建日期从早到晚排序"""
    folder = Path(dir_path)
    if not folder.exists():
        xiaohongshu_logger.warning(f"视频目录不存在: {dir_path}")
        return []

    videos = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
    videos.sort(key=lambda f: f.stat().st_ctime)
    return videos


def parse_title(filename: str) -> str:
    """从文件名按 _ 分割后取第二段作为标题"""
    stem = Path(filename).stem
    # 去掉 [] 标签部分再分割
    clean = re.sub(r"\[.*?\]", "", stem).strip()
    parts = clean.split("_")
    if len(parts) >= 2:
        return parts[1].strip()
    return clean.strip()


def parse_tags(filename: str) -> list[str]:
    """从文件名中提取所有 [] 内的内容作为标签"""
    stem = Path(filename).stem
    return re.findall(r"\[(.+?)\]", stem)


# ---------- 定时时间计算 ----------
def _random_time_in_range(day: datetime) -> datetime:
    """在 day 当天 SCHEDULE_HOUR_MIN:00 ~ SCHEDULE_HOUR_MAX:00 之间生成随机时间"""
    hour = random.randint(SCHEDULE_HOUR_MIN, SCHEDULE_HOUR_MAX)
    minute = random.randint(0, 59)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _generate_random_times_for_day(day: datetime, count: int) -> list[datetime]:
    """
    为某一天生成 count 个随机发布时间（10:00~22:00），
    若 count >= 2，保证任意两个时间间隔 >= MIN_GAP_HOURS 小时。
    """
    if count <= 0:
        return []
    if count == 1:
        return [_random_time_in_range(day)]

    # count == 2：生成两个间隔 >= MIN_GAP_HOURS 的随机时间
    for _ in range(100):
        t1 = _random_time_in_range(day)
        t2 = _random_time_in_range(day)
        if abs((t1 - t2).total_seconds()) >= MIN_GAP_HOURS * 3600:
            return sorted([t1, t2])

    # 保底：固定间隔
    t1 = day.replace(hour=SCHEDULE_HOUR_MIN, minute=random.randint(0, 59), second=0, microsecond=0)
    t2 = day.replace(hour=SCHEDULE_HOUR_MIN + MIN_GAP_HOURS, minute=random.randint(0, 59), second=0, microsecond=0)
    return sorted([t1, t2])


def build_schedule_times(account: str, count_per_day: int, days_per_time: int) -> list[datetime]:
    """
    生成定时发布时间列表。
    以数据库中最后一条定时发布记录的日期 +1 天为起始日，
    如果没有发布记录则从明天开始。
    会查询数据库中每天已发布的数量，只补充剩余的时间槽。
    每天最多 2 条，时间在 10:00~22:00 随机，间隔 >= 4 小时。
    """
    count_per_day = min(count_per_day, 2)

    schedule = []
    last_date_str = get_last_publish_date(account)
    if last_date_str:
        base_date = datetime.strptime(last_date_str, "%Y-%m-%d") + timedelta(days=1)
    else:
        base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    for day_offset in range(days_per_time):
        day = base_date + timedelta(days=day_offset)
        date_str = day.strftime("%Y-%m-%d")
        already_published = get_published_count_by_date(account, date_str)
        remaining = count_per_day - already_published
        if remaining <= 0:
            xiaohongshu_logger.info(f"{date_str} 已发布 {already_published} 条，已达上限 {count_per_day}，跳过")
            continue
        # 生成当天剩余的随机时间槽
        random_times = _generate_random_times_for_day(day, remaining)
        schedule.extend(random_times)

    return schedule


# ---------- 主流程 ----------
async def process_single_account(account: str, video_dir: str, count_per_day: int, days_per_time: int):
    """处理单个小红书账号的发布任务"""
    account_file = str(Path(BASE_DIR) / "cookies" / "xiaohongshu_uploader" / f"{account}.json")

    # 检测 cookie 文件是否存在，不存在则触发扫码登录
    if not os.path.exists(account_file):
        xiaohongshu_logger.info(f"账号 {account}: cookie 文件不存在，开始登录...")
        login_ok = await xiaohongshu_setup(account_file, handle=True, headless=False)
        if not login_ok:
            xiaohongshu_logger.error(f"账号 {account} 登录失败，跳过该账号")
            return
        xiaohongshu_logger.info(f"账号 {account}: 登录成功，等待 10 秒后开始发布...")
        await asyncio.sleep(10)
    else:
        xiaohongshu_logger.info(f"账号 {account}: cookie 文件已存在，跳过登录检测")

    videos = get_video_files(video_dir)
    if not videos:
        xiaohongshu_logger.info(f"账号 {account} 的视频目录为空或不存在: {video_dir}")
        return

    # 过滤已发布的视频
    pending_videos = [v for v in videos if not is_video_published(account, str(v))]
    if not pending_videos:
        xiaohongshu_logger.info(f"账号 {account} 所有视频均已发布，无需操作")
        return

    # 生成定时时间
    schedule_times = build_schedule_times(account, count_per_day, days_per_time)
    upload_count = min(len(pending_videos), len(schedule_times))

    xiaohongshu_logger.info(
        f"账号 {account}: 待发布 {len(pending_videos)} 个视频，"
        f"本次将定时发布 {upload_count} 个"
    )

    for i in range(upload_count):
        video_path = pending_videos[i]
        publish_time = schedule_times[i]
        title = parse_title(video_path.name)
        tags = parse_tags(video_path.name)
        thumbnail_path = video_path.with_suffix(".png")

        xiaohongshu_logger.info(
            f"[{i + 1}/{upload_count}] 视频: {video_path.name} | "
            f"标题: {title} | 标签: {tags} | "
            f"定时: {publish_time.strftime('%Y-%m-%d %H:%M')}"
        )

        try:
            app = XiaoHongShuVideo(
                title=title,
                file_path=str(video_path),
                tags=tags,
                publish_strategy=XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
                publish_date=publish_time,
                account_file=account_file,
                thumbnail_path=str(thumbnail_path) if thumbnail_path.exists() else None,
                desc=title
            )
            # 走和 CLI 完全一致的完整上传流程
            await app.main()

            record_published_video(
                account=account,
                video_path=str(video_path),
                title=title,
                publish_time=publish_time.strftime("%Y-%m-%d %H:%M"),
            )
            xiaohongshu_logger.success(
                f"视频发布成功并已记录: {video_path.name} -> {publish_time.strftime('%Y-%m-%d %H:%M')}"
            )
        except Exception as e:
            xiaohongshu_logger.error(f"视频发布失败: {video_path.name}, 错误: {e}")
            break  # 遇到错误停止当前账号后续发布，避免浪费时间槽

        # 每个视频发布之间间隔 5 秒，避免操作过快
        if i < upload_count - 1:
            xiaohongshu_logger.info("等待 5 秒后继续发布下一个视频...")
            await asyncio.sleep(5)


async def process_account(account_cfg: dict):
    """处理一条配置，xiaohongshu_account 支持字符串或数组"""
    video_dir = account_cfg.get("xiaohongshu_video_upload_dir_path", "")
    count_per_day = min(account_cfg.get("count_per_day", 1), 2)
    days_per_time = min(account_cfg.get("days_per_time", DEFAULT_DAYS_PER_TIME), MAX_DAYS_PER_TIME)
    wifi_match = account_cfg.get("wifi_match", False)
    wifis = account_cfg.get("wifis", [])

    raw_accounts = account_cfg.get("xiaohongshu_account", [])
    # 兼容字符串和数组两种格式
    if isinstance(raw_accounts, str):
        accounts = [raw_accounts]
    else:
        accounts = list(raw_accounts)

    if not accounts or not video_dir:
        xiaohongshu_logger.warning(f"跳过无效配置: accounts={accounts}, video_dir={video_dir}")
        return

    for idx, account in enumerate(accounts):
        if not account:
            continue

        # 切换 WiFi：wifi_match 开启时按下标一一对应，无对应 WiFi 则跳过
        if wifi_match:
            if idx >= len(wifis) or not wifis[idx]:
                xiaohongshu_logger.warning(f"账号 {account}（下标 {idx}）没有对应的 WiFi 配置，跳过该账号")
                continue
            target_wifi = wifis[idx]
            xiaohongshu_logger.info(f"账号 {account} 对应 WiFi: {target_wifi}")
            if not await switch_wifi(target_wifi):
                xiaohongshu_logger.error(f"WiFi 切换失败，跳过账号: {account}")
                continue

        xiaohongshu_logger.info(f"---------- 处理账号: {account} ----------")
        await process_single_account(account, video_dir, count_per_day, days_per_time)
        # 账号之间间隔 5 秒
        if idx < len(accounts) - 1:
            xiaohongshu_logger.info("等待 5 秒后切换到下一个账号...")
            await asyncio.sleep(5)


async def main():
    if not CONFIG_PATH.exists():
        xiaohongshu_logger.error(f"配置文件不存在: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        accounts = json.load(f)

    init_db()

    for account_cfg in accounts:
        if not account_cfg.get("xiaohongshu_account"):
            continue
        xiaohongshu_logger.info(f"========== 开始处理配置组: {account_cfg['xiaohongshu_account']} ==========")
        await process_account(account_cfg)

    xiaohongshu_logger.info("========== 所有账号处理完毕 ==========")


if __name__ == "__main__":
    asyncio.run(main())
