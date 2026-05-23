# KBSearch

KBSearch 是用來支援 Google Workspace 文件同步、向量搜尋，以及 Codex Agent 輔助查詢與閱讀的專案。

## 資料夾結構

```text
KBSearch/
  docs/
  importer/
  query_cli/
  secure_backend/
  agent_runtime/
```

- `docs/`：設計文件。
- `importer/`：在安全電腦上執行的文件匯入與同步程式，負責掃描 Google Workspace、產生 embedding，並寫入 Qdrant。
- `query_cli/`：一般使用者電腦上執行的查詢 CLI，負責接受 Agent 指令、使用使用者 OAuth 查詢或下載文件，並整理查詢結果。
- `secure_backend/`：封裝需要保護 key 的後端能力，例如 DashScope embedding 與 Qdrant 向量查詢。
- `agent_runtime/`：正式環境中 Agent 的工作區，包含查詢結果、任務工作資料、長期 memory 與內部執行資料。

## 補充說明

- Agent 與開發規則請見 `AGENTS.md`。
- 正式運作區內的 Agent 操作規則請見 `agent_runtime/AGENTS.md`。
- 根目錄的 `tests/` 是本機驗證用資料夾，不納入 Git 版控。
