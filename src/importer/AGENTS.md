# AGENTS.md

本文件記錄開發 `src/importer/` 子專案時必須遵守的工程規範。共通規則仍以 repo 根目錄 `AGENTS.md` 為準；功能、同步行為、設定及開發與部署操作見同目錄 [`README.md`](README.md)。

## 子專案邊界

- `src/importer/` 負責後端批次 indexing 與同步流程。
- 不在 `src/importer/` 中實作互動式查詢、使用者端 CLI 或 Agent runtime 專屬流程。

## 分層與依賴方向

- 外部服務存取應包在 adapter / client 中。
- Entrypoint layer 負責組裝 importer 的正式依賴；核心流程使用 protocol 或注入物件接收外部服務能力。
- 新增外部依賴時，優先採 dependency injection，避免在核心流程中硬編碼建構細節。
- 外部服務的 response 與既有索引資料必須先依明確 contract 驗證並轉成 typed model，核心流程不得接收未驗證的資料結構。

## Config

- 所有設定讀取集中在 `kbsearch_importer.config`，其他模組不得直接讀取環境變數。
- 設定值與結構化設定檔須在載入時完成必要欄位、型別、範圍與唯一性驗證；設定無效時必須明確失敗。
- 新增設定時同步更新 `.env.example`、config model 與測試。

## 檔案與路徑處理

- 使用 `pathlib.Path` 處理本機路徑。
- 產生的工作檔案應限制在 importer 約定的工作目錄內，不得寫入 repo 根目錄或不明確位置。
- 由檔名、外部識別碼或其他外部輸入組合路徑時，必須避免路徑穿越與非法檔名問題。

## Error / Logging

- Adapter / client 須將外部服務錯誤轉成明確 domain error，並保留服務、操作與處理對象等排錯資訊；不得吞掉錯誤或讓第三方 library exception 直接進入核心流程。
- 外部服務 client 應明確設定適合批次工作的 timeout。
- library layer 不得呼叫 `sys.exit()`；exit code 只在 CLI 頂層處理。
- 啟動檢查失敗時應記錄可定位問題的錯誤摘要並讓程序退出。
- logging 應能追蹤批次、處理對象、階段、狀態與錯誤摘要。
- log 時間統一使用 UTC。
- 改變外部系統狀態的操作應保留可追蹤 log。

## 測試

- Adapter / client 測試須覆蓋合法 response、違反 contract 的 response，以及第三方錯誤的 domain error 轉換。
