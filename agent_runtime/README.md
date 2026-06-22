# Agent Runtime

本文件供 **IT 人員**在 repo 內了解 `agent_runtime/` 子專案結構與部署步驟，**不部署至使用者運作環境**。使用者端 Agent 的工作區根目錄為 `agent_runtime/`，運作規則見同目錄 [`AGENTS.md`](AGENTS.md)（此檔會隨工作區一併部署）。

## 目錄結構

```text
agent_runtime/
  requirements.txt                # Agent 使用 codex PDF skill 所需套件
  tasks/                          # 使用者任務工作區
  memory.md                       # Agent 跨 session 工作記憶
  AGENTS.md                       # Agent 操作規則（部署至使用者端）
  _internal/
    .venv/                        # Python 虛擬環境（本機建立，不納版控、不複製自其他機器）
    config/
      .env                        # kbsearch 設定
      oauth_client.json           # Google OAuth Desktop 用戶端憑證（不納版控）
      token_cache.json            # 首次授權後由程式寫入（不納版控）
    packages/                     # kbsearch_cli wheel
    logs/                         # 每次 query 的獨立 kbsearch-<日期時間>-<run_id>.log
```

---

## 本機測試環境：準備 agent_runtime

在搬移到正式機之前，可在開發機上依下列步驟建立與正式結構相同的 `agent_runtime/`。

### 1. 安裝 LibreOffice；選用 Poppler

在目標機器安裝 LibreOffice。`soffice.exe` 預設路徑通常為 `C:\Program Files\LibreOffice\program\soffice.exe`。

```powershell
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"
```

輸出為 `True` 後，將 LibreOffice 的 `program` 目錄加入 Windows 系統 `PATH`，並重新啟動 Codex Desktop。`query_cli` 與 Documents Skill 都直接呼叫 `soffice`，不接受另外設定執行檔路徑。
設定完後，使用以下指令驗證：

```powershell
Get-Command soffice
soffice --version
```

查詢結果的 PDF 與 PNG 處理由 `kbsearch` 自身完成。若未來仍需讓 Codex 的 PDF Skill 或 Documents Skill 自行將 PDF 頁面渲染為 PNG，才需另外安裝 Poppler。

Poppler 安裝與設定步驟：

1. 從可信任的發行來源取得 Windows Poppler build，解壓縮或安裝至固定位置，例如 `C:\Program Files\poppler\`。
2. 找到實際包含 `pdfinfo.exe` 與 `pdftoppm.exe` 的目錄，例如 `C:\Program Files\poppler\Library\bin\`。
3. 將該目錄加入 Windows 系統 `PATH`。
4. 重新啟動 Codex Desktop，讓 Agent 執行程序取得更新後的 `PATH`。
5. 在新的 PowerShell 視窗驗證：

```powershell
Get-Command pdfinfo
Get-Command pdftoppm
pdfinfo -v
pdftoppm -v
```

Optional：若需要 Presentations Skill 執行完整 PPTX package 輔助檢查，可另外安裝相容的 `unzip` CLI，並將其執行檔所在目錄加入 Windows 系統 `PATH`。這不是基本 PPTX 匯入或投影片渲染必需項目；用途是讓 Skill 檢查 PPTX 內部 package，例如擷取 `ppt/media/` 內嵌媒體、掃描字型與統計圖表或投影片 XML parts。

```powershell
Get-Command unzip
unzip -v
```

### 2. 放入 wheel

取得 `query_cli` 子專案中的 `kbsearch_cli-*.whl`，並放到 `agent_runtime\_internal\packages\` 中。

### 3. 複製與調整設定檔

從 `query_cli\config\` 取得 `.env` 與 `oauth_client.json`，並複製到 `agent_runtime\_internal\config\`。

若未調整建議的 `agent_runtime` 資料夾結構，複製後須調整 `.env` 中的：

- `KBSEARCH_CJK_FONT_PATH`：改為該機器上**已存在**的 CJK 字型檔絕對路徑（`.ttf` 或 `.ttc`）。`msjh.ttc` 僅為繁中 Windows 常見範例；若不存在，可改用同目錄其他 CJK 字型（例如 `msyh.ttc`、`mingliu.ttc`），或先安裝字型（例如 Noto Sans CJK）後再填入路徑：

```powershell
Test-Path "C:\Windows\Fonts\msjh.ttc"
Get-ChildItem "C:\Windows\Fonts" -Include *.ttf,*.ttc -Recurse | Select-Object -ExpandProperty FullName
```
- `KBSEARCH_SECURE_BACKEND_BASE_URL`：改為運作端可連線的 backend URL
- `KBSEARCH_QUERY_LOG_RETENTION_DAYS`：per-run query log 保留天數，預設 `14`；設為 `0` 停用自動清理。

### 4. 建立 .venv 並安裝 wheel

建立 `.venv` 並安裝基礎依賴：

```powershell
cd agent_runtime\_internal
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r ..\requirements.txt
```

安裝 `kbsearch_cli` wheel。以下程式碼區塊需整段複製至 PowerShell 執行：

```powershell
$wheels = @(Get-ChildItem -LiteralPath .\packages -Filter kbsearch_cli-*.whl)
if ($wheels.Count -ne 1) { throw "Expected exactly one kbsearch_cli wheel, found $($wheels.Count)." }
.\.venv\Scripts\python.exe -m pip install --force-reinstall $wheels[0].FullName
```

請注意：`.venv` 綁定建立當下該機器的 Python 路徑，不可從其他電腦或開發環境整包複製後直接使用。

### 5. 執行查詢

工作目錄為 `agent_runtime\_internal`：

```powershell
cd agent_runtime\_internal
.\.venv\Scripts\kbsearch.exe query `
  --output-dir "../tasks/20260613-130000-agent-runtime-test/query_results/20260613-131500-initial-query" `
  --vector-query "測試向量查詢文字" `
  --drive-query "(fullText contains '關鍵字' or name contains '關鍵字') and trashed = false" `
  --limit 10
```

`--output-dir` 與 `--image` 可使用絕對路徑，或使用相對 `_internal/` 工作目錄的路徑。Agent 依目前目錄結構使用相對路徑，例如 `../tasks/<任務資料夾>/query_results/<查詢資料夾>` 與 `../tasks/<任務資料夾>/user-01.png`。`--image` 可重複指定多次。

完成時 **stdout** 輸出 JSON，含 `run_id`、`log_path` 與 `output_dir`。若部分檔案下載或處理失敗，狀態為 `finished_with_errors`，並提供失敗數量、Google Drive 原檔連結、向量命中頁碼或全文查詢條件，以及 `download_failures.json` 路徑；其他成功檔案仍會保留。每次 query 會在 `agent_runtime\_internal\logs\` 建立獨立的 `kbsearch-<日期時間>-<run_id>.log`，並於啟動時依 `KBSEARCH_QUERY_LOG_RETENTION_DAYS` 清理過期 log。

需要補充產生指定頁面的 PNG 時，同樣在 `agent_runtime\_internal` 工作目錄執行：

```powershell
.\.venv\Scripts\kbsearch.exe render-pdf-pages `
  --pdf "../tasks/<任務資料夾>/query_results/<查詢資料夾>/<文件資料夾>/pdf/document.pdf" `
  --pages "3,5,8-10" `
  --output-dir "../tasks/<任務資料夾>/query_results/<查詢資料夾>/<文件資料夾>/pages"
```

`--pdf` 與 `--output-dir` 使用相對 `_internal/` 工作目錄的路徑；也可改用絕對路徑。`--output-dir` 應指定到同一文件資料夾內的 `pages/`。

首次執行若尚無 `token_cache.json`，程式會開啟瀏覽器完成 Google OAuth 授權，並寫入 `config\token_cache.json`。

---

## 正式環境準備

請依照以下資料夾結構複製子資料夾與相關檔案到正式機，且子資料夾內僅保留下方有列出的檔案。

```text
agent_runtime/
  AGENTS.md
  requirements.txt
  tasks/
  _internal/
    config/
      .env
      oauth_client.json
    packages/
      kbsearch_cli-*.whl
    logs/
```

搬移完成後參考以上 `測試環境準備` 中的步驟建置正式環境。
建置完成後，可刪除 `requirements.txt` 與 `_internal/packages/` 資料夾。
---
