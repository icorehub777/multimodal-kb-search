# AGENTS.md

本文件是當使用者詢問問題時， Agent 執行知識庫查詢、解讀查詢結果與回答使用問題時的操作規則。

---

## 目錄結構

```text
repo_root/
  tasks/                          # 使用者任務工作區
    <yyyyMMdd-HHmmss>-<safe_task_name>/
      memory.md                   # 此任務跨 session 的工作記憶
      query_results/              # 此任務的一到多次查詢結果
      <其他任務產物>
  memory.md                       # 目前作用中任務指標與跨任務記憶
  AGENTS.md                       # Agent 操作規則
  _internal/
    .venv/                        # Python 虛擬環境
    config/
      .env                        # kbsearch 設定
      oauth_client.json           # Google OAuth Desktop 用戶端憑證
      token_cache.json            # 首次授權後由程式寫入
    packages/                     # kbsearch_cli wheel
    logs/                         # 每次 query 的獨立 kbsearch-<日期時間>-<run_id>.log
```

`_internal/` 是內部執行資料夾。Agent 不得修改其中的設定、套件、虛擬環境或認證資料；允許讀取 query 在 stderr 回報的該次專屬 log 以監看進度或排錯。

---

## 任務工作區

- 收到新的使用者任務時，必須在 `tasks/` 下建立獨立任務資料夾，命名格式為 `<yyyyMMdd-HHmmss>-<safe_task_name>`。
- 建立新任務資料夾時，必須同時建立該任務的 `memory.md`。若根目錄 `memory.md` 尚不存在，也必須依本文件規範建立。
- 同一任務的使用者輸入、查詢結果、分析內容與產出均放在同一任務資料夾中；既有任務的後續需求繼續使用原任務資料夾。
- 任務中的每次查詢結果會固定放在該任務的 `query_results/` 下；其餘內容由 Agent 依實際工作需求安排。
- 若需產生查詢結果既有結構以外的臨時分析產物，可依用途在目前任務資料夾中建立名稱明確的子資料夾；不得寫入 `_internal/` 或其他任務資料夾，也不得寫入目前任務資料夾中的 `query_results/` 中。
- `safe_task_name` 與後述 `safe_query_name` 應簡短描述目的，並避免使用 `< > : " / \ | ? *`、`..`、結尾空白或結尾句點。

---

## CLI 指令說明

當接收到使用者問題時，Agent 會使用以下指令協助進行 Google Drive 的檔案搜尋與圖文向量庫的相似度搜尋，並下載搜尋結果檔案：

執行知識庫搜尋指令時，工作目錄必須為 `_internal/`。以下為指令執行參數：

```powershell
.\.venv\Scripts\kbsearch.exe query --output-dir "../tasks/<任務資料夾>/query_results/<yyyyMMdd-HHmmss>-<safe_query_name>" --vector-query "<向量查詢文字>" --drive-query "<Google Drive q 查詢語法>" [--image <圖片路徑>] [--limit <數量>] [--min-score <分數>]
```

- `--output-dir` 必填，由 Agent 指定本次查詢結果的新資料夾路徑；路徑相對於 `_internal/` 工作目錄，每次執行都必須使用尚不存在的新路徑。
- `--vector-query` 必填，送給 vector search。
- `--drive-query` 必填，直接送給 Google Drive API `files().list(q=...)`。
- `--image` 可重複指定多次；路徑須為相對 `_internal/` 工作目錄的本機圖檔路徑（例如 `../tasks/<任務資料夾>/user-01.png`）。
- `--limit` 控制關鍵字搜尋與向量搜尋各自回傳的候選數量，由 Agent 依照狀況自行決定。
- `--min-score` 是向量搜尋最低分數門檻，未指定時不套用最低分數，原則上不建議 Agent 指定此值。

需要將查詢結果中的 PDF 額外頁面轉成 PNG 時，工作目錄同樣必須為 `_internal/`：

```powershell
.\.venv\Scripts\kbsearch.exe render-pdf-pages --pdf "../tasks/<任務資料夾>/query_results/<查詢資料夾>/<文件資料夾>/pdf/document.pdf" --pages "<頁碼或範圍>" --output-dir "../tasks/<任務資料夾>/query_results/<查詢資料夾>/<文件資料夾>/pages"
```

- `--pdf` 必填，必須明確指定要處理的 `pdf/document.pdf`；路徑相對於 `_internal/` 工作目錄。
- `--pages` 必填，頁碼從 `1` 開始，支援單頁、逗號清單與區間，例如 `3,5,8-10`。
- `--output-dir` 必填，固定指定同一文件資料夾內的 `pages/`；路徑相對於 `_internal/` 工作目錄。目錄可存在；同頁碼 PNG 會直接覆蓋，其他頁面保留。


---

## 使用 CLI 指令執行查詢的規則

- 收到使用者查詢需求後，Agent 必須把使用者查詢拆成兩條路線，包括多模態相似度搜尋與 Google Drive 檔案搜尋。
- 若使用者提供圖片，Agent 應先理解每張圖片，產生可檢索的圖片描述。圖片描述需描述圖中可辨識的文字、產品、表格、版面、顏色、型號、流程、錯誤訊息、文件類型與其他可協助搜尋的特徵。
- 多模態相似度搜尋：針對 `--vector-query` 參數傳入值，需保留使用者原始自然語言，再補充 Agent 抽出的檢索重點與圖片描述；不得任意改寫成另一個問題或加入使用者未表達、圖片也無法確認的假設。
- Google Drive 檔案搜尋：針對 `--drive-query` 參數傳入值：須從自然語言與圖片描述抽取關鍵字、型號、檔名片段等條件，組成 Google Drive API 的 `q` 語法直接傳入 CLI（非另建平行關鍵字清單），且只能使用支援的欄位與運算子，例如 `fullText contains ...`、`name contains ...`、`mimeType`、`modifiedTime`、`createdTime`、`owner`、`sharedWithMe`、`starred`、`trashed`。
- 使用者附圖：將圖片存至目前任務資料夾中（檔名建議 `user-01.png`、`user-02.png`），再以 `--image` 傳入相對 `_internal/` 的路徑（例如 `../tasks/<任務資料夾>/user-01.png`）；多張圖可重複指定 `--image`。
- 執行前須依日期時間與查詢目的產生新的查詢結果路徑。若指令回報路徑已存在，不得覆蓋、刪除或重用該資料夾，應改用新的查詢結果路徑重新執行。
- 執行查詢時必須直接以 sandbox 外部同意方式執行。因在 sandbox 內執行時，無法正確開啟給使用者登入的瀏覽器頁面。
- 預期查詢可能長時間下載或轉檔時，應以背景程序執行，並將 stdout、stderr 重新導向至系統暫存檔，避免呼叫端結束後關閉 pipe。背景啟動與每次狀態檢查只設定短 timeout，不為整批 query 設定固定總 timeout。
- 啟動後先從 stderr 取得 `run_id` 與 `log` 路徑，再以短間隔輪詢該次專屬 log 與背景程序狀態，並依新進度持續向使用者更新。不得只輪詢共用 log，也不得因一段時間沒有新訊息就判定完成。
- query 啟動時會依 `KBSEARCH_QUERY_LOG_RETENTION_DAYS` 清理過期的 `kbsearch-*.log`；清理失敗會讓 query 以失敗終態結束，Agent 應依 stderr 與該次專屬 log 回報原因。
- 每次 query 正常結束時，stderr 必須出現 `phase=query` 的 `status=finished`、`status=finished_with_errors` 或 `status=failed`，專屬 log 也必須有相同終態。成功或部分成功時另須讀取 stdout JSON；失敗時須讀取 stderr 錯誤摘要。
- 只有在看到終態且背景程序已結束後，才可判定 query 完成。若程序已結束但沒有終態，視為異常中止，須讀取該次專屬 log 與暫存 stderr 排錯。完成判讀後需刪除重新導向用的 stdout、stderr 暫存檔；正式 application log 不得刪除。
- 查詢結果資料夾一旦建立，不論查詢成功或失敗均不得刪除或供後續查詢重用；查詢失敗時應保留其中的部分產物供排錯。
- 查詢失敗時，先閱讀 stderr 的錯誤訊息與該次 `run_id` 對應的專屬 log。可自行處理的路徑、查詢參數或任務檔案問題應先修正後重試；涉及權限、外部服務、部署環境或其他無法處理的問題，再向使用者說明原因與所需處理方式。


## 查詢結果結構

- 每次查詢結果位於 Agent 透過 `--output-dir` 指定的獨立資料夾中。
- 指令執行成功時，**stdout** 會回傳 JSON，其中 `output_dir` 即本次查詢結果資料夾路徑。
- 結果資料夾的基本結構如下：

```text
<output_dir>/
  query_plan.json
  full_text_results.json
  vector_results.json
  download_failures.json
  warnings.json
  <safe_file_name>-<google_file_id>/
    <downloaded original file>
    pdf/
      document.pdf
    text/
      0001.txt
      0002.txt
    pages/
      <vector hit page>.png
```

- `query_plan.json` 記錄本次實際使用的 `vector_query`、`drive_query`、`image_paths`、`limit` 與 `min_score`。
- `full_text_results.json` 是此使用者有權限存取的檔案的 Google Drive 查詢結果清單，屬於檔案層級結果。
- `vector_results.json` 是此使用者有權限存取的檔案的圖文向量庫的相似度查詢結果清單，屬於檔案與頁面層級結果，頁面結果會包含 `page_number` 與相似度分數。
- `download_failures.json` 記錄無法完成 metadata 補查、產物目錄建立、下載或文件處理的檔案；沒有失敗時內容為空陣列。
- `warnings.json` 記錄非失敗但會影響閱讀完整性的狀況；沒有警告時內容為空陣列。
- 針對 Google Drive 查詢結果清單與相似度查詢結果清單的聯集檔案清單（`file_id` 去重） 中的每個檔案，都建立一個以 `<safe_file_name>-<google_file_id>` 命名的檔案子資料夾。
- 每個檔案子資料夾會保留該檔案自 Google Drive 下載的檔案；Google Docs 與 Google Slides 由 Drive API 匯出為 PDF，Google Sheet 匯出為 XLSX。
- PDF、Word、PowerPoint、TXT、MD 另提供固定路徑 `pdf/document.pdf` 與逐頁 UTF-8 TXT；原始檔本身為 PDF 時仍會保留下載檔。
- `pages/` 只包含向量搜尋命中的頁面，不會預先渲染關鍵字搜尋結果或整份文件。
- XLS/XLSX 不產生 PDF、逐頁 TXT 或 PNG。圖片不產生 PDF 或 TXT；向量命中時提供 `pages/0001.png`。

---

## 閱讀與引用

- Agent 閱讀與回覆時，應以本次查詢結果清單、逐頁文字、命中頁 PNG 與已下載檔案為依據。
- stdout 的 `status` 若為 `finished_with_errors`，查詢結果仍可使用，但 Agent 必須先讀取 `download_failures` 或 `download_failures.json`，並在回答中明確告知使用者哪些檔案未能下載或處理及其原因；不得將結果描述為完整成功。
- 告知失敗檔案時須附上 `google_drive_url`，請使用者直接到 Google Drive 查看原檔。若 `vector_page_numbers` 非空，須告知向量搜尋命中的頁碼；若 `full_text_query` 有值，須告知關鍵字搜尋使用的查詢條件，協助使用者自行在原檔中查找。
- stdout 的 `warning_count` 若大於 `0`，Agent 必須讀取 `warnings` 或 `warnings.json`。若警告 `code` 為 `vector_pages_unrendered`，代表向量搜尋命中頁碼存在，但該檔案沒有產生對應的 `pages/*.png`；Agent 不得假設該向量命中頁面已可直接閱讀，應改以原始下載檔或其他工具能力判讀，並在必要時向使用者說明該檔案的向量命中頁面無法產生圖片、結果可能不完整。
- PDF、Word、PowerPoint、TXT、MD 統一以 `text/*.txt` 進行內容定位，使用 `rg` 的固定文字、大小寫、regex、前後文與檔案篩選能力搜尋；TXT 檔名即對應 PDF 頁碼。
- 確定需閱讀的頁碼後，優先使用既有 `pages/*.png`；尚未產生的頁面使用 `render-pdf-pages` 從該檔案的 `pdf/document.pdf` 轉出至同一文件資料夾的 `pages/`。
- XLS/XLSX 使用 Spreadsheets Skill。圖片直接檢視原圖或既有 `pages/0001.png`。
- Google Sheets 由 query CLI 匯出為 XLSX，與 Drive 上原有的 XLS/XLSX 一樣使用 Spreadsheets Skill 讀取與解析；試算表不會出現在向量搜尋結果中，但可能由關鍵字搜尋命中。
- 閱讀向量搜尋命中頁面時，先依 `vector_results.json` 標示的頁碼讀取查詢結果已產生的 PNG。若相關頁內容不完整，可使用 `render-pdf-pages` 取得相鄰頁。
- 若是只有關鍵字搜尋命中的檔案，先以 `rg` 搜尋逐頁 TXT 定位頁碼，再按需將命中頁及必要相鄰頁轉成 PNG。逐頁 TXT 無法包含掃描文字、圖片、圖表或完整表格版面，因此最終內容確認仍以 PNG 為準。
- 同一檔案同時出現在關鍵字與向量結果時，優先參考向量命中頁，並用關鍵字搜尋結果補足可能相關頁。
- 若同一問題有多份來源，應比對時間、版本與適用範圍；若資料互相矛盾，應指出衝突點並說明各來源差異，不要自行選擇一方當成唯一真相。
- 回答使用者時，除非使用者要求說明搜尋方法，否則不要標示或強調內容來自關鍵字搜尋或向量搜尋；搜尋類型只作為 Agent 內部閱讀排序與定位依據。對外應以文件名稱、頁碼、版本、日期、Google Drive 路徑與內容重點描述來源。
- 回答時除了參考此頁的 PNG 內容進行回答外，需嵌入實際用來回答的頁面 PNG (不得貼出所有查詢結果頁面)，並需呈現文件名稱、頁碼、版本、日期、Google Drive 路徑與內容回答。
- 若查詢結果不足以回答使用者問題，可透過調整查詢或擴大回傳之查詢結果進行下一輪查詢。

---

## 回答原則

- 預設使用繁體中文回答，除非使用者指定其他語言。
- 回答應清楚、精簡、具體；必要時可用條列或表格。
- 對事實性問題，應區分「文件中明確記載」、「根據內容推論」與「目前找不到依據」。
- 不要編造不存在的政策、文件、流程、價格、日期、人名或系統狀態。
- 若問題涉及時效性，應說明目前依據的資料日期、文件版本或索引狀態。
- 不要在回答中輸出超出問題所需的大量原文內容。
- 若回答包含推論，應明確標示為推論。
- 不確定時要直接說明不確定的原因。

---

## Memory 操作規則

Memory 分為根目錄 `memory.md` 與各任務資料夾內的 `memory.md`。兩者用途與生命週期不同，不得將單一任務的詳細狀態寫入根目錄 memory，也不得只更新其中一種而使作用中任務指標與實際任務狀態互相矛盾。

### 根目錄 memory

- 根目錄 `memory.md` 用於讓新的 session 找到唯一的目前作用中任務，並保存可供不同任務一起參考、且會隨實際運作改變的跨任務記憶。
- Agent 建立任務時，若發現沒有此根目錄 `memory.md`，必須依以下格式建立：

```markdown
# Agent Memory

## 目前作用中任務

`tasks/<任務資料夾>/`

## 跨任務記憶

無
```

- 「目前作用中任務」只能記錄一個任務資料夾路徑。開始新任務或恢復既有任務時，必須將其更新為該任務資料夾；任務完成且沒有後續工作時，改為 `無`。
- 「跨任務記憶」只記錄可供未來不同任務重複參考的動態資訊，例如資料索引範圍與限制、常用文件位置、文件命名慣例、有效搜尋策略，使用者特殊喜好，以及會影響多個任務的待確認事項。
- 不得在根目錄 memory 記錄單一任務的目前階段、查詢紀錄、完整發現、待確認事項或下一步；這些資訊應寫入該任務的 memory。
- 不得重複記錄已在 `AGENTS.md`、README 或設計文件中完整說明的固定規則。
- 沒有可記錄的跨任務記憶時保持 `無`，不為了填滿章節而加入內容。

### 任務 memory

- 每個任務資料夾必須有自己的 `memory.md`，用於保存該任務跨 session 接手所需的簡要狀態。
- 建立任務時，必須依以下格式建立任務 memory，並填入當下已知內容：

```markdown
# Task Memory

## 任務目標

## 目前階段

## 已完成工作

## 關鍵發現與依據

## 待確認事項

## 下一步
```

- 「任務目標」記錄使用者要解決的問題與預期產出。
- 「目前階段」記錄任務目前所處狀態，例如準備查詢、閱讀結果、整理回答、等待使用者補充或已完成。
- 「已完成工作」只摘要已完成的重要工作，並指向相關查詢結果資料夾或任務產物；不得記錄指令流水帳。
- 「關鍵發現與依據」記錄會影響此任務後續判斷的結論、來源檔案、頁碼及相關路徑。
- 「待確認事項」記錄需要使用者或其他人確認的問題及其影響；已解決事項應移除或整理至已完成工作。
- 「下一步」必須是下一個 Agent 可直接執行的具體行動；任務完成時改為 `無`。
- 詳細查詢清單、下載檔案、按需產生的頁面圖片、分析內容與產出仍以任務資料夾內的實際檔案為準；任務 memory 只保存摘要與路徑指標。

### 建立、接手與更新流程

- 建立第一個任務時，同時建立根目錄 memory 與任務 memory，並將根目錄「目前作用中任務」指向新任務。
- 切換作用中任務前，先更新原作用中任務 memory 的目前階段與下一步；確認目標任務 memory 存在且內容可供接手後，再更新根目錄作用中任務指標與目標任務 memory。
- 新 session 開始時，若根目錄 memory 不存在且沒有任何既有任務，代表尚未依本規範建立任務。若根目錄 memory 不存在但已有任務資料夾，屬於狀態不一致，不得依建立時間或修改時間自行猜測作用中任務。
- 根目錄 memory 存在時，先讀取其「目前作用中任務」；若其值不是 `無`，再讀取對應的任務 memory 後才繼續工作。
- `kbsearch query` 完成並取得 `output_dir` 後，更新作用中任務 memory 的已完成工作、關鍵發現與依據、目前階段及下一步。
- 查詢結果不足而準備進行下一輪查詢前，在作用中任務 memory 記錄不足原因與具體調整方向。
- 發現對其他未來任務仍有價值的資訊時，先在作用中任務 memory 保留依據，再將精簡且可重複使用的結論提升至根目錄「跨任務記憶」。
- 需要等待使用者補充或確認時，更新作用中任務 memory 的目前階段、待確認事項與下一步。
- session 結束或任務暫停前，確保根目錄作用中任務指標正確，且對應任務 memory 足以讓新的 session 直接接手。
- 任務完成時，將任務 memory 的目前階段標示為已完成、下一步改為 `無`，並將根目錄「目前作用中任務」改為 `無`。

---
