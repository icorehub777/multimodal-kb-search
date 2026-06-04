# AGENTS.md

本文件記錄開發 `secure_backend/` 子專案時必須遵守的工程規範。共通規則仍以 repo 根目錄 `AGENTS.md` 為準。

## 子專案邊界

- `secure_backend/` 是 FastAPI 受保護後端服務，負責阿里雲 embedding model 存取與 Qdrant vector store 操作。
- 不在 `secure_backend/` 中實作 Google Workspace 使用者 OAuth、Google Drive 全文搜尋、查詢流程協調、檔案下載、頁面 PNG 產生或 Agent runtime 操作。

## 分層與依賴方向

- FastAPI route handler 負責 HTTP 邊界處理、request / response model 驗證與錯誤轉換。
- 核心流程應使用 service / adapter 分層處理 embedding 與 Qdrant 行為，避免把外部 SDK 呼叫寫在 route handler 中。
- 外部服務存取應包在 adapter / client 中，例如阿里雲 embedding model、Qdrant。
- 新增外部依賴時，優先採 dependency injection，避免在核心流程中硬編碼建構細節。

## Config 與 Secret

- 所有設定讀取集中在 `app.config`，其他模組不得直接讀取環境變數。
- 缺少必要設定時必須明確失敗。
- 新增設定時同步更新設定範例、config model 與測試。
- 阿里雲 API key、Qdrant API key、Qdrant URL 與 collection 等執行環境設定只應透過設定層提供給 service / adapter。
- 預設設定檔位置為 `secure_backend/config/.env`；README 必須列出每個必要環境變數。

## API Contract

- Request / response 應使用明確 model，避免讓呼叫端依賴字串訊息或外部服務原始 payload。
- API 回應不得包含 API key、credential、內部 URL、完整敏感 request payload 或外部服務原始敏感內容。
- 對外錯誤應使用穩定錯誤結構；外部服務錯誤應轉成明確 domain error。
- 圖片查詢 request 必須接收圖片內容 payload，例如 base64；不得要求呼叫端傳本機路徑供 backend 讀檔。
- Qdrant 查詢 adapter 以目前 `qdrant-client` 的 `query_points` API 為 contract；若升級或改 API，需先更新 adapter 測試與 README。

## Error / Logging

- 不得吞掉外部服務錯誤。
- 服務啟動時必須執行完整環境檢查（設定、DashScope embedding、Qdrant collection 存在與 vector size）；檢查失敗時記錄完整錯誤摘要後讓程序退出。
- logging 應能追蹤 request、階段、外部服務、狀態與錯誤摘要。
- 改變 Qdrant 狀態的操作應保留可追蹤 log。

## 測試

- 單元測試不得依賴真實阿里雲或 Qdrant credential。
- 需要真實外部服務的探查或驗收測試必須明確命名，並與離線單元測試分開。
- 外部探查不得輸出 secret；若需要寫入 Qdrant，必須採受控 probe 資料並清理。

## 文件維護

- 修改設定、API contract、認證方式、執行方式或外部服務契約時，必須同步更新相關 README、設計文件與測試。
