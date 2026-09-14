#!/usr/bin/env python3
"""
channel.py - `slack_channel` 的三態，以及把答案寫回設定檔的 CLI。

設定檔裡這個欄位有三種狀態，不是兩種：

    key 不存在／null   還沒設定 —— 記錄照產，DM 提醒我去問那個部門的 channel ID
    ""                 刻意不發通知 —— 記錄照產，安靜
    "C0XXXXXXXXX"      正常 —— 發那個 channel

壓成一個 falsy 的話「還沒設定」與「刻意不發」分不出來，而排程跑起來之後沒有人在看
stdout，那行 `⚠️ 未設定` 等於靜靜地不通知（#26）。`null` 還會在 `.strip()` 那裡直接
拋 `AttributeError`。

**不擋流程。** 三態判斷回哨符，呼叫端自己分支；記錄的價值不依賴 channel，擋下來只會
讓音檔堆積。

答案用 `python3 channel.py --meeting <key> --channel <id>` 寫回，不做 Slack 互動元件：
下拉選單要 interactivity endpoint、回覆監聽要 Socket Mode，兩個都是為了一年幾次的操作
養一個常駐服務。設定檔是非版控的手改檔，寫入前先備份。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "generate-meeting-notes" / "config.json"
BACKUP_SUFFIX = ".bak"

# 三態的哨符。字串而非 enum：它們會被印進 stdout 的除錯訊息，也會被測試逐字斷言。
UNSET = "unset"
MUTED = "muted"
SEND = "send"

# DM 提醒的第一行。發佈流程的輸出是交棒契約的一部分，這個字串會被斷言
# （同 `parity.DRIFT_HEADER`）。
DM_HEADER = "📮 這場會議還沒設定 Slack channel，所以沒有通知任何人"


def channel_state(meeting: dict) -> str:
    """一個會議設定 → 三態哨符。

    `meeting.get("slack_channel")` 回 `None` 有兩個來源：key 不存在、值是 `null`。
    兩者是同一件事（還沒設定），所以這裡不分 —— 分了呼叫端也只會合回去。
    """
    channel = meeting.get("slack_channel")
    if channel is None:
        return UNSET
    return SEND if channel.strip() else MUTED


def dm_reminder(
    meeting_key: str,
    series_name: str,
    doc_url: str,
    note_path: Path | str | None = None,
) -> str:
    """「還沒設定」時要 DM 給我的那段字。

    三樣東西缺一不可：Doc URL（這次的成品，DM 進來時要點得開）、本機路徑（Doc 之外
    的那份，事後要改要比對都在這裡）、以及拿到 ID 之後要跑的**那一行**指令 —— 少了
    它，收到提醒的人還得回頭翻文件才知道怎麼寫回去，而這是一年幾次的操作，沒有人
    記得住。

    `note_path` 是 `None`（本機歸檔失敗）時那行缺席，不印 `None`：寫 `None` 會讓讀的
    人以為那是一個可以去打開的路徑。
    """
    lines = [
        f"{DM_HEADER}：{series_name}（{meeting_key}）",
        f"📄 {doc_url}",
    ]
    if note_path:
        lines.append(f"🗄️  {note_path}")
    lines += [
        "請去問該部門的 Channel ID，拿到之後跑：",
        f"   python3 {Path(__file__).resolve()} --meeting {meeting_key} --channel C0XXXXXXXXX",
        '   （刻意不發通知就填空字串：--channel ""）',
    ]
    return "\n".join(lines)


def set_channel(meeting_key: str, channel: str, config_path: Path = CONFIG_PATH) -> Path:
    """把 channel 寫回設定檔，回傳備份路徑。

    備份先於寫入，而且是**原檔的位元組**照抄 —— 不是把讀進來的 dict 再 dump 一次。
    dump 一次的話，設定檔裡手改的排版與這支腳本不認得的欄位會在備份裡就已經消失，
    那份備份也就救不回它本來要救的東西。

    會議類型不存在時 raise `KeyError`：新增會議類型是 `setup.py` 的事，在這裡順手
    建一個空 entry 只會讓打錯的 key 靜靜長出一個永遠不會被用到的設定。
    """
    raw = config_path.read_text(encoding="utf-8")
    config = json.loads(raw)
    meetings = config.get("meetings", {})
    if meeting_key not in meetings:
        raise KeyError(meeting_key)

    backup_path = config_path.with_name(config_path.name + BACKUP_SUFFIX)
    backup_path.write_text(raw, encoding="utf-8")

    meetings[meeting_key]["slack_channel"] = channel
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="把 Slack Channel ID 寫回設定檔")
    parser.add_argument("--meeting", required=True, help="會議類型 key（例：team週會）")
    parser.add_argument(
        "--channel",
        required=True,
        help='Slack Channel ID（例：C0XXXXXXXXX）；空字串 = 刻意不發通知',
    )
    args = parser.parse_args()

    # `CONFIG_PATH` 在呼叫當下才取，不吃 `set_channel` 的預設參數 —— 預設參數在 import
    # 當下就綁死了，於是這條路徑只能對著使用者真實的設定檔跑：測 CLI 等於拿自己的
    # config.json 當測試資料，key 剛好撞上就直接覆寫掉它。
    try:
        backup = set_channel(args.meeting, args.channel, CONFIG_PATH)
    except KeyError:
        print(f"❌ 設定檔裡沒有這個會議類型：{args.meeting!r}")
        sys.exit(1)
    except (OSError, ValueError) as exc:
        print(f"❌ 寫入失敗：{type(exc).__name__}: {exc}")
        sys.exit(1)

    state = channel_state({"slack_channel": args.channel})
    print(f"✅ {args.meeting} 的 slack_channel 已寫入（{state}）")
    print(f"🗄️  備份：{backup}")


if __name__ == "__main__":
    main()
