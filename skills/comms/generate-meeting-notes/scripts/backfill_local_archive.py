#!/usr/bin/env python3
"""
backfill_local_archive.py - 一次性補齊：把 Drive 上有、本機缺的正式稿與側檔補回來。

發佈流程從現在起會同時寫本機（見 local_archive.py），但過去的場次只在 Drive。
這支腳本掃 Drive 的系列資料夾，逐場比對本機，只補缺的東西。

預設 dry-run，只印差集不寫檔；要真的寫入必須加 --apply。

用法：
    python3 scripts/backfill_local_archive.py                    # 看差集
    python3 scripts/backfill_local_archive.py --meeting data內會  # 只看單一系列
    python3 scripts/backfill_local_archive.py --apply            # 實際補齊

退出碼：
    0  完成（dry-run 或 --apply 都算）
    1  執行中出錯：憑證、Drive API、或翻頁超過上限
    2  參數錯誤：--meeting 指到 config 裡沒有的會議
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract_audio_sources import get_google_credentials, load_config
from local_archive import LOCAL_ARCHIVE_ROOT, archive_paths, sidecar_content

DATE_DIR = re.compile(r"\d{8}")


def list_all(drive, query: str, max_pages: int) -> list[dict]:
    """翻完一個 Drive 查詢的所有頁。超過上限就炸，不要無聲繞圈。"""
    files: list[dict] = []
    page_token = None
    for _ in range(max_pages):
        response = drive.files().list(
            q=query,
            fields="nextPageToken, files(id,name,mimeType)",
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageToken=page_token,
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files
    raise RuntimeError(
        f"翻頁超過上限 {max_pages} 頁仍未結束（已收 {len(files)} 筆）。\n"
        f"   query: {query}\n"
        f"   Drive 一個系列不該有這麼多日期資料夾——先確認 query 是否選錯資料夾，"
        f"或用 --max-pages 提高上限。"
    )


def export_markdown(drive, doc_id: str) -> str:
    return drive.files().export_media(
        fileId=doc_id, mimeType="text/markdown"
    ).execute().decode("utf-8")


def scan_meeting(drive, meeting: dict, root: Path, max_pages: int) -> list[dict]:
    """回傳這個系列所有「本機缺東西」的場次。"""
    folder_name = meeting.get("folder_name", meeting["series_name"])
    gaps: list[dict] = []

    date_folders = list_all(
        drive,
        f"'{meeting['folder_id']}' in parents "
        "and mimeType='application/vnd.google-apps.folder' and trashed=false",
        max_pages,
    )
    for folder in sorted(date_folders, key=lambda f: f["name"]):
        date = folder["name"]
        if not DATE_DIR.fullmatch(date):
            continue
        docs = list_all(
            drive,
            f"'{folder['id']}' in parents "
            "and mimeType='application/vnd.google-apps.document' and trashed=false",
            max_pages,
        )
        for doc in docs:
            if not doc["name"].startswith("會議記錄"):
                continue
            note_path, sidecar_path = archive_paths(folder_name, date, doc["name"], root)
            if note_path.exists() and sidecar_path.exists():
                continue
            gaps.append({
                "doc_id": doc["id"],
                "doc_url": f"https://docs.google.com/document/d/{doc['id']}/edit",
                "note_path": note_path,
                "sidecar_path": sidecar_path,
                "need_note": not note_path.exists(),
                "need_sidecar": not sidecar_path.exists(),
                # 本機已有正式稿但檔名跟 Doc 名不同 → 補下去會多出一份
                "renamed": sorted(
                    p.name for p in note_path.parent.glob("會議記錄*.md")
                    if p.name != note_path.name
                ) if not note_path.exists() and note_path.parent.is_dir() else [],
            })
    return gaps


def split_collisions(gaps: list[dict]) -> tuple[list[dict], list[dict]]:
    """把「多份 Doc 對到同一個本機檔名」的那些挑出來。回傳 (可補的, 撞名的)。"""
    counts: dict[Path, int] = {}
    for gap in gaps:
        counts[gap["note_path"]] = counts.get(gap["note_path"], 0) + 1
    clean = [g for g in gaps if counts[g["note_path"]] == 1]
    clashed = [g for g in gaps if counts[g["note_path"]] > 1]
    return clean, clashed


def main() -> int:
    parser = argparse.ArgumentParser(description="把 Drive 上本機缺的正式稿與側檔補回來")
    parser.add_argument("--meeting", action="append", default=[],
                        help="只處理指定的會議 key，可重複；省略時處理 config 裡全部")
    parser.add_argument("--apply", action="store_true",
                        help="實際寫入本機。省略時只印差集（dry-run）")
    parser.add_argument("--root", default=str(LOCAL_ARCHIVE_ROOT),
                        help=f"本機會議記錄根目錄（預設 {LOCAL_ARCHIVE_ROOT}）")
    parser.add_argument("--max-pages", type=int, default=20,
                        help="單次 Drive 查詢的翻頁上限，超過即中止（預設 20）")
    args = parser.parse_args()

    meetings = load_config().get("meetings", {})
    if args.meeting:
        unknown = [k for k in args.meeting if k not in meetings]
        if unknown:
            print(f"❌ config 裡沒有這些會議 key：{', '.join(unknown)}")
            print(f"   可用：{', '.join(meetings)}")
            return 2
        meetings = {k: meetings[k] for k in args.meeting}

    root = Path(args.root).expanduser()

    from googleapiclient.discovery import build
    try:
        # 走 skill 自己的憑證，不要走 ADC——兩者是不同的兩份，ADC 過期會誤判成沒憑證
        drive = build("drive", "v3", credentials=get_google_credentials())
    except Exception as exc:
        print(f"❌ 取不到 Google 憑證：{type(exc).__name__}: {exc}")
        print("   skill 的憑證在 ~/.config/generate-meeting-notes/；這裡不使用 ADC。")
        return 1

    all_gaps: list[dict] = []
    collisions: list[dict] = []
    for key, meeting in meetings.items():
        try:
            gaps = scan_meeting(drive, meeting, root, args.max_pages)
        except RuntimeError as exc:
            print(f"❌ {key}：{exc}")
            return 1
        except Exception as exc:
            print(f"❌ {key}：Drive 查詢失敗 {type(exc).__name__}: {exc}")
            return 1
        # 同一個 Drive 日期資料夾裡有兩份同名 Doc → 對到同一個本機檔名，
        # 挑哪一個的 URL 都是猜的。寧可讓側檔缺席，也不要記一個可能錯的 URL。
        gaps, clashed = split_collisions(gaps)
        collisions.extend(clashed)

        print(f"\n📋 {key}（{meeting.get('folder_name', meeting['series_name'])}）"
              f"：{len(gaps)} 場缺東西")
        for gap in gaps:
            missing = " + ".join(
                ["正式稿"] * gap["need_note"] + ["側檔"] * gap["need_sidecar"]
            )
            print(f"   缺 {missing:<11} {gap['note_path'].parent.name}/{gap['note_path'].name}")
            if gap["renamed"]:
                print(f"      ⚠️  本機已有不同檔名的正式稿：{', '.join(gap['renamed'])}")
        all_gaps.extend(gaps)

    if collisions:
        print(f"\n⚠️  {len(collisions)} 份 Doc 撞到同一個本機檔名，一律跳過（URL 挑哪個都是猜的）：")
        for gap in collisions:
            print(f"   {gap['note_path'].parent.name}/{gap['note_path'].name}  ← {gap['doc_url']}")
        print("   要補的話：先在 Drive 上把同名 Doc 改名或刪掉重複的，再跑一次。")

    print(f"\n合計 {len(all_gaps)} 場缺東西"
          f"（正式稿 {sum(g['need_note'] for g in all_gaps)}、"
          f"側檔 {sum(g['need_sidecar'] for g in all_gaps)}）")

    if not args.apply:
        print("這是 dry-run，沒有寫入任何檔案。確認差集無誤後加 --apply。")
        return 0

    for gap in all_gaps:
        gap["note_path"].parent.mkdir(parents=True, exist_ok=True)
        if gap["need_note"]:
            try:
                markdown = export_markdown(drive, gap["doc_id"])
            except Exception as exc:
                print(f"❌ 匯出失敗 {gap['note_path'].name}：{type(exc).__name__}: {exc}")
                return 1
            gap["note_path"].write_text(markdown, encoding="utf-8")
        if gap["need_sidecar"]:
            gap["sidecar_path"].write_text(
                sidecar_content(gap["doc_url"]), encoding="utf-8"
            )
        print(f"   ✓ {gap['note_path'].parent.name}/{gap['note_path'].stem}")

    print(f"\n✅ 補齊完成：{len(all_gaps)} 場")
    return 0


if __name__ == "__main__":
    sys.exit(main())
