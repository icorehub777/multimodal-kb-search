# Tasks

本文件追蹤 `query_cli/` 與 `secure_backend/` 依 `docs/design_spec/01-高階設計規劃.md` 的實作任務。開發順序採 TDD：先補測試，再以最小實作通過測試，最後整理文件與驗收。

## 任務清單

- [x] 建立本任務清單與 end-to-end 驗收測試清單。
- [x] 盤點 importer 既有 config、adapter、domain error、CLI 與文件轉頁實作模式。
- [x] `secure_backend` 設定層：集中讀取 DashScope 與 Qdrant 設定，缺少必要設定時明確失敗。
- [x] `secure_backend` domain model：定義文字、圖片與混合查詢 request / response contract。
- [x] `secure_backend` embedding service：沿用 importer 的 DashScope 圖片 embedding 與向量維度驗證模式，新增文字查詢 embedding 入口。
- [x] `secure_backend` Qdrant search adapter：執行相似度搜尋並依 Google file ID 彙總為檔案 / 頁面兩層結構。
- [x] `secure_backend` FastAPI app：提供健康檢查與向量搜尋 API，route handler 只處理 HTTP 邊界與錯誤轉換。
- [x] `query_cli` 設定層：集中讀取 backend URL、OAuth client/token cache 與查詢結果輸出目錄。
- [x] `query_cli` Google Drive adapter：支援使用者 OAuth service 注入、全文搜尋、可存取性檢查與下載。
- [x] `query_cli` secure backend client：封裝 HTTP contract，不讓核心流程依賴 HTTP response 物件。
- [x] `query_cli` 結果輸出：建立日期時間與查詢名稱子資料夾，寫入全文與向量搜尋清單。
- [x] `query_cli` 查詢流程：並行取得全文搜尋與向量搜尋結果，取交集後下載原始檔並產生頁面 PNG。
- [x] `query_cli` CLI：提供 `probe-config` 與 `query` 子命令，library layer 不呼叫 `sys.exit()`。
- [x] 更新 `query_cli/README.md` 與 `secure_backend/README.md`，反映設定、指令與 API contract。
- [x] 執行全部離線單元測試。
- [x] 依 end-to-end 驗收測試清單完成本機離線驗收。

## End-to-End 驗收測試清單

- [x] `python -m unittest discover -s secure_backend\tests` 通過，且不需要真實 DashScope / Qdrant credential。
- [x] `python -m unittest discover -s query_cli\tests` 通過，且不需要真實 Google OAuth token 或執行中的 backend service。
- [x] `secure_backend` 設定缺少任一必要值時，`probe-config` 或設定載入會回傳明確錯誤，不輸出 secret。
- [x] `secure_backend` 向量搜尋 API 對頁面層級結果依 Google file ID 彙總；檔案依最高分排序，同檔頁面依分數排序。
- [x] `query_cli` 對同一查詢會建立 `agent_runtime/query_results/<timestamp>-<query_name>/`，且查詢名稱經過安全檔名處理。
- [x] 查詢子資料夾包含 `full_text_results.json` 與 `vector_results.json`，格式穩定且可由 Agent 後續讀取。
- [x] 只有同時出現在全文搜尋與向量搜尋清單中的檔案會被建立檔案資料夾、下載原始檔並轉出 `01.png` 起算的頁面 PNG。
- [x] 全文搜尋只透過 query CLI 的使用者 OAuth Google Drive adapter；向量搜尋只透過 `secure_backend` client。
- [x] `query_cli` 若 Google Drive 或 backend 發生錯誤，會轉成 domain error 並由 CLI 頂層回傳非 0 exit code。
- [x] README 的安裝、設定與執行方式與實作一致。
