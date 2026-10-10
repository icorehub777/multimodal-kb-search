# KBSearch 部署

繁體中文 | [English](README.en.md)

`deploy/` 提供 Qdrant、importer 與 secure_backend 的本機執行與部署目錄。三個服務部署於同一台 Docker 主機，共用 `kbsearch` 網路；本機與正式環境沿用相同目錄結構，設定與資料各自獨立。

## 目錄與準備

```text
deploy/
  qdrant/
    docker-compose.yml
    docker_run.ps1
    qdrant_storage/
  importer/
    docker-compose.yml
    docker-compose.dev.yml
    docker_run.ps1
    config/
    logs/
    work/
  secure_backend/
    docker-compose.yml
    docker-compose.dev.yml
    docker_run.ps1
    config/
    logs/
```

部署主機須安裝 Docker 並啟動引擎。依上述結構複製服務的 Compose、啟動入口及設定範本；不要將開發環境的實際設定、憑證或執行資料當作部署範本。

Importer 的 `config/` 須準備 `.env`、`google_drive_sources.yaml` 與管理者提供的 `gcp-adc.json`；backend 須準備 `config/.env`。設定說明與 image 建置方式見 [importer README](../src/importer/README.md) 與 [secure_backend README](../src/secure_backend/README.md)。

## Image 匯出與匯入

在建置機完成 image 建置後匯出：

```powershell
docker save -o kbsearch-importer.tar kbsearch-importer:latest
docker save -o kbsearch-secure-backend.tar kbsearch-secure-backend:latest
```

將 tar 搬到部署主機後匯入；Qdrant image 由 Compose 從 registry 取得：

```powershell
docker load -i kbsearch-importer.tar
docker load -i kbsearch-secure-backend.tar
```

## 啟動與停止

在 `deploy/` 目錄執行，先啟動 Qdrant 建立共用網路，再啟動 backend：

```powershell
./qdrant/docker_run.ps1
./secure_backend/docker_run.ps1
```

Importer 按需或由外部排程執行，每次完成一輪同步後移除 container：

```powershell
./importer/docker_run.ps1
```

本機開發時，importer 與 backend 可加 `-Dev` 掛載原始碼；正式部署及交付驗證使用 image 內的程式，不加此參數。

Qdrant 與 backend 的常駐容器名稱分別為 `kbsearch-qdrant`、`kbsearch-secure-backend`。在各服務目錄可用 `docker compose logs -f` 查看輸出，或以 `docker compose down` 停止；停止 Qdrant 前，先確認 importer 已結束並停止 backend。

## Importer 排程

使用 Windows 工作排程器呼叫同一啟動入口：

- 程式：`powershell.exe`。
- 引數：`-NoProfile -File "C:\deploy\kbsearch\importer\docker_run.ps1"`，替換為實際部署路徑。
- 依需求設定觸發時間；工作執行中選擇「不要啟動新執行個體」。
- 執行帳戶須能操作 Docker，Docker 引擎須保持運行；啟用排程前先完成手動驗證。

## 連線與執行資料

Container 內使用 `http://qdrant:6333` 存取向量庫；主機端 `http://127.0.0.1:6333` 僅供本機檢查。Backend 對主機提供 port `8000`。Qdrant container 的檔案開啟 soft／hard 上限均為 65,536。

Qdrant 資料保存在 `qdrant/qdrant_storage/`，停止 container 不會刪除資料。Importer 與 backend 的 log 保存在各自的 `logs/`，importer 工作檔保存在 `importer/work/`；實際設定、憑證與執行產物不納版控。
