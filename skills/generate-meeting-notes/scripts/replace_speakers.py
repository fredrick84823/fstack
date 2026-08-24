#!/usr/bin/env python3
"""
[LEGACY] replace_speakers.py - 批次替換 Google Doc 中的 [Speaker N] 佔位符

此腳本已不再是主流程。若逐字稿或 NotebookLM 產出 Speaker N / SPEAKER_00
等匿名講者標籤，Transcript 模式下會議記錄預設維持原始標籤，不需要事後替換。

用法：
    uv run scripts/replace_speakers.py --doc-id <DOC_ID> \
        --mapping "Speaker 1=Alice" "Speaker 2=Bob" "Speaker 3=Carol"

也可直接傳入 Google Doc 連結：
    uv run scripts/replace_speakers.py \
        --doc-id https://docs.google.com/document/d/XXXXX/edit \
        --mapping "Speaker 1=Alice" "Speaker 2=Bob"
"""

import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent


def parse_doc_id(raw: str) -> str:
    """從完整 URL 或 doc ID 字串中提取 doc ID"""
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", raw)
    if m:
        return m.group(1)
    return raw.strip()


def replace_in_doc(doc_id: str, mapping: dict[str, str]):
    """使用 Google Docs API 的 replaceAllText 批次替換佔位符"""
    # 借用 extraction 腳本的 get_google_credentials
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "extract_audio_sources",
        SKILL_DIR / "scripts" / "extract_audio_sources.py",
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)  # type: ignore

    from googleapiclient.discovery import build
    creds = mod.get_google_credentials()
    docs = build("docs", "v1", credentials=creds)

    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": f"[{speaker}]", "matchCase": True},
                "replaceText": name,
            }
        }
        for speaker, name in mapping.items()
    ]

    result = docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    replaced = sum(
        r.get("replaceAllText", {}).get("occurrencesChanged", 0)
        for r in result.get("replies", [])
    )
    print(f"✅ 完成：共替換 {replaced} 處")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="替換 Google Doc 中的 Speaker 佔位符")
    parser.add_argument(
        "--doc-id", required=True,
        help="Google Doc ID 或完整連結",
    )
    parser.add_argument(
        "--mapping", nargs="+", required=True,
        metavar="SPEAKER=NAME",
        help='替換對應，例："Speaker 1=Alice" "Speaker 2=Bob"',
    )
    args = parser.parse_args()

    doc_id = parse_doc_id(args.doc_id)

    mapping = {}
    for item in args.mapping:
        if "=" not in item:
            print(f"❌ 格式錯誤（需含 =）：{item}")
            sys.exit(1)
        speaker, name = item.split("=", 1)
        mapping[speaker.strip()] = name.strip()

    print(f"📄 Doc ID：{doc_id}")
    for speaker, name in mapping.items():
        print(f"   [{speaker}] → {name}")
    print()

    replace_in_doc(doc_id, mapping)


if __name__ == "__main__":
    main()
