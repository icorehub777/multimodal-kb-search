# KBSearch Importer

掃描 Google Workspace 指定來源，下載或 export 文件，轉頁後產生多模態 embedding，寫入 Qdrant。

同步以 Google file ID 與 Drive `version` 比對：新增完整匯入、刪除清向量、異動先刪後匯、未變更略過。

掃描時會針對子資料夾內容遞迴掃描，且只將支援的 Google Drive MIME type 納入同步：PDF、Google Docs、Google Slides、Word、PowerPoint、TXT、Markdown、PNG、JPEG、WebP。不支援的 MIME type 會寫入 skip log，不下載、不轉換，也不計為匯入失敗。

目前支援的 MIME type 中，只有 TXT／Markdown 文字檔會碰到潛在的編碼問題，因此在程式處理上會依序支援帶 BOM 的 UTF-8、UTF-16、UTF-32，以及無 BOM 的 UTF-8、CP950。實際採用的文字編碼會寫入 importer log；無法使用上述編碼嚴格解碼時，該文件匯入失敗，不會以替代字元修改內容。

## 目錄與設定

### 開發用 repo 目錄

```text
importer/
  main.py                           # 入口：python main.py
  app/                              # 應用程式模組
  config/
    .env                            # 設定與 secret（不納版控）
    .env.example                    # .env 範本
    gcp-adc.json                    # Service Account JSON（不納版控）
    google_drive_sources.example.yaml  # 掃描來源範本
    google_drive_sources.yaml       # 掃描來源（不納版控）
  docker/
    Dockerfile                      # image 建置定義
    docker-compose.yml              # 本機 build 與執行 compose
  logs/                             # 執行 log（不納版控）
  work/                             # 同步時暫存檔儲存位置（不納版控）
  tests/                            # 單元測試
  requirements.txt                  # Python 相依套件
```

### 正式部署目錄

importer 從 repo 複製 `docker/docker-compose.yml` 到服務根目錄，並建立 `config/`、`logs/`、`work/`：

```text
importer/
  docker-compose.yml
  config/
    .env
    gcp-adc.json
    google_drive_sources.yaml
  logs/
  work/
```

### `.env`

自 `config/.env.example` 複製為 `config/.env`。一般檔案路徑相對 `importer/` 根目錄；`KBSEARCH_CJK_FONT_PATH` 必須使用絕對路徑。

| 變數 | 說明 |
|------|------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Service Account JSON 路徑 |
| `GOOGLE_DRIVE_SOURCE_CONFIG` | 掃描來源 YAML 路徑；檔內 `sources` 可列多筆（見 `google_drive_sources.example.yaml`） |
| `GOOGLE_DWD_SUBJECT_EMAIL` | Domain-Wide Delegation 模擬使用者 |
| `DASHSCOPE_API_KEY` | DashScope API key |
| `DASHSCOPE_EMBEDDING_MODEL` | Embedding 模型 |
| `DASHSCOPE_VECTOR_SIZE` | 向量維度（須與 `QDRANT_VECTOR_SIZE` 相同） |
| `DASHSCOPE_IMAGE_MAX_BYTES` | 送入 Qwen embedding API 的圖片上限；範圍 1–10,485,760 bytes，預設 9,728,000，低於 API 的 10,240 KB 硬限制以保留傳輸餘裕 |
| `DASHSCOPE_JPEG_QUALITY` | 圖片超過上限時轉 JPEG 的起始品質；範圍 1–100，預設 95，以保留 embedding 所需細節 |
| `QDRANT_URL` | 本機測試時用 `http://127.0.0.1:6333`；docker 部署時用 `http://qdrant:6333` |
| `QDRANT_API_KEY` | 選填；地端預設不啟用 API key，雲端託管時再填 |
| `QDRANT_COLLECTION` | Collection 名稱 |
| `QDRANT_VECTOR_SIZE` | Collection 向量維度 |
| `KBSEARCH_CJK_FONT_PATH` | CJK 字型絕對路徑 |
| `IMPORTER_PDF_RENDER_TARGET_DPI` | PDF 一般頁面的目標渲染解析度；範圍 72–600，預設 200；極大頁面為符合像素上限會降低實際 DPI |
| `IMPORTER_PDF_RENDER_MAX_PIXELS` | PDF 單頁渲染像素上限；範圍 1–89,000,000，預設 80,000,000，避免巨型 PNG 觸發 Pillow 安全限制或大量記憶體用量 |
| `IMPORTER_KEEP_SUCCESS_WORK_FILES` | 檔案匯入成功後是否保留 `work/` 暫存 |
| `IMPORTER_KEEP_FAILED_WORK_FILES` | 檔案匯入失敗後是否保留 `work/` 暫存 |
| `IMPORTER_LOG_RETENTION_DAYS` | 執行 log 保留天數；每次啟動會刪除較舊的 `logs/importer-*.log`；設 `0` 表示不自動清理 |


Google 存取的認證方式為 Service Account JSON + Domain-Wide Delegation（`signJwt`）。

### Qwen 圖片前處理

PDF 頁面通常依 `IMPORTER_PDF_RENDER_TARGET_DPI` 轉成 PNG；只有預估像素超過 `IMPORTER_PDF_RENDER_MAX_PIXELS` 時，才會降低該頁實際 DPI。送入 `qwen3-vl-embedding` 時，小於 `DASHSCOPE_IMAGE_MAX_BYTES` 的圖片保持原檔並由 DashScope SDK 上傳；超過時先維持尺寸降低 JPEG 品質，仍超限才等比例縮小。這些限制是配合 Qwen API 的 10,240 KB 圖片硬限制，並避免 Pillow 在巨型圖片上觸發 decompression-bomb 保護。

執行 log：每次執行寫入 `logs/importer-YYYYMMDD-HHMMSS-ffffff-pPID.log`，並同時輸出 stdout；依 `IMPORTER_LOG_RETENTION_DAYS` 清理舊 log（預設 14 天）。清理失敗時會記錄錯誤並中止匯入。

## 開發測試環境準備

### 建立基本環境

本機開發使用 repo 共用的 conda 環境名稱 `kbsearch`。先檢查環境是否存在：

```powershell
conda env list | Select-String kbsearch
```

若沒有 `kbsearch`，先建立環境：

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

進入環境並安裝依賴（在 `importer/` 目錄下執行）：

```powershell
conda activate kbsearch
cd importer
python -m pip install -r requirements.txt
```

### 安裝文件處理工具

安裝 LibreOffice，並將其 `program` 目錄加入 Windows 系統 `PATH`。importer 固定以 `soffice` 指令執行 LibreOffice。

```powershell
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"
Get-Command soffice
soffice --version
```

另需準備一個 CJK 字型檔供 TXT／MD 轉 PDF，並將其絕對路徑設定於 `KBSEARCH_CJK_FONT_PATH`。

```powershell
Test-Path "C:\Windows\Fonts\msjh.ttc"
```

### 建立本機設定

建立本機設定檔：

```powershell
cd importer
Copy-Item config\.env.example config\.env
Copy-Item config\google_drive_sources.example.yaml config\google_drive_sources.yaml
```

### 其他前置環境準備

- 確認 `google_drive_sources.yaml` 中設定的 Google Drive 同步來源正確。
- 確認 `.env` 中的字型存在，若不存在請設定其他本機存在的字型檔，如 `mingliu.ttc`（細明體) 或 `kaiu.ttf`（標楷體）。
- 確認已跟 GCP 管理員拿到 Service Account JSON 認證檔，放到 `config/` 後，確定與 `.env` 中設定一致。
- 確定 `GOOGLE_DWD_SUBJECT_EMAIL` 中設定的 GMAIL 帳號有所有要同步的 Google Drive 來源的存取權限。
- 須先啟動 Qdrant，並確認 `.env` 中的 `QDRANT_URL` 設定為 `http://127.0.0.1:6333`。
- 確認 `.env` 中的 `dashscope` 設定正確。

編輯 `config/.env`、`config/google_drive_sources.yaml`，並放入 `config/gcp-adc.json`。

### 執行同步
```powershell
cd importer
python main.py
```

### 執行測試
```powershell
python -m unittest discover -s tests
```

## 正式環境部署

需確認正式環境主機須已安裝 Docker 且 Docker 引擎在建立 image 與排程觸發時為運行中。

以下步驟會先建置 image、完成環境準備並在手動測試 OK 後，再設定作業系統排程每次都從此 image 啟動一個 container，執行同步後結束（**跑完即停**的 batch job）。

### 建置/匯出/匯入 image：

```powershell
cd importer/docker
docker compose build
```

建置完成後本機 image 名稱為 `kbsearch-importer`。

匯出 image（於建置機執行，產生 tar 檔供搬移至正式環境）：

```powershell
docker save -o kbsearch-importer.tar kbsearch-importer:latest
```

將 `kbsearch-importer.tar` 複製到正式機後匯入：

```powershell
docker load -i kbsearch-importer.tar
```

### 準備正式環境
在正式環境依照以下資料夾結構建立 `importer/` 服務根目錄；子資料夾內僅保留下方列出的檔案：

```text
importer/
  docker-compose.yml
  config/
    .env
    gcp-adc.json
    google_drive_sources.yaml
  logs/
  work/
```

參考 `開發測試環境準備` 中的設定檔複製/調整與其他建置環境準備的內容準備正式環境。
其中 `QDRANT_URL` 的設定要改成 `http://qdrant:6333`


### 手動測試
在服務根目錄手動執行同步：

```powershell
cd C:\path\to\importer
docker compose run --rm importer
```

`docker compose run --rm` 會啟動 container、執行 `python main.py`、結束後移除 container。執行紀錄寫入 `logs/importer-YYYYMMDD-HHMMSS-ffffff-pPID.log`。

### 設定排程執行

透過作業系統的排程服務，在服務根目錄執行 `docker compose run --rm importer`；且同一時間只可以跑一個同步。

**Windows 工作排程器**

1. 開啟「工作排程器」→「建立工作」（或「建立基本工作」）。
2. **一般**：名稱例如 `KBSearch Importer`；勾選「不論使用者登入與否均執行」（無人值守主機）；執行中帳戶須能執行 Docker。
3. **觸發程序**：依需求設定（例如每日一次）；避免與上次執行重疊（單次同步可能超過一個觸發間隔）。
4. **動作** →「啟動程式」：
   - **程式或腳本**：`docker`（若找不到指令，改填完整路徑，例如 `C:\Program Files\Docker\Docker\resources\bin\docker.exe`）
   - **新增引數**：`compose run --rm importer`
   - **開始於**：服務根目錄的完整路徑（例如 `C:\deploy\kbsearch\importer`）；須含 `docker-compose.yml` 與 `config/`
5. 主機須已安裝 Docker 且 Docker 引擎在排程觸發時為運行中（Windows 上通常為 Docker Desktop 或同等服務）。
6. 排程的「動作」與上方「手動測試」相同；啟用排程前請先完成手動測試。儲存後可在工作排程器對該工作按「執行」，並檢查 `logs/` 下最新的 `importer-*.log`。
