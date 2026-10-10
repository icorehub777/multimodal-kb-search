# AGENTS.md

本文件補充 `query_cli/` 的工程約束；共通規範以根目錄 `AGENTS.md` 為準。修改功能前先閱讀 [`README.md`](README.md) 中相關的設定、指令與產物契約。

## 框架與實作入口

- CLI 使用 `argparse`，搜尋結果檢視頁使用 Streamlit，backend HTTP client 使用 `requests`。
- 設定讀取集中於 `kbsearch_cli.config`，正式依賴由 `kbsearch_cli.factories` 組裝；CLI 入口負責參數、exit code 與 terminal 輸出。

## 能力與檔案邊界

- 受保護的後端能力必須透過既有 backend client 存取。
- 由指令參數、檔名、外部識別碼或產物 metadata 組合本機路徑時，必須避免路徑穿越與非法檔名，並在讀寫前驗證實際路徑及既有檔案均符合所屬邊界。
- CLI 輸入須在建立 log、產物目錄或呼叫外部服務前完成驗證，並以測試確認無副作用。

## 執行與可觀測性

- terminal 輸出是通知通道，stdout 或 stderr 無法寫入時不得反過來中止已在執行的核心流程；完整狀態仍須寫入該次專屬 log。
- log 僅在設定載入成功後初始化，儲存位置統一由設定層解析；初始化前的錯誤只輸出至 stderr，不另選預設 log 路徑。初始化後的失敗訊息須附 log 檔絕對路徑。
- 有 log 的指令須以同一個 `run_id` 串接完整執行流程，涵蓋前置檢查、主要階段與終態；略過或失敗須記錄原因，各階段須有可追蹤進度的計數或摘要。

## 交付驗證

- wheel 交付驗證須涵蓋套件載入、kbsearch 指令入口與各子指令的 --help。
