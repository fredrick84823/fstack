# eval 結果：precision-first 的 GAP validator 擋不擋得住雜訊

跑法 `python3 skills/skill-evolution/improve/evals/run_validator_eval.py`。
14 筆 fixture × 三次 ＝ 42 跑。**三次都對才算過** —— 判對一次可能是模型自己猜中。

| 項 | 值 |
|---|---|
| 日期 | 2026-09-15 |
| 分類器 | `claude -p --safe-mode --model claude-haiku-4-5-20251001`，`--json-schema`，全部工具自動拒絕 |
| 判準 | 跑的當下現讀 `references/validate-gap-prompt.md`（commit `9aecdb5` 之後） |
| 受測對象 | `scripts/validate-gap.sh` 本身，不是另刻一份 `claude -p` |
| 語料 | `validator-fixtures.json`，14 筆全部取自 `signal-queue.md` 真實條目，已去識別化 |
| 耗時 | 969s（42 跑）＋ trap-03 修正後重跑 139s |

## 結果

```
                                     三次全對
  recall（須 accept）   4 筆   ██████████  4/4    真 gap 沒有被 precision-first 誤殺
  clean （須 reject）   4 筆   ██████████  4/4    環境／一次性偏好全擋下
  trap  （須 reject）   6 筆   ██████████  6/6    placeholder｜自指｜misroute｜重複 ×3
                                          ─────
                                          42/42 跑
```

逐筆：

| fixture | 類別 | 取材 | 期望 | 三次 | `risk_class` |
|---|---|---|---|---|---|
| recall-01 | recall | 07-30 create-handoff：thoughts 本體內跑 sync 必失敗 | accept | 3/3 | `valid_gap` |
| recall-02 | recall | 07-08 generate-pm-weekly-doc：author 寫死漏掉本週 PR | accept | 3/3 | `valid_gap` |
| recall-03 | recall | 07-22 generate-meeting-notes：extract 收下 meta 回覆 | accept | 3/3 | `valid_gap` |
| recall-04 | recall | 07-08 create-handoff：共用腳本路徑不存在無 fallback | accept | 3/3 | `valid_gap` |
| clean-01 | clean | 07-27：瀏覽器自動化元件沒裝 | reject | 3/3 | `data_issue` |
| clean-02 | clean | 07-27：OAuth 只授權了一個 scope | reject | 3/3 | `data_issue` / `uncertain` ⚠️ |
| clean-03 | clean | 07-29：憑證過期需手動拿 token | reject | 3/3 | `misroute` / `uncertain` ⚠️ |
| clean-04 | clean | 一次性語氣偏好（SKILL.md abstain 例） | reject | 3/3 | `one_shot_pref` |
| trap-01 | trap | 04-30：Layer 1 之前的 placeholder 雜訊 | reject | 3/3 | `placeholder` |
| trap-02 | trap | 07-23/24/29：digest cron 對自己提 gap | reject | 3/3 | `self_referential` |
| trap-03 | trap | 07-22：agent 自報，使用者只回「嗯」 | reject | 3/3 | `uncertain` |
| trap-04 | trap | 07-28：缺口屬 doc-to-html，掛在上游 skill 名下 | reject | 3/3 | `misroute` |
| trap-05 | trap | 07-22：換句話說的重複 | reject + `duplicate_of` | 3/3 | `duplicate` |
| trap-06 | trap | 07-30：換句話說的重複 | reject + `duplicate_of` | 3/3 | `duplicate` |

⚠️ 是 `risk_class` 與預期不同但 **verdict 正確**的筆數。`risk_class` 只記錄不判定
（見下）。

## 過程中改掉的兩件事 —— 都是 eval 找出來的

**① 歸因沒有被當成閘門（trap-04，0/1 → 3/3）。**
第一輪 trap-04 被 accept：缺口是真的，只是掛錯 skill，而「可重複」「有引用」
「講得出 expected/actual」三個條件在一筆掛錯的 signal 上會愉快地全過。
prompt 原本只在表格裡放了一行 `misroute`。改成四個條件**依序**檢查、歸因排第一，
並明寫「發現自己得改 `target_skill` 才講得通」本身就是 misroute。

**② prompt 教了 fixture 的答案。**
`## Duplicates` 原本的例子是「上傳缺少進度回報與明確 timeout」對上「長時間上傳時
沒有任何輸出，應該要有逾時上限」—— 跟 trap-05 幾乎逐字相同。那一輪 42 跑作廢重跑，
例子改成不含任何 fixture 字串的說明。現在有一條檢查釘住這件事：
prompt 與任一 fixture `gap` 的 12 字連續重疊必須為零。

**③ trap-03 的期望本來是錯的（不是模型錯）。**
原本要求它把「上傳缺少進度回報與明確 timeout」判成 07-22 17:09 那筆
「extraction 卡住時缺少自動 timeout 與 fallback」的重複。但上傳與 extraction 是
兩個階段、要改的是 SKILL.md 兩個不同段落，真實 queue 裡也是分開的兩筆 ——
我的 `expect_duplicate_of` 是錯的。模型三次都回 `reject` / `duplicate_of: null`，
理由是「excerpt 裡唯一的使用者發言是『嗯』，沒有可引用的原話」，那是對的判斷。
fixture 改成它真正在測的東西：**反向的重複對照** —— 同一個 skill、同一天、
都提到 timeout，但 `duplicate_of` 必須維持 `null`。

## `risk_class` 為什麼不判定

`data_issue` 與 `one_shot_pref`、`uncertain` 與各種具體 reject 類別，界線本來就可爭辯。
clean-02（OAuth scope 沒授權）三次裡有回 `data_issue` 也有回 `uncertain`；
兩個都是 reject，對呼叫端沒有差別。把它綁成硬條件只會得到一支**沒人相信的 eval**，
而沒人相信的 eval 跟沒有 eval 是同一件事。

`duplicate_of` 反過來是**硬條件**，兩個方向都驗：

- 該指的要指對（trap-05 / trap-06）
- 不該指的要是 `null`（其餘 12 筆，特別是 trap-03）

只驗前者的話，一個對每筆都填上最近一個 signal id 的模型會拿滿分 —— 而那正好是
去重壞掉的樣子。#44 拿 `duplicate_of` 做 session 級去重，指錯或漏填就是一筆重複進 queue。

## 這支測不到什麼

- **真實 transcript 的長度**。fixture 的 excerpt 是幾行對話；session 級分類器要讀的是
  整份 transcript，「從幾百輪裡挑出哪一句是證據」這件事沒有被量到。那是 #44 的事。
- **`IMPROVE_VALIDATOR_MODEL` 換模型後的表現**。只跑過預設的
  `claude-haiku-4-5-20251001`。換 sonnet 只要 `IMPROVE_VALIDATOR_MODEL=sonnet` 再跑一次。
- **rate 的另一半**。14 筆 fixture 說得出「這 14 種形狀判對了」，說不出 precision／recall
  的實際數字。那要等 #44 接線後跑真實 session 累積。

## 離線那一半

這支進不了 CI（要起 `claude -p`、要花錢）。不需要模型也能錯的部分釘在
`tests/unit/test_validator_contract.py`（35 條，進 `make test`）：契約的兩份副本是否一致、
兩道降級守衛、fail-closed、`grade()` 的判讀、以及「判準只有一份」。
注入「拿掉 duplicate 降級」與「拔掉 `===KNOWN_SIGNALS===` 接線」兩個 bug，各有一條測試變紅。
