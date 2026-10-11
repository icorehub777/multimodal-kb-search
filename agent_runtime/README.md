# Agent Runtime

繁體中文 | [English](README.en.md)

本文件供 **IT 人員**在 repo 內了解 `agent_runtime/` 子專案結構與部署步驟。使用者端 Agent 的工作區根目錄為 `agent_runtime/`，運作規則見同目錄 [`AGENTS.md`](AGENTS.md)（此檔會隨工作區一併部署）。

## 建置與運作目錄結構

```text
agent_runtime/
  requirements.txt                # Agent 使用 codex PDF skill 所需套件
  tasks/                          # 使用者任務工作區
  AGENTS.md                       # Agent 操作規則（部署至使用者端）
  _internal/
    .venv/                        # Python 虛擬環境（本機建立，不納版控、不複製自其他機器）
    config/
      .env.example                # kbsearch 設定範本
      .env                        # kbsearch 設定
      oauth_client.json           # Google OAuth Desktop 用戶端憑證（不納版控）
    packages/                     # kbsearch_cli wheel
    logs/                         # 每次 query 的獨立 kbsearch-<日期時間>-<run_id>.log
```

---

## 本機測試環境：準備 agent_runtime

在搬移到正式機之前，可在開發機上依下列步驟建立與正式結構相同的 `agent_runtime/`。

### 1. 安裝 LibreOffice；選用 Poppler

在目標機器安裝 LibreOffice。`soffice.exe` 預設路徑通常為 `C:\Program Files\LibreOffice\program\soffice.exe`。

```powershell
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"
```

輸出為 `True` 後，將 LibreOffice 的 `program` 目錄加入 Windows 系統 `PATH`，並重新啟動 Codex Desktop。`query_cli` 與 Documents Skill 都直接呼叫 `soffice`，不接受另外設定執行檔路徑。
設定完後，使用以下指令驗證：

```powershell
Get-Command soffice
soffice --version
```

搜尋結果的 PDF 與 PNG 處理由 `kbsearch` 自身完成。若未來仍需讓 Codex 的 PDF Skill 或 Documents Skill 自行將 PDF 頁面渲染為 PNG，才需另外安裝 Poppler。

Poppler 安裝與設定步驟：

1. 從可信任的發行來源取得 Windows Poppler build，解壓縮或安裝至固定位置，例如 `C:\Program Files\poppler\`。
2. 找到實際包含 `pdfinfo.exe` 與 `pdftoppm.exe` 的目錄，例如 `C:\Program Files\poppler\Library\bin\`。
3. 將該目錄加入 Windows 系統 `PATH`。
4. 重新啟動 Codex Desktop，讓 Agent 執行程序取得更新後的 `PATH`。
5. 在新的 PowerShell 視窗驗證：

```powershell
Get-Command pdfinfo
Get-Command pdftoppm
pdfinfo -v
pdftoppm -v
```

Optional：若需要 Presentations Skill 執行完整 PPTX package 輔助檢查，可另外安裝相容的 `unzip` CLI，並將其執行檔所在目錄加入 Windows 系統 `PATH`。這不是基本 PPTX 匯入或投影片渲染必需項目；用途是讓 Skill 檢查 PPTX 內部 package，例如擷取 `ppt/media/` 內嵌媒體、掃描字型與統計圖表或投影片 XML parts。

```powershell
Get-Command unzip
unzip -v
```

### 2. 準備 CLI package

依 [query_cli 的建置方式](../query_cli/README.md#正式環境部署)準備 `_internal/packages/kbsearch_cli-*.whl`，供交付驗證與正式部署使用。

### 3. 準備設定檔

依 [`query_cli/README.md` 的「建立本機設定」](../query_cli/README.md#建立本機設定)準備 `_internal/config/.env` 與 `oauth_client.json`；開發與部署均使用此處的設定。

完整設定項目與可用值見上述文件。使用本文件建議的 `agent_runtime` 資料夾結構時，須確認以下部署相關設定：

- `KBSEARCH_CJK_FONT_PATH`：改為該機器上**已存在**的 CJK 字型檔絕對路徑（`.ttf` 或 `.ttc`）。`msjh.ttc` 僅為繁中 Windows 常見範例；若不存在，可改用同目錄其他 CJK 字型（例如 `msyh.ttc`、`mingliu.ttc`），或先安裝字型（例如 Noto Sans CJK）後再填入路徑：

```powershell
Test-Path "C:\Windows\Fonts\msjh.ttc"
Get-ChildItem "C:\Windows\Fonts" -Include *.ttf,*.ttc -Recurse | Select-Object -ExpandProperty FullName
```
- `KBSEARCH_SECURE_BACKEND_BASE_URL`：改為運作端可連線的 backend URL
- `KBSEARCH_SECURE_BACKEND_API_KEY`：設定為 `secure_backend` 使用的 `SECURE_BACKEND_API_KEY`
- `KBSEARCH_VIEWER_PORT`：搜尋結果檢視頁使用的 port，預設使用 Streamlit 標準 `8501`。

### 4. 建立 .venv 並安裝 CLI

建立 `.venv` 並安裝基礎依賴：

```powershell
cd agent_runtime\_internal
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r ..\requirements.txt
```

開發時使用 editable install，程式修改後不需重新打包：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ../../query_cli
```

交付驗證與正式部署使用 wheel 安裝：

```powershell
.\.venv\Scripts\python.exe -m pip install --force-reinstall (Get-ChildItem .\packages\kbsearch_cli-*.whl).FullName
```

交付驗證完成後，若要繼續開發，重新執行上述 editable install 指令。

請注意：`.venv` 不可從其他電腦或開發環境整包複製後直接使用，因其綁定建立當下該機器的 Python 路徑。

---

## 正式環境搬移與建置

以下為搬移至正式機前的檔案清單；`.venv` 不隨檔案複製，須在正式機重新建立。子資料夾內僅保留下方列出的檔案。

```text
agent_runtime/
  AGENTS.md
  requirements.txt
  tasks/
  _internal/
    config/
      .env
      oauth_client.json
    packages/
      kbsearch_cli-*.whl
    logs/
```

搬移完成後參考以上「本機測試環境：準備 agent_runtime」中的步驟建置正式環境。
建置完成後，可刪除 `requirements.txt` 與 `_internal/packages/` 資料夾。
---
