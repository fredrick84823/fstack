# 去識別化替換表。複製到 ~/.config/generate-meeting-notes/sanitize.sed
# 再換成自己的值。同步後對 *.md *.py *.toml *.yaml 執行（sed -f）。
#
# 人名不做自動替換：'Mark' 會命中 'Markdown'。人名一律在安裝版就寫化名，
# 真名若重新出現由 guard 擋下來，人工處理。

s/`example-oauth-client`/`<your-oauth-client-name>`/g
s/example-gcp-project/<your-gcp-project>/g
s/「Example Consent Screen」/「你的 consent screen 名稱」/g
s|^\([[:space:]]*>*[[:space:]]*\)背景見 `~/example-notes/.*$|\1背景與決策脈絡請記錄在你自己的團隊文件中。|
