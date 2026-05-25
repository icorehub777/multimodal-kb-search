# KBSearch Secure Backend

`secure_backend/` 是 KBSearch 的 FastAPI 受保護後端服務。它負責阿里雲 embedding model 存取與 Qdrant vector store 操作，供查詢端透過 HTTP API 呼叫。

## 資料夾結構

```text
secure_backend/
  AGENTS.md                         # Agent 開發規範
  README.md                         # 本文件
  pyproject.toml                    # Python package 設定
  src/
    kbsearch_secure_backend/        # secure backend package
  tests/
    test_*.py                       # 離線單元測試
```

## 環境需求

- Python 3.10 以上。
- 阿里雲 embedding model API key 與模型設定。
- Qdrant URL、API key、collection 與必要權限。
- FastAPI / ASGI server 相關依賴。

## 安裝

在 repo root 執行：

```powershell
python -m pip install -e secure_backend
```

正式服務依賴維護在 `pyproject.toml`，包含 FastAPI、ASGI server、阿里雲 SDK 與 Qdrant client。

## 設定

此子專案由部署環境提供設定，至少包含：

- `DASHSCOPE_API_KEY`：阿里雲 API key。
- `DASHSCOPE_EMBEDDING_MODEL`：阿里雲多模態 embedding model 名稱。
- `DASHSCOPE_VECTOR_SIZE`：阿里雲 embedding 向量維度。
- `QDRANT_URL`：Qdrant URL。
- `QDRANT_API_KEY`：Qdrant API key。
- `QDRANT_COLLECTION`：Qdrant collection。
- `QDRANT_VECTOR_SIZE`：Qdrant collection 向量維度，必須與 `DASHSCOPE_VECTOR_SIZE` 相同。
- `KBSEARCH_SECURE_BACKEND_LOG_FILE`：必填，application log file 路徑；相對路徑以 `secure_backend/` app 根目錄為基準，每日切分新 log 檔。

若使用設定檔，預設讀取位置為 `secure_backend/config/.env`。
可從 `secure_backend/config/.env.example` 複製後填入部署設定；範例中的 `logs/secure_backend.log` 會解析到 `secure_backend/logs/secure_backend.log`。實際 `.env` 與 API key 不得提交 Git。

設定檢查：

```powershell
kbsearch-secure-backend probe-config
```

## 執行

FastAPI app 應提供穩定 ASGI 入口。開發環境可用 ASGI server 啟動服務，例如：

```powershell
uvicorn kbsearch_secure_backend.app:create_app --factory --host 127.0.0.1 --port 8000
```

## API Contract

健康檢查：

```http
GET /healthz
```

向量搜尋：

```http
POST /search/vector
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

`images` 需包含圖片內容本身；backend 不讀取呼叫端主機上的本機路徑。

Response：

```json
{
  "results": [
    {
      "google_file_id": "file-id",
      "source_name": "Spec.pdf",
      "source_location": "Drive/Spec.pdf",
      "source_url": "https://drive.google.com/...",
      "google_drive_version": "7",
      "google_drive_modified_time": "2026-05-24T00:00:00Z",
      "score": 0.91,
      "pages": [
        {
          "google_file_id": "file-id",
          "source_name": "Spec.pdf",
          "source_location": "Drive/Spec.pdf",
          "source_url": "https://drive.google.com/...",
          "google_drive_version": "7",
          "google_drive_modified_time": "2026-05-24T00:00:00Z",
          "page_number": 1,
          "page_image_path": "pages/01.png",
          "source_file_path": "source/Spec.pdf",
          "score": 0.91
        }
      ]
    }
  ]
}
```

搜尋結果會依 Google file ID 彙總；檔案依最高相似度排序，同一檔案內頁面依相似度排序。
Qdrant adapter 使用 `qdrant-client` 的 `query_points` API 執行查詢。

錯誤回應：

```json
{
  "detail": {
    "error": "ConfigError",
    "message": "Missing required config: DASHSCOPE_API_KEY"
  }
}
```

錯誤訊息不得包含 API key、credential 或外部服務原始敏感 payload。

## 測試與驗收

離線單元測試：

```powershell
python -m unittest discover -s secure_backend\tests
```

需要真實阿里雲或 Qdrant 的探查測試應與離線單元測試分開。若探查測試會寫入 Qdrant，需使用受控 probe 資料並在測試結束後清理。
