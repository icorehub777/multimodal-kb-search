# KBSearch Secure Backend

`secure_backend/` 是 KBSearch 的 FastAPI 後端服務。它封裝 DashScope embedding model 與 Qdrant vector store 操作，提供查詢端 HTTP API。

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

`config/.env` 放本機開發設定與 secret，主要欄位為 DashScope 與 Qdrant。應用程式 log 固定寫入 `logs/secure_backend.log`（Docker 部署時由 `docker/logs/` 掛載取得）。

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

依照正式環境的狀況調整 `.env` 中的設定後，於此服務根目錄執行以下指令啟動 container：

```powershell
docker compose up -d
```

查看 log 或停止服務：

```powershell
docker compose logs -f
docker compose down
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

Response 會依 Google file ID 彙總搜尋結果，檔案依最高相似度排序，同一檔案內頁面依相似度排序。
