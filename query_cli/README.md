# KBSearch Query CLI

`query_cli/` 是 KBSearch 提供給終端人類員工與 Agent 使用的查詢 CLI。它負責使用者查詢流程與查詢結果檔案處理流程；阿里雲 embedding model 與 Qdrant vector store 操作透過 `secure_backend` FastAPI 服務執行。

## 資料夾結構

```text
query_cli/
  AGENTS.md                # Agent 開發規範
  README.md                # 本文件
  pyproject.toml           # Python package 與 console script 設定
  src/
    kbsearch_cli/          # query CLI package
  tests/
    test_*.py              # 離線單元測試
```

## 環境需求

- Python 3.10 以上。
- 可連線的 `secure_backend` FastAPI 服務。
- Google OAuth client 設定。
- 可寫入的查詢結果目錄。

## 安裝

開發環境可在 repo root 執行：

```powershell
python -m pip install -e query_cli
```

安裝後會提供 `kbsearch` console script。

## 設定

Query CLI 的設定由使用者環境或目前工作目錄下的 `config/.env` 提供，至少包含：

- `KBSEARCH_SECURE_BACKEND_BASE_URL`：`secure_backend` base URL。
- `GOOGLE_OAUTH_CLIENT_CONFIG`：Google OAuth client JSON 設定檔路徑。
- `GOOGLE_OAUTH_TOKEN_CACHE`：OAuth token cache 路徑。此路徑應位於使用者個人環境或明確指定的位置，不得放在 repo 根目錄。
- `KBSEARCH_QUERY_RESULTS_ROOT`：查詢結果輸出根目錄；相對路徑會以目前工作目錄解析。
- `KBSEARCH_QUERY_LOGS_ROOT`：查詢 CLI log 目錄；相對路徑會以目前工作目錄解析。CLI 會寫入 `kbsearch_cli.log`，並於每天 midnight 切割新檔案。
- `LIBREOFFICE_COMMAND`：Office 文件轉 PDF 指令，必填，需填完整絕對路徑，例如 `C:/Program Files/LibreOffice/program/soffice.exe`。
- `KBSEARCH_CJK_FONT_PATH`：必填，TXT / MD 轉 PDF 使用的單一 CJK 字型完整絕對路徑，例如 `C:/Windows/Fonts/msjh.ttc`。

OAuth token cache 應放在使用者個人環境或明確設定的位置。
執行 `kbsearch` 前應先進入 `query_cli` 目錄；預設設定檔位置為目前工作目錄的 `config/.env`。
可從 `config/.env.example` 複製後填入本機設定；實際 `.env`、OAuth client secret 與 token cache 不得提交 Git。

在 repo 開發環境中，從 `query_cli/` 執行時可設定：

```env
KBSEARCH_QUERY_RESULTS_ROOT=query_results
KBSEARCH_QUERY_LOGS_ROOT=logs
```

部署到只有 `agent_runtime/` 的環境時，建議結構為：

```text
agent_runtime/
  query_results/
  query_cli/
    .venv/
    config/
      .env
    logs/
```

此時先進入 `agent_runtime/query_cli` 再執行 CLI，並設定：

```env
KBSEARCH_QUERY_RESULTS_ROOT=../query_results
KBSEARCH_QUERY_LOGS_ROOT=logs
```

設定檢查：

```powershell
kbsearch probe-config
```

## Google Workspace 認證

Query CLI 對 Google Drive API 的使用者身分認證方式是 OAuth 2.0 授權碼流程。員工執行查詢時，CLI 需以該員工授權取得的 token 查詢與下載 Google Drive 檔案。

## 執行

安裝後先進入 `query_cli` 目錄，再使用 `kbsearch query` 執行查詢：

```powershell
cd C:\path\to\agent_runtime\query_cli
.\.venv\Scripts\kbsearch.exe probe-config
.\.venv\Scripts\kbsearch.exe query --name "客戶查詢" --query "產品型號 ABC-123" --limit 10 --min-score 0.5
```

開發環境若已安裝 editable package，也可以從 repo 的 `query_cli/` 目錄執行：

```powershell
cd C:\path\to\KBSearch\query_cli
kbsearch query --name "客戶查詢" --query "產品型號 ABC-123" --limit 10 --min-score 0.5
```

若有圖片查詢依據，可重複提供 `--image`：

```powershell
kbsearch query --name "圖片查詢" --query "相似版型" --image C:\path\sample.png
```

每次查詢會建立：

```text
<KBSEARCH_QUERY_RESULTS_ROOT>/<yyyyMMdd-HHmmss>-<query_name>/
  full_text_results.json
  vector_results.json
  <file_name>-<google_file_id>/
    <downloaded original file>
    01.png
    02.png
```

只有同時出現在全文搜尋與向量搜尋清單中的檔案會被下載與轉頁。
資料夾名稱會附加 Google file ID，避免不同文件在檔名正規化後互相碰撞。
圖片查詢會由 CLI 讀取本機圖片並以 base64 payload 傳給 `secure_backend`，backend 不需也不應讀取 CLI 主機上的本機路徑。

目前查詢結果轉頁支援 PDF、PNG、JPG、JPEG、WEBP、DOC、DOCX、PPT、PPTX、TXT 與 MD。Google Docs 與 Google Slides 會先透過 Google Drive export 下載為 PDF 後再轉頁。

## 測試

離線單元測試：

```powershell
python -m unittest discover -s query_cli\tests
```

需要真實 Google OAuth 或 `secure_backend` 的探查測試應與離線單元測試分開。
