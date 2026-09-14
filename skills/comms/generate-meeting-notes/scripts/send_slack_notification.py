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

# slack_sdk 在函式裡才 import。這支模組的斷言層（誰該被通知、誰不該）必須在 CI 與
# mutmut 那道 env 底下 import 得起來，而那兩個地方都沒有 slack_sdk —— module-level
# import 會讓那些測試變成 collection error，而 error 跟 fail 一樣是 exit 1，mutmut
# 會把每顆 mutant 都記成 killed（setup.cfg 警告的第三條靜默路徑）。

CONFIG_PATH = Path.home() / ".config" / "generate-meeting-notes" / "config.json"


def load_config() -> dict:
    """設定檔內容。讀不到就回空 dict —— 呼叫端各自決定那算不算致命。"""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load_token() -> str:
    config = load_config()
    if not config:
        # 「檔案不在」與「檔案在但不是有效 JSON」在 `load_config` 那層已經合流，
        # 所以這句不能只講前者 —— 手改壞的設定檔被說成「尚未設定」會讓人去重跑
        # setup，然後把原本只是少一個逗號的檔案整份覆蓋掉。
        print(f"❌ 讀不到設定（{CONFIG_PATH}），請確認它存在且是有效的 JSON，或重新執行 setup.py")
        sys.exit(1)
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


def _post(token: str, target: str, text: str, what: str) -> bool:
    """送一則訊息，回傳是否真的送出去了。**任何失敗都只印一行**，不拋、不 sys.exit。

    兩個呼叫端都跑在 Doc 已經建好之後。那時候拋例外等於用一個附屬品毀掉主要交棒 ——
    `RESULT_URL` 只有發佈當下拿得到。`slack_sdk` 沒裝也走這條：它在函式裡才 import，
    所以缺套件的症狀是**這一則訊息沒送出**，不是整支腳本掛掉。
    """
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        print(f"⚠️  沒有安裝 slack_sdk，{what}跳過")
        return False

    try:
        WebClient(token=token).chat_postMessage(channel=target, text=text)
        print(f"✅ {what}已送出")
        return True
    except SlackApiError as e:
        print(f"⚠️  {what}失敗：{e.response['error']}")
        return False


def send_notification(channel: str, doc_url: str, drive_path: str, series_name: str, date_str: str) -> bool:
    """發送通知，回傳是否成功。失敗時印警告但不中斷程式。"""
    return _post(
        load_token(),
        channel,
        build_message(series_name, date_str, doc_url, drive_path),
        "Slack 通知",
    )


def send_dm(text: str) -> bool:
    """把提醒 DM 給設定檔裡的 `slack_dm_user`，回傳是否真的送出去了。

    **不 sys.exit。** 這條路徑跑在 Doc 已經建好之後，用一個「提醒你去設 channel」
    把一次成功的發佈變成非零退出，只會讓人學會忽略它（同 `report_drift`）。沒 token
    或沒設 DM 對象時印一行就回 False —— 提醒本身已經印在 stdout 上，沒有跟著消失。
    """
    config = load_config()
    token = config.get("slack_bot_token", "").strip()
    user = (config.get("slack_dm_user") or "").strip()
    if not token or not user:
        print("⚠️  沒有 slack_bot_token 或 slack_dm_user，提醒只留在上面這段輸出裡")
        return False

    return _post(token, user, text, "提醒 DM")


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
