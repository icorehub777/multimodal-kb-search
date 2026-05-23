# AGENTS.md

本文件提供 repo 開發時的共通工程規則。各子專案的細部規範，皆寫在該子專案自己的 `AGENTS.md`。

## 專案簡述

KBSearch 是用來支援 Google Workspace 文件同步，並協助 Codex Agent 進行多模態向量查詢與 Google Workspace 關鍵字查詢。

主要開發子專案如下：

- `importer/`：在安全電腦上執行匯入與同步程式。
- `query_cli/`：在一般使用者電腦上執行的查詢 CLI。
- `secure_backend/`：封裝需要保護 key 的 embedding 與向量查詢能力。
- `agent_runtime/`：正式 Agent 的工作區，不是一般開發輸出區。

## 使用技術

- Python 3.10+
- Google Workspace / Google Drive API
- 使用者 OAuth (Google Drive API)
- DashScope / Qwen 多模態 embedding
- Qdrant vector database
- Python package 與 CLI entry point
- Windows Service

## 資料夾結構

```text
KBSearch/
  docs/
  importer/
  query_cli/
  secure_backend/
  agent_runtime/
  tests/
```

- `docs/`：設計文件。
- `importer/`：同步 Google Workspace 文件、轉檔、產生 embedding、寫入 Qdrant。
- `query_cli/`：提供給 Agent 使用的 `kbsearch` CLI。包括 CLI 參數解析、Google Drive API 目前使用者 OAuth 授權、查詢流程協調與結果整理。
- `secure_backend/`：封裝 DashScope embedding、Qdrant 查詢，以及 service 化需要的 backend client 邊界。
- `agent_runtime/`：正式運作時的 Agent 工作區。其正式運作規則見 `agent_runtime/AGENTS.md`。
- `tests/`：本機驗證與 spike 測試資料夾，不納入 Git 版控。

## 架構邊界

- `importer/` 負責安全環境中的同步、轉檔、embedding、Qdrant 寫入，不應部署到一般使用者電腦。
- `query_cli/` 負責 CLI 參數解析、Google Drive API 目前使用者 OAuth 授權、查詢流程協調、結果整理與 `agent_runtime/memory.md` 更新。
- `secure_backend/` 負責封裝需要保護 key 的操作，包括 DashScope embedding 與 Qdrant vector search。
- CLI 不應直接依賴 DashScope 或 Qdrant SDK；需要 embedding 或 vector search 時應透過 backend client。
- 核心邏輯不應依賴 CLI `print`、`argparse`、terminal output 或 Agent 文字格式。
- Request / response contract 應保持穩定，並優先使用 typed dataclass、Pydantic model 或等價的明確結構。
- 子專案專屬規則應放在各自的 `AGENTS.md`，不要把細節全部塞進根目錄規範。

## 跨專案開發規範

- 採測試驅動開發。新增或修改行為時，優先先寫可重現需求或問題的測試。
- 遵循紅綠燈規則：
  - Red：先寫出失敗測試，明確定義需求或問題。
  - Green：以最小必要變更讓測試通過。
  - Refactor：在測試保護下整理命名、結構與重複邏輯。
- 不得自行在程式中加入 fallback 策略。若判斷某處需要 fallback 策略，必須先明確與開發人員確認預期行為、觸發條件、錯誤處理與可觀測性後再實作。
- 除非使用者特別指示，否則修改程式時完全不需考慮與之前設計相容之設計。
- 文件以繁體中文為主，程式識別字、package name、module name、class name、function name 使用英文。
- 撰寫或修改任何文檔或程式碼註解時，除非使用者特別指示，否則撰寫內容應描述真實運作流程與當前事實，不放入修正歷史、設計討論背景或只屬於開發測試的指示。
- 不提交 `.env`、credential、token、service account key、OAuth secret、venv、cache、binary、zip、測試輸出或 runtime 產物。
- 變更應小而聚焦，只處理目前需求範圍；不要順手重構無關模組。
- 若既有文件顯示亂碼，先確認原始編碼與使用者意圖，不要未經確認就進行大規模轉碼。
