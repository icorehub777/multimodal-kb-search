# KBSearch Query CLI

`query_cli/` 提供 `kbsearch` 指令給 Agent 使用。它負責查詢流程、Google Drive 全文搜尋、文件下載與查詢結果檔案整理；embedding 與 Qdrant 查詢透過 `secure_backend` HTTP API 完成。

## 開發測試環境準備

本機開發使用 repo 共用的 conda 環境名稱 `kbsearch`。先檢查環境是否存在：

```powershell
conda env list | Select-String kbsearch
```

若沒有 `kbsearch`，先建立環境：

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

進入環境並安裝 `query_cli` package。：


```powershell
conda activate kbsearch
cd query_cli
python -m pip install -e .
```

建立本機設定檔：

```powershell
Copy-Item query_cli\config\.env.example query_cli\config\.env
```

`config/.env` 範例：

```env
KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000
GOOGLE_OAUTH_CLIENT_CONFIG=config/oauth_client.json
GOOGLE_OAUTH_TOKEN_CACHE=config/token_cache.json
KBSEARCH_QUERY_LOGS_ROOT=logs
LIBREOFFICE_COMMAND=C:\Program Files\LibreOffice\program\soffice.exe
KBSEARCH_CJK_FONT_PATH=C:\Windows\Fonts\msjh.ttc
```

`config/oauth_client.json` 為 Google OAuth **Desktop 用戶端憑證**，須向**內部 Google / GCP 管理者**申請並取得 JSON 後，手動放到 `config/oauth_client.json`（程式不會自動產生）。`config/token_cache.json` 則在首次執行 `kbsearch query`、完成 browser 授權後由程式寫入；若 token 無法 refresh 或驗證失敗，程式會刪除該檔並在下次 query 時重新開啟 browser 登入。兩者皆不納版控。

每次 `kbsearch query` 會先建立呼叫端指定的查詢結果目錄，再執行 startup 檢查：OAuth client、LibreOffice、CJK 字型與 `secure_backend /healthz`；若已有 token cache 也會驗證 Google Drive 授權。

## 手動測試

執行前請確認 `secure_backend` 已在本機啟動（`KBSEARCH_SECURE_BACKEND_BASE_URL` 可連線）。在 `query_cli/` 目錄下執行：

```powershell
kbsearch query `
  --output-dir "C:\path\to\task\query_results\20260613-131500-manual-test" `
  --vector-query "附圖為產品外觀，請找出操作手冊中與此零件安裝相關的說明" `
  --drive-query "(fullText contains '推車' or name contains '推車') and trashed = false" `
  --image "C:\path\to\photo.png" `
  --limit 10 `
  --min-score 0.5
```

參數說明：

- `--output-dir`：本次查詢結果的完整資料夾路徑，必須使用尚不存在的新路徑；父目錄不存在時會自動建立。
- `--vector-query`：語意查詢文字；若有附圖，在此描述問題與圖片內容，連同 `--image` 一併送給 `secure_backend` 做向量搜尋。
- `--drive-query`：Google Drive API `q` 語法，原樣送出，用於全文／檔名搜尋。
- `--image`：本機圖片路徑（PNG/JPEG 等），可重複指定；省略則僅以文字做向量搜尋。
- `--limit`：向量與 Drive 搜尋各別的結果筆數上限，預設 `10`。
- `--min-score`：向量相似度下限；省略則不過濾低分結果。

執行中會在 **stderr** 輸出進度；每個下載檔案僅輸出 `phase=download status=started` 與 `phase=download status=finished`（含 `page_count`；涵蓋 Drive 下載與分頁渲染）。與 union 層的 `phase=download` 以欄位區分（單檔含 `file_id`、`index`、`total`）。下載與分頁轉檔可能較久。成功時 **stdout** 輸出 JSON 摘要：

```json
{
  "status": "finished",
  "output_dir": "C:/path/to/task/query_results/20260613-131500-manual-test",
  "full_text_count": 1,
  "vector_count": 4,
  "download_count": 4
}
```

查詢開始前會以不可覆蓋既有目錄的方式建立 `output_dir`；若路徑已存在，指令會在實際查詢前失敗。查詢途中失敗時，已建立的目錄與部分產物會保留，不得重用相同路徑。詳細清單與下載檔案見該資料夾內的 JSON 與子目錄。

設定成功載入後，查詢過程與失敗資訊會記錄於 `KBSEARCH_QUERY_LOGS_ROOT` 下的 `kbsearch_cli.log`。失敗訊息會附上 log 路徑，供 Agent 或人員排查問題。

## 離線單元測試

```powershell
python -m unittest discover -s query_cli\tests
```

## 正式環境部署

正式環境中 Agent 使用 `agent_runtime/`，不透過 repo 內 `query_cli/` 原始碼執行。部署前需先打包 wheel。

若全域 python 中沒有安裝 build 打包工具，則可使用此指令安裝：

```powershell
python -m pip install build  
```

在 repo 根目錄執行（需已安裝 Python 與 `build`）：

```powershell
cd C:\path\to\KBSearch
python -m build query_cli --wheel
```

`python -m build` 會產生 `query_cli/build/`（建置暫存）與 `query_cli/dist/kbsearch_cli-*.whl`。

提供給 `agent_runtime` 部署的檔案為 `query_cli/dist/kbsearch_cli-*.whl`。
