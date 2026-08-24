#!/usr/bin/env python3
"""
setup.py - Generate Meeting Notes 一鍵設定

預設設定文字輸入 source preparation 與 main synthesis；若要啟用錄音檔支援，請加上 --with-audio。

執行方式：
    python3 scripts/setup.py
    python3 scripts/setup.py --with-audio
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# ─── 路徑設定 ──────────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = Path.home() / ".config" / "generate-meeting-notes"
CONFIG_PATH = CONFIG_DIR / "config.json"
NOTEBOOKLM_STORAGE = Path.home() / ".notebooklm" / "storage_state.json"
GOOGLE_ADC = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
GOOGLE_CREDENTIALS = CONFIG_DIR / "credentials.json"
GOOGLE_TOKEN = CONFIG_DIR / "google_token.json"
GOOGLE_SCOPES = ",".join([
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/cloud-platform",
])

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"

# ─── 輸出工具 ──────────────────────────────────────────────────────────────────

def header(title: str):
    print(f"\n{'─' * 52}")
    print(f"  {title}")
    print(f"{'─' * 52}")

def ok(msg: str):    print(f"  ✅ {msg}")
def warn(msg: str):  print(f"  ⚠️  {msg}")
def err(msg: str):   print(f"  ❌ {msg}")
def tip(msg: str):   print(f"  💡 {msg}")
def info(msg: str):  print(f"     {msg}")

def step(n: int, total: int, title: str):
    print(f"\n[{n}/{total}] {title}")

def run(cmd, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kwargs)

def run_in_skill(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    """在 skill 目錄下用 uv run 執行"""
    return run(["uv", "run"] + cmd, cwd=SKILL_DIR, **kwargs)

def abort(msg: str):
    err(msg)
    print("\n設定中斷。解決問題後重新執行 setup.py。")
    sys.exit(1)

# ─── Step 1：uv ────────────────────────────────────────────────────────────────

def check_install_uv():
    if shutil.which("uv"):
        result = run(["uv", "--version"], capture_output=True, text=True)
        ok(f"uv 已安裝（{result.stdout.strip()}）")
        return

    warn("uv 未安裝，正在安裝...")
    if IS_MAC:
        if shutil.which("brew"):
            result = run(["brew", "install", "uv"])
            if result.returncode == 0:
                ok("uv 安裝成功（透過 Homebrew）")
                return
        # fallback：官方 install script
        result = run("curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True)
        if result.returncode == 0:
            uv_path = Path.home() / ".local" / "bin"
            os.environ["PATH"] = f"{uv_path}:{os.environ['PATH']}"
            ok("uv 安裝成功")
            return
    elif IS_WIN:
        result = run(
            'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
            shell=True
        )
        if result.returncode == 0:
            ok("uv 安裝成功")
            return

    abort(
        "無法自動安裝 uv\n"
        "  請手動安裝：https://docs.astral.sh/uv/getting-started/installation/"
    )

# ─── Step 2：ffmpeg ────────────────────────────────────────────────────────────

def check_install_ffmpeg():
    if shutil.which("ffmpeg"):
        result = run(["ffmpeg", "-version"], capture_output=True, text=True)
        version = result.stdout.split("\n")[0] if result.stdout else "unknown"
        ok(f"ffmpeg 已安裝")
        return

    warn("ffmpeg 未安裝，正在安裝...")
    if IS_MAC and shutil.which("brew"):
        result = run(["brew", "install", "ffmpeg"])
        if result.returncode == 0:
            ok("ffmpeg 安裝成功（透過 Homebrew）")
            return
        abort("Homebrew 安裝 ffmpeg 失敗，請手動執行：brew install ffmpeg")

    # 無法自動安裝時引導使用者
    err("無法自動安裝 ffmpeg")
    if IS_MAC:
        tip("請安裝 Homebrew 後執行：brew install ffmpeg")
        tip("Homebrew 安裝：https://brew.sh")
    elif IS_WIN:
        tip("請下載 ffmpeg：https://ffmpeg.org/download.html#build-windows")
        tip("解壓後將 ffmpeg.exe 加入系統 PATH")
    else:
        tip("請用套件管理器安裝：sudo apt install ffmpeg")

    input("\n安裝完成後按 Enter 繼續...")
    if not shutil.which("ffmpeg"):
        abort("仍找不到 ffmpeg，請確認安裝完成並重試")
    ok("ffmpeg 已就緒")

# ─── Step 3：gcloud CLI ────────────────────────────────────────────────────────

def check_install_gcloud():
    if shutil.which("gcloud"):
        result = run(["gcloud", "--version"], capture_output=True, text=True)
        version_line = result.stdout.split("\n")[0] if result.stdout else ""
        ok(f"gcloud 已安裝（{version_line}）")
        return

    warn("gcloud CLI 未安裝（需要用來存取 Google Drive）")
    if IS_MAC and shutil.which("brew"):
        tip("正在透過 Homebrew 安裝（約 300MB，需要幾分鐘）...")
        result = run(["brew", "install", "--cask", "google-cloud-sdk"])
        if result.returncode == 0:
            # brew cask 安裝後需要重新載入 PATH
            sdk_path = Path("/usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/bin")
            if sdk_path.exists():
                os.environ["PATH"] = f"{sdk_path}:{os.environ['PATH']}"
            if shutil.which("gcloud"):
                ok("gcloud 安裝成功")
                return

    err("請手動安裝 gcloud CLI：")
    if IS_MAC:
        info("方式一（推薦）：brew install --cask google-cloud-sdk")
        info("方式二：https://cloud.google.com/sdk/docs/install")
    else:
        info("下載安裝：https://cloud.google.com/sdk/docs/install")

    input("\n安裝完成後按 Enter 繼續...")
    if not shutil.which("gcloud"):
        abort("仍找不到 gcloud，請確認安裝完成並重試")
    ok("gcloud 已就緒")

# ─── Step 4：Python 套件 ────────────────────────────────────────────────────────

def setup_python_deps(with_audio: bool):
    info("安裝 Python 套件（首次約需 1 分鐘）...")
    result = run(["uv", "sync"], cwd=SKILL_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        abort(f"套件安裝失敗：\n{result.stderr[-500:]}")
    ok("Python 套件安裝完成")

    if not with_audio:
        info("略過 Playwright Chromium；只有錄音檔支援需要 NotebookLM browser runtime")
        return

    info("安裝 Playwright Chromium（約 170MB）...")
    result = run(
        ["uv", "run", "playwright", "install", "chromium"],
        cwd=SKILL_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        abort(f"Playwright 安裝失敗：\n{result.stderr[-300:]}")
    ok("Playwright Chromium 安裝完成")

# ─── Step 5：NotebookLM 登入 ───────────────────────────────────────────────────

def check_notebooklm_auth() -> bool:
    result = run(
        ["uv", "run", "notebooklm", "auth", "check", "--test"],
        cwd=SKILL_DIR,
        capture_output=True,
        text=True,
        timeout=15,
    )
    combined = f"{result.stdout}\n{result.stderr}".lower()
    return result.returncode == 0 and (
        "authenticated" in combined or "logged in" in combined or "ok" in combined
    )

def setup_notebooklm_auth():
    if check_notebooklm_auth():
        ok("NotebookLM 已登入")
        return

    warn("需要登入 NotebookLM")
    info("即將開啟瀏覽器，請用你的 Google 帳號登入")
    input("  按 Enter 開始...")
    result = run(["uv", "run", "notebooklm", "login"], cwd=SKILL_DIR)
    if result.returncode != 0:
        abort("NotebookLM 登入失敗，請稍後重試")
    ok("NotebookLM 登入成功")

# ─── Step 6：Google Drive 認證 ─────────────────────────────────────────────────

def check_google_auth() -> bool:
    """走 get_google_credentials()（與正式流程同一條路徑）確認認證有效且能打 Drive API"""
    result = run_in_skill(
        ["python", "-c",
         "import sys; sys.path.insert(0, 'scripts'); "
         "from extract_audio_sources import get_google_credentials; "
         "from googleapiclient.discovery import build; "
         "svc = build('drive', 'v3', credentials=get_google_credentials()); "
         "svc.files().list(pageSize=1, supportsAllDrives=True).execute(); "
         "print('OK')"],
        capture_output=True, text=True, timeout=180
    )
    return "OK" in result.stdout


def setup_google_auth():
    if check_google_auth():
        ok("Google Drive 認證有效")
        return

    # ── 正解：自有 OAuth client（credentials.json）──
    if not GOOGLE_CREDENTIALS.exists():
        warn(f"缺少 {GOOGLE_CREDENTIALS}")
        info("這是本 skill 的 OAuth client（app 身分），不含任何個人 token，可由團隊共用一份。")
        info("取得方式（二選一）：")
        info("  a) 向已設定好的同事索取（整份檔案可以直接複製）")
        info("  b) GCP Console → APIs & Services → Credentials → Create OAuth client ID")
        info("     → Application type 選「Desktop app」→ 下載 JSON")
        info("放置方式：")
        info(f"  mkdir -p {CONFIG_DIR}")
        info(f"  mv ~/Downloads/client_secret_*.json {GOOGLE_CREDENTIALS}")
        info(f"  chmod 600 {GOOGLE_CREDENTIALS}")
        info("兩個檔案的角色差異見 SKILL.md「認證檔案的角色」。")
        input("  放好後按 Enter 繼續（或直接 Enter 改走 ADC fallback）...")

    if GOOGLE_CREDENTIALS.exists():
        info("即將開啟瀏覽器完成授權，請用你的公司 Google 帳號登入")
        info("同意畫面顯示的 app 名稱與「查看及管理雲端硬碟」權限都是正常的")
        input("  按 Enter 開始...")
        # get_google_credentials() 自己會跑 InstalledAppFlow 並寫入 google_token.json
        if check_google_auth():
            ok(f"Google Drive 認證完成（token 已存於 {GOOGLE_TOKEN}）")
            return
        warn("授權流程跑完但 Drive API 測試仍失敗")
        info("常見原因：帳號不是目標共用雲端硬碟的成員（這不是 scope 問題）")
        info(f"要重跑授權可先刪掉 token：rm {GOOGLE_TOKEN}")
        abort("請排除後重試，或改走下方 ADC fallback")

    # ── fallback：ADC。只有使用者明確選擇才走 ──
    warn("將改用 ADC（gcloud）路徑")
    info("這條是 legacy 旗標、受 reauth session policy 影響，且 ADC 是全機共用狀態——")
    info("其他工具跑 `gcloud auth application-default login` 會把 scope 覆寫掉。")
    info("只適合互動式一次性救急，不要當排程的解。")
    if not ask_yes_no("仍要走 ADC fallback？", default=False):
        abort(f"已中止。請放置 {GOOGLE_CREDENTIALS} 後重跑本腳本")

    input("  按 Enter 開啟瀏覽器...")
    result = run([
        "gcloud", "auth", "login",
        "--enable-gdrive-access",
        "--update-adc",  # 不可省略：少了它只更新 gcloud 自己那份，ADC 不動，403 依舊
    ])
    if result.returncode != 0:
        abort("Google 認證失敗，請稍後重試")

    if not check_google_auth():
        abort(
            "認證完成，但 Drive API 測試失敗\n"
            "  診斷：https://oauth2.googleapis.com/tokeninfo?access_token=$(gcloud auth print-access-token)\n"
            "  沒報錯不等於 scope 拿到了，用上面的 URL 反查實際授到的 scope"
        )
    ok("Google Drive 認證完成（ADC fallback）")

# ─── Step 7：使用者設定 ────────────────────────────────────────────────────────

def ask(prompt_text: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    value = input(f"  {prompt_text}{hint}: ").strip()
    return value if value else default


def ask_yes_no(prompt_text: str, default: bool = False) -> bool:
    default_label = "Y/n" if default else "y/N"
    value = input(f"  {prompt_text} [{default_label}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def ensure_glossary_file(glossary_path: Path):
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    if glossary_path.exists():
        ok(f"glossary 已存在 → {glossary_path}")
        return

    template = {
        "global_terms": [],
        "meeting_terms": {},
    }
    with open(glossary_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
        f.write("\n")
    ok(f"已建立 glossary 範本 → {glossary_path}")


def load_glossary(glossary_path: Path) -> dict:
    with open(glossary_path, encoding="utf-8") as f:
        glossary = json.load(f)
    if not isinstance(glossary.get("global_terms"), list):
        glossary["global_terms"] = []
    if not isinstance(glossary.get("meeting_terms"), dict):
        glossary["meeting_terms"] = {}
    return glossary


def save_glossary(glossary_path: Path, glossary: dict):
    with open(glossary_path, "w", encoding="utf-8") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)
        f.write("\n")


def make_term_id(canonical: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in canonical)
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed or "term"


def setup_glossary_entries(glossary_path: Path, meetings: dict):
    glossary = load_glossary(glossary_path)
    global_count = len(glossary["global_terms"])
    meeting_count = sum(len(v) for v in glossary["meeting_terms"].values())

    print()
    print("  【設定 Glossary 專有名詞表】")
    print("  用來修正人名、專案名、縮寫與常見誤聽字。")
    print("  不可用來補會議事實、決策、數字或待辦。")
    info(f"目前共有 {global_count} 筆 global terms、{meeting_count} 筆 meeting terms")

    if not ask_yes_no("要現在新增 glossary 詞彙嗎？", default=False):
        tip(f"之後可直接編輯：{glossary_path}")
        return

    meeting_keys = list(meetings.keys())
    while True:
        print()
        scope = ask("詞彙範圍（global / meeting，空白結束）").lower()
        if not scope:
            break
        if scope not in {"global", "meeting"}:
            warn("請輸入 global 或 meeting")
            continue

        meeting_key = ""
        if scope == "meeting":
            if not meeting_keys:
                warn("目前尚未設定任何 meeting type，請先完成會議類型設定")
                continue
            info(f"可用 meeting types：{', '.join(meeting_keys)}")
            meeting_key = ask("套用到哪個 meeting type")
            if meeting_key not in meetings:
                warn("找不到這個 meeting type，請輸入已設定的名稱")
                continue

        canonical = ask("正式名稱 canonical（例：MCP、Alice、Project X）")
        if not canonical:
            warn("canonical 不可空白")
            continue
        aliases_raw = ask("別名 aliases（用逗號分隔，可空白）")
        term_type = ask("類型 type", "term")
        render_hint = ask("render_hint（可空白）")
        disambiguation = ask("disambiguation（可空白）")
        status = ask("status", "active")

        aliases = [alias.strip() for alias in aliases_raw.split(",") if alias.strip()]
        entry = {
            "id": make_term_id(canonical),
            "canonical": canonical,
            "aliases": aliases,
            "type": term_type,
            "status": status,
        }
        if render_hint:
            entry["render_hint"] = render_hint
        if disambiguation:
            entry["disambiguation"] = disambiguation

        if scope == "global":
            glossary["global_terms"].append(entry)
        else:
            glossary["meeting_terms"].setdefault(meeting_key, []).append(entry)

        ok(f"已加入 glossary term：{canonical}")

    save_glossary(glossary_path, glossary)
    ok(f"glossary 已更新 → {glossary_path}")


def setup_config(with_audio: bool):
    existing_meetings = {}
    existing_slack_token = ""
    existing_glossary_path = str(CONFIG_DIR / "glossary.json")
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            existing = json.load(f)
        existing_meetings = existing.get("meetings", {})
        existing_slack_token = existing.get("slack_bot_token", "")
        existing_glossary_path = existing.get("glossary_path", existing_glossary_path)
        info("找到現有設定（現有會議類型將保留，可新增或略過）")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Slack Bot Token（全域設定）
    print()
    print("  【設定 Slack Bot Token】")
    print("  至 api.slack.com → 你的 App → OAuth & Permissions → Bot User OAuth Token")
    print("  格式：xoxb-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxxxxxxxx")
    slack_bot_token = ask(
        "Slack Bot Token（空白跳過 Slack 通知功能）",
        existing_slack_token,
    )

    # 預設 prompt
    user_prompt = CONFIG_DIR / "prompt.md"
    if not user_prompt.exists():
        shutil.copy(SKILL_DIR / "references" / "default-prompt.md", user_prompt)
        info(f"已複製預設 prompt → {user_prompt}（可自行編輯）")
    glossary_path = Path(existing_glossary_path).expanduser()
    ensure_glossary_file(glossary_path)

    meetings = dict(existing_meetings)

    print()
    print("  【設定會議類型】")
    print("  每個會議類型對應一個 Shared Drive 資料夾。")
    if with_audio:
        print("  錄音檔支援另需 NotebookLM Notebook 名稱。")
    print("  可設定多個（例如：team週會、pm會議）。輸入空白結束。")
    print()

    while True:
        print(f"  目前已有會議類型：{list(meetings.keys()) or '（無）'}")
        key = input("  新增/更新會議類型（例：team週會），空白則完成：").strip()
        if not key:
            break

        existing_m = meetings.get(key, {})
        print(f"  ── 設定「{key}」──")

        notebook = existing_m.get("notebook_name", "")
        if with_audio:
            notebook = ask(
                "NotebookLM Notebook 名稱（錄音檔支援使用，例：Team 會議記錄）",
                notebook,
            )
            tip(f"請確認已在 notebooklm.google.com 手動建立名為「{notebook}」的 Notebook")
            tip("若 Notebook 不存在，執行錄音檔支援時會報錯：找不到 Notebook")
        print("  請從瀏覽器開啟 Shared Drive 資料夾，複製網址中的 Folder ID")
        print("  https://drive.google.com/drive/folders/【這段就是 Folder ID】")
        folder_id = ask(
            "Shared Drive Folder ID",
            existing_m.get("folder_id", ""),
        )
        folder_name = ask(
            "資料夾顯示名稱（用於 Slack 通知，例：team-meetings）",
            existing_m.get("folder_name", key),
        )
        series_name = ask(
            "會議系列簡稱（用於文件命名，例：Data內會）",
            existing_m.get("series_name", key),
        )
        print("  請在 Slack 中右鍵點擊 channel → View channel details → 複製 Channel ID")
        slack_channel = ask(
            "Slack Channel ID（例：C0XXXXXXXXX，空白跳過）",
            existing_m.get("slack_channel", ""),
        )

        meetings[key] = {
            "notebook_name": notebook,
            "folder_id": folder_id,
            "folder_name": folder_name,
            "series_name": series_name,
            "slack_channel": slack_channel,
            "attendees": existing_m.get("attendees", []),
            "custom_prompt": existing_m.get("custom_prompt", ""),
        }
        ok(f"「{key}」已設定")
        print()

    if not meetings:
        warn("未設定任何會議類型，稍後請手動編輯 config.json")

    config = {
        "slack_bot_token": slack_bot_token,
        "meetings": meetings,
        "prompt_path": str(user_prompt),
        "glossary_path": str(glossary_path),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    ok(f"設定已儲存 → {CONFIG_PATH}")
    tip("與會者（attendees）與補充說明（custom_prompt）請直接編輯 config.json")
    setup_glossary_entries(glossary_path, meetings)
    tip(f"專有名詞對應表位置：{glossary_path}")

# ─── 最終驗證 ──────────────────────────────────────────────────────────────────

def final_verify():
    result = run_in_skill(
        ["python", "-c",
         "import json, pathlib; "
         "cfg = json.loads(pathlib.Path('~/.config/generate-meeting-notes/config.json').expanduser().read_text()); "
         "keys = list(cfg.get('meetings', {}).keys()); "
         "print('OK:', ', '.join(keys) if keys else '（無會議類型）')"],
        capture_output=True, text=True, timeout=15
    )
    if "OK:" in result.stdout:
        meetings_info = result.stdout.split("OK:")[-1].strip()
        ok(f"驗證通過（會議類型：{meetings_info}）")
    else:
        warn("驗證出現問題，但可能不影響使用")
        if result.stderr:
            info(result.stderr[:200])

# ─── 主程式 ────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="設定 generate-meeting-notes。預設準備文字輸入 source preparation 與 main synthesis。"
    )
    parser.add_argument(
        "--with-audio",
        action="store_true",
        help="同時準備錄音檔支援（ffmpeg、Playwright Chromium、NotebookLM 登入）",
    )
    return parser.parse_args()

def main():
    args = parse_args()
    total = 7 if args.with_audio else 5

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║      Generate Meeting Notes - Text 設定          ║")
    print("╚══════════════════════════════════════════════════╝")
    if args.with_audio:
        info("本次會同時設定錄音檔支援。")
    else:
        info("預設設定逐字稿/文字紀錄 source preparation 與 main synthesis；錄音檔支援可日後用 --with-audio 啟用。")

    step(1, total, "檢查 uv（Python 套件管理器）")
    check_install_uv()  # 透過 install.sh 通常已存在；直接執行 setup.py 時的保險

    current_step = 2
    if args.with_audio:
        step(current_step, total, "檢查 ffmpeg（錄音檔處理）")
        check_install_ffmpeg()
        current_step += 1

    step(current_step, total, "檢查 gcloud（Google 雲端工具）")
    check_install_gcloud()
    current_step += 1

    step(current_step, total, "安裝 Python 套件")
    setup_python_deps(args.with_audio)
    current_step += 1

    if args.with_audio:
        step(current_step, total, "登入 NotebookLM")
        setup_notebooklm_auth()
        current_step += 1

    step(current_step, total, "設定 Google Drive 認證")
    setup_google_auth()
    current_step += 1

    step(current_step, total, "填寫個人設定")
    setup_config(args.with_audio)

    header("驗證")
    final_verify()

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║  設定完成！                                       ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  執行範例：                                       ║")
    print("║  逐字稿：請 Agent 用 generate-meeting-notes 讀取文字 ║")
    if args.with_audio:
        print("║  錄音檔：                                         ║")
        print(f"║  1. cd {str(SKILL_DIR)[:38]:<38} ║")
        print("║  2. uv run scripts/extract_audio_sources.py \\    ║")
        print("║        ~/Desktop/meeting_YYYYMMDD.m4a \\          ║")
        print("║        --meeting team週會                        ║")
    else:
        print("║  需要錄音檔支援時，請再執行：                    ║")
        print("║  uv run scripts/setup.py --with-audio            ║")
    print("╚══════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
