#!/usr/bin/env python3
"""
create_gdoc_from_md.py - 將 Markdown 會議記錄寫入 Google Doc + Shared Drive + Slack

此腳本是 Main Synthesis 的發佈層：
  main agent 讀 source artifacts + 歷史 context → 生成 meeting_notes.md → 此腳本建 Doc + 發通知

用法：
    # 從檔案讀取 markdown
    uv run scripts/create_gdoc_from_md.py \\
        --meeting team週會 \\
        --date 20260514 \\
        --content-file /tmp/meeting_notes.md

    # 同時上傳 source artifacts
    uv run scripts/create_gdoc_from_md.py \\
        --meeting team週會 \\
        --date 20260514 \\
        --content-file /tmp/meeting_notes.md \\
        --source-dir /tmp/meeting_sources/team週會_20260514

    # 從 stdin 讀取 markdown
    echo "# 會議記錄..." | uv run scripts/create_gdoc_from_md.py \\
        --meeting team週會 \\
        --date 20260514

    # dry-run（只建 Doc，不發 Slack）
    uv run scripts/create_gdoc_from_md.py \\
        --meeting team週會 --date 20260514 \\
        --content-file /tmp/notes.md --no-slack

    # 同一天同會議類型的第二場，使用 title suffix 避免 Doc 名稱混淆
    uv run scripts/create_gdoc_from_md.py \\
        --meeting team週會 --date 20260514 \\
        --content-file /tmp/meeting_notes_team週會_20260514_pm.md \\
        --title-suffix pm

    # 原始音訊一併歸檔到 Drive，驗證大小相符後刪本機檔
    uv run scripts/create_gdoc_from_md.py \\
        --meeting team週會 --date 20260514 \\
        --content-file /tmp/meeting_notes.md \\
        --source-dir /tmp/meeting_sources/team週會_20260514 \\
        --audio-file ~/Downloads/team_meeting_20260514.m4a \\
        --delete-local-audio
"""

import argparse
import mimetypes
import re
import sys
from pathlib import Path

# 從同目錄的 extract_audio_sources.py import 可重用函式
sys.path.insert(0, str(Path(__file__).parent))
from extract_audio_sources import (
    create_gdoc_in_shared_drive,
    get_google_credentials,
    inject_attendees,
    load_config,
)


def extract_date_from_str(s: str) -> str:
    """
    從字串提取 YYYYMMDD。
    支援：
      - 連續 8 位數：20260514
      - 含日期的逐字稿檔名：2026-05-14 11_03_01-transcript.txt → 20260514
    """
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    m = re.search(r"\d{8}", s)
    if m:
        return m.group(0)
    raise ValueError(f"無法從字串提取日期：{s!r}")


def collect_source_files(source_files: list[str], source_dir: str | None) -> list[Path]:
    paths: list[Path] = []
    for raw_path in source_files:
        path = Path(raw_path).expanduser()
        if not path.exists():
            print(f"⚠️  source file 不存在，略過：{path}")
            continue
        if path.is_file():
            paths.append(path)

    if source_dir:
        directory = Path(source_dir).expanduser()
        if not directory.exists() or not directory.is_dir():
            print(f"⚠️  source dir 不存在或不是資料夾，略過：{directory}")
        else:
            for path in sorted(directory.iterdir()):
                if path.is_file() and path.name in {"transcript.md", "extract.md", "meeting-context.md"}:
                    paths.append(path)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            deduped.append(resolved)
            seen.add(resolved)
    return deduped


def upload_audio_file(audio_path: Path, folder_id: str, delete_local: bool) -> tuple[str, bool]:
    """把原始音訊上傳到 Drive 日期資料夾。回傳 (file_id, 本機是否已刪除)。

    只有在 Drive 端回報的位元數與本機完全相同時才刪本機檔——上傳沒驗證過就不刪。
    音訊動輒上百 MB，用 resumable 分塊上傳。
    """
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    local_size = audio_path.stat().st_size
    drive = build("drive", "v3", credentials=get_google_credentials())

    # 重跑時常見：同名同大小的檔已在該資料夾 → 不重傳，避免產生重複檔
    escaped = audio_path.name.replace("\\", "\\\\").replace("'", "\\'")
    existing = drive.files().list(
        q=f"name = '{escaped}' and '{folder_id}' in parents and trashed = false",
        fields="files(id,size)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute().get("files", [])
    hit = next((f for f in existing if str(f.get("size")) == str(local_size)), None)

    if hit:
        file_id = hit["id"]
        print(f"\n🎧 音訊已在 Drive 且大小相符，跳過上傳：{audio_path.name}")
    else:
        mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/mp4"
        media = MediaFileUpload(
            str(audio_path), mimetype=mime_type, resumable=True, chunksize=8 * 1024 * 1024
        )
        request = drive.files().create(
            body={"name": audio_path.name, "parents": [folder_id]},
            media_body=media,
            supportsAllDrives=True,
            fields="id",
        )
        print(f"\n🎧 上傳原始音訊 {audio_path.name}（{local_size / 1024 / 1024:.1f} MB）...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"\r   {status.progress() * 100:5.1f}%", end="", flush=True)
        print("\r   100.0% ✓")
        file_id = response["id"]

    # 不信任上傳回應，另外向 Drive 問一次實際大小
    remote_size = drive.files().get(
        fileId=file_id, fields="size", supportsAllDrives=True
    ).execute().get("size")

    if str(remote_size) != str(local_size):
        print(f"⚠️  大小不符（本機 {local_size} / Drive {remote_size}），保留本機檔案不刪除")
        return file_id, False

    if not delete_local:
        print(f"   已驗證大小相符（{local_size} bytes）；未指定 --delete-local-audio，保留本機檔案")
        return file_id, False

    audio_path.unlink()
    print(f"🗑️  已刪除本機音訊：{audio_path}")
    return file_id, True


def upload_source_files(source_files: list[Path], folder_id: str) -> list[tuple[Path, str]]:
    if not source_files:
        return []

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = get_google_credentials()
    drive = build("drive", "v3", credentials=creds)
    uploaded: list[tuple[Path, str]] = []

    print(f"\n📎 上傳 {len(source_files)} 個 source artifact...")
    for path in source_files:
        mime_type = mimetypes.guess_type(path.name)[0] or "text/markdown"
        media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)
        created = drive.files().create(
            body={"name": path.name, "parents": [folder_id]},
            media_body=media,
            supportsAllDrives=True,
            fields="id",
        ).execute()
        uploaded.append((path, created["id"]))
        print(f"   {path.name} ✓")
    return uploaded


def main():
    parser = argparse.ArgumentParser(
        description="將 Claude 生成的 Markdown 會議記錄寫入 Google Doc + Slack"
    )
    parser.add_argument("--meeting", required=True, help="會議類型 key（例：team週會、pm會議）")
    parser.add_argument("--date", help="日期 YYYYMMDD（省略時從 --content-file 檔名推斷）")
    parser.add_argument("--content-file", help="Markdown 內容檔案路徑（省略時從 stdin 讀取）")
    parser.add_argument("--source-file", action="append", default=[], help="要一起上傳到 Drive 日期資料夾的 source artifact，可重複指定")
    parser.add_argument("--source-dir", help="包含 transcript.md、extract.md、meeting-context.md 的 source artifact 資料夾")
    parser.add_argument("--title-suffix", help="同日同會議類型多場次時附加到 Google Doc 名稱的短識別碼")
    parser.add_argument("--audio-file", help="原始音訊檔路徑，一併上傳到 Drive 日期資料夾")
    parser.add_argument("--delete-local-audio", action="store_true",
                        help="上傳並驗證 Drive 端大小與本機相符後，刪除本機音訊檔（需搭配 --audio-file）")
    parser.add_argument("--no-slack", action="store_true", help="跳過 Slack 通知")
    args = parser.parse_args()

    # 讀取 markdown 內容
    if args.content_file:
        content_path = Path(args.content_file).expanduser()
        if not content_path.exists():
            print(f"❌ 找不到內容檔案：{content_path}")
            sys.exit(1)
        content = content_path.read_text(encoding="utf-8")
        # 從檔名推斷日期（若未指定 --date）
        if not args.date:
            try:
                args.date = extract_date_from_str(content_path.name)
            except ValueError:
                pass
    else:
        if sys.stdin.isatty():
            print("❌ 請提供 --content-file 或從 stdin 輸入 Markdown 內容")
            sys.exit(1)
        content = sys.stdin.read()

    if not args.date:
        print("❌ 無法推斷日期，請用 --date YYYYMMDD 指定")
        sys.exit(1)

    # 驗證日期格式
    if not re.fullmatch(r"\d{8}", args.date):
        try:
            args.date = extract_date_from_str(args.date)
        except ValueError:
            print(f"❌ 日期格式錯誤：{args.date!r}，請用 YYYYMMDD 格式")
            sys.exit(1)

    # 載入 config
    config = load_config()
    meetings = config.get("meetings", {})
    if args.meeting not in meetings:
        available = ", ".join(meetings.keys())
        print(f"❌ 找不到會議類型：{args.meeting!r}")
        print(f"   可用：{available}")
        sys.exit(1)

    meeting = meetings[args.meeting]
    date_str = args.date
    series_name = meeting["series_name"]
    folder_name = meeting.get("folder_name", series_name)

    print(f"\n📅 日期：{date_str}")
    print(f"📋 會議類型：{args.meeting}（{series_name}）")
    print(f"📝 內容長度：{len(content)} 字元")

    # 注入與會者（若內容尚未包含）
    attendees = meeting.get("attendees", [])
    content = inject_attendees(content, attendees)

    # 建立 Google Doc + 移至 Shared Drive
    doc_url, subfolder_id = create_gdoc_in_shared_drive(
        date_str,
        content,
        meeting,
        title_suffix=args.title_suffix,
        return_folder_id=True,
    )

    source_files = collect_source_files(args.source_file, args.source_dir)
    uploaded_sources = upload_source_files(source_files, subfolder_id)

    audio_file_id: str | None = None
    audio_deleted = False
    if args.audio_file:
        audio_path = Path(args.audio_file).expanduser()
        if not audio_path.is_file():
            print(f"⚠️  音訊檔不存在，略過：{audio_path}")
        else:
            audio_file_id, audio_deleted = upload_audio_file(
                audio_path, subfolder_id, args.delete_local_audio
            )
    elif args.delete_local_audio:
        print("⚠️  指定了 --delete-local-audio 但沒有 --audio-file，不做任何事")

    drive_path = f"{folder_name}/{date_str}"
    print(f"\nRESULT_URL: {doc_url}")
    print(f"RESULT_DRIVE_PATH: {drive_path}")
    print(f"RESULT_SERIES_NAME: {series_name}")
    print(f"RESULT_DATE: {date_str}")
    if uploaded_sources:
        print("RESULT_SOURCE_FILES:")
        for source_path, file_id in uploaded_sources:
            print(f"  {source_path.name}: {file_id}")
    if audio_file_id:
        print(f"RESULT_AUDIO_FILE: {audio_file_id}")
        print(f"RESULT_LOCAL_AUDIO: {'deleted' if audio_deleted else 'kept'}")

    # Slack 通知
    if not args.no_slack:
        slack_channel = meeting.get("slack_channel", "").strip()
        if slack_channel:
            from send_slack_notification import send_notification
            send_notification(slack_channel, doc_url, drive_path, series_name, date_str)
        else:
            print(f"⚠️  未設定 slack_channel，跳過通知")

    print("\n✅ 完成")


if __name__ == "__main__":
    main()
