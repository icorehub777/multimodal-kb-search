# AGENTS.md

本文件是 `query_cli/` 子專案的開發規範。共通工程規則仍以 repo 根目錄 `AGENTS.md` 為準。

## 子專案定位

- `query_cli/` 是給終端人類員工與 Agent 使用的查詢 CLI。
- `query_cli/` 負責解析 `kbsearch` 指令、執行 Google Drive 使用者授權、呼叫查詢 backend、整理查詢結果，並將輸出放入 `agent_runtime/` 的指定位置。
- `query_cli/` 不負責後端 indexing、不寫入 Qdrant、不持有 DashScope API key，也不使用高權限 Google Workspace indexing credential。

## Google Workspace 認證規範

- `query_cli/` 對 Google Drive API 的唯一使用者身分認證方式是 OAuth 2.0 授權碼流程。
- 不論本機開發期或正式發布給全公司使用，都必須讓員工在瀏覽器中登入並同意授權，例如同意程式讀取自己的 Google Drive。
- `query_cli/` 不得使用 service account impersonation、Domain-Wide Delegation 或 Workload Identity Federation 來代表員工查詢。
- `query_cli/` 不得讀取 importer 的 Google Application Default Credentials，也不得依賴 `google.auth.default()` 取得員工查詢身分。
- OAuth token cache 若需要落地，必須放在使用者個人環境或明確設定的位置，不得提交 Git，也不得寫入 repo 根目錄。
- Log 與查詢結果不得記錄 access token、refresh token、OAuth client secret 或其他 credential。

## 架構邊界

- CLI 參數解析與輸出格式應留在 CLI layer。
- Google Drive 使用者 OAuth 與文件可存取性檢查屬於 query CLI layer。
- DashScope embedding 與 Qdrant vector search 應透過 backend client 呼叫，不得在 CLI 中直接使用外部服務 SDK 或 secret。
- Request / response contract 應使用明確結構，避免讓核心流程依賴 terminal output 或 Agent 文字格式。
- 查詢下載或產生的檔案必須寫入 `agent_runtime/` 下的規定子資料夾，不得任意寫入 repo 根目錄。

## 測試規範

- 新增 CLI 參數、OAuth 流程、查詢結果整理或 backend client 行為時，優先先寫測試。
- 單元測試不得依賴真實 Google OAuth token、DashScope、Qdrant 或 backend service。
- 需要真實 OAuth 的探查測試必須明確命名，且不得輸出 token 或個人敏感資料。
