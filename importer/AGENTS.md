# AGENTS.md

本文件補充 `importer/` 的工程約束；共通規範以根目錄 `AGENTS.md` 為準。修改功能前先閱讀 [`README.md`](README.md) 中相關的同步、設定與執行契約。

## 實作入口

- 設定讀取集中於 `kbsearch_importer.config`，結構化 YAML 設定使用 PyYAML。
- 正式依賴集中於 `kbsearch_importer.factories` 組裝，由 orchestrator 協調同步流程，各處理階段透過注入物件銜接。

## 工作檔案與追蹤

- 文件處理產物放在約定的工作目錄；由外部檔名或識別碼組合路徑時，驗證其不會跨出所屬目錄。
- Log 須能對應同一次批次執行中的文件、處理階段與結果；外部資料寫入與刪除須留下可追蹤紀錄。
