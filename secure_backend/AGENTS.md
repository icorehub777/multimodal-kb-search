# AGENTS.md

本文件記錄開發 `secure_backend/` 子專案時必須遵守的工程規範。共通規則仍以 repo 根目錄 `AGENTS.md` 為準。

## 子專案邊界

- `secure_backend/` 提供受保護的後端 API 與外部服務整合。
- 不在 `secure_backend/` 中實作使用者端認證流程、CLI 流程協調、檔案產物處理或 Agent runtime 操作。

## 分層與依賴方向

- FastAPI route handler 負責 HTTP 邊界處理、request / response model 驗證與錯誤轉換。
- 核心流程應使用 service / adapter 分層處理業務行為，避免把外部 SDK 呼叫寫在 route handler 中。
- 外部服務存取應包在 adapter / client 中。
- 新增外部依賴時，優先採 dependency injection，避免在核心流程中硬編碼建構細節。

## Config 與 Secret

- 所有設定讀取集中在 `app.config`，其他模組不得直接讀取環境變數。
- 缺少必要設定時必須明確失敗。
- 新增設定時同步更新設定範例、config model 與測試。
- 執行環境設定與 credential 只應透過設定層提供給 service / adapter。
- README 必須列出必要設定及其用途。

## API Contract

- Request / response 應使用明確 model，避免讓呼叫端依賴字串訊息或外部服務原始 payload。
- API 回應不得包含 credential、內部連線資訊、完整敏感 request payload 或外部服務原始敏感內容。
- 對外錯誤應使用穩定錯誤結構；外部服務錯誤應轉成明確 domain error。
- API contract 或外部 SDK contract 變更時，必須先更新對應測試與文件。

## Error / Logging

- 不得吞掉外部服務錯誤。
- 啟動檢查失敗時應記錄可定位問題的錯誤摘要並讓程序退出。
- logging 應能追蹤 request、階段、外部服務、狀態與錯誤摘要。
- 改變外部系統狀態的操作應保留可追蹤 log。

## 測試

- 單元測試不得依賴真實外部服務或 credential。
- 需要真實外部服務的探查或驗收測試必須明確命名，並與離線單元測試分開。
- 外部探查不得輸出 secret；若需要寫入外部服務，必須採受控 probe 資料並清理。

## 文件維護

- 修改設定、API contract、認證方式、執行方式或外部服務契約時，必須同步更新相關 README、設計文件與測試；特定 endpoint 或功能細節不得寫入本文件。
