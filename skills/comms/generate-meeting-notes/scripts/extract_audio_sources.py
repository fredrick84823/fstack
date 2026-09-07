#!/usr/bin/env python3
"""
extract_audio_sources.py - NotebookLM 音訊 source extraction 流程

流程：
  1. 用 ffmpeg 將音訊拆成固定分鐘數，或依目標段數平均切分 → ~/Downloads/
  2. 上傳所有片段到 NotebookLM 指定 Notebook
  3. 等待 AI 處理完成
  4. 產出本次來源 artifacts：transcript.md、extract.md、meeting-context.md
  5. 後續由本地 Agent 讀取 artifacts + default prompt 生成正式會議記錄

用法：
    python3 extract_audio_sources.py <audio_file_path>
    python3 extract_audio_sources.py <audio_file_path> --segment-count 20
    python3 extract_audio_sources.py <audio_file_path> --segment-minutes 10

範例：
    python3 extract_audio_sources.py ~/Desktop/data_meeting_20260309.m4a

注意：此腳本只處理音訊/錄音的 source extraction，不直接建立 Google Doc 或發 Slack。
正式會議記錄由 Agent 讀取 transcript/extract 後產生 Markdown，再交給
create_gdoc_from_md.py 發佈。
"""

import asyncio
import json
import re
import subprocess
import sys
import time
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "generate-meeting-notes"
CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_GLOSSARY_PATH = CONFIG_DIR / "glossary.json"
SKILL_DIR = Path(__file__).parent.parent
DEFAULT_PROMPT_PATH = SKILL_DIR / "references" / "default-prompt.md"


# ─── 設定 ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("❌ 尚未設定。請先執行：")
        print(f"   python3 {Path(__file__).parent}/setup.py")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


SHARED_GLOSSARY_CACHE = CONFIG_DIR / "glossary.shared.cache.json"


def fetch_shared_glossary(config: dict) -> tuple[dict | None, str]:
    """從 Google Drive 抓共用 glossary。回傳 (doc, 來源說明)。

    共用檔放 Drive 而非 GCS：現有 OAuth token 已涵蓋 drive scope，
    不需要新增 scope、也不需要同事重新授權（GCS 需要 devstorage/cloud-platform）。

    永不拋例外。抓不到就退回本機 cache，cache 也沒有就回 None ——
    網路或權限問題不該讓會議記錄整個跑不出來。
    """
    shared = config.get("shared_glossary") or {}
    file_id = str(shared.get("file_id", "")).strip()
    if not file_id:
        return None, "未設定"

    ttl_hours = float(shared.get("cache_ttl_hours", 24))
    if SHARED_GLOSSARY_CACHE.exists():
        age_hours = (time.time() - SHARED_GLOSSARY_CACHE.stat().st_mtime) / 3600
        if age_hours < ttl_hours:
            try:
                return json.loads(SHARED_GLOSSARY_CACHE.read_text(encoding="utf-8")), \
                    f"cache（{age_hours:.1f}h 內）"
            except Exception:
                pass  # cache 壞了就當沒有，往下重抓

    try:
        from googleapiclient.discovery import build
        drive = build("drive", "v3", credentials=get_google_credentials())
        raw = drive.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
        doc = json.loads(raw.decode("utf-8"))
        SHARED_GLOSSARY_CACHE.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return doc, "Drive"
    except Exception as e:
        if SHARED_GLOSSARY_CACHE.exists():
            try:
                doc = json.loads(SHARED_GLOSSARY_CACHE.read_text(encoding="utf-8"))
                print(f"⚠️  共用 glossary 讀取失敗，改用過期 cache：{e}")
                return doc, "cache（已過期）"
            except Exception:
                pass
        print(f"⚠️  共用 glossary 讀取失敗且無 cache，只用本機：{e}")
        return None, "讀取失敗"


def load_glossary_entries(config: dict, meeting_key: str) -> tuple[list[dict], Path | None]:
    glossary_path = Path(config.get("glossary_path", DEFAULT_GLOSSARY_PATH)).expanduser()

    local_doc: dict = {}
    if glossary_path.exists():
        try:
            local_doc = json.loads(glossary_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  本機 glossary.json 解析失敗，略過：{e}")

    shared_doc, shared_origin = fetch_shared_glossary(config)

    def terms(doc: dict) -> list[dict]:
        out = list(doc.get("global_terms", []))
        out.extend(doc.get("meeting_terms", {}).get(meeting_key, []))
        return out

    local_terms = terms(local_doc)
    shared_terms = terms(shared_doc or {})

    # 本機放前面：下方 dedup 保留同 id 的第一筆 → 本機覆寫共用。
    # 本機視為個人微調或尚未上游的實驗，共用檔是團隊累積的基準。
    raw_entries = local_terms + shared_terms

    if not local_doc and shared_doc is None:
        return [], glossary_path if glossary_path.exists() else None

    entries: list[dict] = []
    seen_ids: set[str] = set()
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or entry.get("canonical") or "").strip()
        if not entry_id or entry_id in seen_ids:
            continue
        status = str(entry.get("status", "active")).strip().lower()
        meetings = entry.get("meetings", [])
        if status != "active":
            continue
        if meetings and meeting_key not in meetings:
            continue
        entries.append(entry)
        seen_ids.add(entry_id)

    # 來源統計只印到 stdout，不進 meeting-context.md ——
    # 模型不需要知道詞彙來自哪一邊，但除錯時要看得到。
    local_ids = {str(e.get("id") or e.get("canonical") or "").strip()
                 for e in local_terms if isinstance(e, dict)}
    shared_ids = {str(e.get("id") or e.get("canonical") or "").strip()
                  for e in shared_terms if isinstance(e, dict)}
    overridden = len(local_ids & shared_ids)
    print(
        f"📚 glossary：共 {len(entries)} 筆進 context"
        f"（共用 {len(shared_ids)} 筆／{shared_origin}"
        f" + 本機 {len(local_ids)} 筆，其中 {overridden} 筆覆寫共用）"
    )

    return entries, glossary_path


def build_glossary_prompt(entries: list[dict]) -> str:
    if not entries:
        return ""

    lines = [
        "## Glossary Context (Naming Only)",
        "Use these mappings only for naming, abbreviation expansion, person/project legibility, and transcript typo correction.",
        "Do not infer decisions, action items, metrics, dates, or factual claims from glossary entries alone.",
        "This list is a full org roster, not an attendee list: most entries will not appear in any given meeting. "
        "Only map a name when the transcript actually contains it or a close phonetic variant. "
        "Never pick the closest-sounding roster entry to resolve an unclear reference — keep the transcript wording and mark [待確認].",
    ]

    for entry in entries:
        canonical = str(entry.get("canonical", "")).strip()
        if not canonical:
            continue
        aliases = [str(alias).strip() for alias in entry.get("aliases", []) if str(alias).strip()]
        entry_type = str(entry.get("type", "other")).strip()
        render_hint = str(entry.get("render_hint", "")).strip()
        disambiguation = str(entry.get("disambiguation", "")).strip()

        parts = [f"- {canonical} ({entry_type})"]
        if aliases:
            parts.append(f"aliases: {', '.join(aliases)}")
        if render_hint:
            parts.append(f"render: {render_hint}")
        lines.append(" | ".join(parts))
        if disambiguation:
            lines.append(f"  - ambiguity: {disambiguation}")

    return "\n".join(lines)


META_EXTRACT_HINTS = (
    "我已生成索引",
    "已生成索引",
    "以下是索引",
    "以下是摘要",
    "我已完成",
    "as requested",
    "here is",
    "i have generated",
)

EXTRACT_CONTENT_HINTS = (
    "議題",
    "決策",
    "行動",
    "風險",
    "未決",
    "專有名詞",
)


def is_non_content_extract(content: str) -> bool:
    normalized = re.sub(r"\s+", " ", content.strip())
    if len(normalized) < 120:
        return True

    lowered = normalized.lower()
    if any(hint.lower() in lowered for hint in META_EXTRACT_HINTS):
        return True

    content_hits = sum(1 for hint in EXTRACT_CONTENT_HINTS if hint in normalized)
    return content_hits < 2


def load_prompt(config: dict, meeting: dict, meeting_key: str) -> str:
    prompt_path = Path(config.get("prompt_path", "")).expanduser()
    if prompt_path.exists():
        base = prompt_path.read_text(encoding="utf-8")
    elif DEFAULT_PROMPT_PATH.exists():
        base = DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")
    else:
        base = "請根據提供的會議音訊，撰寫一份完整的繁體中文會議記錄，包含關鍵要點、討論過程、行動項目。"

    sections = [base.rstrip()]
    glossary_entries, _ = load_glossary_entries(config, meeting_key)
    glossary_prompt = build_glossary_prompt(glossary_entries)
    if glossary_prompt:
        sections.append(glossary_prompt)

    custom = meeting.get("custom_prompt", "").strip()
    if custom:
        sections.append(custom)
    return "\n\n---\n\n".join(sections)


# ─── 音訊處理 ─────────────────────────────────────────────────────────────────

def extract_date(filename: str) -> str:
    """從檔名提取 YYYYMMDD，例如 data_meeting_20260309.m4a → 20260309"""
    match = re.search(r"(\d{8})", filename)
    if not match:
        raise ValueError(
            f"無法從檔名提取日期（需含 YYYYMMDD）：{filename}\n"
            f"範例：data_meeting_20260309.m4a"
        )
    return match.group(1)


def get_audio_duration_seconds(audio_path: Path) -> float:
    """用 ffprobe 取得音訊長度（秒）。"""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe 取得音訊長度失敗：{result.stderr[-2000:]}")
    try:
        return float(result.stdout.strip())
    except ValueError as e:
        raise RuntimeError(f"無法解析音訊長度：{result.stdout!r}") from e


def split_audio(
    audio_path: Path,
    *,
    segment_minutes: float | None = None,
    segment_count: int | None = None,
) -> list[Path]:
    """用 ffmpeg 將音訊拆分後輸出到 ~/Downloads/。

    預設以 10 分鐘切段；若提供 segment_count，會先取得音訊長度再平均切成
    指定段數的近似等長片段。
    """
    output_dir = Path.home() / "Downloads"
    basename = audio_path.stem
    ext = audio_path.suffix
    output_pattern = str(output_dir / f"{basename}_output_%03d{ext}")

    if segment_count is not None:
        if segment_count <= 0:
            raise ValueError("segment_count 必須大於 0")
        duration_seconds = get_audio_duration_seconds(audio_path)
        segment_seconds = max(1.0, duration_seconds / segment_count)
        segment_label = f"約 {segment_count} 段（每段約 {segment_seconds / 60:.2f} 分鐘）"
    else:
        if segment_minutes is None:
            segment_minutes = 10
        if segment_minutes is None or segment_minutes <= 0:
            raise ValueError("segment_minutes 必須大於 0")
        segment_seconds = segment_minutes * 60
        segment_label = f"{segment_minutes:g} 分鐘片段"

    print(f"\n🎵 拆分音訊為 {segment_label}...")
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", str(segment_seconds),
            "-c", "copy",
            output_pattern,
            "-y",  # 覆蓋已存在的檔案
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"❌ ffmpeg 錯誤：\n{result.stderr[-2000:]}")
        sys.exit(1)

    segments = sorted(output_dir.glob(f"{basename}_output_*{ext}"))
    if not segments:
        print("❌ 沒有產生任何片段，請確認音訊檔格式正確")
        sys.exit(1)

    print(f"✅ 建立 {len(segments)} 個片段 → ~/Downloads/")
    return segments


# ─── NotebookLM ────────────────────────────────────────────────────────────────

def build_meeting_context_markdown(config: dict, meeting: dict, meeting_key: str, date: str) -> str:
    """Build local context for the agent. This is legibility context, not evidence."""
    attendees = meeting.get("attendees", [])
    lines = [
        "# Meeting Context",
        "",
        f"- Meeting key: {meeting_key}",
        f"- Series: {meeting.get('series_name', meeting_key)}",
        f"- Date: {date}",
        f"- Notebook: {meeting.get('notebook_name', '')}",
        f"- Drive folder: {meeting.get('folder_name', '')}",
        "",
        "## Attendees",
    ]
    if attendees:
        lines.extend(f"- {name}" for name in attendees)
    else:
        lines.append("- [not configured]")

    custom_prompt = meeting.get("custom_prompt", "").strip()
    if custom_prompt:
        lines.extend(["", "## Meeting-Type Notes", custom_prompt])

    glossary_entries, glossary_path = load_glossary_entries(config, meeting_key)
    lines.extend(["", "## Glossary Context (Naming Only)"])
    if glossary_path:
        lines.append(f"- Glossary path: {glossary_path}")
    if glossary_entries:
        for entry in glossary_entries:
            canonical = str(entry.get("canonical", "")).strip()
            if not canonical:
                continue
            aliases = ", ".join(str(alias).strip() for alias in entry.get("aliases", []) if str(alias).strip())
            entry_type = str(entry.get("type", "other")).strip()
            line = f"- {canonical} ({entry_type})"
            if aliases:
                line += f" | aliases: {aliases}"
            lines.append(line)
    else:
        lines.append("- No active glossary entries for this meeting.")

    lines.extend([
        "",
        "## Evidence Rules",
        "- transcript.md is the primary source.",
        "- extract.md is an index/checklist, not a replacement for transcript.md.",
        "- meeting-context.md can only improve naming and legibility.",
        "- Do not infer decisions, action items, metrics, dates, or factual claims from context alone.",
    ])
    return "\n".join(lines) + "\n"


async def upload_and_extract_sources(
    notebook_name: str,
    segments: list[Path],
    *,
    context_prompt: str,
) -> tuple[str, str]:
    """Upload audio, wait for processing, and return transcript/extract markdown."""
    from notebooklm import NotebookLMClient

    async with await NotebookLMClient.from_storage() as client:

        # 找到指定 Notebook
        notebooks = await client.notebooks.list()
        notebook = next(
            (nb for nb in notebooks if nb.title == notebook_name), None
        )
        if not notebook:
            available = [nb.title for nb in notebooks]
            raise ValueError(
                f"找不到 Notebook：'{notebook_name}'\n"
                f"可用的 Notebook：{available}"
            )
        print(f"\n📚 使用 Notebook：{notebook.title} ({notebook.id})")

        # 上傳音訊片段
        print(f"\n⬆️  上傳 {len(segments)} 個音訊片段...")
        source_ids = []
        for seg in segments:
            print(f"   上傳 {seg.name}...")
            source = await client.sources.add_file(notebook.id, str(seg))
            source_ids.append(source.id)
        print(f"✅ 上傳完成")

        # 等待所有 sources 處理完成
        print(f"\n⏳ 等待 NotebookLM 分析音訊（可能需要數分鐘）...")
        ready_source_ids = []
        failed_count = 0
        for i, source_id in enumerate(source_ids, 1):
            while True:
                source = await client.sources.get(notebook.id, source_id)
                if source is None:
                    await asyncio.sleep(5)
                    continue
                if source.is_ready:
                    print(f"   [{i}/{len(source_ids)}] {source.title or source_id} ✓")
                    ready_source_ids.append(source_id)
                    break
                elif source.is_error:
                    print(f"   [{i}/{len(source_ids)}] {source.title or source_id} ⚠️ 處理失敗，略過")
                    failed_count += 1
                    break
                await asyncio.sleep(5)
        if not ready_source_ids:
            raise RuntimeError("所有音訊片段均處理失敗")
        if failed_count:
            print(f"⚠️  {failed_count} 段略過，使用 {len(ready_source_ids)}/{len(source_ids)} 段生成報告")
        else:
            print("✅ 所有音訊分析完成")
        source_ids = ready_source_ids

        transcript_parts = ["# Transcript", ""]
        missing_fulltext = []
        print("\n📄 讀取 NotebookLM source fulltext 作為 transcript...")
        for i, source_id in enumerate(source_ids, 1):
            try:
                fulltext = await client.sources.get_fulltext(notebook.id, source_id)
                content = fulltext.content.strip()
                if content:
                    transcript_parts.extend([
                        f"## Segment {i}: {fulltext.title or source_id}",
                        "",
                        content,
                        "",
                    ])
                    print(f"   [{i}/{len(source_ids)}] {fulltext.title or source_id} ({len(content)} chars)")
                else:
                    missing_fulltext.append(source_id)
                    print(f"   [{i}/{len(source_ids)}] {source_id} ⚠️ empty fulltext")
            except Exception as e:
                missing_fulltext.append(source_id)
                print(f"   [{i}/{len(source_ids)}] {source_id} ⚠️ fulltext 讀取失敗：{e}")

        transcript = "\n".join(transcript_parts).strip() + "\n"
        if len(transcript.strip()) < 200:
            print("\n⚠️  fulltext 不足，改用 source-scoped chat 產生 transcript...")
            transcript_question = (
                "請只根據本次選取的音訊 sources，產出高保真繁體中文逐字稿。"
                "請依時間順序整理，保留 Speaker 1、Speaker 2 等匿名標籤；"
                "聽不清楚處標記 [聽不清楚]；不要加入摘要、決策或外部背景。"
            )
            transcript_result = await client.chat.ask(notebook.id, transcript_question, source_ids=source_ids)
            transcript = "# Transcript\n\n" + transcript_result.answer.strip() + "\n"

        print("\n🧾 產生 extract.md（議題/決策/待辦索引）...")
        extract_question = (
            f"{context_prompt}\n\n"
            "請只根據本次選取的音訊 sources 產出結構化 extract。"
            "這不是正式會議記錄，而是供本地 Agent 生成會議記錄的索引。"
            "請用繁體中文 Markdown，包含：\n"
            "1. 議題清單\n"
            "2. 明確決策（標記 [已確認]；不確定標 [待確認]）\n"
            "3. 行動項目（負責人不確定就用 Speaker# 或 [待確認]）\n"
            "4. 風險/未決問題\n"
            "5. 專有名詞與可能誤聽詞\n"
            "嚴禁引用本次音訊 sources 之外的 Notebook 歷史內容。"
        )

        retry_question = (
            extract_question
            + "\n\n"
            "注意：不要輸出 meta 說明、完成宣告或自我描述。"
            "如果前一版像『我已生成索引』這類非內容回覆，請直接重新輸出完整 Markdown。"
        )

        extract = ""
        for attempt, question in enumerate((extract_question, retry_question), 1):
            extract_result = await client.chat.ask(notebook.id, question, source_ids=source_ids)
            candidate = extract_result.answer.strip()
            if not is_non_content_extract(candidate):
                extract = "# Extract\n\n" + candidate + "\n"
                break
            print(
                f"⚠️  NotebookLM extract 似乎不是內容型回覆（第 {attempt} 次），準備重試..."
            )
        if not extract:
            raise RuntimeError(
                "NotebookLM extract 產出疑似非內容回覆，已重試仍失敗；"
                "請檢查 NotebookLM 輸出或重新執行 source extraction。"
            )

        return transcript, extract


# ─── Google 認證 ───────────────────────────────────────────────────────────────

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


def get_google_credentials():
    """
    依序嘗試三種認證來源：
    1. credentials.json（SA 或 OAuth Client）
    2. gcloud user credentials（gcloud auth login --enable-gdrive-access）
    3. ADC（gcloud auth application-default login）
    """
    creds_path = CONFIG_DIR / "credentials.json"

    # ── 來源 1：credentials.json ──
    if creds_path.exists():
        with open(creds_path, encoding="utf-8") as f:
            creds_data = json.load(f)

        if creds_data.get("type") == "service_account":
            from google.oauth2 import service_account
            return service_account.Credentials.from_service_account_file(
                str(creds_path), scopes=GOOGLE_SCOPES
            )

        if "installed" in creds_data or "web" in creds_data:
            # OAuth Client → InstalledAppFlow，token 存本機
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow

            token_path = CONFIG_DIR / "google_token.json"
            creds = None
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(
                    str(token_path), GOOGLE_SCOPES
                )
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), GOOGLE_SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                token_path.write_text(creds.to_json())
            return creds

    # ── 來源 2 & 3：google.auth.default()
    # 會依序嘗試：gcloud user credentials → ADC → metadata server
    try:
        import google.auth
        creds, _ = google.auth.default(scopes=GOOGLE_SCOPES)
        return creds
    except Exception as e:
        raise RuntimeError(
            "找不到有效的 Google 認證，請執行以下其中一個指令：\n"
            "  gcloud auth login --enable-gdrive-access\n"
            "  gcloud auth application-default login\n"
            f"原始錯誤：{e}"
        ) from e


# ─── Google Drive ──────────────────────────────────────────────────────────────

INLINE_CODE_STYLE = {
    "weightedFontFamily": {"fontFamily": "Roboto Mono"},
    "backgroundColor": {"color": {"rgbColor": {"red": .95, "green": .95, "blue": .95}}},
    "foregroundColor": {"color": {"rgbColor": {"red": .78, "green": .12, "blue": .35}}},
}


def _parse_inline(
    text: str,
) -> tuple[str, list[tuple[int, int]], list[tuple[int, int]]]:
    """解析 **bold** 與 `code`，回傳 (純文字, bold_ranges, code_ranges)"""
    plain = ""
    bold_ranges: list[tuple[int, int]] = []
    code_ranges: list[tuple[int, int]] = []
    last_end = 0
    for m in re.finditer(r"\*\*(.+?)\*\*|`([^`]+)`", text):
        plain += text[last_end:m.start()]
        start = len(plain)
        if m.group(1) is not None:
            plain += m.group(1)
            bold_ranges.append((start, len(plain)))
        else:
            plain += m.group(2)
            code_ranges.append((start, len(plain)))
        last_end = m.end()
    plain += text[last_end:]
    return plain, bold_ranges, code_ranges


def _parse_inline_bold(text: str) -> tuple[str, list[tuple[int, int]]]:
    """相容包裝：只取 bold ranges"""
    plain, bolds, _ = _parse_inline(text)
    return plain, bolds


def _parse_blocks(content: str) -> list[tuple[str, list[str]]]:
    """將 Markdown 拆成 ('text', lines) 和 ('table', lines) 交替的 block 列表"""
    blocks: list[tuple[str, list[str]]] = []
    text_lines: list[str] = []
    table_lines: list[str] = []

    for line in content.rstrip("\n").split("\n"):
        if re.match(r"^\|", line):
            if text_lines:
                blocks.append(("text", text_lines))
                text_lines = []
            table_lines.append(line)
        else:
            if table_lines:
                blocks.append(("table", table_lines))
                table_lines = []
            text_lines.append(line)

    if table_lines:
        blocks.append(("table", table_lines))
    if text_lines:
        blocks.append(("text", text_lines))
    return blocks


def _parse_table_rows(table_lines: list[str]) -> list[list[str]]:
    """解析 Markdown 表格，跳過分隔列，回傳 rows（每 row 是 cells 列表）"""
    rows = []
    for line in table_lines:
        if re.match(r"^\|\s*[-:]+[-:\s|]*\s*\|", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if any(cells):
            rows.append(cells)
    return rows


def _classify_line(line: str) -> tuple[str, int, str, list, list]:
    """解析單行 Markdown，回傳 (kind, level, plain_text, bold_ranges, code_ranges)"""
    m = re.match(r"^(#{1,6})\s+(.*)", line)
    if m:
        plain, bolds, codes = _parse_inline(m.group(2))
        return "heading", len(m.group(1)), plain, bolds, codes

    m = re.match(r"^(\s*)[\*\-]\s+(.*)", line)
    if m:
        plain, bolds, codes = _parse_inline(m.group(2))
        return "bullet", len(m.group(1)), plain, bolds, codes

    if re.match(r"^[-\*_]{3,}\s*$", line):
        return "normal", 0, "", [], []

    plain, bolds, codes = _parse_inline(line)
    return "normal", 0, plain, bolds, codes


def _markdown_to_gdocs(
    content: str,
) -> tuple[str, list[dict], list[tuple[int, list]]]:
    """將 Markdown 轉為 Google Docs API 請求。
    回傳：
      plain_text  — 不含表格的純文字，insertText 插入 index=1
      fmt_requests — 段落樣式與文字樣式 requests
      tables      — [(doc_insert_index, rows), ...] 按出現順序排列
                    呼叫方需以**反向順序**逐一 insertTable + 填入 cell
    """
    HEADING_STYLES = {
        1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3",
        4: "HEADING_4", 5: "HEADING_5", 6: "HEADING_6",
    }
    blocks = _parse_blocks(content)
    plain_parts: list[str] = []
    fmt_requests: list[dict] = []
    tables: list[tuple[int, list]] = []
    char_pos = 0  # plain_parts 已累積的字元數

    for block_type, block_lines in blocks:
        if block_type == "table":
            rows = _parse_table_rows(block_lines)
            if rows:
                tables.append((1 + char_pos, rows))
            continue

        for line in block_lines:
            kind, level, plain, bolds, codes = _classify_line(line)
            line_start = 1 + char_pos
            line_end = line_start + len(plain)
            para_range = {"startIndex": line_start, "endIndex": line_end + 1}

            if kind == "heading":
                fmt_requests.append({
                    "updateParagraphStyle": {
                        "range": para_range,
                        "paragraphStyle": {"namedStyleType": HEADING_STYLES[level]},
                        "fields": "namedStyleType",
                    }
                })
                # H1 一律加粗
                if level == 1:
                    fmt_requests.append({
                        "updateTextStyle": {
                            "range": para_range,
                            "textStyle": {"bold": True},
                            "fields": "bold",
                        }
                    })
            elif kind == "bullet":
                fmt_requests.append({
                    "createParagraphBullets": {
                        "range": para_range,
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                    }
                })

            for bs, be in bolds:
                if bs < be:
                    fmt_requests.append({
                        "updateTextStyle": {
                            "range": {
                                "startIndex": line_start + bs,
                                "endIndex": line_start + be,
                            },
                            "textStyle": {"bold": True},
                            "fields": "bold",
                        }
                    })

            # `code` — Docs 無原生 code 樣式，以等寬字體＋淺灰底＋深紅字模擬
            for cs, ce in codes:
                if cs < ce:
                    fmt_requests.append({
                        "updateTextStyle": {
                            "range": {
                                "startIndex": line_start + cs,
                                "endIndex": line_start + ce,
                            },
                            "textStyle": INLINE_CODE_STYLE,
                            "fields": "weightedFontFamily,backgroundColor,foregroundColor",
                        }
                    })

            plain_parts.append(plain + "\n")
            char_pos += len(plain) + 1

    full_text = "".join(plain_parts)
    return full_text, fmt_requests, tables


def create_gdoc_in_shared_drive(
    date: str,
    content: str,
    meeting: dict,
    *,
    title_suffix: str | None = None,
    return_folder_id: bool = False,
) -> str | tuple[str, str]:
    """建立 Google Doc，在 Shared Drive 建立日期子資料夾，將文件移入"""
    from googleapiclient.discovery import build

    creds = get_google_credentials()
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    series_name = meeting["series_name"]
    series_folder_id = meeting["folder_id"]
    doc_title = f"會議記錄_{series_name}_{date}"
    if title_suffix:
        cleaned_suffix = re.sub(r"[\\/:*?\"<>|]+", "-", title_suffix).strip(" -_")
        if cleaned_suffix:
            doc_title = f"{doc_title}_{cleaned_suffix}"

    # 在 Shared Drive 建立（或重用）日期子資料夾
    existing = drive.files().list(
        q=(
            f"'{series_folder_id}' in parents and name='{date}' "
            "and mimeType='application/vnd.google-apps.folder' and trashed=false"
        ),
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        fields="files(id)",
    ).execute().get("files", [])
    if existing:
        subfolder_id = existing[0]["id"]
        print(f"\n📁 重用已存在的子資料夾：{date}")
    else:
        print(f"\n📁 建立子資料夾：{date}...")
        subfolder = drive.files().create(
            body={
                "name": date,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [series_folder_id],
            },
            supportsAllDrives=True,
            fields="id",
        ).execute()
        subfolder_id = subfolder["id"]

    # 建立 Google Doc（直接建在 Shared Drive 子資料夾內）
    # 註：部分 Workspace 政策下 docs.documents().create() 會回傳無法存取的 id，
    #     故改用 Drive API 直接在目標資料夾建立空白 Google Doc。
    print(f"📄 建立 Google Doc：{doc_title}...")
    doc_file = drive.files().create(
        body={
            "name": doc_title,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [subfolder_id],
        },
        supportsAllDrives=True,
        fields="id",
    ).execute()
    doc_id = doc_file["id"]

    # 寫入內容（Markdown 轉 Google Docs 格式）
    plain_text, fmt_requests, tables = _markdown_to_gdocs(content)

    # Phase 1：插入所有文字 + 格式
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {"insertText": {"location": {"index": 1}, "text": plain_text}},
                *fmt_requests,
            ]
        },
    ).execute()

    # Phase 2：插入表格（反向順序，避免前面的 index 被後面的插入影響）
    for table_doc_idx, rows in reversed(tables):
        num_cols = max(len(row) for row in rows)
        num_rows = len(rows)

        # 插入表格結構
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{
                "insertTable": {
                    "rows": num_rows,
                    "columns": num_cols,
                    "location": {"index": table_doc_idx},
                }
            }]},
        ).execute()

        # 讀取文件，取得各 cell 的實際 paragraph startIndex
        doc_body = docs.documents().get(documentId=doc_id).execute()
        cell_indices: dict[tuple[int, int], int] = {}
        for elem in doc_body.get("body", {}).get("content", []):
            if "table" not in elem:
                continue
            if abs(elem.get("startIndex", 0) - table_doc_idx) <= 5:
                for r, trow in enumerate(elem["table"]["tableRows"]):
                    for c, tcell in enumerate(trow["tableCells"]):
                        content = tcell.get("content", [])
                        if content:
                            cell_indices[(r, c)] = content[0]["startIndex"]
                break

        # 填入 cell 內容（以 index 反向順序插入，避免前面的插入影響後面的 index）
        cell_data: list[tuple[int, str]] = []
        for r, row in enumerate(rows):
            for c, cell_text in enumerate(row[:num_cols]):
                plain_cell, _ = _parse_inline_bold(cell_text)
                if plain_cell and (r, c) in cell_indices:
                    cell_data.append((cell_indices[(r, c)], plain_cell))

        cell_data.sort(key=lambda x: x[0], reverse=True)
        cell_requests = [
            {"insertText": {"location": {"index": idx}, "text": text}}
            for idx, text in cell_data
        ]
        if cell_requests:
            docs.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": cell_requests},
            ).execute()

    # 文件已直接建立於 Shared Drive 子資料夾，無需搬移
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    if return_folder_id:
        return doc_url, subfolder_id
    return doc_url


# ─── 後處理 ────────────────────────────────────────────────────────────────────

def preprocess_content(content: str) -> str:
    """清理 NotebookLM 可能回傳的 HTML 標籤。
    - <u>text</u> 獨行 → **text**（事件標題）
    - 其他 HTML 標籤直接移除
    """
    # 獨行的 <u>...</u> → **...**（事件標題格式）
    content = re.sub(r"^<u>(.*?)</u>\s*$", r"**\1**", content, flags=re.MULTILINE)
    # 其餘 HTML 標籤一律去除
    content = re.sub(r"<[^>]+>", "", content)
    return content


def inject_attendees(content: str, attendees: list[str]) -> str:
    """在報告內容中插入與會者列表（位於日期行之後）。"""
    if not attendees:
        return content
    # 若已有與會者行則跳過（避免重複，相容「與會者」與「與會人員」兩種寫法）
    if re.search(r"與會者|與會人員", content):
        return content
    attendees_line = f"- 與會者：{', '.join(attendees)}"
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^- 日期：", line):
            lines.insert(i + 1, attendees_line)
            return "\n".join(lines)
    # fallback：插入在標題行之後
    for i, line in enumerate(lines):
        if re.match(r"^#\s", line):
            lines.insert(i + 1, attendees_line)
            return "\n".join(lines)
    return attendees_line + "\n" + content


# ─── 清理 ──────────────────────────────────────────────────────────────────────

def cleanup_segments(segments: list[Path], auto_delete: bool = False):
    if auto_delete:
        for seg in segments:
            seg.unlink(missing_ok=True)
        print(f"✅ 已刪除 {len(segments)} 個片段")
        return
    try:
        confirm = input("\n是否刪除 ~/Downloads/ 中的音訊片段？(y/N): ").strip().lower()
    except EOFError:
        confirm = "n"
    if confirm == "y":
        for seg in segments:
            seg.unlink(missing_ok=True)
        print(f"✅ 已刪除 {len(segments)} 個片段")


# ─── 主程式 ────────────────────────────────────────────────────────────────────

async def main(
    audio_file: str,
    meeting_key: str,
    delete_segments: bool = False,
    segment_minutes: float | None = None,
    segment_count: int | None = None,
    output_dir: str | None = None,
):
    config = load_config()
    meetings = config.get("meetings", {})

    if meeting_key not in meetings:
        available = ", ".join(meetings.keys())
        print(f"❌ 找不到會議類型：'{meeting_key}'")
        print(f"   可用的會議類型：{available}")
        sys.exit(1)

    meeting = meetings[meeting_key]

    if not meeting.get("folder_id"):
        print(f"❌ 會議類型 '{meeting_key}' 尚未設定 folder_id，請更新 config.json")
        sys.exit(1)

    audio_path = Path(audio_file).expanduser().resolve()
    if not audio_path.exists():
        print(f"❌ 找不到音訊檔：{audio_path}")
        sys.exit(1)

    date = extract_date(audio_path.name)
    print(f"\n📅 會議日期：{date}")
    print(f"🎙️  音訊檔：{audio_path.name}")
    print(f"📋 會議類型：{meeting_key}（{meeting['series_name']}）")

    glossary_entries, glossary_path = load_glossary_entries(config, meeting_key)
    if glossary_path and glossary_entries:
        print(f"🧭 載入 glossary：{glossary_path}（{len(glossary_entries)} 條 active entries）")
    elif glossary_path:
        print(f"🧭 glossary 存在但本次沒有可用條目：{glossary_path}")

    # 1. 拆分音訊
    segments = split_audio(
        audio_path,
        segment_minutes=segment_minutes,
        segment_count=segment_count,
    )

    context = build_meeting_context_markdown(config, meeting, meeting_key, date)

    # NotebookLM chat 有 question 長度上限；glossary 只給本地 agent（meeting-context.md），
    # 不塞進 extract 問題裡，否則大 glossary 會讓 chat.ask 被伺服器拒絕（status 3）。
    context_prompt = "\n".join(
        part
        for part in (
            f"會議類型：{meeting.get('series_name', meeting_key)}",
            "與會者：" + "、".join(meeting.get("attendees", [])),
            meeting.get("custom_prompt", "").strip(),
        )
        if part.strip()
    )

    # 2. 上傳 + 等待 + 產出 transcript/extract source artifacts
    transcript, extract = await upload_and_extract_sources(
        meeting["notebook_name"],
        segments,
        context_prompt=context_prompt,
    )

    if output_dir:
        source_dir = Path(output_dir).expanduser().resolve()
    else:
        source_dir = Path("/tmp/meeting_sources") / f"{meeting_key}_{date}"
    source_dir.mkdir(parents=True, exist_ok=True)

    transcript_path = source_dir / "transcript.md"
    extract_path = source_dir / "extract.md"
    context_path = source_dir / "meeting-context.md"

    transcript_path.write_text(transcript, encoding="utf-8")
    extract_path.write_text(extract, encoding="utf-8")
    context_path.write_text(context, encoding="utf-8")

    print(f"\n{'=' * 50}")
    print("✅ Source extraction 完成")
    print(f"📄 Transcript：{transcript_path}")
    print(f"🧾 Extract：{extract_path}")
    print(f"🧭 Context：{context_path}")
    print(f"{'=' * 50}")
    print(f"RESULT_TRANSCRIPT: {transcript_path}")
    print(f"RESULT_EXTRACT: {extract_path}")
    print(f"RESULT_CONTEXT: {context_path}")
    print(f"RESULT_SOURCE_DIR: {source_dir}")
    print(f"RESULT_SERIES_NAME: {meeting['series_name']}")
    print(f"RESULT_DATE: {date}")
    print("\n💡 下一步：Agent 讀取 transcript.md + extract.md + meeting-context.md，依 default prompt 生成 meeting_notes.md，然後執行 create_gdoc_from_md.py 發佈。")

    cleanup_segments(segments, auto_delete=delete_segments)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="從音訊萃取 transcript/extract source artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="範例：\n  python3 extract_audio_sources.py ~/Desktop/data_meeting_20260309.m4a --meeting team週會 --delete-segments --segment-count 20",
    )
    parser.add_argument("audio_file", help="音訊檔路徑（檔名需含 YYYYMMDD）")
    parser.add_argument("--meeting", "-m", required=True, help="會議類型（對應 config.json 中的 meetings key）")
    parser.add_argument("--delete-segments", action="store_true", help="完成後自動刪除 ~/Downloads/ 中的音訊片段，不詢問確認")
    parser.add_argument("--segment-count", type=int, help="將音訊平均切成指定段數")
    parser.add_argument("--segment-minutes", type=float, help="每段片長（分鐘），預設 10")
    parser.add_argument("--output-dir", help="source artifacts 輸出資料夾，預設 /tmp/meeting_sources/<meeting>_<date>")
    args = parser.parse_args()

    asyncio.run(
        main(
            args.audio_file,
            args.meeting,
            delete_segments=args.delete_segments,
            segment_minutes=args.segment_minutes,
            segment_count=args.segment_count,
            output_dir=args.output_dir,
        )
    )
