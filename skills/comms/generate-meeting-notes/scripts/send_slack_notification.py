#!/usr/bin/env python3
"""
send_slack_notification.py - 發送會議記錄完成通知到 Slack

用法：
    python3 send_slack_notification.py \
        --channel C0XXXXXXXXX \
        --doc-url "https://docs.google.com/document/d/.../edit" \
        --drive-path "team-meetings/20260313" \
        --series-name "Data內會" \
        --date "20260313"

測試（不實際發送）：
    python3 send_slack_notification.py ... --dry-run
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

CONFIG_PATH = Path.home() / ".config" / "generate-meeting-notes" / "config.json"


def load_token() -> str:
    if not CONFIG_PATH.exists():
        print("❌ 尚未設定。請先執行 setup.py")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    token = config.get("slack_bot_token", "").strip()
    if not token:
        print("❌ config.json 中沒有 slack_bot_token，請重新執行 setup.py")
        sys.exit(1)
    return token


def format_date_display(date_str: str) -> str:
    """YYYYMMDD → YYYY/MM/DD"""
    return f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"


def build_message(series_name: str, date_str: str, doc_url: str, drive_path: str) -> str:
    display_date = format_date_display(date_str)

    try:
        meeting_date = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        yesterday = date.today() - timedelta(days=1)
        date_prefix = "昨天的" if meeting_date == yesterday else f"{display_date} 的"
    except ValueError:
        date_prefix = f"{display_date} 的"

    return (
        f"{date_prefix} {series_name} 會議紀錄整理好囉！連結在下面，再麻煩大家確認。\n\n"
        f"📄 連結： {doc_url}\n\n"
        f"📂 雲端： {drive_path}"
    )


def send_notification(channel: str, doc_url: str, drive_path: str, series_name: str, date_str: str) -> bool:
    """發送通知，回傳是否成功。失敗時印警告但不中斷程式。"""
    token = load_token()
    message = build_message(series_name, date_str, doc_url, drive_path)

    client = WebClient(token=token)
    try:
        client.chat_postMessage(channel=channel, text=message)
        print("✅ Slack 通知已發送")
        return True
    except SlackApiError as e:
        print(f"⚠️  Slack 發送失敗：{e.response['error']}")
        return False


def main():
    parser = argparse.ArgumentParser(description="發送會議記錄完成通知到 Slack")
    parser.add_argument("--channel", required=True, help="Slack Channel ID（例：C0XXXXXXXXX）")
    parser.add_argument("--doc-url", required=True, help="Google Doc 連結")
    parser.add_argument("--drive-path", required=True, help="雲端路徑")
    parser.add_argument("--series-name", required=True, help="會議系列名稱")
    parser.add_argument("--date", required=True, help="日期（YYYYMMDD）")
    parser.add_argument("--dry-run", action="store_true", help="只印出訊息預覽，不實際發送")
    args = parser.parse_args()

    message = build_message(args.series_name, args.date, args.doc_url, args.drive_path)

    if args.dry_run:
        print("─── [dry-run] 訊息預覽 ───")
        print(f"Channel: {args.channel}")
        print()
        print(message)
        print("──────────────────────────")
        return

    send_notification(args.channel, args.doc_url, args.drive_path, args.series_name, args.date)


if __name__ == "__main__":
    main()
