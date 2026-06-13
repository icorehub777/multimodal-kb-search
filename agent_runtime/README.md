# Agent Runtime

本文件供 **IT 人員**在 repo 內了解 `agent_runtime/` 子專案結構與部署步驟，**不部署至使用者運作環境**。使用者端 Agent 的工作區根目錄為 `agent_runtime/`，運作規則見同目錄 [`AGENTS.md`](AGENTS.md)（此檔會隨工作區一併部署）。

## 目錄結構

```text
agent_runtime/
  tasks/                          # 使用者任務工作區
  memory.md                       # Agent 跨 session 工作記憶
  AGENTS.md                       # Agent 操作規則（部署至使用者端）
  _internal/
    .venv/                        # Python 虛擬環境（本機建立，不納版控、不複製自其他機器）
    config/
      .env                        # kbsearch 設定
      oauth_client.json           # Google OAuth Desktop 用戶端憑證（不納版控）
      token_cache.json            # 首次授權後由程式寫入（不納版控）
    packages/                     # kbsearch_cli wheel
    logs/                         # kbsearch_cli.log 等
```

---

## 本機測試環境：準備 agent_runtime

在搬移到正式機之前，可在開發機上依下列步驟建立與正式結構相同的 `agent_runtime/`。

### 1. 安裝 LibreOffice 並確認路徑

在目標機器安裝 LibreOffice。`soffice.exe` 預設路徑通常為 `C:\Program Files\LibreOffice\program\soffice.exe`。

```powershell
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"
```

輸出為 `True` 時，記下實際路徑，供步驟 3 寫入 `.env` 的 `LIBREOFFICE_COMMAND`。

### 2. 放入 wheel

取得 `query_cli` 子專案中的 `kbsearch_cli-*.whl`，並放到 `agent_runtime\_internal\packages\` 中。

### 3. 複製與調整設定檔

從 `query_cli\config\` 取得 `.env` 與 `oauth_client.json`，並複製到 `agent_runtime\_internal\config\`。

若未調整建議的 `agent_runtime` 資料夾結構，複製後須調整 `.env` 中的：

- `LIBREOFFICE_COMMAND`：改為步驟 1 確認的 `soffice.exe` 路徑
- `KBSEARCH_CJK_FONT_PATH`：改為該機器上**已存在**的 CJK 字型檔絕對路徑（`.ttf` 或 `.ttc`）。`msjh.ttc` 僅為繁中 Windows 常見範例；若不存在，可改用同目錄其他 CJK 字型（例如 `msyh.ttc`、`mingliu.ttc`），或先安裝字型（例如 Noto Sans CJK）後再填入路徑：

```powershell
Test-Path "C:\Windows\Fonts\msjh.ttc"
Get-ChildItem "C:\Windows\Fonts" -Include *.ttf,*.ttc -Recurse | Select-Object -ExpandProperty FullName
```
- `KBSEARCH_SECURE_BACKEND_BASE_URL`：改為運作端可連線的 backend URL

### 4. 建立 .venv 並安裝 wheel

```powershell
cd agent_runtime\_internal
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --force-reinstall .\packages\kbsearch_cli-*.whl
```

`.venv` 綁定建立當下該機器的 Python 路徑，不可從其他電腦或開發環境整包複製後直接使用。

### 5. 執行查詢

工作目錄為 `agent_runtime\_internal`：

```powershell
cd agent_runtime\_internal
.\.venv\Scripts\kbsearch.exe query `
  --output-dir "../tasks/20260613-130000-agent-runtime-test/query_results/20260613-131500-initial-query" `
  --vector-query "測試向量查詢文字" `
  --drive-query "(fullText contains '關鍵字' or name contains '關鍵字') and trashed = false" `
  --limit 10
```

若有附圖則可加上 `--image` 參數。此參數可重複指定多次；路徑須為相對 `_internal/` 工作目錄的本機圖檔路徑（例如 `../tasks/<任務資料夾>/user-01.png`）。

成功時 **stdout** 輸出 JSON，含 `output_dir`；結果寫入指定的查詢結果資料夾。Log 寫入 `agent_runtime\_internal\logs\kbsearch_cli.log`。

首次執行若尚無 `token_cache.json`，程式會開啟瀏覽器完成 Google OAuth 授權，並寫入 `config\token_cache.json`。

---

## 正式環境準備

請依照以下資料夾結構複製子資料夾與相關檔案到正式機，且子資料夾內僅保留下方有列出的檔案。

```text
agent_runtime/
  AGENTS.md
  memory.md
  tasks/
  _internal/
    config/
      .env
      oauth_client.json
    packages/
      kbsearch_cli-*.whl
    logs/
```

搬移完成後參考以上 `測試環境準備` 中的步驟建置正式環境。
---
