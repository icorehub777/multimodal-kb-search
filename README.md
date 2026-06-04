# KBSearch

KBSearch 專案主要目的：
1. 讓 Google Workspace 文件與圖文混合向量庫同步。
2. 讓 Codex Agent 可以透過工具執行 GCP 全文檢索與向量相似度搜尋，以回答使用者問題。

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
- `importer/`：Goolge Workspace 文件與向量庫同步子專案。
- `query_cli/`：協助 Agent 進行 google workspace 全文檢索與向量庫查詢的指令工具子專案，並透過 `secure_backend` 存取 embedding model 與操作 vector store。
- `secure_backend/`：FastAPI 子專案，封裝阿里雲 embedding model 存取與 Qdrant vector store 操作(因為此兩服務的 api key 不得讓一般使用者看到，所以必須切割出這個 api 服務專案)。
- `agent_runtime/`：正式環境中 Agent 的運作區，會把 query_cli 的指令工具打包放到此環境給 Agent 使用。

## 文件入口

- Repo 共通開發規範：`AGENTS.md`
- 設計文件：`docs/`
- 子專案使用方式：各子專案的 `README.md`
- 子專案開發規範：各子專案的 `AGENTS.md`
- Agent 運作區規則：`agent_runtime/AGENTS.md`

## 執行環境分工

- `importer/`：正式環境以 container 執行，由外部排程啟動同步工作。
- `secure_backend/`：正式環境以 container 執行，提供常態性的 FastAPI 服務。
- `query_cli/`：打包成 Python package，安裝到 `agent_runtime` 使用的 Python 環境中，提供 `kbsearch` 指令。
- `agent_runtime/`：正式環境中 Agent 進行 KB search 的工作目錄；正式運行時只需要這個目錄、已安裝的 `kbsearch` 指令。

各子專案的開發測試環境準備與正式環境部署規劃寫在各自的 `README.md`。

## 補充說明

- 根目錄 README 只提供專案總覽；子專案細節請看各子專案文件。
- 根目錄 `tests/` 是本機驗證用資料夾，不納入 Git 版控。
