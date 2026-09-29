# KBSearch Secure Backend

`secure_backend/` 是 KBSearch 的內部 FastAPI 服務。它封裝 DashScope embedding model 與 Qdrant vector store 操作，並以 API key 保護服務 API。

## 目錄結構

```text
secure_backend/
  main.py              # uvicorn 入口：main:app
  app/                 # 應用程式模組
    factory.py         # create_app()
    config.py
    ...
  config/
    .env
  docker/              # 正式環境 image 與 compose
  tests/
  requirements.txt
```

## 開發測試環境準備

本機開發使用 repo 共用的 conda 環境名稱 `kbsearch`。先檢查環境是否存在：

```powershell
conda env list | Select-String kbsearch
```

若沒有 `kbsearch`，先建立環境：

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

進入環境並安裝外部依賴：

```powershell
conda activate kbsearch
python -m pip install -r requirements.txt
```

複製 `.env.example` 到 `.env`（在 `secure_backend/` 目錄下執行）：

```powershell
cd secure_backend
Copy-Item config\.env.example config\.env
```

`config/.env` 的設定如下：

| 設定 | 用途 |
|------|------|
| `SECURE_BACKEND_API_KEY` | 呼叫 API 時使用的共用 API key |
| `DASHSCOPE_API_KEY` | DashScope API key |
| `DASHSCOPE_EMBEDDING_MODEL` | embedding model 名稱 |
| `DASHSCOPE_VECTOR_SIZE` | 正整數向量維度，須與 `QDRANT_VECTOR_SIZE` 相同 |
| `DASHSCOPE_IMAGE_MAX_BYTES` | 傳送至 DashScope 的單張圖片大小上限 |
| `DASHSCOPE_JPEG_QUALITY` | 圖片壓縮時的起始 JPEG 品質 |
| `QDRANT_URL` | Qdrant URL；本機預設為 `http://127.0.0.1:6333` |
| `QDRANT_API_KEY` | Qdrant API key；未啟用時可留空 |
| `QDRANT_COLLECTION` | 查詢使用的 collection |
| `QDRANT_VECTOR_SIZE` | Collection 正整數向量維度 |
| `SECURE_BACKEND_MAX_QUERY_LENGTH` | 查詢文字字數上限，預設 `4000` |
| `SECURE_BACKEND_MAX_IMAGES` | 每次查詢的圖片數量上限，預設 `5` |
| `SECURE_BACKEND_MAX_SEARCH_LIMIT` | 每次查詢的結果筆數上限，預設 `100` |
| `SECURE_BACKEND_LOG_LEVEL` | Log level，可設為 `DEBUG`、`INFO`、`WARNING` 或 `ERROR`，預設 `INFO` |

應用程式 log 寫入 `logs/secure_backend.log` 並同時輸出 stdout；時間與每日輪替均使用 UTC，保留 14 份輪替檔案。Docker 部署時可由 `docker/logs/` 取得 log。

啟動本機 API（在 `secure_backend/` 目錄下執行）。服務啟動時會自動檢查設定、DashScope embedding 與 Qdrant collection；檢查失敗時程序會退出，並在 log 中留下錯誤摘要：

```powershell
cd secure_backend
uvicorn main:app --host 127.0.0.1 --port 8000
```

離線單元測試：

```powershell
cd secure_backend
python -m unittest discover -s tests
```

## 正式環境部署

`secure_backend/docker/` 提供 image 建置與服務啟動所需檔案：

建置 image：

```powershell
cd secure_backend/docker
docker compose build
```

建置完成後本機 image 名稱為 `kbsearch-secure-backend`。

匯出 image（於建置機執行，產生 tar 檔供搬移至正式環境）：

```powershell
docker save -o kbsearch-secure-backend.tar kbsearch-secure-backend:latest
```

將 `kbsearch-secure-backend.tar` 複製到正式機後匯入：

```powershell
docker load -i kbsearch-secure-backend.tar
```

在正式環境依照以下資料夾結構建立 secure_backend 資料夾：

```text
secure_backend/
  docker-compose.yml
  config/
    .env
  logs/
```

| 路徑 | 用途 |
|------|------|
| `docker-compose.yml` | 從專案資料夾中的 `docker/` 中複製。以建置、啟動與管理服務 |
| `config/.env` | 從專案資料夾中的 `config/` 中複製，包含各種 secret 設定 |
| `logs/` | 服務 log 輸出目錄 |

依照正式環境的狀況調整 `.env` 中的設定後（`QDRANT_URL` 要改成 `http://qdrant:6333`），於此服務根目錄執行以下指令啟動 container：

```powershell
docker compose up -d
```

常駐容器名稱為 `kbsearch-secure-backend`（`docker ps` 可見）。

查看 log 或停止服務：

```powershell
docker compose logs -f
docker compose down
```

## API Contract

所有 endpoint 都必須使用下列 header：

```http
X-API-Key: <SECURE_BACKEND_API_KEY>
```

健康檢查：

```http
GET /healthz
```

向量搜尋：

```http
POST /search/vector
Content-Type: application/json
```

Request：

```json
{
  "query": "查詢文字",
  "images": [
    {
      "filename": "query.png",
      "mime_type": "image/png",
      "base64_data": "iVBORw0KGgo..."
    }
  ],
  "limit": 10,
  "min_score": 0.5
}
```

`query` 與 `images` 至少須提供一項；查詢文字長度、圖片數量及結果筆數不得超過服務端設定的上限。`limit` 必須為正整數，`min_score` 若有提供，必須是 `-1` 至 `1` 之間的有限數值。

Response 會依 Google file ID 彙總搜尋結果，檔案依最高相似度排序，同一檔案內頁面依相似度排序。

錯誤回應使用固定結構：

```json
{
  "error": "invalid_request",
  "field": "limit",
  "message": "limit must be between 1 and 100."
}
```

`field` 只在錯誤可定位至特定 request 欄位時提供；`message` 會包含呼叫端修正輸入所需的限制資訊。

| HTTP status | `error` | 情況 |
|-------------|---------|------|
| `401` | `authentication` | API key 缺少或不正確 |
| `400` | `invalid_request` | Request 不符合查詢條件 |
| `413` | `payload_too_large` | 圖片超過處理限制 |
| `502` | `external_service` | DashScope 或 Qdrant 呼叫失敗 |
| `500` | `internal` | 其他服務錯誤 |

`5xx` response 不包含 DashScope、Qdrant 或內部連線的原始錯誤內容；完整資訊記錄於 server log。
