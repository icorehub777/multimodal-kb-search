# KBSearch Secure Backend

繁體中文 | [English](README.en.md)

`src/secure_backend/` 是 KBSearch 的內部 FastAPI 服務。它封裝 DashScope embedding model 與 Qdrant vector store 操作，並以 API key 保護服務 API。

## 目錄與設定

程式位於 `src/secure_backend/`，測試位於 `tests/secure_backend/`，image 建置檔位於根目錄 `docker/`。本機執行使用 `deploy/secure_backend/`，目錄配置見 [部署說明](../../deploy/README.md#目錄與準備)。

`config/.env` 的設定如下：

| 設定 | 用途 |
|------|------|
| `SECURE_BACKEND_API_KEY` | 呼叫 API 時使用的共用 API key |
| `DASHSCOPE_API_KEY` | DashScope API key |
| `DASHSCOPE_EMBEDDING_MODEL` | embedding model 名稱 |
| `KBSEARCH_VECTOR_SIZE` | Embedding 與 Qdrant 共用的正整數向量維度；須與 importer 相同 |
| `DASHSCOPE_IMAGE_MAX_BYTES` | 傳送至 DashScope 的單張圖片大小上限 |
| `DASHSCOPE_JPEG_QUALITY` | 圖片壓縮時的起始 JPEG 品質 |
| `QDRANT_URL` | Container 內使用 `http://qdrant:6333` |
| `QDRANT_API_KEY` | Qdrant API key；未啟用時可留空 |
| `QDRANT_COLLECTION` | 查詢使用的 collection |
| `SECURE_BACKEND_MAX_QUERY_LENGTH` | 查詢文字字數上限，預設 `4000` |
| `SECURE_BACKEND_MAX_IMAGES` | 每次查詢的圖片數量上限，預設 `5` |
| `SECURE_BACKEND_MAX_SEARCH_LIMIT` | 每次查詢的結果筆數上限，預設 `100` |
| `SECURE_BACKEND_LOG_LEVEL` | Log level，可設為 `DEBUG`、`INFO`、`WARNING` 或 `ERROR`，預設 `INFO` |

應用程式 log 寫入服務目錄的 `logs/secure_backend.log` 並同時輸出 stdout；時間與每日輪替均使用 UTC，保留 14 份輪替檔案。

## 開發與測試

離線單元測試使用[根 README](../../README.md#本機開發測試環境準備)的 conda 環境。在 repo 根目錄執行：

```powershell
conda activate kbsearch
python -m pip install -e "./src/secure_backend[dev]"
python -m unittest discover -s tests/secure_backend -t .
```

### 建置 image

需安裝 Docker 並啟動引擎。第一次執行，或 pyproject.toml／Dockerfile 變更時，在 repo 根目錄建置：

```powershell
./docker/docker_build_secure_backend.ps1
```

Image 名稱為 `kbsearch-secure-backend`。

### 準備設定與啟動

在 repo 根目錄建立設定：

```powershell
Copy-Item deploy/secure_backend/config/.env.example deploy/secure_backend/config/.env
```

填寫 API key、DashScope 與測試 collection 設定，先依 [部署說明](../../deploy/README.md#啟動與停止)啟動 Qdrant，再執行：

```powershell
./deploy/secure_backend/docker_run.ps1 -Dev
```

啟動後的 API 位址為 `http://localhost:8000`。

`-Dev` 會載入 `deploy/secure_backend/docker-compose.dev.yml`，唯讀掛載 `src/secure_backend/kbsearch_backend/` 並啟用 reload，即可在開發期直接使用 Docker 執行，且程式修改後自動重啟，不需每次重新建置 image。

服務啟動時會檢查設定、DashScope 與 Qdrant collection；失敗時退出並記錄錯誤。

## 正式環境部署

Image 匯出與匯入、部署準備及服務啟停見 [部署說明](../../deploy/README.md)。

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
