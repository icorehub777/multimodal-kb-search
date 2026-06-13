# AGENTS.md

本文件是當使用者詢問問題時， Agent 執行知識庫查詢、解讀查詢結果與回答使用問題時的操作規則。

---

## 目錄結構

```text
repo_root/
  tasks/                          # 使用者任務工作區
    <yyyyMMdd-HHmmss>-<safe_task_name>/
      query_results/              # 此任務的一到多次查詢結果
      <其他任務產物>
  memory.md                       # Agent 跨 session 工作記憶
  AGENTS.md                       # Agent 操作規則
  _internal/
    .venv/                        # Python 虛擬環境
    config/
      .env                        # kbsearch 設定
      oauth_client.json           # Google OAuth Desktop 用戶端憑證
      token_cache.json            # 首次授權後由程式寫入
    packages/                     # kbsearch_cli wheel
    logs/                         # kbsearch_cli.log
```

`_internal/` 是內部執行資料夾。Agent 不得修改其中的設定、套件、虛擬環境或認證資料；允許在查詢失敗時讀取 `_internal/logs/kbsearch_cli.log` 進行排錯。

---

## 任務工作區

- 收到新的使用者任務時，必須在 `tasks/` 下建立獨立任務資料夾，命名格式為 `<yyyyMMdd-HHmmss>-<safe_task_name>`。
- 同一任務的使用者輸入、查詢結果、分析內容與產出均放在同一任務資料夾中；既有任務的後續需求繼續使用原任務資料夾。
- 任務中的每次查詢結果固定放在該任務的 `query_results/` 下；其餘內容由 Agent 依實際工作需求安排。
- `safe_task_name` 與後述 `safe_query_name` 應簡短描述目的，並避免使用 `< > : " / \ | ? *`、`..`、結尾空白或結尾句點。

---

## CLI 指令說明

當接收到使用者問題時，Agent 會使用以下指令協助進行 Google Drive 的檔案搜尋與圖文向量庫的相似度搜尋，與搜尋結果的檔案下載與分頁轉換：

執行知識庫搜尋指令時，工作目錄必須為 `_internal/`。以下為指令執行參數：

```powershell
.\.venv\Scripts\kbsearch.exe query --output-dir "../tasks/<任務資料夾>/query_results/<yyyyMMdd-HHmmss>-<safe_query_name>" --vector-query "<向量查詢文字>" --drive-query "<Google Drive q 查詢語法>" [--image <圖片路徑>] [--limit <數量>] [--min-score <分數>]
```

- `--output-dir` 必填，由 Agent 指定本次查詢結果的完整新資料夾路徑；每次執行都必須使用尚不存在的新路徑。
- `--vector-query` 必填，送給 vector search。
- `--drive-query` 必填，直接送給 Google Drive API `files().list(q=...)`。
- `--image` 可重複指定多次；路徑須為相對 `_internal/` 工作目錄的本機圖檔路徑（例如 `../tasks/<任務資料夾>/user-01.png`）。
- `--limit` 控制全文搜尋與向量搜尋各自回傳的候選數量，由 Agent 依照狀況自行決定。
- `--min-score` 是向量搜尋最低分數門檻，未指定時不套用最低分數，原則上不建議 Agent 指定此值。

---

## 執行環境規則

- 執行 `kbsearch.exe query` 時，Agent 必須直接要求使用者同意以 sandbox 外部方式執行，不得先在 sandbox 內試跑。
- 任何可能觸發 Google OAuth、瀏覽器登入視窗、GUI 視窗或本機認證流程的命令，都必須直接以 sandbox 外部同意方式執行。
- 原因是首次授權時需要開啟瀏覽器或輸出 Google OAuth URL；sandbox 內可能無法正確帶出登入流程，容易造成逾時後才重試。

---

## 查詢執行規則

- 收到使用者查詢需求後，Agent 必須把使用者查詢拆成兩條路線，包括多模態相似度搜尋與 Google Drive 檔案搜尋。
- 若使用者提供圖片，Agent 應先理解每張圖片，產生可檢索的圖片描述。圖片描述需描述圖中可辨識的文字、產品、表格、版面、顏色、型號、流程、錯誤訊息、文件類型與其他可協助搜尋的特徵。
- 多模態相似度搜尋：針對 `--vector-query` 參數傳入值，需保留使用者原始自然語言，再補充 Agent 抽出的檢索重點與圖片描述；不得任意改寫成另一個問題或加入使用者未表達、圖片也無法確認的假設。
- Google Drive 檔案搜尋：針對 `--drive-query` 參數傳入值：須從自然語言與圖片描述抽取關鍵字、型號、檔名片段等條件，組成 Google Drive API 的 `q` 語法直接傳入 CLI（非另建平行關鍵字清單），且只能使用支援的欄位與運算子，例如 `fullText contains ...`、`name contains ...`、`mimeType`、`modifiedTime`、`createdTime`、`owner`、`sharedWithMe`、`starred`、`trashed`。
- 使用者附圖：將圖片存至目前任務資料夾中（檔名建議 `user-01.png`、`user-02.png`），再以 `--image` 傳入相對 `_internal/` 的路徑（例如 `../tasks/<任務資料夾>/user-01.png`）；多張圖可重複指定 `--image`。
- 執行前須依日期時間與查詢目的產生新的查詢結果路徑。若指令回報路徑已存在，不得覆蓋、刪除或重用該資料夾，應改用新的查詢結果路徑重新執行。
- 查詢結果資料夾一旦建立，不論查詢成功或失敗均不得刪除或供後續查詢重用；查詢失敗時應保留其中的部分產物供排錯。
- 查詢失敗時，先閱讀 stderr 的錯誤訊息與 `_internal/logs/kbsearch_cli.log`。可自行處理的路徑、查詢參數或任務檔案問題應先修正後重試；涉及權限、外部服務、部署環境或其他無法處理的問題，再向使用者說明原因與所需處理方式。


## 查詢結果結構

- 每次查詢結果位於 Agent 透過 `--output-dir` 指定的獨立資料夾中。
- 指令執行成功時，**stdout** 會回傳 JSON，其中 `output_dir` 即本次查詢結果資料夾路徑。
- 結果資料夾的基本結構如下：

```text
<output_dir>/
  query_plan.json
  full_text_results.json
  vector_results.json
  <safe_file_name>-<google_file_id>/
    <downloaded original file>
    0001.png
    0002.png
    ...
```

- `query_plan.json` 記錄本次實際使用的 `vector_query`、`drive_query`、`image_paths`、`limit` 與 `min_score`。
- `full_text_results.json` 是此使用者有權限存取的檔案的 Google Drive 查詢結果清單，屬於檔案層級結果。
- `vector_results.json` 是此使用者有權限存取的檔案的圖文向量庫的相似度查詢結果清單，屬於檔案與頁面層級結果，頁面結果會包含 `page_number` 與相似度分數。
- 針對 Google Drive 查詢結果清單與相似度查詢結果清單的聯集檔案清單（`file_id` 去重） 中的每個檔案，都建立一個以 `<safe_file_name>-<google_file_id>` 命名的檔案子資料夾。
- 每個檔案子資料夾內會放該檔案自 Google Drive 下載的原始檔，以及由該原始檔重新轉出的頁面 PNG；頁面 PNG 以 `0001.png`、`0002.png` 這類四位數頁碼命名。

---

## 閱讀與引用

- Agent 閱讀與回覆時，應以本次查詢結果資料夾中的清單與轉頁產生的 PNG 為依據。
- 閱讀向量搜尋命中頁面時，優先依 `vector_results.json` 標示的頁碼，閱讀本次查詢結果資料夾中對應頁面 PNG。
- 閱讀檔案搜尋結果時，盡可能避免閱讀整份文檔，需先依本次查詢關鍵字在已下載原始檔中定位相關頁，再讀取該頁對應之頁面 PNG。
- 同一檔案同時出現在全文與向量結果時，優先參考向量命中頁，並用全文關鍵字結果補足可能相關頁。
- 若同一問題有多份來源，應比對時間、版本與適用範圍；若資料互相矛盾，應指出衝突點並說明各來源差異，不要自行選擇一方當成唯一真相。
- 回答使用者時，除非使用者要求說明搜尋方法，否則不要標示或強調內容來自全文搜尋或向量搜尋；搜尋類型只作為 Agent 內部閱讀排序與定位依據。對外應以文件名稱、頁碼、版本、日期、Google Drive 路徑與內容重點描述來源。
- 回答時只嵌入實際用來回答的頁面 PNG（不得貼出所有查詢結果頁面），並標明原始檔案名稱、Google Drive 路徑與 URL、頁碼，以及該 PNG 在 repo 根目錄的相對路徑，讓使用者能對照來源。
- 若查詢結果品質不足以回答使用者問題，可透過調整查詢或擴大回傳之查詢結果頁面進行下一輪查詢。

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

## Memory.md 填寫規則

- `memory.md` 供跨 session 接手任務時所需的資訊。
- **更新時機**：
  - 開始新一輪查詢或後續任務時，更新「目前正在處理」。
  - `kbsearch query` 完成並取得 `output_dir` 後，更新「最近查詢與處理紀錄」；若該輪查詢已可直接回答或任務結束，清空或重置「目前正在處理」。
  - 查詢結果不足而進行下一輪查詢前，在「最近查詢與處理紀錄」或「後續建議」簡記本輪不足原因與調整方向。
  - 發現會影響後續判斷的資料限制、索引狀態或重要結論時，更新「已知資料狀態」或「重要發現」。
  - 需等待使用者補充條件或確認時，更新「待確認」。
  - session 結束或任務暫停前，確保「目前正在處理」與「待確認」反映最新狀態。
- **更新注意**
  - 以任務資料夾與查詢結果資料夾路徑等**指標**記錄即可；詳細清單、下載檔、PNG 與任務產物仍以該任務資料夾內的檔案為準。
  - 同一任務持續進行時更新既有條目，避免並留多份互相矛盾的「目前正在處理」。

---
