"""共用 glossary 回寫的純函式層 —— **不打網路**。

`read_shared` / `write_shared` / `_drive` / `main` 一個都不碰（issue #8：Drive 呼叫
不測）。這裡量的是分類、合併、驗證、瘦身這四段純函式，以及兩條可機械判定的契約
（dry-run 是預設、不掛進產會議記錄的流程）。

**重心是五條驗證的「只有那條紅」。** 驗收腳本進不了 CI（要真 Drive ＋ token），
它自己的靜默失敗沒人守 —— 唯一守得住的地方是斷言層。所以每條驗證都有一個
「只壞那一件事」的對照組，斷言回傳的代號集合**恰好等於** {那一條}，不是「包含」。
連坐的話（alias 衝突順便讓筆數也紅）就分不出擋下的是哪一件事，而
`--include-modified` 的判斷會建在錯的訊號上。

樣本一律從 `original()` / `merged_ok()` 複製出來再改一個地方，判紅的原因不會互相汙染
（同 `test_layout_contract.py` 的作法）。
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from tests.unit.conftest import ROOT, SCRIPTS, load_script

mod = load_script("push_shared_glossary")

GLOBAL = mod.GLOBAL_SCOPE
MEETING_KEY = "data內會"

OLD_STAMP = "2026-09-01T00:00:00+08:00"
NEW_STAMP = "2026-09-14T10:30:00+08:00"


def original() -> dict:
    """合併前的共用檔：global 兩筆 ＋ 一場會議一筆，共三筆。"""
    return {
        "global_terms": [
            {
                "id": "mcp",
                "canonical": "MCP",
                "aliases": ["NCP"],
                "type": "technical_term",
                "status": "active",
            },
            {
                "id": "roas",
                "canonical": "ROAS",
                "aliases": ["羅阿斯"],
                "type": "technical_term",
                "status": "active",
            },
        ],
        "meeting_terms": {
            MEETING_KEY: [
                {
                    "id": "px",
                    "canonical": "Project X",
                    "aliases": ["PX"],
                    "type": "project",
                    "status": "active",
                }
            ]
        },
        "last_updated": OLD_STAMP,
    }


CAC = {
    "id": "cac",
    "canonical": "CAC",
    "aliases": ["獲客成本"],
    "type": "technical_term",
    "status": "active",
}


def merged_ok() -> dict:
    """合格的合併結果：原本三筆全在，加一筆新的，`last_updated` 已往前。"""
    doc = original()
    doc["global_terms"].append(copy.deepcopy(CAC))
    doc["last_updated"] = NEW_STAMP
    return doc


def codes(merged: dict, base: dict | None = None) -> set[str]:
    issues = mod.validate_merged(merged, original() if base is None else base)
    assert isinstance(issues, list)
    for issue in issues:
        code, why = issue
        assert isinstance(code, str) and isinstance(why, str)
        assert why.strip(), f"{code} 沒有說明；操作者看不出擋下的是什麼"
    return {code for code, _ in issues}


# --------------------------------------------------------------------------- #
# flatten
# --------------------------------------------------------------------------- #


def test_flatten_keys_the_two_scopes_apart():
    flat = mod.flatten(original())

    assert set(flat) == {
        (GLOBAL, "mcp"),
        (GLOBAL, "roas"),
        (MEETING_KEY, "px"),
    }
    assert flat[(GLOBAL, "mcp")]["canonical"] == "MCP"
    assert flat[(MEETING_KEY, "px")]["canonical"] == "Project X"


def test_flatten_treats_the_same_id_under_global_and_a_meeting_as_two_entries():
    """同名不同 scope 是兩筆不同條目 —— 壓成一筆會讓某一邊被另一邊的定義蓋掉。"""
    doc = original()
    doc["meeting_terms"][MEETING_KEY].append(
        {"id": "mcp", "canonical": "某會議專用的 MCP", "aliases": []}
    )

    flat = mod.flatten(doc)

    assert flat[(GLOBAL, "mcp")]["canonical"] == "MCP"
    assert flat[(MEETING_KEY, "mcp")]["canonical"] == "某會議專用的 MCP"


@pytest.mark.parametrize("junk", ["不是 dict", None, []], ids=["str", "none", "list"])
def test_flatten_skips_entries_that_are_not_dicts(junk):
    """夾在**中間** —— 放最後的話「略過」與「就此中斷」分不出來。"""
    doc = original()
    doc["global_terms"].insert(1, junk)

    assert set(mod.flatten(doc)) == set(mod.flatten(original()))


def test_flatten_skips_an_entry_with_neither_id_nor_canonical():
    doc = original()
    doc["global_terms"].append({"id": "", "canonical": "", "aliases": []})

    assert set(mod.flatten(doc)) == set(mod.flatten(original()))


def test_flatten_keys_an_id_less_entry_by_its_canonical():
    """有 id 的與只有 canonical 的並存 —— 只認得其中一種就會漏掉另一半。"""
    doc = original()
    doc["global_terms"].append({"canonical": "純 canonical", "aliases": []})

    flat = mod.flatten(doc)

    assert flat[(GLOBAL, "mcp")]["canonical"] == "MCP"
    assert flat[(GLOBAL, "純 canonical")]["aliases"] == []


@pytest.mark.parametrize("bad", [{"id": "x"}, "不是 list"], ids=["dict", "str"])
def test_flatten_skips_a_scope_whose_terms_are_not_a_list(bad):
    """壞掉的那場排在**前面** —— 就此中斷的話後面那場整場不見。"""
    doc = {
        "global_terms": [],
        "meeting_terms": {"壞掉的會議": bad, MEETING_KEY: original()["meeting_terms"][MEETING_KEY]},
    }

    assert set(mod.flatten(doc)) == {(MEETING_KEY, "px")}


def test_flatten_of_an_empty_doc_is_empty():
    assert mod.flatten({}) == {}
    assert mod.flatten({"global_terms": [], "meeting_terms": {}}) == {}


# --------------------------------------------------------------------------- #
# classify
# --------------------------------------------------------------------------- #


def classified() -> dict:
    """本機 = 共用檔的 mcp（原封不動）＋ 改過的 roas ＋ 全新的 cac。

    共用檔的 `px` 本機沒有 —— 它不該出現在任何一桶。
    """
    local = {
        "global_terms": [
            {
                "id": "mcp",
                "canonical": "MCP",
                "aliases": ["NCP"],
                "type": "technical_term",
                "status": "active",
            },
            {
                "id": "roas",
                "canonical": "ROAS",
                "aliases": ["羅阿斯", "投報率"],
                "type": "technical_term",
                "status": "active",
            },
            copy.deepcopy(CAC),
        ],
        "meeting_terms": {},
        "last_updated": NEW_STAMP,
    }
    return mod.classify(local, original())


def only_keys(bucket: list) -> list:
    return [change["key"] for change in bucket]


def test_classify_sorts_local_entries_into_new_modified_same():
    buckets = classified()

    assert only_keys(buckets["new"]) == [(GLOBAL, "cac")]
    assert only_keys(buckets["modified"]) == [(GLOBAL, "roas")]
    assert only_keys(buckets["same"]) == [(GLOBAL, "mcp")]


def test_classify_carries_both_sides_of_each_change():
    buckets = classified()

    new = buckets["new"][0]
    assert new["local"]["canonical"] == "CAC"
    assert new["shared"] is None, "新條目共用檔那側必須是 None，不是空 dict"

    changed = buckets["modified"][0]
    assert changed["local"]["aliases"] == ["羅阿斯", "投報率"]
    assert changed["shared"]["aliases"] == ["羅阿斯"]


def test_classify_leaves_shared_only_entries_out_of_every_bucket():
    """共用檔獨有的 `px` 進了任何一桶都會被當成「要推的東西」往回推。"""
    buckets = classified()

    assert (MEETING_KEY, "px") not in [
        change["key"] for bucket in buckets.values() for change in bucket
    ]


def test_classify_does_not_call_a_reordered_alias_list_modified():
    """aliases 換順序不算改動 —— 算的話每次 dump 都會冒出一堆假 modified。"""
    local = original()
    local["global_terms"][0]["aliases"] = list(reversed(["NCP", "Model Context Protocol"]))
    shared = original()
    shared["global_terms"][0]["aliases"] = ["NCP", "Model Context Protocol"]

    buckets = mod.classify(local, shared)

    assert only_keys(buckets["modified"]) == []
    assert (GLOBAL, "mcp") in only_keys(buckets["same"])


@pytest.mark.parametrize(
    "local_entry,shared_entry",
    [
        (
            {"id": "x", "canonical": "X", "aliases": ["a"]},
            {"aliases": ["a"], "canonical": "X", "id": "x"},
        ),
        (
            {"id": "x", "canonical": "X", "tags": ["b", "a"]},
            {"id": "x", "canonical": "X", "tags": ["a", "b"]},
        ),
        (
            {"id": "x", "canonical": "專案代號", "aliases": ["內部叫法"]},
            {"id": "x", "canonical": "專案代號", "aliases": ["內部叫法"]},
        ),
    ],
    ids=["field-order", "other-list-order", "zh-hant"],
)
def test_classify_calls_these_two_the_same_entry(local_entry, shared_entry):
    """欄位順序、aliases 以外的 list 順序、繁中的跳脫方式都不是改動 ——
    算改動的話每次 dump 都會冒出一堆假 modified。"""
    buckets = mod.classify(
        {"global_terms": [local_entry], "meeting_terms": {}},
        {"global_terms": [shared_entry], "meeting_terms": {}},
    )

    assert only_keys(buckets["same"]) == [(GLOBAL, "x")]
    assert buckets["modified"] == []


def scoped(alias: str) -> dict:
    """兩場會議，scope 的大小順序與 id 的大小順序**相反**。"""
    return {
        "global_terms": [],
        "meeting_terms": {
            "aaa會議": [
                {"id": "z-mod", "canonical": "ZM", "aliases": [alias]},
                {"id": "z-same", "canonical": "ZS", "aliases": []},
            ],
            "zzz會議": [
                {"id": "a-mod", "canonical": "AM", "aliases": [alias]},
                {"id": "a-same", "canonical": "AS", "aliases": []},
            ],
        },
    }


def test_classify_sorts_by_scope_before_id():
    """只照 id 排的話，同一場會議的條目會被別場的插在中間。"""
    local = scoped("改過")
    local["meeting_terms"]["aaa會議"].append({"id": "z-new", "canonical": "ZN", "aliases": []})
    local["meeting_terms"]["zzz會議"].append({"id": "a-new", "canonical": "AN", "aliases": []})

    buckets = mod.classify(local, scoped("原本"))

    for bucket, suffix in (("new", "new"), ("modified", "mod"), ("same", "same")):
        assert only_keys(buckets[bucket]) == [
            ("aaa會議", f"z-{suffix}"),
            ("zzz會議", f"a-{suffix}"),
        ]


def test_classify_against_an_empty_shared_doc_makes_everything_new():
    buckets = mod.classify(original(), {"global_terms": [], "meeting_terms": {}})

    assert len(buckets["new"]) == 3
    assert buckets["modified"] == []
    assert buckets["same"] == []


# --------------------------------------------------------------------------- #
# keys_to_push
# --------------------------------------------------------------------------- #


def test_keys_to_push_defaults_to_new_only():
    assert mod.keys_to_push(classified(), include_modified=False) == [(GLOBAL, "cac")]


def test_keys_to_push_adds_modified_only_when_asked():
    pushed = mod.keys_to_push(classified(), include_modified=True)

    assert sorted(pushed) == [(GLOBAL, "cac"), (GLOBAL, "roas")]


@pytest.mark.parametrize("include_modified", [False, True], ids=["plain", "include-modified"])
def test_keys_to_push_never_pushes_unchanged_entries(include_modified):
    assert (GLOBAL, "mcp") not in mod.keys_to_push(classified(), include_modified)


# --------------------------------------------------------------------------- #
# diff_lines
# --------------------------------------------------------------------------- #


def test_diff_lines_of_a_new_entry_prints_every_field():
    change = {"key": (GLOBAL, "cac"), "local": copy.deepcopy(CAC), "shared": None}

    text = "\n".join(mod.diff_lines(change))

    assert "cac" in text
    assert "CAC" in text
    assert "獲客成本" in text
    assert "technical_term" in text
    assert "\\u" not in text, "繁中跳脫成 \\uXXXX 的話 diff 讀不了"


def test_diff_lines_of_a_modified_entry_prints_only_the_fields_that_differ():
    """全欄都印的話 dry-run 的 diff 讀不出「同事改了哪裡」，`--include-modified`
    就變成閉著眼睛按。"""
    shared = {"id": "roas", "canonical": "ROAS", "aliases": ["羅阿斯"], "type": "technical_term"}
    local = {**shared, "aliases": ["羅阿斯", "投報率"]}
    change = {"key": (GLOBAL, "roas"), "local": local, "shared": shared}

    text = "\n".join(mod.diff_lines(change))

    assert "投報率" in text
    assert "羅阿斯" in text, "共用檔那行的中文"
    assert "\\u" not in text, "繁中跳脫成 \\uXXXX 的話 diff 讀不了"
    assert "technical_term" not in text, "沒差的欄位不該出現在 diff 裡"


def test_diff_lines_names_a_field_only_one_side_has():
    """單邊才有的欄位被吃掉的話，dry-run 看不出同事新增或刪掉了什麼欄位。"""
    shared = {"id": "roas", "canonical": "ROAS", "legacy_note": "舊註解"}
    local = {"id": "roas", "canonical": "ROAS", "render_hint": "粗體"}
    change = {"key": (GLOBAL, "roas"), "local": local, "shared": shared}

    text = "\n".join(mod.diff_lines(change))

    assert "render_hint" in text, "本機多出來的欄位"
    assert "legacy_note" in text, "共用檔才有、本機沒有的欄位"


def test_diff_lines_returns_strings():
    change = {"key": (GLOBAL, "cac"), "local": copy.deepcopy(CAC), "shared": None}

    lines = mod.diff_lines(change)

    assert lines and all(isinstance(line, str) for line in lines)


# --------------------------------------------------------------------------- #
# merge
# --------------------------------------------------------------------------- #


def local_for_merge() -> dict:
    """本機：改過的 roas ＋ 全新的 cac ＋ 一場共用檔沒有的會議。"""
    return {
        "global_terms": [
            {
                "id": "roas",
                "canonical": "ROAS",
                "aliases": ["羅阿斯", "投報率"],
                "type": "technical_term",
                "status": "active",
            },
            copy.deepcopy(CAC),
        ],
        "meeting_terms": {
            "rd週會": [{"id": "gmn", "canonical": "generate-meeting-notes", "aliases": []}]
        },
        "last_updated": NEW_STAMP,
    }


def test_merge_appends_a_new_entry_and_keeps_everything_shared_had():
    """read-merge-write 的整支重點：共用檔獨有的條目不得消失。"""
    out = mod.merge(original(), local_for_merge(), [(GLOBAL, "cac")], NEW_STAMP)
    flat = mod.flatten(out)

    assert set(flat) == {
        (GLOBAL, "mcp"),
        (GLOBAL, "roas"),
        (MEETING_KEY, "px"),
        (GLOBAL, "cac"),
    }
    assert flat[(MEETING_KEY, "px")]["canonical"] == "Project X"


def test_merge_replaces_an_existing_entry_in_place_without_duplicating_the_id():
    out = mod.merge(original(), local_for_merge(), [(GLOBAL, "roas")], NEW_STAMP)

    assert [e["id"] for e in out["global_terms"]] == ["mcp", "roas"]
    assert mod.flatten(out)[(GLOBAL, "roas")]["aliases"] == ["羅阿斯", "投報率"]


def test_merge_only_applies_the_keys_it_was_given():
    """沒列進 keys 的本機條目一律不上去 —— 不然 `--include-modified` 形同永遠開著。"""
    out = mod.merge(original(), local_for_merge(), [(GLOBAL, "cac")], NEW_STAMP)
    flat = mod.flatten(out)

    assert flat[(GLOBAL, "roas")]["aliases"] == ["羅阿斯"]
    assert ("rd週會", "gmn") not in flat


def test_merge_creates_a_meeting_bucket_the_shared_doc_did_not_have():
    out = mod.merge(original(), local_for_merge(), [("rd週會", "gmn")], NEW_STAMP)

    assert mod.flatten(out)[("rd週會", "gmn")]["canonical"] == "generate-meeting-notes"
    assert mod.flatten(out)[(MEETING_KEY, "px")]["canonical"] == "Project X"


def test_merge_stamps_the_given_now():
    out = mod.merge(original(), local_for_merge(), [(GLOBAL, "cac")], NEW_STAMP)

    assert out["last_updated"] == NEW_STAMP


def test_merge_does_not_touch_its_arguments():
    """就地改參數的話樂觀鎖那一輪拿去比對的「原本」已經被改過，比了等於沒比。"""
    shared, local = original(), local_for_merge()

    mod.merge(shared, local, [(GLOBAL, "cac"), (GLOBAL, "roas")], NEW_STAMP)

    assert shared == original()
    assert local == local_for_merge()


@pytest.mark.parametrize(
    "shared,key,canonical",
    [
        ({"meeting_terms": {}}, (GLOBAL, "cac"), "CAC"),
        ({"global_terms": []}, ("rd週會", "gmn"), "generate-meeting-notes"),
    ],
    ids=["no-global-terms", "no-meeting-terms"],
)
def test_merge_into_a_shared_doc_missing_a_whole_section(shared, key, canonical):
    """剛開好的共用檔只有一半的鍵 —— 推不進去的話第一次上傳就卡死。"""
    out = mod.merge(shared, local_for_merge(), [key], NEW_STAMP)

    assert mod.flatten(out)[key]["canonical"] == canonical


def test_merge_survives_non_dict_entries_in_the_shared_list():
    """判不了的元素不該讓「同 id 就地取代」退化成追加 —— 那會變成兩筆同 id。"""
    shared = original()
    shared["global_terms"] = ["不是 dict", shared["global_terms"][1], None]

    out = mod.merge(shared, local_for_merge(), [(GLOBAL, "roas")], NEW_STAMP)

    roas = [e for e in out["global_terms"] if isinstance(e, dict) and e.get("id") == "roas"]
    assert len(roas) == 1
    assert roas[0]["aliases"] == ["羅阿斯", "投報率"]


def test_merge_replaces_an_id_less_shared_entry_keyed_by_its_canonical():
    """共用檔那筆只有 canonical —— 認不出來的話同一個詞會變成兩筆。"""
    entry = {"canonical": "CAC", "aliases": ["獲客成本"], "type": "technical_term"}
    shared = {"global_terms": [entry], "meeting_terms": {}}
    local = {"global_terms": [{**entry, "aliases": ["獲客成本", "取得成本"]}], "meeting_terms": {}}

    out = mod.merge(shared, local, [(GLOBAL, "CAC")], NEW_STAMP)

    assert len(out["global_terms"]) == 1
    assert mod.flatten(out)[(GLOBAL, "CAC")]["aliases"] == ["獲客成本", "取得成本"]


@pytest.mark.parametrize("bad", [{"id": "x"}, "不是 list"], ids=["dict", "str"])
def test_merge_skips_a_scope_whose_terms_are_not_a_list(bad):
    """手改壞的 glossary.json 就長這樣 —— 就此中斷的話後面那場整場推不上去。"""
    shared = {"global_terms": [], "meeting_terms": {"壞掉的會議": bad, MEETING_KEY: []}}
    local = {"meeting_terms": {MEETING_KEY: [{"id": "py", "canonical": "Project Y"}]}}

    out = mod.merge(shared, local, [(MEETING_KEY, "py")], NEW_STAMP)

    assert mod.flatten(out)[(MEETING_KEY, "py")]["canonical"] == "Project Y"


def test_merge_keeps_going_past_a_key_the_local_doc_does_not_have():
    """找不到的 key 排在**前面** —— 就此停住的話後面的條目靜默漏推。"""
    out = mod.merge(
        original(),
        local_for_merge(),
        [(GLOBAL, "根本沒有這一筆"), (GLOBAL, "cac")],
        NEW_STAMP,
    )
    flat = mod.flatten(out)

    assert flat[(GLOBAL, "cac")]["canonical"] == "CAC"
    assert (GLOBAL, "根本沒有這一筆") not in flat, "本機沒有的 key 不該憑空長出一筆"


def test_merge_returns_a_doc_that_shares_no_nested_object_with_its_inputs():
    """回傳的 doc 與輸入共用巢狀物件的話，之後動它等於回頭改了比對用的「原本」。"""
    shared, local = original(), local_for_merge()

    out = mod.merge(shared, local, [(GLOBAL, "cac")], NEW_STAMP)
    for entry in out["global_terms"]:
        entry["aliases"].append("汙染")

    assert local == local_for_merge()
    assert shared == original()


def test_merge_shares_no_nested_object_when_it_replaces_in_place():
    """追加分支深拷了不代表取代分支也深拷 —— 兩條路要各驗一次。"""
    shared, local = original(), local_for_merge()

    out = mod.merge(shared, local, [(GLOBAL, "roas")], NEW_STAMP)
    replaced = [e for e in out["global_terms"] if e["id"] == "roas"]
    assert len(replaced) == 1
    replaced[0]["aliases"].append("汙染")

    assert local == local_for_merge()
    assert shared == original()


def test_merge_with_no_keys_only_moves_the_timestamp():
    out = mod.merge(original(), local_for_merge(), [], NEW_STAMP)

    assert mod.flatten(out) == mod.flatten(original())
    assert out["last_updated"] == NEW_STAMP


# --------------------------------------------------------------------------- #
# validate_merged —— 五條驗證，每條一個「只壞那一件事」的對照組
# --------------------------------------------------------------------------- #


def test_a_clean_merge_reports_nothing():
    assert mod.validate_merged(merged_ok(), original()) == []


def break_fields(doc: dict) -> dict:
    doc["global_terms"][-1].pop("canonical")
    return doc


def break_duplicate_id(doc: dict) -> dict:
    # 一字不差的複本：同 canonical、同 aliases，除了 id 重複之外沒壞別的
    doc["global_terms"].append(copy.deepcopy(CAC))
    return doc


def break_alias_conflict(doc: dict) -> dict:
    # 別的 id、別的 canonical，但搶走 mcp 的 alias「NCP」
    doc["global_terms"].append(
        {
            "id": "ncp-vendor",
            "canonical": "NCP 系統",
            "aliases": ["NCP"],
            "type": "technical_term",
            "status": "active",
        }
    )
    return doc


def break_count(doc: dict) -> dict:
    doc["global_terms"] = doc["global_terms"][:1]
    return doc


def break_stale(doc: dict) -> dict:
    doc["last_updated"] = OLD_STAMP
    return doc


BREAKS = [
    (break_fields, mod.V_FIELDS),
    (break_duplicate_id, mod.V_DUP_ID),
    (break_alias_conflict, mod.V_ALIAS),
    (break_count, mod.V_COUNT),
    (break_stale, mod.V_STALE),
]


@pytest.mark.parametrize(
    "break_it,expected",
    BREAKS,
    ids=["fields", "duplicate-id", "alias-conflict", "count-shrunk", "stale"],
)
def test_each_break_lights_exactly_its_own_check(break_it, expected):
    """「只有那條紅」跟「有紅」一樣重要。

    連坐的話（alias 衝突順便讓筆數那條也紅）就分不出擋下的是哪一件事 ——
    而驗收腳本進不了 CI，這裡是唯一守得住的地方。
    """
    assert codes(break_it(merged_ok())) == {expected}


def test_the_five_codes_are_five_distinct_strings():
    assert len({mod.V_FIELDS, mod.V_DUP_ID, mod.V_ALIAS, mod.V_COUNT, mod.V_STALE}) == 5


@pytest.mark.parametrize("bad_id", [None, ""], ids=["missing", "blank"])
def test_an_entry_without_an_id_is_incomplete_not_invisible(bad_id):
    """id 不見的條目若在 flatten 那層就被略過，五條驗證裡「欄位完整」永遠看不到它 ——
    那是靜默漏掉，不是擋下。"""
    doc = merged_ok()
    if bad_id is None:
        doc["global_terms"][-1].pop("id")
    else:
        doc["global_terms"][-1]["id"] = bad_id

    assert mod.V_FIELDS in codes(doc)


def test_the_same_id_in_two_scopes_is_not_a_duplicate():
    """scope 是 key 的一部分 —— 不分 scope 的話每個會議專用詞都會誤判成重複。"""
    doc = merged_ok()
    doc["meeting_terms"][MEETING_KEY].append(
        {"id": "cac", "canonical": "CAC", "aliases": ["獲客成本"]}
    )

    assert codes(doc) == set()


def test_an_alias_shared_by_one_canonical_twice_is_not_a_conflict():
    """同一個 canonical 在兩處掛同一個 alias 沒有歧義，擋下來只會逼人手動繞過驗證。"""
    doc = merged_ok()
    doc["meeting_terms"][MEETING_KEY].append(
        {"id": "cac-local", "canonical": "CAC", "aliases": ["獲客成本"]}
    )

    assert mod.V_ALIAS not in codes(doc)


def test_an_equal_count_is_not_shrunk():
    """只改既有條目（`--include-modified`）不會讓筆數變多 —— 擋掉就等於這條路走不了。"""
    doc = original()
    doc["global_terms"][1]["aliases"] = ["羅阿斯", "投報率"]
    doc["last_updated"] = NEW_STAMP

    assert codes(doc) == set()


def meeting_break_fields(doc: dict) -> dict:
    doc["meeting_terms"][MEETING_KEY][0].pop("canonical")
    return doc


def meeting_break_duplicate_id(doc: dict) -> dict:
    doc["meeting_terms"][MEETING_KEY].append(
        copy.deepcopy(doc["meeting_terms"][MEETING_KEY][0])
    )
    return doc


def meeting_break_alias_conflict(doc: dict) -> dict:
    # 別的 id、別的 canonical，但搶走 px 的 alias「PX」
    doc["meeting_terms"][MEETING_KEY].append(
        {"id": "px-vendor", "canonical": "PX 外包版", "aliases": ["PX"], "status": "active"}
    )
    return doc


@pytest.mark.parametrize(
    "break_it,expected",
    [
        (meeting_break_fields, mod.V_FIELDS),
        (meeting_break_duplicate_id, mod.V_DUP_ID),
        (meeting_break_alias_conflict, mod.V_ALIAS),
    ],
    ids=["fields", "duplicate-id", "alias-conflict"],
)
def test_each_break_inside_a_meeting_bucket_lights_its_own_check(break_it, expected):
    """五條驗證只掃 `global_terms` 的話，meeting bucket 整個是無人看守的 ——
    而人名、專案名這些最會撞的詞大多住在那裡。"""
    assert codes(break_it(merged_ok())) == {expected}


@pytest.mark.parametrize(
    "entries,expected",
    [
        (
            [{"canonical": "甲方", "aliases": []}, {"canonical": "乙方", "aliases": []}],
            mod.V_DUP_ID,
        ),
        (
            [
                {"id": "a", "aliases": ["同一個別名"]},
                {"id": "b", "aliases": ["同一個別名"]},
            ],
            mod.V_ALIAS,
        ),
    ],
    ids=["no-id", "no-canonical"],
)
def test_two_incomplete_entries_do_not_light_a_second_check(entries, expected):
    """缺欄位的條目不該被當成「有 id」「有 canonical」拿去互比 ——
    連坐的話操作者以為撞名，實際上只是有人少填一格。"""
    doc = merged_ok()
    doc["global_terms"].extend(entries)

    assert codes(doc) == {mod.V_FIELDS}, f"不得順便點亮 {expected}"


@pytest.mark.parametrize(
    "break_it,expected", BREAKS[:3], ids=["fields", "duplicate-id", "alias-conflict"]
)
def test_a_non_dict_does_not_stop_the_checks_after_it(break_it, expected):
    """判不了的元素若讓迴圈就此中斷，它後面的條目再也檢查不到 —— 那是靜默放行。"""
    doc = break_it(merged_ok())
    doc["global_terms"].insert(-1, "不是 dict")

    assert expected in codes(doc)


def test_the_count_check_copes_with_a_doc_that_has_no_meeting_terms():
    merged, base = merged_ok(), original()
    merged.pop("meeting_terms")
    base.pop("meeting_terms")

    assert codes(merged, base) == set()


def test_an_original_without_last_updated_is_not_stale():
    """共用檔還沒蓋過時間戳 —— 拿不到「原本」不等於沒往前。"""
    base = original()
    base.pop("last_updated")

    assert mod.V_STALE not in codes(merged_ok(), base)


def test_a_missing_last_updated_is_stale():
    doc = merged_ok()
    doc.pop("last_updated")

    assert mod.V_STALE in codes(doc)


# --------------------------------------------------------------------------- #
# prune_local
# --------------------------------------------------------------------------- #


def test_prune_local_drops_entries_that_match_the_shared_copy_exactly():
    local = original()

    out = mod.prune_local(local, original())

    assert mod.flatten(out) == {}


def test_prune_local_keeps_a_local_change_that_has_not_gone_upstream():
    """留著才有下一次 dry-run 可看；掃掉等於本機的改動無聲消失。"""
    local = original()
    local["global_terms"][1]["aliases"] = ["羅阿斯", "投報率"]
    local["global_terms"].append(copy.deepcopy(CAC))

    flat = mod.flatten(mod.prune_local(local, original()))

    assert set(flat) == {(GLOBAL, "roas"), (GLOBAL, "cac")}
    assert flat[(GLOBAL, "roas")]["aliases"] == ["羅阿斯", "投報率"]


def test_prune_local_removes_a_meeting_bucket_it_emptied():
    """空 bucket 留著會讓下一次 diff 多出一個永遠是空的 scope。"""
    local = original()
    local["global_terms"] = []

    out = mod.prune_local(local, original())

    assert MEETING_KEY not in out.get("meeting_terms", {})


def test_prune_local_keeps_a_meeting_bucket_that_still_has_something():
    local = original()
    local["meeting_terms"][MEETING_KEY].append(
        {"id": "py", "canonical": "Project Y", "aliases": []}
    )

    flat = mod.flatten(mod.prune_local(local, original()))

    assert set(flat) == {(MEETING_KEY, "py")}


def test_prune_local_keeps_entries_it_cannot_judge():
    """瘦身只移除「與共用檔一字不差」的條目 —— 判不了的掃掉就是無聲刪資料。"""
    local = original()
    local["global_terms"].insert(1, "不是 dict")

    out = mod.prune_local(local, original())

    assert "不是 dict" in out["global_terms"]
    assert mod.flatten(out) == {}


def test_prune_local_drops_an_id_less_entry_that_matches_the_shared_copy():
    entry = {"canonical": "CAC", "aliases": ["獲客成本"], "type": "technical_term"}

    out = mod.prune_local(
        {"global_terms": [dict(entry)], "meeting_terms": {}},
        {"global_terms": [dict(entry)], "meeting_terms": {}},
    )

    assert mod.flatten(out) == {}


def test_prune_local_returns_a_doc_that_shares_no_nested_object_with_its_input():
    local = original()
    local["global_terms"][1]["aliases"] = ["羅阿斯", "投報率"]

    out = mod.prune_local(local, original())
    for entry in out["global_terms"]:
        entry["aliases"].append("汙染")

    assert local["global_terms"][1]["aliases"] == ["羅阿斯", "投報率"]


def test_prune_local_does_not_touch_its_arguments():
    local, shared = original(), original()

    mod.prune_local(local, shared)

    assert local == original()
    assert shared == original()


# --------------------------------------------------------------------------- #
# summary_line
# --------------------------------------------------------------------------- #


def test_summary_line_carries_all_three_counts():
    buckets = {
        "new": [{"key": (GLOBAL, "a")}, {"key": (GLOBAL, "b")}],
        "modified": [{"key": (GLOBAL, "c")}],
        "same": [],
    }

    line = mod.summary_line(buckets)

    assert "\n" not in line
    assert "2" in line and "1" in line and "0" in line


def test_summary_line_moves_with_the_buckets():
    """同一條字串不論桶子長怎樣都印得出來的話，它量的是版型不是資料。"""
    empty = mod.summary_line({"new": [], "modified": [], "same": []})
    filled = mod.summary_line(
        {"new": [{"key": (GLOBAL, "a")}], "modified": [], "same": []}
    )

    assert empty != filled


# --------------------------------------------------------------------------- #
# CLI 與流程隔離 —— 兩條可機械判定的契約
# --------------------------------------------------------------------------- #


def test_dry_run_is_the_default():
    """`--push` 沒打就不上傳。預設會推的話，看 diff 的人已經推完了。"""
    args = mod.build_parser().parse_args([])

    assert args.push is False
    assert args.include_modified is False
    assert args.prune_local is False


@pytest.mark.parametrize(
    "flag,attr",
    [
        ("--push", "push"),
        ("--include-modified", "include_modified"),
        ("--prune-local", "prune_local"),
    ],
    ids=["push", "include-modified", "prune-local"],
)
def test_each_flag_turns_on_exactly_its_own_switch(flag, attr):
    args = mod.build_parser().parse_args([flag])

    assert getattr(args, attr) is True
    assert sum(bool(getattr(args, a)) for a in ("push", "include_modified", "prune_local")) == 1


PIPELINE = [
    "extract_audio_sources.py",
    "create_gdoc_from_md.py",
    "generate_meeting_notes.py",
]


@pytest.mark.parametrize("script", PIPELINE, ids=[Path(s).stem for s in PIPELINE])
def test_the_note_pipeline_does_not_reach_for_the_push_script(script):
    """「不掛進產會議記錄的流程，只能明示執行」——
    共用詞彙表被無聲改動比詞彙錯誤更難查。

    import 用 AST 釘（精準），另外連字串都不准出現 —— 掛進去的方式不只 import，
    `subprocess` 起一支腳本同樣算掛。
    """
    source = (SCRIPTS / script).read_text(encoding="utf-8")

    imported = {
        name.name.rsplit(".", 1)[-1]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for name in node.names
    } | {
        node.module.rsplit(".", 1)[-1]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "push_shared_glossary" not in imported
    assert "push_shared_glossary" not in source


def test_the_push_script_is_in_the_mutation_scope():
    """純函式加了卻沒掛進 `PURE` 就是量不到它 —— Makefile 的註解自己說了。"""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    setup_cfg = (ROOT / "setup.cfg").read_text(encoding="utf-8")

    assert "push_shared_glossary.py" in setup_cfg
    for func in ("flatten", "classify", "diff_lines", "merge", "validate_merged",
                 "prune_local", "keys_to_push", "summary_line"):
        assert f"\t{func} \\" in makefile or f"\t{func}\n" in makefile
