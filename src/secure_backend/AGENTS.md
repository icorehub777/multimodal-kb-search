# AGENTS.md

本文件補充 `src/secure_backend/` 的工程約束；共通規範以根目錄 `AGENTS.md` 為準。修改功能前先閱讀 [`README.md`](README.md) 中相關的設定、API 與執行契約。

## 框架與分層

- API 使用 FastAPI，request / response model 使用 Pydantic；route handler 只負責認證、驗證與 HTTP 轉換，查詢流程由 service 組合。
- 設定讀取集中於 `kbsearch_backend.config`；應用程式建立與 HTTP 處理集中於 `kbsearch_backend.factory`，正式服務依賴由 `kbsearch_backend.factories` 組裝。

## 錯誤與追蹤

- 包含 framework 驗證錯誤在內的 API 失敗，均須轉成 README 定義的錯誤契約，並以 route 測試驗證；排錯細節與 traceback 留在 server log。
- 外部呼叫使用有限 timeout；log 須能對應 request、處理階段與外部服務結果。
