# AGENTS.md

本文件記錄開發 `secure_backend/` 子專案時必須遵守的工程規範。共通規則仍以 repo 根目錄 `AGENTS.md` 為準。

## 子專案邊界

- `secure_backend/` 提供受保護的查詢 API，封裝 embedding 與 vector store 存取。
- 不在 `secure_backend/` 中實作使用者端認證流程、CLI 流程協調、檔案產物處理或 Agent runtime 操作。

## 分層與依賴方向

- FastAPI route handler 負責 API 認證、request / response model 驗證與 HTTP 錯誤轉換，不承擔查詢流程或外部 SDK 操作。
- 核心流程使用 service 組合查詢行為，並以 protocol 或注入物件接收外部能力。
- 外部服務存取應包在 adapter / client 中，第三方 response 必須先依明確 contract 驗證並轉成 typed model。
- 新增外部依賴時，優先採 dependency injection，避免在核心流程中硬編碼建構細節。

## Config

- 所有設定讀取集中在 `app.config`，其他模組不得直接讀取環境變數。
- 設定值須在載入時完成必要欄位、型別與範圍驗證；設定無效時必須明確失敗。
- 新增或修改設定時同步更新設定範例、config model 與測試。

## API Contract

- Request、成功 response 與錯誤 response 應使用明確 model，核心流程不得接收未驗證的 HTTP payload。
- 認證失敗、輸入錯誤與服務失敗應使用穩定錯誤結構及對應 HTTP status；對外錯誤不得包含 credential、內部連線資訊或第三方服務原始內容。
- API contract 或外部 SDK contract 變更時，必須先更新對應測試。

## Error / Logging

- Adapter / client 須為外部呼叫設定有限 timeout，並將第三方 exception 轉成明確 domain error；不得吞掉錯誤或讓第三方 exception 直接進入 route handler。
- 排錯所需的錯誤資訊與 traceback 寫入 server log，且不得包含 credential；API 僅回傳 contract 定義的安全資訊。
- logging 應能追蹤 request、處理階段、外部服務、狀態與錯誤摘要，時間統一使用 UTC。

## 測試

- Route 測試須覆蓋認證、request 驗證、HTTP status 與錯誤 response contract。
- Adapter / client 測試須覆蓋合法 response、違反 contract 的 response，以及第三方錯誤的 domain error 轉換。
