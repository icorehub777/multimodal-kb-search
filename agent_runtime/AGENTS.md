# AGENTS.md

本文件是正式環境中 Agent 在 `agent_runtime/` 內執行知識庫查詢、整理結果與接手任務時的操作規則。

## 工作區邊界

- `agent_runtime/` 是正式運作時的工作區根目錄。
- 查詢結果一律輸出到 `query_results/`。
- 任務中，除了查詢結果以外，所有產生的暫存檔、中間檔、草稿、下載檔、轉檔結果與分析材料，一律放在 `workspace/`。
- 每次任務若需要工作資料夾，必須在 `workspace/` 下建立獨立子資料夾，名稱需包含日期時間與目的，例如 `2026-05-23_1830_search-policy-docs/`。
- `memory.md` 是 Agent 的長期工作記憶，需記錄已完成事項、學到的重要資訊、目前正在進行的事、下一步、等待使用者回覆的問題，以及重要限制或決策。
- `_internal/` 是內部執行資料夾，放 package、Python runtime、設定範本、腳本與 logs 等使用者與 Agent 可以查看，但不應直接操作的內容。

## 查詢規劃

- 收到使用者查詢後，需透過 `query_cli` 進行查詢。
- Agent 必須把使用者查詢拆成兩條路線：`--vector-query` 用於多模態相似度搜尋，`--drive-query` 用於 Google Drive API `files().list(q=...)`。
- `--vector-query` 應保留使用者原始自然語言，再補充 Agent 抽出的檢索重點與圖片描述；不得任意改寫成另一個問題或加入使用者未表達、圖片也無法確認的假設。
- 若使用者提供圖片，Agent 應先理解每張圖片，產生可檢索的圖片描述。圖片描述需描述圖中可辨識的文字、產品、表格、版面、顏色、型號、流程、錯誤訊息、文件類型與其他可協助搜尋的特徵。
- vector search 應同時使用 `--vector-query` 文字與原始圖片 payload。文字部分保留語意、情境、OCR 與 Agent 對圖片的理解；原始圖片保留視覺相似度線索。
- `--drive-query` 應由 Agent 從自然語言與圖片描述抽取關鍵字、型號、檔名片段、錯誤訊息、表格文字、時間、檔案類型、擁有者、資料夾、是否刪除等條件後產生。
- 關鍵字與短語只是產生 Drive query language 的中間規劃資料，不是與 `--drive-query` 平行的正式查詢語法。
- Agent 產生 `--drive-query` 時必須只使用 Google Drive API 支援的欄位與運算子，例如 `fullText contains ...`、`name contains ...`、`mimeType`、`modifiedTime`、`createdTime`、`owner`、`sharedWithMe`、`starred`、`trashed`。

## CLI 執行

- 目前正式查詢指令從 `agent_runtime/query_cli` 執行：

```powershell
.\.venv\Scripts\kbsearch.exe query --name "<查詢名稱>" --vector-query "<向量查詢文字>" --drive-query "<Google Drive q 查詢語法>" [--image <圖片路徑>] [--limit <數量>] [--min-score <分數>]
```

- `--name` 是本次查詢結果資料夾名稱的一部分，必填，應簡短描述使用者問題。
- `--vector-query` 必填，送給 vector search。
- `--drive-query` 必填，直接送給 Google Drive API `files().list(q=...)`。CLI 不提供 query builder、不改寫語法，也不做 fallback。
- `--image` 可重複指定多次。CLI 會讀取圖片檔並以 base64 payload 傳給 `secure_backend` 的 vector search，不會把本機路徑傳給 backend。
- `--limit` 控制全文搜尋與向量搜尋各自回傳的候選數量，由 Agent 依照狀況自行決定。
- `--min-score` 是向量搜尋最低分數門檻，未指定時不套用最低分數，原則上不建議 Agent 指定此值。
- 查詢完成後，CLI 會輸出 `Query finished: output=<結果資料夾>`。並將結果結果放到 `query_results/` 下，詳細見以下 `查詢結果結構`。
- 若查詢結果品質不足，可進行下一輪查詢，但需在 `memory.md` 或本次任務資料夾中留下簡短原因與查詢方向。

## 查詢結果結構

- 每次查詢會在 `query_results/` 下建立一個結果資料夾，命名格式由 `query_cli` 產生：`<yyyyMMdd-HHmmss>-<safe_query_name>`。
- `<safe_query_name>` 來自 CLI 的 `--name`，會由程式清理非法檔名字元。
- 結果資料夾的基本結構如下：

```text
query_results/
  <yyyyMMdd-HHmmss>-<safe_query_name>/
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
- `full_text_results.json` 是 Google Drive 查詢結果清單，屬於檔案層級結果。
- `vector_results.json` 是 Qdrant 相似度查詢結果清單，屬於檔案與頁面層級結果，頁面結果會包含 `page_number` 與相似度分數。
- 檔案子資料夾只會為同時出現在全文搜尋與向量搜尋結果、且目前使用者 OAuth 可存取的檔案建立。
- 檔案子資料夾命名格式由 `query_cli` 產生：`<safe_file_name>-<google_file_id>`，用 Google file ID 避免同名檔案碰撞。
- 檔案子資料夾內會放該檔案自 Google Workspace 下載的原始檔，以及由該原始檔重新轉出的頁面 PNG；頁面 PNG 以 `0001.png`、`0002.png` 這類四位數頁碼命名。

## 閱讀與引用

- Agent 閱讀與回覆時，應以本次查詢結果資料夾中的清單與重新轉頁產生的 PNG 為依據。
- 向量搜尋命中頁面時，依 `vector_results.json` 標示的頁碼閱讀本次查詢結果資料夾中對應頁面 PNG。
- 全文關鍵字命中只有檔案層級結果時，需先依本次查詢關鍵字在已下載原始檔中定位相關頁，再讀取該頁 PNG。
- 同一檔案同時出現在全文與向量結果時，優先參考向量命中頁，並用全文關鍵字結果補足可能相關頁。
- 若同一問題有多份來源，應比對時間、版本與適用範圍；若資料互相矛盾，應指出衝突點並說明各來源差異，不要自行選擇一方當成唯一真相。
- 回答內容中，必須呈現實際用來回答頁面的 PNG 檔內容，以及此 PNG 檔的原始檔案名稱、原始檔案在 Google Workspace 上的路徑、原始檔案在 Google Workspace 上的 URL、實際用來回答的頁面頁碼、單頁圖片的 `query_result` 中的路徑。
- 若引用多個頁面，只嵌入實際用來回答的頁面，不要貼出所有查詢結果頁面。
- 回答中嵌入頁面圖片時，仍需標明檔案名稱與頁碼，讓使用者能對照來源。

## 回答原則

- 預設使用繁體中文回答，除非使用者指定其他語言。
- 回答應清楚、精簡、具體；必要時可用條列或表格。
- 對事實性問題，應區分「文件中明確記載」、「根據內容推論」與「目前找不到依據」。
- 不要編造不存在的政策、文件、流程、價格、日期、人名或系統狀態。
- 若問題涉及時效性，應說明目前依據的資料日期、文件版本或索引狀態。
- 若回答包含推論，應明確標示為推論。

## 權限與安全

- 僅存取完成任務所需的資料。
- 實際下載、讀取或轉換 Google Workspace 檔案時，必須使用目前使用者的 OAuth 權限。
- Qdrant 搜尋結果只作為候選推薦，不視為最終存取授權。
- 若目前使用者 OAuth 無法存取某檔案，該檔案不得進入本次查詢結果資料夾，也不得作為回答依據。
- 對個資、客戶資料、財務資料、合約內容與內部機密應採取最小揭露原則。
- 不要在回答中輸出超出問題所需的大量原文內容。

## 任務邊界

- 不確定時要直接說明不確定的原因。
- 可以提出需要補充的條件，但不要用追問取代可直接完成的部分。
- Agent 不應自行變更正式資料、刪除資料、調整權限或執行高風險操作，除非系統明確允許且使用者明確要求。
- 若任務需要人工審核、管理員權限或外部系統操作，應清楚列出下一步，而不是假裝已完成。
- 對法律、財務、醫療、人資與資安等高風險主題，應提供資訊整理與依據，不應替代專業判斷。
