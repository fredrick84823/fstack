# 測試入口。從 repo root 執行：
#   make test                      unit test
#   make integration               明示才跑；吃本機安裝版，CI 上整包 skip
#   make mutation                  mutmut，範圍是 setup.cfg 的檔案再交集 PURE
#   make mutation FUNC=extract_date   只跑單一函式的 mutant
#   make crap                      CRAP 基線（複雜度 × 未覆蓋率）

PYTEST ?= python3 -m pytest
# repo 沒有 pyproject.toml，`--no-project` 讓 uv 不要往上找一個不存在的專案。
UVRUN := uv run --no-project

SCRIPTS := skills/comms/generate-meeting-notes/scripts
MUT_LOG := .mutmut-run.log

# setup.cfg 的 source_paths 只能切到**檔案**，而 extract_audio_sources.py 裡純函式與
# NotebookLM／Drive I/O 混在同一支。所以範圍在這裡再切一層到函式：只掛 Seam ① 的純
# 函式。I/O 那些現在零測試，掛進去只會噴一牆 🫥 no-tests，數字沒有意義。
# 新增純函式時把名字加進來 —— 不加就是量不到它。
PURE := \
	build_glossary_prompt \
	is_non_content_extract \
	extract_date \
	_unescape_md \
	_parse_inline \
	_parse_inline_bold \
	_parse_blocks \
	_parse_table_rows \
	_classify_line \
	preprocess_content \
	inject_attendees

# key 的形狀是 `<路徑轉點>.x_<函式名>__mutmut_<n>` —— `x_` 前綴是 mutmut 加的，
# 少了它 fnmatch 一個都配不到，而配不到時 mutmut 是 assert 不是靜靜跳過。
MUT_FILTER = $(if $(FUNC),'*.x_$(FUNC)__mutmut_*',$(foreach f,$(PURE),'*.x_$(f)__mutmut_*'))

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
# 所以清快取只是預防，事後的計數才是判準：**不是 0 就不能信這輪的數字**，而不是
# 寫在文件裡靠人記得。gdoc-mcp 實測同一次改動前後分別印
# `🎉 139 🙁 0`（278 次例外，假的）與 `🎉 136 🙁 3`（0 次例外，真的）。
mutation:
	rm -rf mutants .mutmut-cache $(MUT_LOG)
	@set -o pipefail; \
	$(UVRUN) --with mutmut --with pytest mutmut run $(MUT_FILTER) 2>&1 | tee $(MUT_LOG); \
	rc=$$?; \
	n=$$(grep -c BadTestExecutionCommandsException $(MUT_LOG) || true); \
	echo "BadTestExecutionCommandsException: $$n"; \
	if [ "$$n" != "0" ]; then \
		echo "→ mutmut 有 $$n 次選不到覆蓋測試，那些會被記成 killed。這輪的數字不能信。"; \
		exit 1; \
	fi; \
	exit $$rc

# radon 的 key 與 coverage 的 key 都是相對於 repo root 的路徑，兩邊要對得起來才配得上。
crap:
	$(UVRUN) --with coverage --with pytest coverage run --source=$(SCRIPTS) -m pytest tests/unit -q
	$(UVRUN) --with coverage coverage json -o .coverage.json -q
	$(UVRUN) --with radon radon cc -j $(SCRIPTS) > .radon-cc.json
	$(UVRUN) python3 bin/crap.py .radon-cc.json .coverage.json
