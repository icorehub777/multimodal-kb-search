# AGENTS.md

本文件記錄開發 `query_cli/` 子專案時必須遵守的工程規範。共通規則仍以 repo 根目錄 `AGENTS.md` 為準。

## 子專案邊界

- `query_cli/` 是給終端人類員工與 Agent 使用的查詢 CLI，負責使用者查詢流程與查詢結果檔案處理流程。
- 阿里雲 embedding model 存取與 Qdrant vector store 操作必須透過 `secure_backend` FastAPI 服務。
- 不在 `query_cli/` 中實作後端 indexing、Qdrant 寫入、DashScope SDK 呼叫或高權限 Google Workspace indexing credential 流程。

## 分層與依賴方向

- CLI layer 負責解析命令列參數、載入 query CLI 設定、組裝正式依賴與處理 exit code。
- 查詢流程核心應使用 protocol 或注入物件接收 Google Drive、`secure_backend` client、檔案處理與結果輸出能力。
- Google Drive OAuth、全文搜尋、檔案可存取性檢查與下載應包在 query CLI 專用 client / adapter 中。
- `secure_backend` 呼叫應包在 client 中，核心流程不得直接依賴 HTTP library 的 response 物件。
- 傳送圖片查詢至 `secure_backend` 時，HTTP request 必須包含圖片內容本身，例如 base64 payload；不得傳送 CLI 本機路徑並要求 backend 讀取。

## Config 與認證

- 使用者 Google Drive 認證只能使用 OAuth 2.0 授權碼流程。
- 不使用 service account impersonation、Domain-Wide Delegation、Workload Identity Federation 或 importer 的 Application Default Credentials 代表使用者查詢。
- OAuth token cache 若需要落地，必須放在使用者個人環境或明確設定的位置，不得寫入 repo 根目錄。
- `secure_backend` base URL、OAuth client 設定與輸出位置等 query CLI 設定應集中在設定層讀取。
- 預設設定檔位置為 `query_cli/config/.env`；新增設定時需同步更新 config model、README 與測試。

## 檔案與路徑處理

- 使用 `pathlib.Path` 處理本機路徑。
- 查詢下載或產生的檔案必須限制在 `agent_runtime/` 約定的查詢結果目錄內。
- 對查詢名稱、檔案名稱、Google file ID 或外部輸入組合路徑時，必須避免路徑穿越與非法檔名問題。
- 下載交集檔案的資料夾名稱必須含 Google file ID 或等價唯一識別，避免正規化後檔名碰撞。
- 產生結果清單、下載原始檔與頁面 PNG 時，應維持穩定且可測試的檔案命名規則。
- 文件轉頁支援規則需與 README 和測試一致；TXT / MD 轉 PDF 若含 CJK 文字，需使用可設定的 `KBSEARCH_CJK_FONT_PATH` 或系統候選字型。

## Error / Logging

- library layer 不得呼叫 `sys.exit()`；exit code 只在 CLI 頂層處理。
- Google Drive 與 `secure_backend` 錯誤應轉成明確 domain error，並保留足夠排錯資訊。
- logging 應能追蹤查詢名稱、階段、檔案、狀態與錯誤摘要。

## 測試

- 單元測試不得依賴真實 Google OAuth token、`secure_backend` service 或外部服務 credential。
- 需要真實 OAuth 或 `secure_backend` 的探查或驗收測試必須明確命名，並與離線單元測試分開。
- 探查測試不得輸出 token、credential 或個人敏感資料。

## 文件維護

- 修改 CLI 參數、設定方式、OAuth 流程、`secure_backend` client contract、輸出目錄結構或檔案命名規則時，必須同步更新相關 README、設計文件與測試。
