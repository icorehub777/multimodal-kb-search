# KBSearch Qdrant

地端 Qdrant 向量庫（Docker）。與 `importer/`、`secure_backend/` 同機、同層部署，共用網路 `kbsearch`。

## Repo 目錄

```text
qdrant/
  docker/
    docker-compose.yml
    qdrant_storage/          # 執行資料
```

## 建置與啟動

建立服務根目錄（與 `importer/`、`secure_backend/` 同層），自 repo 複製 `qdrant/docker/docker-compose.yml` 為 `docker-compose.yml`，並建立 `qdrant_storage/`：

```text
qdrant/
  docker-compose.yml
  qdrant_storage/
```

```powershell
cd C:\path\to\qdrant
docker compose up -d
```

本機開發可直接在 repo 的 `qdrant/docker/` 執行 `docker compose up -d`。

常駐容器名稱：`kbsearch-qdrant`。停止：`docker compose down`（`qdrant_storage/` 保留資料）。

`importer`、`secure_backend` 的 `QDRANT_URL`：測試／開發（本機 conda 或 `uvicorn`）用 `http://127.0.0.1:6333`；正式環境（container）用 `http://qdrant:6333`。
