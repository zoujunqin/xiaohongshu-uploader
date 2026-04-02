"""
清理小红书发布记录：删除配置文件中不存在的账号的数据库记录。

读取 multiple_account_config.json 中所有 xiaohongshu_account，
将数据库 xiaohongshu_publish_log 表中不在配置里的账号记录全部删除。
"""

import json
import sqlite3
from pathlib import Path

from conf import BASE_DIR

CONFIG_PATH = Path.home() / "Desktop" / "douyin-downloader" / "multiple_account_config.json"
DB_PATH = Path(BASE_DIR) / "db" / "database.db"


def main():
    if not CONFIG_PATH.exists():
        print(f"配置文件不存在: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        accounts_cfg = json.load(f)

    valid_accounts = set()
    for cfg in accounts_cfg:
        raw = cfg.get("xiaohongshu_account", [])
        if isinstance(raw, str):
            if raw:
                valid_accounts.add(raw)
        else:
            valid_accounts.update(a for a in raw if a)

    if not valid_accounts:
        print("配置文件中没有任何 xiaohongshu_account，将清除所有记录")

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # 查询数据库中所有不同的账号
    cursor.execute("SELECT DISTINCT account FROM xiaohongshu_publish_log")
    db_accounts = {row[0] for row in cursor.fetchall()}

    accounts_to_delete = db_accounts - valid_accounts

    if not accounts_to_delete:
        print("没有需要清理的账号记录")
        conn.close()
        return

    print(f"配置中的账号: {valid_accounts}")
    print(f"数据库中的账号: {db_accounts}")
    print(f"将要删除的账号: {accounts_to_delete}")

    placeholders = ",".join("?" for _ in accounts_to_delete)
    cursor.execute(
        f"DELETE FROM xiaohongshu_publish_log WHERE account IN ({placeholders})",
        list(accounts_to_delete),
    )
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"已删除 {deleted_count} 条记录（账号: {accounts_to_delete}）")


if __name__ == "__main__":
    main()
