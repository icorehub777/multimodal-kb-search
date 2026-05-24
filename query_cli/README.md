# KBSearch Query CLI

`query_cli/` 是 KBSearch 提供給終端人類員工與 Agent 使用的查詢 CLI。它負責接受 `kbsearch` 指令、以目前員工身分存取 Google Drive、呼叫查詢 backend，並整理查詢結果。

## 認證機制

Query CLI 對 Google Drive API 的唯一使用者身分認證方式是 OAuth 2.0 授權碼流程。

也就是說，不論是開發期或正式發布給全公司使用，程式都會讓員工透過瀏覽器登入並授權：

```text
員工啟動 kbsearch
  -> 瀏覽器開啟 Google OAuth 授權頁
  -> 員工登入自己的 Google 帳號
  -> 員工同意程式讀取自己的 Google Drive
  -> CLI 取得該員工授權下的 access token
  -> CLI 只能查詢或下載該員工可存取的檔案
```

Query CLI 不使用以下認證方式代表員工查詢：

- service account impersonation
- Domain-Wide Delegation
- Workload Identity Federation
- importer 使用的 Application Default Credentials

這些機制屬於後端 indexing / importer 的執行環境，不屬於一般使用者查詢程式。

## 與其他子專案的邊界

- `importer/`：負責安全環境中的文件同步、轉檔、embedding 與 Qdrant 寫入。
- `secure_backend/`：封裝需要保護 key 的 embedding 與向量查詢能力。
- `query_cli/`：只處理 CLI、使用者 OAuth、查詢協調與結果整理。
- `agent_runtime/`：查詢結果、下載檔案與 Agent 工作資料應寫入此運作區。

## 安全規則

- OAuth token、refresh token、client secret 不得提交 Git。
- Log 與查詢結果不得輸出 token 或 credential。
- 查詢工具只能使用目前員工 OAuth 授權可存取的 Google Drive 資料。
- 若文件需要下載，下載動作也必須使用目前員工 OAuth 授權，不得繞過使用者權限。
