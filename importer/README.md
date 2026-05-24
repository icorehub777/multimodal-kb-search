# KBSearch Importer

`importer/` 是 KBSearch 的文件匯入與同步子專案，預期部署在安全電腦、受控 Windows/Linux 主機或 container 中。它負責把 Google Workspace 指定來源中的文件同步到 Qdrant 多模態向量庫。

## 主要流程

```text
Google Workspace
  -> 掃描文件 metadata
  -> 與 Qdrant 既有資料比對
  -> 下載或 export 文件
  -> 轉成 PDF 或整理為頁面圖片
  -> 逐頁輸出 PNG
  -> 呼叫 DashScope / Qwen 多模態 embedding
  -> 寫入 Qdrant
```

同步判斷使用 Google file ID 與 Google Drive version，會產生四種行為：

- 新增：完整匯入。
- 刪除：清除 Qdrant 中該文件的所有向量。
- 異動：先刪除舊向量，再完整匯入。
- 未變更：略過。

## 資料夾結構

```text
importer/
  AGENTS.md                         # Agent 開發規範
  README.md                         # 本文件
  pyproject.toml                    # Python package 設定
  config/
    .env.example                    # 設定範例，可提交
    .env                            # 真實設定，不提交
    google_drive_sources.example.yaml
    google_drive_sources.yaml       # 真實掃描來源，不提交
  src/
    kbsearch_importer/              # importer package
  tests/
    test_*.py                       # 離線單元測試
    probe_integrations.py           # 真實外部服務探查
  work/                             # 下載、轉檔、切頁暫存，不提交
```

`work/` 的保留策略由 `IMPORTER_KEEP_SUCCESS_WORK_FILES` 與 `IMPORTER_KEEP_FAILED_WORK_FILES` 控制：

```text
work/<google_file_id>/
  source/   # Google Drive 下載檔或 export PDF
  pdf/      # Office / TXT / MD 轉出的 PDF
  pages/    # 每頁 PNG，例如 01.png、02.png
```

檔名與資料夾名稱以 Google file ID 與清理後的檔名產生，避免不同文件同名時互相覆蓋。

## 支援文件類型

- PDF：直接渲染成每頁 PNG。
- Google Docs / Google Slides：透過 Google Drive export 成 PDF。
- Word / PowerPoint：透過 LibreOffice headless 轉成 PDF。
- TXT / MD：以固定版面產生 PDF。
- PNG / JPG / JPEG / WEBP：視為單頁文件，頁碼固定為 1，統一整理為頁面圖片後進入 embedding 流程。
- Excel / Google Sheets：不直接向量化，也不自動 export 匯入；使用者需先手動轉成 A4 PDF，確認格式正確後再納入流程。

Drive scanner 會排除 Excel 與 Google Sheets，不會把它們當成文件匯入。掃描來源若是 Google Drive folder，會遞迴掃描子資料夾，並在 `source_location` 中保留來源內的資料夾路徑。

## 環境需求

- Python 3.10 以上。
- Google Application Default Credentials。
- Google Workspace Domain-Wide Delegation 設定。
- DashScope API key。
- Qdrant collection 與寫入權限。
- LibreOffice，用於 Word / PowerPoint 轉 PDF。
- Pillow，用於 PNG / JPG / JPEG / WEBP 正規化為頁面 PNG。

Windows 上 LibreOffice 常見路徑：

```text
C:\Program Files\LibreOffice\program\soffice.exe
```

## 安裝

在 repo root 執行：

```powershell
python -m pip install -e importer
```

## 設定

此子專案使用自己的設定檔，不依賴 repo root：

```powershell
Copy-Item importer\config\.env.example importer\config\.env
Copy-Item importer\config\google_drive_sources.example.yaml importer\config\google_drive_sources.yaml
```

`config/.env` 放外部服務連線設定與 secret，不提交 Git。主要欄位包含：

- `GOOGLE_DRIVE_SOURCE_CONFIG`
- `GOOGLE_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_DWD_SUBJECT_EMAIL`
- `DASHSCOPE_API_KEY`
- `DASHSCOPE_EMBEDDING_MODEL`
- `DASHSCOPE_VECTOR_SIZE`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `QDRANT_COLLECTION`
- `QDRANT_VECTOR_SIZE`
- `LIBREOFFICE_COMMAND`：必填，需填完整絕對路徑，例如 `C:\Program Files\LibreOffice\program\soffice.exe`。
- `KBSEARCH_CJK_FONT_PATH`：必填，TXT / MD 轉 PDF 使用的單一 CJK 字型完整絕對路徑，例如 `C:\Windows\Fonts\msjh.ttc`。
- `IMPORTER_KEEP_SUCCESS_WORK_FILES`
- `IMPORTER_KEEP_FAILED_WORK_FILES`

`IMPORTER_KEEP_SUCCESS_WORK_FILES` 與 `IMPORTER_KEEP_FAILED_WORK_FILES` 控制 `work/` 中暫存檔的保留策略：

- `true`：保留該情境下的工作檔案。
- `false`：在該情境結束後刪除該文件的工作資料夾。

`config/google_drive_sources.yaml` 定義掃描來源，例如 shared drive 或指定 folder。此檔案屬於部署環境設定，不提交 Git。

### TXT / MD 中文轉 PDF 字型

TXT / MD 轉 PDF 時若內容包含中文，轉換器需要可讀取的 CJK 字型，否則會停止轉換以避免產生亂碼頁面。

Windows 通常可直接使用系統字型。Container / Linux 建議安裝 Noto CJK，例如 Debian / Ubuntu image：

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
```

請在 `config/.env` 指定唯一使用的 CJK 字型檔完整路徑。

Windows 範例：

```text
KBSEARCH_CJK_FONT_PATH=C:\Windows\Fonts\msjh.ttc
```

Linux / container 範例：

```text
KBSEARCH_CJK_FONT_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
```

## Google Workspace 認證

Importer 是後端 indexing 程式，程式碼層面固定使用 `google.auth.default()` 取得 Application Default Credentials。開發期與正式環境的差異只在於執行環境如何提供 ADC，程式碼不需要因此改動。

本機開發期使用 service account impersonation 取得暫時 ADC：

```powershell
gcloud.cmd auth application-default login --impersonate-service-account="..."
```

Windows PowerShell 若 `gcloud` 被 execution policy 擋住，可使用：

```powershell
gcloud.cmd auth application-default login --impersonate-service-account="..."
```

正式上線時，地端伺服器或 container 應由執行環境提供 ADC，並採用 Workload Identity Federation。

## 執行

檢查設定：

```powershell
python -m kbsearch_importer probe-config
```

檢查設定並實際探查 Google Drive、DashScope 與 Qdrant 連線：

```powershell
python -m kbsearch_importer probe-services
```

執行完整同步：

```powershell
python -m kbsearch_importer sync
```

## 測試與驗收

離線單元測試：

```powershell
python -m unittest discover -s importer\tests
```

外部服務探查：

```powershell
python importer\tests\probe_integrations.py all
```

LibreOffice 轉檔探查：

```powershell
python importer\tests\probe_integrations.py libreoffice
```

受控同步決策驗收：

```powershell
python importer\tests\probe_integrations.py sync-decisions
```

`sync-decisions` 會在 configured Qdrant collection 中製造受控狀態，以驗證新增、刪除、異動、未變更四種同步行為；此探查會寫入並清理 probe 資料。
