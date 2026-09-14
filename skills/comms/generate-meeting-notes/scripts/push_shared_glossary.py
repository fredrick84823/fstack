#!/usr/bin/env python3
"""
push_shared_glossary.py - 把本機 glossary 的新條目回寫共用檔，並把本機瘦身成 delta。

共用 glossary 原本只有拉下來的路。缺的兩件事不是一件：

    ┌─ push 缺       → 同事永遠拿不到本機新發現的詞彙
    └─ pull 形同半殘 → 本機是共用檔的舊複本，同 id 本機勝，
                       同事對既有條目的改動被本機的舊值壓過

**不整檔覆蓋。** Drive 上傳是覆蓋語意，把本機整份推上去會讓同事這期間對既有條目的
改動無聲消失。所以流程是 read-merge-write：讀共用檔 → 只把要推的條目疊上去 → 寫回。

**已改動的既有條目預設不推。** 那些「差異」多半是共用檔往前走、本機沒跟上，推上去
等於幫同事回滾。要推必須明示 `--include-modified`，而且 dry-run 已經把 diff 印出來。

**不掛進產會議記錄的流程**，只能明示執行 —— 共用詞彙表被無聲改動比詞彙錯誤更難查。

用法（與 SKILL.md 一致，都從 skill 目錄用 uv 跑）：
    uv run scripts/push_shared_glossary.py                       # dry-run，看 diff
    uv run scripts/push_shared_glossary.py --push                # 只推 new
    uv run scripts/push_shared_glossary.py --push --include-modified
    uv run scripts/push_shared_glossary.py --push --prune-local  # 推完把已上游的條目移出本機

退出碼：
    0  完成（dry-run、或 --push 成功、或沒東西可推）
    1  中止：憑證／Drive API 失敗、樂觀鎖偵測到共用檔被改、五條驗證未過
    2  參數或設定錯誤：未設定 shared_glossary.file_id、--prune-local 沒配 --push
"""

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

GLOBAL_SCOPE = "global"

# 五條驗證的代號。任一條不通過就中止不上傳。
# 代號存在的理由是**可鑑別**：驗收腳本進不了 CI，守它的是 unit test 裡的對照組 ——
# 每壞一件事必須且「只有」對應那條變紅。回傳訊息字串的話，測試只能比對子字串，
# 「有紅」與「只有那條紅」就分不開了。
V_FIELDS = "fields_incomplete"
V_DUP_ID = "duplicate_id"
V_ALIAS = "alias_conflict"
V_COUNT = "count_shrunk"
V_STALE = "last_updated_stale"


# ─── 純函式層（Seam ①：dict in → dict out，不碰網路、不碰檔案）─────────────

def _norm(entry: dict) -> str:
    """條目的比較形式。list 欄位排序後比 —— aliases 換個順序不是一次改動。"""
    normalized = {
        k: sorted(v, key=str) if isinstance(v, list) else v
        for k, v in entry.items()
    }
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def flatten(doc: dict) -> dict:
    """把一份 glossary 攤成 {(scope, id): entry}。

    scope 是 "global" 或 meeting_key —— 同一個 id 在 global 與某場會議底下是**兩筆**
    不同的條目（下游 load_glossary_entries 也是這樣取的），不能壓成一筆。
    key 的取法與 pull 端的 dedup 同一把（`id` 缺席時退回 `canonical`）—— 兩邊不同把
    尺的話，這裡判成「new」的條目在下游會與既有條目撞成同一筆。兩個都空才略過，
    而那種條目照樣進得了 `validate_merged` 的 `fields_incomplete`：在這裡被略過的是
    key，不是條目本身，缺欄位是驗證要擋下的事，不是這裡要靜靜吞掉的事。
    條目不是 dict 的略過。
    """
    out: dict = {}
    buckets = [(GLOBAL_SCOPE, doc.get("global_terms") or [])]
    for meeting_key, terms in (doc.get("meeting_terms") or {}).items():
        buckets.append((meeting_key, terms or []))

    for scope, terms in buckets:
        if not isinstance(terms, list):
            continue
        for entry in terms:
            if not isinstance(entry, dict):
                continue
            entry_id = str(entry.get("id") or entry.get("canonical") or "").strip()
            if not entry_id:
                continue
            out.setdefault((scope, entry_id), entry)
    return out


def classify(local_doc: dict, shared_doc: dict) -> dict:
    """分類本機相對共用檔的狀態。回傳 {"new": [...], "modified": [...], "same": [...]}。

    每個元素是 {"key": (scope, id), "local": entry, "shared": entry|None}。
    只看「本機有的」—— 共用檔獨有的條目不在任何一桶裡，它們不需要任何動作。
    """
    shared_flat = flatten(shared_doc)
    buckets: dict = {"new": [], "modified": [], "same": []}

    for key, local_entry in flatten(local_doc).items():
        shared_entry = shared_flat.get(key)
        if shared_entry is None:
            bucket = "new"
        elif _norm(shared_entry) == _norm(local_entry):
            bucket = "same"
        else:
            bucket = "modified"
        buckets[bucket].append({"key": key, "local": local_entry, "shared": shared_entry})

    for items in buckets.values():
        items.sort(key=lambda item: (item["key"][0], item["key"][1]))
    return buckets


def diff_lines(change: dict) -> list[str]:
    """單筆的逐欄 diff。new 印全欄，modified 只印有差的欄。"""
    scope, entry_id = change["key"]
    local, shared = change["local"], change["shared"]
    head = f"  [{scope}] {entry_id}"

    if shared is None:
        return [head] + [f"      + {k}: {json.dumps(v, ensure_ascii=False)}"
                         for k, v in sorted(local.items())]

    lines = [head]
    for field in sorted(set(shared) | set(local)):
        before, after = shared.get(field), local.get(field)
        if before != after:
            lines.append(f"      共用: {field} = {json.dumps(before, ensure_ascii=False)}")
            lines.append(f"      本機: {field} = {json.dumps(after, ensure_ascii=False)}")
    return lines


def merge(shared_doc: dict, local_doc: dict, keys, now: str) -> dict:
    """read-merge-write 的 merge：以共用檔為底，只把 keys 指到的本機條目疊上去。

    共用檔獨有的條目原封不動留著 —— 整檔覆蓋正是這支腳本存在的理由。
    """
    merged = copy.deepcopy(shared_doc)
    merged.setdefault("global_terms", [])
    merged.setdefault("meeting_terms", {})
    local_flat = flatten(local_doc)

    for key in keys:
        entry = local_flat.get(key)
        if entry is None:
            continue
        scope, entry_id = key
        if scope == GLOBAL_SCOPE:
            terms = merged["global_terms"]
        else:
            terms = merged["meeting_terms"].setdefault(scope, [])

        replaced = False
        for i, existing in enumerate(terms):
            if not isinstance(existing, dict):
                continue
            existing_id = str(existing.get("id") or existing.get("canonical") or "").strip()
            if existing_id == entry_id:
                terms[i] = copy.deepcopy(entry)
                replaced = True
                break
        if not replaced:
            terms.append(copy.deepcopy(entry))

    merged["last_updated"] = now
    return merged


def _all_entries(doc: dict) -> list[tuple[str, dict]]:
    """(scope, entry) 逐筆列出，**不去重**。驗證要看的是原樣，去重會把重複 id 藏掉。"""
    out: list[tuple[str, dict]] = []
    buckets = [(GLOBAL_SCOPE, doc.get("global_terms") or [])]
    for meeting_key, terms in (doc.get("meeting_terms") or {}).items():
        buckets.append((meeting_key, terms or []))
    for scope, terms in buckets:
        if isinstance(terms, list):
            out.extend((scope, e) for e in terms if isinstance(e, dict))
    return out


def validate_merged(merged: dict, original: dict) -> list[tuple[str, str]]:
    """五條驗證。回傳 [(代號, 說明)]；空 list 才能上傳。

    五條彼此獨立 —— 壞一件事只會有對應那一條回報。所以：
      · id 重複只看**非空**的 id（空 id 是「欄位不完整」那條的事，不是重複）
      · alias 衝突只看**有 canonical** 的條目（同上）
      · 筆數數的是原樣筆數，重複 id 不會順帶把它壓低
    連坐的話 `--include-modified` 的判斷會建在錯的訊號上。
    """
    problems: list[tuple[str, str]] = []
    entries = _all_entries(merged)

    incomplete = [
        f"[{scope}] {entry.get('id') or entry.get('canonical') or '<無 id>'}"
        for scope, entry in entries
        if not str(entry.get("id") or "").strip() or not str(entry.get("canonical") or "").strip()
    ]
    if incomplete:
        problems.append((V_FIELDS, "缺 id 或 canonical：" + "、".join(incomplete)))

    seen: set[tuple[str, str]] = set()
    dups: list[str] = []
    for scope, entry in entries:
        entry_id = str(entry.get("id") or "").strip()
        if not entry_id:
            continue
        if (scope, entry_id) in seen:
            dups.append(f"[{scope}] {entry_id}")
        seen.add((scope, entry_id))
    if dups:
        problems.append((V_DUP_ID, "id 重複：" + "、".join(dups)))

    alias_owner: dict[str, str] = {}
    conflicts: list[str] = []
    for _, entry in entries:
        canonical = str(entry.get("canonical") or "").strip()
        if not canonical:
            continue
        for alias in entry.get("aliases") or []:
            alias = str(alias).strip()
            if not alias:
                continue
            owner = alias_owner.setdefault(alias, canonical)
            if owner != canonical:
                conflicts.append(f"{alias} → {owner} / {canonical}")
    if conflicts:
        problems.append((V_ALIAS, "同一個 alias 指到兩個 canonical：" + "、".join(conflicts)))

    before, after = len(_all_entries(original)), len(entries)
    if after < before:
        problems.append((V_COUNT, f"筆數變少：{before} → {after}"))

    merged_stamp = str(merged.get("last_updated") or "").strip()
    if not merged_stamp or merged_stamp == str(original.get("last_updated") or "").strip():
        problems.append((V_STALE, "last_updated 沒有更新"))

    return problems


def prune_local(local_doc: dict, shared_doc: dict) -> dict:
    """把已經與共用檔一字不差的條目從本機移除，讓 pull 接管。

    只移除**內容完全相同**的：本機還沒上游的改動留著，否則瘦身會變成無聲丟棄。
    空掉的 meeting_terms bucket 一併移除，剩下的才是真正的 delta。
    """
    shared_flat = flatten(shared_doc)

    def keep(scope: str, entry) -> bool:
        if not isinstance(entry, dict):
            return True
        entry_id = str(entry.get("id") or entry.get("canonical") or "").strip()
        upstream = shared_flat.get((scope, entry_id))
        return upstream is None or _norm(upstream) != _norm(entry)

    # 先整份深拷貝，之後只在**拷貝**上篩 —— 留下來的條目也必須是新物件。
    # 從 local_doc 篩的話回傳值與參數會共用同一批 dict，呼叫端改一邊另一邊跟著變。
    pruned = copy.deepcopy(local_doc)
    pruned["global_terms"] = [e for e in (pruned.get("global_terms") or [])
                              if keep(GLOBAL_SCOPE, e)]
    meeting_terms = {}
    for meeting_key, terms in (pruned.get("meeting_terms") or {}).items():
        kept = [e for e in (terms or []) if keep(meeting_key, e)]
        if kept:
            meeting_terms[meeting_key] = kept
    pruned["meeting_terms"] = meeting_terms
    return pruned


def keys_to_push(buckets: dict, include_modified: bool) -> list:
    """要推哪些 key。modified 預設不推 —— 那些差異多半是共用檔往前走、本機沒跟上。"""
    keys = [c["key"] for c in buckets["new"]]
    if include_modified:
        keys += [c["key"] for c in buckets["modified"]]
    return keys


def summary_line(buckets: dict) -> str:
    return (f"📤 本機相對共用檔：new {len(buckets['new'])} 筆"
            f"／modified {len(buckets['modified'])} 筆"
            f"／same {len(buckets['same'])} 筆")


# ─── Drive I/O（不測，行為靠上面那層純函式撐）───────────────────────────────

def _shared_module():
    """`extract_audio_sources` 的設定與憑證這裡照用，不另外寫一份。

    在函式裡 import 而不是模組頂層：上面那整層純函式不需要它，頂層 import 會讓
    「載得進來」綁在 Google 套件與 sys.path 上，也會把另一支腳本的模組名一起拖進
    mutmut 的 trampoline 記錄裡（那邊認的是路徑推出來的模組名）。
    """
    sys.path.insert(0, str(Path(__file__).parent))
    import extract_audio_sources
    return extract_audio_sources


def _drive():
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=_shared_module().get_google_credentials())


def read_shared(drive, file_id: str) -> tuple[dict, str]:
    """讀共用檔內容與版本標記。版本標記用來當樂觀鎖 —— Drive 沒有 CAS。"""
    meta = drive.files().get(
        fileId=file_id, fields="version,md5Checksum", supportsAllDrives=True
    ).execute()
    raw = drive.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
    return json.loads(raw.decode("utf-8")), f"{meta.get('version')}/{meta.get('md5Checksum')}"


def write_shared(drive, file_id: str, doc: dict) -> None:
    from googleapiclient.http import MediaInMemoryUpload

    payload = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    drive.files().update(
        fileId=file_id,
        media_body=MediaInMemoryUpload(payload, mimetype="application/json"),
        supportsAllDrives=True,
    ).execute()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把本機 glossary 的新條目回寫共用檔（read-merge-write），並可把本機瘦身成 delta",
    )
    parser.add_argument("--push", action="store_true",
                        help="實際寫回共用檔。不加就是 dry-run（預設）")
    parser.add_argument("--include-modified", action="store_true",
                        help="連「已改動的既有條目」一起推。預設只警告不推")
    parser.add_argument("--prune-local", action="store_true",
                        help="推成功後把已上游的條目從本機移除，讓 pull 接管（需配 --push）")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.prune_local and not args.push:
        print("❌ --prune-local 需要 --push：沒推上去就瘦身等於丟資料", file=sys.stderr)
        return 2

    config = _shared_module().load_config()
    file_id = str((config.get("shared_glossary") or {}).get("file_id", "")).strip()
    if not file_id:
        print("❌ config.json 沒有 shared_glossary.file_id，沒有共用檔可推", file=sys.stderr)
        return 2

    local_path = Path(
        config.get("glossary_path", _shared_module().DEFAULT_GLOSSARY_PATH)
    ).expanduser()
    try:
        local_doc = json.loads(local_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"❌ 本機 glossary 讀不到或解析失敗：{local_path}（{e}）", file=sys.stderr)
        return 2

    try:
        drive = _drive()
        shared_doc, version_before = read_shared(drive, file_id)
    except Exception as e:
        print(f"❌ 共用 glossary 讀取失敗，中止：{e}", file=sys.stderr)
        return 1

    buckets = classify(local_doc, shared_doc)
    print(summary_line(buckets))

    for bucket, label in (("new", "new（會推）"), ("modified", "modified"), ("same", "same")):
        if not buckets[bucket]:
            continue
        print(f"\n── {label} ──")
        if bucket == "same":
            print("  " + "、".join(f"[{s}] {i}" for s, i in
                                   (c["key"] for c in buckets["same"])))
            continue
        for change in buckets[bucket]:
            print("\n".join(diff_lines(change)))

    if buckets["modified"] and not args.include_modified:
        print(f"\n⚠️  {len(buckets['modified'])} 筆既有條目本機與共用檔不同，預設不推。"
              "\n   這種差異多半是共用檔往前走、本機沒跟上，推上去等於幫同事回滾。"
              "\n   看過上面的 diff 確定要推，才加 --include-modified。")

    push_keys = keys_to_push(buckets, args.include_modified)

    if not args.push:
        print(f"\n🔍 dry-run（預設）。要實際寫回請加 --push —— 會推 {len(push_keys)} 筆。")
        return 0

    if not push_keys:
        print("\n✅ 沒有要推的條目，共用檔不動。")
    else:
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        merged = merge(shared_doc, local_doc, push_keys, now)

        problems = validate_merged(merged, shared_doc)
        if problems:
            print("\n❌ 驗證未過，不上傳：", file=sys.stderr)
            for code, detail in problems:
                print(f"   {code}: {detail}", file=sys.stderr)
            return 1

        # 樂觀鎖：Drive 沒有 CAS，只能在寫入前再讀一次版本，變了就中止。
        try:
            _, version_recheck = read_shared(drive, file_id)
        except Exception as e:
            print(f"❌ 寫入前重讀共用檔失敗，中止：{e}", file=sys.stderr)
            return 1
        if version_recheck != version_before:
            print(f"❌ 共用檔在這段期間被改過（{version_before} → {version_recheck}），"
                  "中止不上傳。重跑一次即可。", file=sys.stderr)
            return 1

        try:
            write_shared(drive, file_id, merged)
            shared_doc, version_after = read_shared(drive, file_id)
        except Exception as e:
            print(f"❌ 寫回共用檔失敗：{e}", file=sys.stderr)
            return 1
        print(f"\n✅ 已推 {len(push_keys)} 筆，共用檔現在 "
              f"{len(_all_entries(shared_doc))} 筆（版本 {version_before} → {version_after}）")

    # 寫入後刷新本機快取：不刷的話下一次產會議記錄會在 TTL 內抓到舊值。
    cache_path = _shared_module().SHARED_GLOSSARY_CACHE
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(shared_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"♻️  已刷新共用 glossary 快取：{cache_path}")

    if args.prune_local:
        pruned = prune_local(local_doc, shared_doc)
        before = len(flatten(local_doc))
        after = len(flatten(pruned))
        local_path.write_text(
            json.dumps(pruned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"🧹 本機瘦身成 delta：{before} 筆 → {after} 筆（{local_path}）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
