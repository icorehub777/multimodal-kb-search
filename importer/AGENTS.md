# AGENTS.md

本文件記錄開發 `importer/` 子專案時必須遵守的工程規範。共通規則仍以 repo 根目錄 `AGENTS.md` 為準。

## 子專案邊界

- `importer/` 負責後端批次 indexing 與同步流程。
- 不在 `importer/` 中實作互動式查詢、使用者端 CLI 或 Agent runtime 專屬流程。

## 分層與依賴方向

- 外部服務存取應包在 adapter / client 中。
- CLI layer 負責組裝 importer 的正式依賴；核心流程使用 protocol 或注入物件接收外部服務能力。
- 新增外部依賴時，優先採 dependency injection，避免在核心流程中硬編碼建構細節。

## Config 與 Secret

- 所有設定讀取集中在 `app.config`，其他模組不得直接讀取環境變數。
- 缺少必要設定時必須明確失敗。
- 新增設定時同步更新 `.env.example`、config model 與測試。
- 執行環境設定、credential、工作目錄與同步產物不得提交 Git。

## 檔案與路徑處理

- 使用 `pathlib.Path` 處理本機路徑。
- 產生的工作檔案應限制在 importer 約定的工作目錄內，不得寫入 repo 根目錄或不明確位置。
- 由檔名、外部識別碼或其他外部輸入組合路徑時，必須避免路徑穿越與非法檔名問題。

## Error / Logging

- 不得吞掉外部服務錯誤。
- 外部服務錯誤應轉成明確 domain error，並保留足夠排錯資訊。
- library layer 不得呼叫 `sys.exit()`；exit code 只在 CLI 頂層處理。
- 啟動檢查失敗時應記錄可定位問題的錯誤摘要並讓程序退出。
- logging 應能追蹤批次、處理對象、階段、狀態與錯誤摘要。
- 改變外部系統狀態的操作應保留可追蹤 log。

## 測試

- 單元測試不得依賴真實外部服務或 credential。
- 需要真實外部服務的探查或驗收測試必須明確命名，並與離線單元測試分開。
- 外部探查不得輸出 secret；若需要寫入外部服務，必須採受控 probe 資料並清理。

## 文件維護

- 修改設定、執行方式、支援範圍或外部服務契約時，必須同步更新相關 README、設計文件與測試；特定功能細節不得寫入本文件。
