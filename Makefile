# 測試入口。從 repo root 執行：
#   make test                      unit test
#   make integration               明示才跑；吃本機安裝版，CI 上整包 skip
#   make mutation                  mutmut，範圍是 setup.cfg 的檔案再交集 PURE
#   make crap                      CRAP 基線（複雜度 × 未覆蓋率）

PYTEST ?= python3 -m pytest
# repo 沒有 pyproject.toml，`--no-project` 讓 uv 不要往上找一個不存在的專案。
UVRUN := uv run --no-project

# mutmut 跑測試用的那道 env 跟 `make test` 的 system python **不是同一個**，只有這裡
# `--with` 列出來的套件。google-api-python-client 是 tests/unit 的 request-side 測試
# （Seam ②）建假 Docs client 用的；少了它那些測試在這道 env 裡是 error 而不是 fail，
# 而 error 一樣讓 pytest 以 exit 1 收場 → mutmut 每顆 mutant 都記成 killed。
MUTENV := $(UVRUN) --with mutmut --with pytest --with google-api-python-client

SCRIPTS := skills/comms/generate-meeting-notes/scripts
MUT_LOG := .mutmut-run.log

# setup.cfg 的 source_paths 只能切到**檔案**，而 extract_audio_sources.py 裡純函式與
# NotebookLM／Drive I/O 混在同一支。所以範圍在這裡再切一層到函式：只掛 Seam ① 的純
# 函式。I/O 那些現在零測試，掛進去只會噴一牆 🫥 no-tests，數字沒有意義。
# 新增純函式時把名字加進來 —— 不加就是量不到它。
# parity.py 同理只掛 drift_warning 與 sync_direction：sync_diff / report_drift /
# direction_against_installed / _mtimes 碰檔案系統與子行程，是 I/O 那一層，不是 Seam ①
#（它們有自己的測試，只是不該拿 mutation 去量）。
# 沒列進來的純函式：build_glossary_prompt / is_non_content_extract / inject_attendees。
# 它們現在零測試，掛進去是 147 顆 🫥 no-tests —— 跟掛 NotebookLM／Drive I/O 同一種
# 稀釋，只是走函式那道門。有測試了再加回來（glossary 那支是 #8；is_non_content_extract
# 與 inject_attendees 目前沒有對應的票）。
# history_index.py 的 `open_items` 與 `_open_items_block` 是 #36 加的：前者是「哪些項目
# 還沒結案」的判準（`!=` 被變異成 `==` 就會變成只收已結案的），後者是 40 行上限那道切法
# （`[:MAX_OPEN_ITEMS]` 的邊界、以及「剩幾條」那行在不在）。兩處都是靜靜地少東西的形狀，
# 正是該被 mutant 問一次的。
# history_index.py 的那六支碰檔案系統，但碰的是測試自己建的 tmp 目錄 —— 不是
# NotebookLM／Drive 那種要憑證與網路的 I/O，所以照樣掛。日期邊界（`>=` vs `>`）正是
# 最該被 mutant 問一次的地方。
# `build_index` 會留下幾顆殺不掉的：警告訊息的字面值、`encoding="utf-8"` → `None`／
# `"UTF-8"`（這台機器上等價）。那些不寫測試 —— 要殺就得逐字釘死訊息文案，而那正是
# 棒④ 會刪掉的裝飾性測試。
# channel.py 的三支全掛：`channel_state` / `dm_reminder` 是 dict/str in → str out，
# `set_channel` 碰檔案系統但碰的是測試自己建的 tmp 檔（同 history_index 的理由）——
# 「備份有沒有先於寫入」正是最該被 mutant 問一次的地方。`main` 是 CLI 進入點，不掛。
# reconcile_drive.py 的純函式全掛（`in_window` 到 `dm_blocked`）：這支是**無人看管**跑的，
# 它的判準錯了沒有人會在旁邊看到 —— 差集算多一場的代價是重跑 NotebookLM 並覆寫既有記錄。
# `in_window` 的 `0 <= delta < window_days` 兩個邊界、`compute_pending` 的 `[:limit]`、
# `is_note` 的「Doc **且** 檔名前綴」那個 `and`，全都是靜靜地多算或少算的形狀。
# `credential_gap` / `prompt_file` 碰檔案系統，但碰的是測試自己建的 tmp 目錄（同
# `set_channel` 的理由），照樣掛。Drive 掃描、下載與三個子行程那幾支不掛：它們要憑證、
# 要網路、要 NotebookLM，是 I/O 那一層。
# `synthesis_prompt`（22 顆）與 `credential_gap`（17 顆）會留下殺不掉的：全部是 prompt
# 與錯誤訊息的**字面值**，以及 `encoding="utf-8"` → `None`／`"UTF-8"`、
# `"credentials.json"` → `"CREDENTIALS.JSON"`（這台的檔案系統大小寫不敏感）。那些不寫
# 測試 —— 要殺就得逐字釘死文案，而那正是棒④ 會刪掉的裝飾性測試（同 `build_index`）。
# `failure_notice` 到 `prune_sent` 是 #55 加的雙軌通知：一則給維運者、一則給會議成員。
# 去重那兩支（`notice_key` / `notice_due`）最該被 mutant 問一次 —— `!=` 變成 `==` 的症狀
# 是「該提醒的那天不提醒、不該提醒的每輪都提醒」，兩個方向都不會讓任何東西變紅。
# `notify_channel` 不掛：它讀寫狀態檔、發 Slack，是 I/O 那一層（判準已經切出來了）。
# `dm_notice_key` 是 #64 把維運者的 DM 也納進去重時加的：`sorted` 掉了的症狀是
# 「Drive 換個順序就等於一則新提醒」，而那正是去重本來要擋的那件事。
# `dm_unregistered` 是 #64 加的：未登記系列只報系列、不逐檔。那句 `if not i.meeting_key`
# 被變異掉的症狀是兩份清單互換（可執行的建議消失、101 行不可執行的湧進來），而兩個方向
# 都不會讓任何東西變紅。
# `compute_misplaced` 到 `misplaced_notice` 是 #57 加的「放錯層的音檔」：那兩道濾網
#（不是資料夾、而且是音檔）任何一道被變異掉，症狀都是每小時對整個會議 channel 喊一次
# 假警報 —— 而假警報跟無聲一樣會讓人學會忽略這條通知。`notify_once` / `notify_misplaced`
# 同 `notify_channel`，是 I/O 那一層。
# `when_label` 與 `_by_date` 是 #56／#53 加的：前者決定訊息指認的是日期、日期＋場次還是
# 資料夾名（指錯的症狀是 channel 裡兩場長得一模一樣），後者是同日多場的處理順序。
# local_archive.py 的那五支是同日多場的**共用詞彙**（#56／#53）：資料夾名怎麼拆
# （`parse_date_dir`）、檔名尾端的場次（`note_instance`）、場次的真實時序
# （`instance_rank` / `instance_order_key`）、以及 Drive 日期資料夾怎麼命名
# （`date_dir_name`）。掃描層、歷史索引、補齊腳本與發佈層四支都吃它們，各抄一份的話
# 版面改了只會改到其中一份 —— 而 `instance_rank` 回 `None` 那條路徑（定不出序）錯掉的
# 症狀是「索引靜靜地照字母序」，正是 #53 的病本身。其餘的（`clean_for_filename` /
# `note_title` / `archive_paths` / `sidecar_content` / `write_local_archive` /
# `_configured_root`）不掛：它們是 #6 的既有介面，這張票沒有為它們補測試，掛進去只會
# 多一牆 🫥 no-tests。
# parity_skills.py（bin/）掛四支：`_sanitized` 是涵蓋與否的唯一判準（放行一支沒被涵蓋的
# skill＝那支從此沒有任何東西在比對它）、`installed_dir` 是「安裝版是攤平的」那條規則
#（算錯就是找不到安裝版，而找不到的行為是安靜地跳過）、`_probes` 決定 git 收不收得到
# 目錄規則與會不會被 symlink 打成整批 abort、`_differs` 是比對本身的五類清單（漏收
# funny 那兩類＝懸空連結對著一般檔被讀成「一致」，閘門放行 rsync --delete）。
# `_gitignored` 不掛：它起子行程，是 I/O 那一層（判準已經切進 `_probes`）。
# `sync_direction` 早就在清單裡，但它的新家不在 source_paths 之前等於沒掛 —— 見 setup.cfg。
PURE := \
	_sanitized \
	installed_dir \
	_probes \
	_differs \
	outline \
	open_items \
	_open_items_block \
	render \
	doc_url \
	find_notes \
	read_session \
	build_index \
	extract_date \
	_unescape_md \
	_parse_inline \
	_parse_inline_bold \
	_u16len \
	_markdown_to_gdocs \
	_parse_blocks \
	_parse_table_rows \
	_classify_line \
	preprocess_content \
	drift_warning \
	sync_direction \
	_norm \
	flatten \
	classify \
	diff_lines \
	merge \
	_all_entries \
	validate_merged \
	prune_local \
	keys_to_push \
	summary_line \
	entry_id \
	_buckets \
	channel_state \
	channel_id \
	channel_from_answer \
	dm_reminder \
	set_channel \
	in_window \
	_as_date \
	is_audio \
	is_note \
	compute_pending \
	series_map \
	credential_gap \
	parse_handoff \
	prompt_file \
	synthesis_prompt \
	dm_skipped \
	dm_blocked \
	failure_notice \
	notice_key \
	dm_notice_key \
	notice_due \
	prune_sent \
	compute_misplaced \
	dm_misplaced \
	dm_unregistered \
	misplaced_notice \
	when_label \
	_by_date \
	parse_date_dir \
	note_instance \
	instance_rank \
	instance_order_key \
	date_dir_name

# key 的形狀是 `<路徑轉點>.x_<函式名>__mutmut_<n>` —— `x_` 前綴是 mutmut 加的，
# 少了它 fnmatch 一個都配不到，而配不到時 mutmut 是 assert 不是靜靜跳過。
MUT_FILTER = $(foreach f,$(PURE),'*.x_$(f)__mutmut_*')

.PHONY: test integration mutation crap

test:
	$(PYTEST) tests/unit -v

integration:
	$(PYTEST) tests/integration -v

# 每次都先清 `mutants/` 與 `.mutmut-cache`。mutmut 把「哪些測試覆蓋哪顆 mutant」快取
# 在 mutants/ 底下 —— 改過測試之後不清，它會拿**舊版測試的 node id** 去挑覆蓋測試，
# 選不到 → pytest exit 4 → BadTestExecutionCommandsException → child 以 exit 1 收場 →
# mutmut 的 status_by_exit_code{1: "killed"} 把它記成 🎉。
#
# 所以清快取只是預防，事後的計數才是判準 —— 但它是**單向**的：不是 0 就一定不能信，
# 是 0 只表示沒踩到這一條路徑。gdoc-mcp 實測同一次改動前後分別印
# `🎉 139 🙁 0`（278 次例外，假的）與 `🎉 136 🙁 3`（0 次例外，真的）。
#
# 另一條路徑例外計數看不見：覆蓋那些 mutant 的測試整支不見時 pytest 正常收尾、例外
# 是 0，mutant 記成 🫥 no-tests。驗收條件本來就要求範圍內 🫥 為 0（實測拿掉
# test_md_unescape 一條 → 🎉 59 🫥 83 而例外仍是 0），所以兩個都擋。
#
# 第三條路徑兩個事後計數都看不見，所以擋在**事前**：測試在這道 env 裡 error（缺套件、
# collection 失敗）時，pytest 照樣 exit 1、mutmut 照樣記成 killed，而
# BadTestExecutionCommandsException 與 🫥 都是 0 —— 印出來的是滿分假綠。實測：
# test_inline_style_requests 需要 google-api-python-client，少了它那道 env 是
# 「271 passed, 13 errors」而 `make test` 是「284 passed」，唯一含 emoji 的語料在
# mutation 那輪一條都沒執行 —— 整票要擋的那顆雷剛好量不到。所以先跑一次基線，
# 紅了就停在這裡，不要產生任何數字。
mutation:
	rm -rf mutants .mutmut-cache $(MUT_LOG)
	@echo "── 基線：mutmut 那道 env 底下 tests/unit 必須全綠 ──"
	$(MUTENV) python -m pytest tests/unit -q
	@set -o pipefail; \
	$(MUTENV) mutmut run $(MUT_FILTER) 2>&1 | tee $(MUT_LOG); \
	rc=$$?; \
	n=$$(grep -c BadTestExecutionCommandsException $(MUT_LOG) || true); \
	z=$$(grep -c '^🫥 ' $(MUT_LOG) || true); \
	echo "BadTestExecutionCommandsException: $$n / 🫥 no-tests: $$z"; \
	if [ "$$n" != "0" ]; then \
		echo "→ mutmut 有 $$n 次選不到覆蓋測試，那些會被記成 killed。這輪的數字不能信。"; \
		exit 1; \
	fi; \
	if [ "$$z" != "0" ]; then \
		echo "→ 範圍內有 $$z 顆 mutant 沒有任何測試覆蓋。要嘛測試不見了，要嘛 PURE 掛了零測試的函式。"; \
		exit 1; \
	fi; \
	exit $$rc

# radon 的 key 與 coverage 的 key 都是相對於 repo root 的路徑，兩邊要對得起來才配得上。
crap:
	$(UVRUN) --with coverage --with pytest coverage run --source=$(SCRIPTS) -m pytest tests/unit -q
	$(UVRUN) --with coverage coverage json -o .coverage.json -q
	$(UVRUN) --with radon radon cc -j $(SCRIPTS) > .radon-cc.json
	$(UVRUN) python3 bin/crap.py .radon-cc.json .coverage.json
