# KBSearch

繁體中文 | [English](README.en.md)

KBSearch 專案主要目的：
1. 讓 Google Workspace 文件與圖文混合向量庫同步。
2. 讓 Codex Agent 可以透過工具執行 GCP 關鍵字搜尋與向量相似度搜尋，以回答使用者問題。

## 資料夾結構

```text
KBSearch/
  docs/
  qdrant/
  importer/
  query_cli/
  secure_backend/
  agent_runtime/
```

- `docs/`：設計文件。
- `qdrant/`：地端 Qdrant 向量庫。
- `importer/`：Goolge Workspace 文件與向量庫同步子專案。
- `query_cli/`：協助 Agent 進行 google workspace 關鍵字搜尋與向量庫查詢的指令工具子專案，並透過 `secure_backend` 存取 embedding model 與操作 vector store。
- `secure_backend/`：FastAPI 子專案，封裝阿里雲 embedding model 存取與 Qdrant vector store 操作(因為此兩服務的 api key 不得讓一般使用者看到，所以必須切割出這個 api 服務專案)。
- `agent_runtime/`：正式環境中 Agent 的運作區，會把 query_cli 的指令工具打包放到此環境給 Agent 使用。

## 文件入口

- Repo 共通開發規範：`AGENTS.md`
- 系統需求與設計：先閱讀 [`docs/design_spec/00-專案目標.md`](docs/design_spec/00-專案目標.md) 與 [`docs/design_spec/01-高階設計規劃.md`](docs/design_spec/01-高階設計規劃.md)
- Google 管理端設定：[`docs/google-setup.md`](docs/google-setup.md)
- 參與開發：[`CONTRIBUTING.md`](CONTRIBUTING.md)
- 子專案使用方式：各子專案的 `README.md`
- 子專案開發規範：各子專案的 `AGENTS.md`
- Agent 運作區規則：`agent_runtime/AGENTS.md`

## 專案開發原則

本專案採文件驅動的 Agent 開發模式。`docs/` 定義系統層級的高階需求與設計，各子專案的 `README.md` 定義其功能、設定、操作方式與對外契約，`AGENTS.md` 則定義開發時需遵守的工程規範。

程式碼由開發 Agent 依據上述文件採測試驅動開發（TDD）完成：先以測試具體化需求，再進行實作與重構，並以測試驗證程式符合既定需求與工程規範。

## 執行環境分工

- `importer/`：正式環境以 container 執行，由外部排程啟動同步工作。
- `secure_backend/`：正式環境以 container 執行，提供常態性的 FastAPI 服務。
- `query_cli/`：打包成 Python package，安裝到 `agent_runtime` 使用的 Python 環境中，提供 `kbsearch` 指令。
- `agent_runtime/`：正式環境中 Agent 進行 KB search 的工作目錄；正式運行時只需要這個目錄、已安裝的 `kbsearch` 指令。

## 本機開發測試環境準備

除 `agent_runtime/` 子專案使用 `agent_runtime/_internal/.venv` 環境外，其他 Python 子專案一律使用 repo 共用 conda 環境 `kbsearch`。

先檢查環境是否存在：

```powershell
conda env list | Select-String kbsearch
```

若沒有 `kbsearch`，先建立環境：

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

進入環境並安裝跨子專案的共用開發測試依賴 (在 repo 根目錄執行)：

```powershell
conda activate kbsearch
python -m pip install -r requirements-dev.txt
```

各子專案的開發測試環境準備與正式環境部署規劃寫在各自的 `README.md`。

## 補充說明

- 根目錄 README 只提供專案總覽；子專案細節請看各子專案文件。
- 根目錄 `tests/` 是本機驗證用資料夾，不納入 Git 版控。

## 授權

Copyright (C) 2026 iCoreHub contributors

本專案依 [GNU Affero General Public License v3.0](LICENSE) 授權，主要考量是所使用的 [PyMuPDF](https://github.com/pymupdf/PyMuPDF) 由 Artifex Software, Inc. 提供 GNU AGPL v3 或商業授權兩種選擇，本專案選擇依 GNU AGPL v3 條款使用。其他第三方元件適用其各自的授權條款。
