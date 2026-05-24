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
- `importer/`：文件匯入與同步子專案。
- `query_cli/`：使用者查詢 CLI 子專案。
- `secure_backend/`：受保護後端能力子專案。
- `agent_runtime/`：正式環境中 Agent 的運作區。

## 文件入口

- Repo 共通開發規範：`AGENTS.md`
- 設計文件：`docs/`
- 子專案使用方式：各子專案的 `README.md`
- 子專案開發規範：各子專案的 `AGENTS.md`
- Agent 運作區規則：`agent_runtime/AGENTS.md`

## 補充說明

- 根目錄 README 只提供專案總覽；子專案細節請看各子專案文件。
- 根目錄 `tests/` 是本機驗證用資料夾，不納入 Git 版控。
