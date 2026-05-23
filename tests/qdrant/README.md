# Qdrant Cloud 串接測試

驗證 Qdrant Cloud 可正常**連線、匯入（upsert）、向量查詢、依 Google file ID 刪除**，對應 [01-高階設計規劃](../../docs/design_spec/01-高階設計規劃.md) 中的向量庫操作。

## 前置條件

| 項目 | 說明 |
|------|------|
| Qdrant Cloud 叢集 | 已建立並可從本機連線 |
| API Key | [Qdrant Cloud Dashboard](https://cloud.qdrant.io/) → Cluster → **API Keys** |
| Python 3.10+ | 建議使用虛擬環境 |

本專案預設叢集 URL（可於 `.env` 覆寫）：

`https://b021a478-36b4-4dd3-812b-d189971a03b3.australia-southeast1-0.gcp.cloud.qdrant.io`

Cloud 上 collection **`kbsearch_integration_test`** 設定：**2560 維**、**Cosine**；測試程式會自動為 `google_file_id` 建立 keyword 索引（依檔案刪除所需）。

## 安裝

```powershell
cd "C:\Users\MarcoChang\Documents\GitSource\Belltaih\KBSearch\KBSearch\tests\qdrant"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 設定 `.env`

```powershell
Copy-Item .env.example .env
```

編輯 `.env`，至少填入：

- `QDRANT_URL`：Cloud 叢集 URL（`.env.example` 已預填）
- `QDRANT_API_KEY`：Cloud API Key（**勿提交版控**）

選填：

- `QDRANT_COLLECTION`：預設 `kbsearch_integration_test`（與 Cloud 上既有 collection 同名）
- `QDRANT_VECTOR_SIZE`：須與 collection 一致，目前為 **2560**、距離度量 **Cosine**（對應阿里雲多模態 Embedding 維度）

## 執行測試

手動端到端腳本（建議第一次先跑這個）：

```powershell
python test_qdrant.py
```

pytest：

```powershell
pytest test_qdrant_integration.py -v
```

成功時 `test_qdrant.py` 會依序印出：連線 → 匯入 2 筆 → 查詢命中 → 刪除後剩餘 0 筆。

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `qdrant_helpers.py` | 客戶端、匯入、刪除、查詢（可給正式 indexer 重用） |
| `test_qdrant.py` | 可獨立執行的端到端驗證 |
| `test_qdrant_integration.py` | pytest 串接測試 |
| `.env.example` | 環境變數範本 |

## 常見錯誤

- **未設定 QDRANT_API_KEY**：複製 `.env.example` 為 `.env` 並填入 API Key。
- **403 / Unauthorized**：API Key 錯誤或已撤銷；確認 Key 對應正確叢集。
- **Connection refused / timeout**：URL 錯誤、公司防火牆阻擋，或叢集區域與本機網路不通。
- **vector size mismatch**：`.env` 的 `QDRANT_VECTOR_SIZE` 與 Cloud collection 不符（目前應為 `2560`）。

## 本機 Qdrant（選用）

若需在本機跑 Qdrant 而非 Cloud，可改用 `QDRANT_URL=http://localhost:6333` 並省略 API Key，或執行 `docker compose up -d`（見 `docker-compose.yml`）。正式環境以 Cloud 為準。
