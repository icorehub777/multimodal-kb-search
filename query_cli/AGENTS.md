# AGENTS.md

本文件記錄 `query_cli/` 子專案（`kbsearch` CLI）的**跨指令共通**工程規範。共通規則仍以 repo 根目錄 `AGENTS.md` 為準；子指令的安裝、設定、參數、terminal 輸出與產物結構見 [`README.md`](README.md)。

## 子專案邊界

- `query_cli/` 提供 `kbsearch` 指令給終端人類員工與 Agent 使用；目前含 `query` 等子指令，後續可擴充，但本文件規範的是**所有子指令共用**的邊界與分層。
- 阿里雲 embedding model 存取與 Qdrant vector store 操作必須透過 `secure_backend` FastAPI 服務。
- 不在 `query_cli/` 中實作後端 indexing、Qdrant 寫入、DashScope SDK 呼叫或高權限 Google Workspace indexing credential 流程。

## 分層與依賴方向

- CLI layer 負責解析命令列、載入設定、組裝依賴、處理 exit code 與 terminal 輸出；library layer 不得呼叫 `sys.exit()`。
- 各子指令的核心流程應以 protocol 或注入物件接收外部能力（Google Drive、`secure_backend`、檔案處理、結果輸出等），核心邏輯不得依賴 argparse、terminal 格式或 Agent 文字格式。
- 外部服務呼叫應包在 client / adapter 中；核心流程不得直接依賴 HTTP library 的 response 物件。
- Google Drive OAuth、Drive API 操作應集中在 query CLI 專用 client；使用者 Drive 認證只能使用 OAuth 2.0 授權碼流程。
- `secure_backend` base URL、OAuth 路徑與 log 位置等環境設定應集中在設定層讀取；預設為目前工作目錄的 `config/.env`。新增或變更設定時需同步更新 config model、README 與測試。

## 檔案與路徑

- 使用 `pathlib.Path`；設定中的相對路徑相對於 CLI 執行時的目前工作目錄解析。
- 由外部輸入（指令參數、檔名、Google file ID 等）組合本機路徑時，必須避免路徑穿越與非法檔名。
- 由呼叫端指定的產物目錄應視為該次指令的寫入邊界；指令不得覆蓋既有產物目錄或寫出指定目錄之外。

## CLI 輸出

- **stderr**：錯誤訊息與長時間操作的即時進度；訊息須說明哪個設定、路徑或服務出問題，供 Agent 與人類判斷原因。
- `query` 子指令的進度 `phase` 須與 log 一致（`search`、`access_check`、`download`、`complete`）。單檔 `phase=download` 涵蓋 Drive 下載與分頁渲染；與 union 層 `download` 以欄位（如 `file_id`、`index`）區分。
- `KBSEARCH_RENDER_DOWNLOADED_FILES=false` 時只下載檔案，不得呼叫頁面 renderer。Google Docs / Slides 固定匯出 PDF，Google Sheets 固定匯出 XLSX；其他格式不得自行加入匯出策略。
- XLS/XLSX 不交由 query CLI 頁面 renderer 處理，僅保留下載檔供 Agent 使用 Spreadsheets Skill 讀取與解析。
- **stdout**：成功時輸出該子指令的**可解析結果**（格式由各指令文件定義）；失敗時 exit code 為 `1`。
- 可預期失敗須轉成明確 domain error（`ConfigError`、`ExternalServiceError`、`DocumentRenderError`、`QueryCliError` 等），保留排錯資訊；不得讓第三方 library 原始 exception 直接外洩到 terminal。
- 若 logging 已初始化，失敗訊息應附 log 檔絕對路徑；設定尚未載入成功、無法得知 log 根目錄時，僅 stderr 輸出，不得改用其他預設 log 路徑。

## Logging

- log 僅在設定載入成功後初始化；寫入 `KBSEARCH_QUERY_LOGS_ROOT`，並以每日切割保留。
- library 與 CLI 共用同一 logger；各子指令在 library 內分階段寫 log，不另建 ad hoc logger。
- log 應覆蓋**該次指令**自開始到結束的生命週期（含前置檢查、主要階段、完成或失敗），各階段須有足以追蹤進度與結果的計數或摘要。
- 步驟被跳過、權限或存取不足、外部服務或檔案處理失敗時，log 須說明原因與定位問題所需的識別資訊，不得 silent。
- 失敗路徑須保留 exception 與 traceback；摘要可含設定路徑、服務 URL 等排錯資訊，但不得輸出 token、credential 或個人敏感資料。

## 測試

- 單元測試不得依賴真實 Google OAuth token、`secure_backend` service 或外部服務 credential。
- 需要真實 OAuth 或 `secure_backend` 的探查或驗收測試必須明確命名，並與離線單元測試分開。
- 探查測試不得輸出 token、credential 或個人敏感資料。

## 文件維護

- 新增或修改子指令、CLI 參數、設定、OAuth 流程、client contract、輸出目錄或 terminal 契約時，須同步更新 README、設計文件與測試；**子指令專屬細節不寫入本 AGENTS.md**。
