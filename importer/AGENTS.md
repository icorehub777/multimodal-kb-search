# AGENTS.md

本文件記錄開發 `importer/` 子專案時必須遵守的工程規範。共通規則仍以 repo 根目錄 `AGENTS.md` 為準。

## 子專案邊界

- `importer/` 是後端 indexing / 同步程式，負責安全環境中的 Google Workspace 掃描、文件處理、embedding 與 Qdrant 寫入。
- 不在 `importer/` 中實作一般使用者查詢、Agent runtime 操作或 query CLI 專屬流程。

## 分層與依賴方向

- 外部服務存取應包在 adapter / client 中，例如 Google Drive、DashScope、Qdrant。
- CLI layer 負責組裝 importer 的正式依賴；核心流程使用 protocol 或注入物件接收外部服務能力。
- 新增外部依賴時，優先採 dependency injection，避免在核心流程中硬編碼建構細節。

## Config 與 Secret

- 所有設定讀取集中在 `app.config`，其他模組不得直接讀取環境變數。
- 缺少必要設定時必須明確失敗。
- 新增設定時同步更新 `.env.example`、config model 與測試。
- `LIBREOFFICE_COMMAND` 必須由設定層提供完整絕對路徑，不得依賴 `PATH` 中的 `soffice`。
- `KBSEARCH_CJK_FONT_PATH` 必須由設定層提供完整絕對路徑；TXT / MD 轉 PDF 只可使用此單一字型設定，不得掃描候選字型或讀取環境 fallback。
- `config/.env`、`config/gcp-adc.json`、`config/google_drive_sources.yaml`、`work/` 與同步產物屬於 importer 執行環境內容，不得提交 Git。

## Google Workspace 認證

- 背景同步採 Service Account JSON + Domain-Wide Delegation。

## 檔案與路徑處理

- 使用 `pathlib.Path` 處理本機路徑。
- 產生的工作檔案應限制在 importer 約定的工作目錄內，不得寫入 repo 根目錄或不明確位置。
- 支援格式、排除格式與轉檔規則屬於產品規格；修改時必須同步設計文件、README 與測試。
- 對檔名、Google file ID 或外部輸入組合路徑時，必須避免路徑穿越與非法檔名問題。

## Error / Logging

- 不得吞掉外部服務錯誤。
- 外部服務錯誤應轉成明確 domain error，並保留足夠排錯資訊。
- library layer 不得呼叫 `sys.exit()`；exit code 只在 CLI 頂層處理。
- 服務啟動時必須執行完整環境檢查（設定、LibreOffice、CJK 字型、Google Drive、DashScope embedding、Qdrant collection 與 vector size）；若 Qdrant collection 不存在，依 `QDRANT_COLLECTION` 與 `QDRANT_VECTOR_SIZE` 自動建立（cosine）；檢查失敗時記錄完整錯誤摘要後讓程序退出。
- logging 應能追蹤批次、文件、階段、狀態與錯誤摘要；log 固定寫入 `logs/importer.log` 並同時輸出 stdout。
- 改變 Qdrant 狀態的操作應保留可追蹤 log。

## 測試

- 單元測試不得依賴真實 Google、DashScope 或 Qdrant credential。
- 需要真實外部服務的探查或驗收測試必須明確命名，並與離線單元測試分開。
- 外部探查不得輸出 secret；若需要寫入外部服務，必須採受控 probe 資料並清理。

## 文件維護

- 修改設定、支援格式、認證方式、執行方式或外部服務契約時，必須同步更新相關 README、設計文件與測試。
