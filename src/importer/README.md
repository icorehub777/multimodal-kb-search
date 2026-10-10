# KBSearch Importer

繁體中文 | [English](README.en.md)

掃描 Google Workspace 指定來源，下載或 export 文件，轉頁後產生多模態 embedding，寫入 Qdrant。

同步以 Google file ID 與 Drive `modifiedTime` 比對：新增完整匯入、刪除清向量、異動先刪後匯、未變更略過。Drive `version` 僅保留於向量 metadata 供排錯，不參與異動判斷。

掃描時會針對子資料夾內容遞迴掃描，且只將支援的 Google Drive MIME type 納入同步：PDF、Google Docs、Google Slides、Word、PowerPoint、TXT、Markdown、PNG、JPEG、WebP。不支援的 MIME type 會寫入 skip log，不下載、不轉換，也不計為匯入失敗。

目前支援的 MIME type 中，只有 TXT／Markdown 文字檔會碰到潛在的編碼問題，因此在程式處理上會依序支援帶 BOM 的 UTF-8、UTF-16、UTF-32，以及無 BOM 的 UTF-8、CP950。實際採用的文字編碼會寫入 importer log；無法使用上述編碼嚴格解碼時，該文件匯入失敗，不會以替代字元修改內容。

單一文件在下載、轉換、分頁、embedding 或寫入向量時失敗，會記錄失敗並繼續處理其他文件；全部文件處理完成後，本次 importer 程序以非 0 exit code 結束。但若是完整來源清單或索引狀態無法取得，以及刪除向量失敗時，則立即中止同步。

## 目錄與設定

程式與單元測試位於 `src/importer/`，image 建置檔位於根目錄 `docker/`。本機執行使用 `deploy/importer/`，目錄配置見 [部署說明](../../deploy/README.md#目錄與準備)。

### `.env`

自 `config/.env.example` 複製為 `config/.env`，填寫以下設定。

| 變數 | 說明 |
|------|------|
| `GOOGLE_DWD_SUBJECT_EMAIL` | Domain-Wide Delegation 模擬使用者 |
| `DASHSCOPE_API_KEY` | DashScope API key |
| `DASHSCOPE_EMBEDDING_MODEL` | Embedding 模型 |
| `KBSEARCH_VECTOR_SIZE` | Embedding 與 Qdrant 共用的正整數向量維度；須與 backend 相同 |
| `DASHSCOPE_IMAGE_MAX_BYTES` | 送入 Qwen embedding API 的圖片上限；範圍 1–10,485,760 bytes，預設 9,728,000。真實 DashScope API 實測此限制以 base64 解碼後的圖片 bytes 計，不以 base64 字串或整個 request payload 計 |
| `DASHSCOPE_JPEG_QUALITY` | 圖片超過上限時轉 JPEG 的起始品質；範圍 1–100，預設 95，以保留 embedding 所需細節 |
| `QDRANT_URL` | Container 內使用 `http://qdrant:6333` |
| `QDRANT_API_KEY` | 選填；地端預設不啟用 API key，雲端託管時再填 |
| `QDRANT_COLLECTION` | Collection 名稱 |
| `IMPORTER_PDF_RENDER_TARGET_DPI` | PDF 一般頁面的目標渲染解析度；範圍 72–600，預設 200；極大頁面為符合像素上限會降低實際 DPI |
| `IMPORTER_PDF_RENDER_MAX_PIXELS` | PDF 單頁渲染像素上限；範圍 1–89,000,000，預設 80,000,000，避免巨型 PNG 觸發 Pillow 安全限制或大量記憶體用量 |
| `IMPORTER_KEEP_SUCCESS_WORK_FILES` | 檔案匯入成功後是否保留 `work/` 暫存，預設 `false` |
| `IMPORTER_KEEP_FAILED_WORK_FILES` | 檔案匯入失敗後是否保留 `work/` 暫存，預設 `true` |
| `IMPORTER_LOG_RETENTION_DAYS` | 執行 log 保留天數；每次啟動會刪除較舊的 `logs/importer-*.log`；設 `0` 表示不自動清理 |
| `IMPORTER_LOG_LEVEL` | Log level，可設為 `DEBUG`、`INFO`、`WARNING` 或 `ERROR`，預設 `INFO` |


Google 存取使用 `config/gcp-adc.json` 的 Service Account JSON + Domain-Wide Delegation，管理端設定見 [Google 設定指引](../../docs/google-setup.md)。

`config/google_drive_sources.yaml` 的 `sources` 可列多筆來源，名稱與來源識別不得重複（見範例）；`GOOGLE_DWD_SUBJECT_EMAIL` 須有來源存取權限。

### Qwen 圖片前處理

PDF 頁面通常依 `IMPORTER_PDF_RENDER_TARGET_DPI` 轉成 PNG；只有預估像素超過 `IMPORTER_PDF_RENDER_MAX_PIXELS` 時，才會降低該頁實際 DPI。送入 `qwen3-vl-embedding` 時，小於 `DASHSCOPE_IMAGE_MAX_BYTES` 的圖片保持原檔並由 DashScope SDK 上傳；超過時先維持尺寸降低 JPEG 品質，仍超限才等比例縮小。這些限制是配合 Qwen API 的 10,240 KB 圖片硬限制，並避免 Pillow 在巨型圖片上觸發 decompression-bomb 保護。

執行 log：每次執行寫入 `logs/importer-YYYYMMDD-HHMMSS-ffffff-pPID.log`，並同時輸出 stdout；時間使用 UTC，level 由 `IMPORTER_LOG_LEVEL` 控制。Importer 依 `IMPORTER_LOG_RETENTION_DAYS` 清理舊 log（預設 14 天），清理失敗時會記錄錯誤並中止匯入。

## 開發與測試

離線單元測試使用[根 README](../../README.md#本機開發測試環境準備)的 conda 環境。在 repo 根目錄執行：

```powershell
conda activate kbsearch
python -m pip install -e ./src/importer
cd src/importer
python -m unittest discover -s tests
```

### 建置 image

需安裝 Docker 並啟動引擎。第一次執行，或 pyproject.toml／Dockerfile 變更時，在 repo 根目錄建置：

```powershell
./docker/docker_build_importer.ps1
```

Image 名稱為 `kbsearch-importer`，以 Python 3.12／Debian 12（Bookworm）建置，內含無介面版 LibreOffice；TXT／Markdown 轉 PDF 使用內建的文泉驛正黑字型。Debian 套件預設從官方來源下載；若下載較慢，可指定鏡像，例如 `./docker/docker_build_importer.ps1 -DebianMirror http://ftp.tw.debian.org/debian`。

### 準備設定與執行

在 repo 根目錄建立開發設定：

```powershell
Copy-Item deploy/importer/config/.env.example deploy/importer/config/.env
Copy-Item deploy/importer/config/google_drive_sources.example.yaml deploy/importer/config/google_drive_sources.yaml
```

依上節填寫測試環境設定並準備憑證。先依 [部署說明](../../deploy/README.md#啟動與停止)啟動 Qdrant，再執行：

```powershell
./deploy/importer/docker_run.ps1 -Dev
```

`-Dev` 會載入 `deploy/importer/docker-compose.dev.yml`，唯讀掛載 `src/importer/kbsearch_importer/`，執行 container 內的 `python -m kbsearch_importer`。程式修改後重新執行即可；

設定、log 與暫存分別位於 `deploy/importer/config/`、`logs/`、`work/`。

## 正式環境部署

Image 匯出與匯入、部署準備、執行及排程見 [部署說明](../../deploy/README.md)。
