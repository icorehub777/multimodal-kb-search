# KBSearch Query CLI

`query_cli/` 提供 `kbsearch` 指令作為 Agent 使用的工具集合。

它提供的指令包括：
- 相似度/關鍵字搜尋：可執行多模態向量庫相似度搜尋 (透過 secure_backend 的 API 服務) 與 Google Drive 關鍵字搜尋 (透過 Google Drive API)，並針對搜尋結果中的檔案進行下載、內容整理轉換。
- PDF 檔單頁圖片轉出：指定 PDF 檔與頁碼後，可轉出此頁的 PNG 圖片檔。
- 搜尋結果檢視網頁啟動：開啟搜尋結果檢視網頁。

## 開發測試環境準備

本機開發使用 repo 共用的 conda 環境名稱 `kbsearch`。先檢查環境是否存在：

```powershell
conda env list | Select-String kbsearch
```

若沒有 `kbsearch`，先建立環境：

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

進入環境並安裝 `query_cli` package：

```powershell
conda activate kbsearch
cd query_cli
python -m pip install -e .  # 調整程式後會即時更新
```

### 安裝文件處理工具

安裝 LibreOffice，並將其 `program` 目錄加入 Windows 系統 `PATH`。query_cli 直接呼叫 `soffice` 將 DOC、DOCX、PPT、PPTX 轉成中介 PDF。

```powershell
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"
Get-Command soffice
soffice --version
```

另需準備一個 CJK 字型檔供 TXT／MD 轉 PDF，並將其絕對路徑設定於 `KBSEARCH_CJK_FONT_PATH`。

```powershell
Test-Path "C:\Windows\Fonts\msjh.ttc"
```

### 建立本機設定

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
KBSEARCH_TASKS_ROOT=tasks
KBSEARCH_VIEWER_PORT=8501
KBSEARCH_QUERY_LOG_RETENTION_DAYS=14
KBSEARCH_CJK_FONT_PATH=C:\Windows\Fonts\msjh.ttc
```

LibreOffice 的 `soffice` 必須可從系統 `PATH` 找到，並須設定 `KBSEARCH_CJK_FONT_PATH`。

`config/oauth_client.json` 為 Google OAuth **Desktop 用戶端憑證**，須向**內部 Google / GCP 管理者**申請並取得 JSON 後，手動放到 `config/oauth_client.json`（程式不會自動產生）。`config/token_cache.json` 則在首次執行 `kbsearch query`、完成 browser 授權後由程式寫入；若 token 無法 refresh 或驗證失敗，程式會刪除該檔並在下次 query 時重新開啟 browser 登入。兩者皆不納版控。

## 手動測試

### 相似度 / 關鍵字搜尋

若要做相似度搜尋，執行前請確認 `secure_backend` 已在本機啟動（`KBSEARCH_SECURE_BACKEND_BASE_URL` 可連線）。

手動測試時需保持與 `agent_runtime` 中一樣的資料夾結構 (如此搜尋結果網頁才能正確解析)。也就是在根目錄的 tasks 資料夾下先建立任務資料夾，且若有搜尋用圖片，亦須將其放在任務資料夾中：

```text
tasks/<task-name>/
tasks/<task-name>/<image-file>
```

並在執行查詢指令時，將搜尋結果資料夾路徑參數指向以下路徑，此指令會自行建立 `<query-name>` 資料夾：

```text
tasks/<task-name>/query_results/<query-name>
```

接下來請在 `query_cli/` 目錄下，執行以下指令：

若是由 Agent 執行此指令，必須以 sandbox 外部同意方式執行查詢，讓 OAuth 能正確開啟瀏覽器登入頁。

```powershell
kbsearch query `
  --output-dir "C:\path\to\tasks\20260613-130000-manual-test\query_results\20260613-131500-initial-query" `
  --vector-query "附圖為產品外觀，請找出操作手冊中與此零件安裝相關的說明" `
  --drive-query "(fullText contains '推車' or name contains '推車') and trashed = false" `
  --image "C:\path\to\tasks\20260613-130000-manual-test\photo.png" `
  --limit 10 `
  --min-score 0.5
```

參數說明：

- `--output-dir`：本次搜尋結果的輸出資料夾路徑，必須使用 `tasks/<task-name>/query_results/<query-name>/` 結構中的 `<query-name>` 目錄。指令執行時會自動建立 `<query-name>` 目錄，若執行前該目錄已存在，指令會執行失敗。
- `--vector-query`：語意查詢文字；可與 `--image` 一起或單獨送給 `secure_backend` 做相似度搜尋。相似度搜尋僅涵蓋 importer 已同步的文件。與 `--image` 皆省略時不執行相似度搜尋。
- `--drive-query`：Google Drive API `q` 語法，原樣送出，用於檔名、全文或 metadata 的關鍵字搜尋。搜尋範圍依目前使用者的 Drive 權限決定，不受 importer 同步來源資料夾限制。省略時不執行關鍵字搜尋。
- `--image`：本機圖片路徑（PNG/JPEG 等），可重複指定；可與 `--vector-query` 一起或單獨送給 `secure_backend` 做相似度搜尋。相似度搜尋僅涵蓋 importer 已同步的文件。與 `--vector-query` 皆省略時不執行相似度搜尋。
- `--limit`：相似度與關鍵字搜尋各別的結果筆數上限，預設 `10`。
- `--min-score`：相似度搜尋時的相似度分數下限；省略則不過濾低分結果。

`--vector-query`、`--drive-query`、`--image` 至少要提供其中一個；三者皆未提供時指令會顯示失敗。
`--output-dir` 與 `--image` 均可使用絕對或相對路徑；相對路徑以執行指令時的目前工作目錄解析。

指令啟動時會先載入設定並建立本次專屬 log，接著建立呼叫端指定的搜尋結果目錄，再執行 startup 檢查：OAuth client、`secure_backend /healthz` (只在有 `--vector-query` 或 `--image` 時才呼叫)、系統 `PATH` 中的 `soffice` 與 CJK 字型。若已有 token cache 也會驗證 Google Drive 授權。

下載與轉換搜尋結果檔案的詳細動作，請參考設計文件。

執行中會在 **stderr** 輸出進度；下載階段會先輸出 union 層的 `phase=download status=started`，並包含 `union_count` 等摘要。單檔下載成功時會輸出 `phase=download status=started` 與 `phase=download status=finished`，完成訊息包含文字頁數與實際渲染頁數；單檔失敗時會輸出 `phase=download status=failed`。單檔進度可用 `file_id`、`index`、`total` 與 union 層進度區分。下載與文件處理可能較久。成功時 **stdout** 輸出 JSON 摘要：

設定與本次專屬 log 初始化完成後，stderr 會先輸出一行可解析的 query 啟動事件：

```json
{"event":"query_started","status":"started","run_id":"a1b2c3d4","output_dir":"C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query","log_path":"C:/path/to/logs/kbsearch-20260622-083245-123456-a1b2c3d4.log","monitor":"log","stdout":"final_json_on_success"}
```

`monitor=log` 表示長時間執行時應依 `log_path` 即時監控進度；`stdout=final_json_on_success` 表示 stdout 在程序執行期間不提供啟動摘要，僅在成功或部分成功完成時輸出下列最終 JSON。

```json
{
  "status": "finished_with_errors",
  "run_id": "a1b2c3d4",
  "log_path": "C:/path/to/logs/kbsearch-20260622-083245-123456-a1b2c3d4.log",
  "output_dir": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query",
  "full_text_count": 1,
  "vector_count": 4,
  "download_count": 3,
  "downloaded_files_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/downloaded_files.json",
  "downloaded_files": [
    {
      "google_file_id": "file-1",
      "name": "Alpha.pdf",
      "directory": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde",
      "source_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde/Alpha.pdf",
      "pdf_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde/pdf/document.pdf",
      "text_paths": [
        "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde/text/0001.txt"
      ],
      "page_paths": [
        "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde/pages/0003.png"
      ]
    }
  ],
  "download_failure_count": 1,
  "download_failures_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/download_failures.json",
  "warning_count": 1,
  "warnings_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/warnings.json",
  "download_failures": [
    {
      "google_file_id": "file-4",
      "name": "Broken.pdf",
      "stage": "process",
      "error_type": "DocumentRenderError",
      "message": "PDF text extraction failed",
      "google_drive_url": "https://drive.google.com/file/d/file-4/view",
      "vector_page_numbers": [3, 5],
      "full_text_query": "fullText contains 'Broken' and trashed = false"
    }
  ],
  "warnings": [
    {
      "code": "vector_pages_unrendered",
      "google_file_id": "file-5",
      "name": "Archive.zip",
      "mime_type": "application/zip",
      "google_drive_url": "https://drive.google.com/file/d/file-5/view",
      "vector_page_numbers": [7],
      "message": "Vector search matched pages, but no page images were rendered for this file."
    }
  ]
}
```

每次 `query` 會產生唯一 `run_id`。第一筆 query 進度會在 stderr 回報 `run_id` 與該次專屬 `log` 路徑；其後所有進度均帶同一個 `run_id`。結束時一定會輸出下列其中一種終態：

```text
Query progress: phase=query status=finished run_id=a1b2c3d4 ...
Query progress: phase=query status=finished_with_errors run_id=a1b2c3d4 ...
Query progress: phase=query status=failed run_id=a1b2c3d4 ...
```

所有檔案皆成功時，`status` 為 `finished` 且 `download_failure_count` 為 `0`。若單一檔案在 metadata 補查、產物目錄建立、下載或文件處理階段失敗，該檔案會被略過，其餘檔案繼續處理；此時指令仍以成功 exit code 完成，但 `status` 為 `finished_with_errors`。

`download_count` 是成功下載的檔案數量，不包含 `download_failure_count`。`downloaded_files` 是成功下載與處理的檔案清單，提供 `google_file_id`、原始檔名、文件子資料夾 `directory`、下載檔 `source_path`、標準 PDF 路徑 `pdf_path`、逐頁文字 `text_paths` 與命中頁圖 `page_paths`。完整清單同時寫入 `downloaded_files.json`。

每筆失敗包含 `google_file_id`、檔名、失敗階段、錯誤類型、訊息與 `google_drive_url`，讓使用者可直接到 Google Drive 查看原檔。若檔案來自向量搜尋，`vector_page_numbers` 會列出命中頁碼；若來自關鍵字搜尋，`full_text_query` 會保留本次查詢條件。同時命中兩種搜尋時兩組資訊都會提供。完整清單同時寫入 `download_failures.json`。失敗檔案已建立的部分產物會保留供排錯。

`warnings` 記錄非失敗但會影響閱讀完整性的狀況，完整清單同時寫入 `warnings.json`。例如 `vector_pages_unrendered` 表示向量搜尋命中頁碼存在，但該檔案沒有產生對應的 `pages/*.png`；常見原因是 Drive 上同一個 `file_id` 的檔案在同步後變成不支援文件處理的 MIME type。此時檔案仍算下載成功，但 Agent 應改以原始下載檔或其他工具能力判讀，並在必要時向使用者說明該向量命中頁面無法直接閱讀。

設定與本次專屬 log 初始化完成後，會以不可覆蓋既有目錄的方式建立 `output_dir`；若路徑已存在，指令會在 startup 檢查、實際搜尋與下載前失敗。查詢途中失敗時，已建立的目錄與部分產物會保留，不得重用相同路徑。詳細清單與下載檔案見該資料夾內的 JSON 與子目錄。

設定成功載入後，每次查詢會在 `KBSEARCH_QUERY_LOGS_ROOT` 建立獨立 log，檔名格式為 `kbsearch-<日期時間>-<run_id>.log`。每行均包含 `run_id`，且最後記錄成功、部分成功或失敗終態。stderr 與成功 stdout 也會提供該次 log 絕對路徑。

`KBSEARCH_QUERY_LOG_RETENTION_DAYS` 控制 per-run log 保留天數，預設 `14`。每次 query 啟動時會刪除較舊的 `kbsearch-*.log`；設為 `0` 可停用自動清理。清理失敗時該次 query 會記錄錯誤並停止。

搜尋結果資料夾會包含失敗清單；每個成功下載的檔案子資料夾會保留下載檔，並依 Google Drive MIME type 與匯出結果產生：

```text
<output_dir>/
  query_plan.json
  full_text_results.json
  vector_results.json
  downloaded_files.json
  download_failures.json
  warnings.json
  <safe_file_name>-<google_file_id_prefix>/
    <downloaded file>
    pdf/
      document.pdf
    text/
      0001.txt
      0002.txt
    pages/
      0003.png
```

#### 文件子資料夾產物

- 每個文件子資料夾名稱為 `<safe_file_name>-<google_file_id_prefix>`：`safe_file_name` 在前，`google_file_id` 前綴在後；前綴預設先取前 5 碼，若同一批查詢發生撞名，則逐碼加長至可區分。
- PDF、Word、PowerPoint、TXT、MD、Google Docs 與 Google Slides 會產生固定路徑 `pdf/document.pdf`，以及依頁碼命名的 UTF-8 `text/000N.txt`。
- `query` 自動整理的 `pages/` 只放本次相似度搜尋或全文關鍵字定位命中的頁面。兩種搜尋命中同一頁時共用一份 `000N.png`；查詢流程內發現目標 PNG 已存在時直接沿用。
- PNG、JPG、JPEG、WEBP 視為單頁文件，但只在相似度搜尋命中時產生 `pages/0001.png`。Google Drive 全文搜尋或 OCR 命中圖片時，因無逐頁文字可供定位，只保留檔案層級結果。
- Google Sheets 匯出為 XLSX。其他不支援轉換及逐頁處理的 MIME type 只保留原始下載檔，不會因未產生 PDF、逐頁文字或頁面 PNG 而列為下載失敗。

#### `full_text_results.json`

`full_text_results.json` 保留 Google Drive 關鍵字搜尋的檔案順序。Google Drive 原始結果不含頁碼；下載並產生逐頁文字後，系統只使用 Drive query 中正向 `fullText contains '<關鍵字>'` 的值定位頁面。`name`、metadata 與其他查詢條件不會用於頁面定位。

頁面定位採不分大小寫的字面子字串比對，不推導同義詞，也不模擬 Google Drive 的索引規則。每個定位成功的頁面寫入該檔案的 `pages`：`page_number` 是頁碼，`keyword` 是該頁命中的全文關鍵字。同頁命中多個關鍵字時，依查詢條件中的出現順序去重，再以逗號加空白串接；頁面依 `page_number` 由小到大排列。

查詢不含 `fullText contains`、逐頁文字沒有命中，或檔案無法產生逐頁文字時，`pages` 為空陣列，檔案層級結果仍會保留。`source_location` 是 Google Drive 顯示路徑；個人雲端硬碟根目錄顯示為 `雲端硬碟`，共用雲端硬碟根目錄顯示為該共用雲端硬碟名稱。資料結構如下：

```json
[
  {
    "google_file_id": "file-1",
    "name": "Alpha.pdf",
    "mime_type": "application/pdf",
    "web_url": "https://drive.google.com/file/d/file-1/view",
    "source_location": "KBSearch_Test/Products/Alpha.pdf",
    "pages": [
      {
        "page_number": 1,
        "keyword": "推車"
      },
      {
        "page_number": 6,
        "keyword": "推車, 安裝"
      }
    ]
  }
]
```

#### `vector_results.json`

`vector_results.json` 保留 `secure_backend` 相似度搜尋回傳的檔案順序。檔案層級的 `score` 是該檔案整體相似度分數，`pages` 內的 `score` 是各命中頁面的相似度分數。資料結構如下：

```json
[
  {
    "google_file_id": "file-1",
    "source_name": "Alpha.pdf",
    "source_location": "KBSearch_Test/Products/Alpha.pdf",
    "source_url": "https://drive.google.com/file/d/file-1/view",
    "google_drive_version": "7",
    "google_drive_modified_time": "2026-05-24T00:00:00Z",
    "score": 0.91,
    "pages": [
      {
        "page_number": 3,
        "score": 0.88
      }
    ]
  }
]
```

### 開啟搜尋結果檢視網頁

查詢完成後，可啟動搜尋結果檢視頁。檢視頁會從 `KBSEARCH_TASKS_ROOT` 讀取任務資料夾，並使用 `KBSEARCH_VIEWER_PORT` 指定的 port：

```powershell
kbsearch view-results
```

指令啟動後會輸出可開啟的 `viewer_url`，以及可預設載入指定任務與搜尋結果的網址範例。若同一個 port 上已有 KBSearch 檢視頁，會先關閉後重啟；若該 port 被其他服務占用，指令會停止並提示調整 `KBSEARCH_VIEWER_PORT`。

```json
{
  "status": "starting",
  "viewer_url": "http://127.0.0.1:8501/",
  "task_query_url_example": "http://127.0.0.1:8501/?task=<task-name>&query=<query-name>",
  "tasks_dir": "C:\\path\\to\\tasks",
  "restarted_process_count": 0
}
```

### 指定 PDF 頁面轉圖

指定 PDF 路徑與頁碼，將額外需要閱讀的頁面轉為 PNG：

```powershell
kbsearch render-pdf-pages `
  --pdf "C:\path\to\<safe_file_name>-<google_file_id_prefix>\pdf\document.pdf" `
  --pages "3,5,8-10" `
  --output-dir "C:\path\to\<safe_file_name>-<google_file_id_prefix>\pages"
```

- `--pdf`：要處理的 `pdf/document.pdf` 路徑。
- `--output-dir`：完整輸出資料夾位置路徑。以目前設計，需指定到同一文件子資料夾內的 `pages/`；目錄不存在時會建立，已存在時直接使用。
- `--pages`：頁碼從 `1` 開始，支援逗號清單與區間。

`--pdf` 與 `--output-dir` 均可使用絕對或相對路徑；相對路徑以執行指令時的目前工作目錄解析。

指定頁面的同名 PNG 會直接覆蓋，其他既有頁面不受影響。成功時 stdout 會輸出包含頁碼與 PNG 路徑的 JSON。


## 離線單元測試

在 repo 根目錄執行：

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
