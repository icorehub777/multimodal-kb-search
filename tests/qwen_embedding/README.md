# qwen3-vl-embedding 串接測試

驗證阿里雲 DashScope **多模態 Embedding**（`qwen3-vl-embedding`）可正常產生**文字、圖片與融合查詢向量**，對應 [01-高階設計規劃](../../docs/design_spec/01-高階設計規劃.md) 中的向量化與相似度搜尋。

## 前置條件

| 項目 | 說明 |
|------|------|
| 百煉 API Key | [阿里雲百煉控制台](https://bailian.console.aliyun.com/) → API Key（**中國北京區**） |
| 模型 | `qwen3-vl-embedding`（預設 2560 維，與 Qdrant collection 一致） |
| Python 3.10+ | 建議使用虛擬環境 |

> **區域限制**：`qwen3-vl-embedding` 僅在中國（北京）區提供，端點為 `https://dashscope.aliyuncs.com/api/v1`。請使用北京區建立的 API Key。

## 安裝

```powershell
cd "C:\Users\MarcoChang\Documents\GitSource\Belltaih\KBSearch\KBSearch\tests\qwen_embedding"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 設定 `.env`

```powershell
Copy-Item .env.example .env
```

編輯 `.env`，至少填入：

- `DASHSCOPE_API_KEY`：百煉 API Key（**勿提交版控**）

選填：

- `DASHSCOPE_EMBEDDING_MODEL`：預設 `qwen3-vl-embedding`
- `DASHSCOPE_BASE_URL`：預設北京區端點
- `EMBEDDING_DIMENSION`：預設 `2560`（須與 Qdrant `QDRANT_VECTOR_SIZE` 一致）

## 執行測試

手動端到端腳本（建議第一次先跑這個）：

```powershell
python test_qwen_embedding.py
```

pytest：

```powershell
pytest test_qwen_embedding_integration.py -v
```

成功時會印出：文字向量維度 → 圖片向量維度 → 融合向量（單一 2560 維）。

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `embedding_helpers.py` | API 設定、`embed_text` / `embed_image_url` / `embed_contents` |
| `test_qwen_embedding.py` | 可獨立執行的端到端驗證 |
| `test_qwen_embedding_integration.py` | pytest 串接測試 |
| `.env.example` | 環境變數範本 |

## 與 Qdrant 測試的關係

1. 先在本資料夾確認 Embedding 維度為 **2560**。
2. 再在 `tests/qdrant` 以相同維度寫入 Qdrant（`QDRANT_VECTOR_SIZE=2560`）。

正式 indexer 可重用 `embedding_helpers.py` 的 `embed_image_url`（分頁 PNG）與 `embed_contents(..., enable_fusion=True)`（文字＋圖片查詢）。

## 常見錯誤

- **未設定 DASHSCOPE_API_KEY**：複製 `.env.example` 為 `.env` 並填入 Key。
- **InvalidApiKey / 401**：Key 錯誤，或使用了非北京區的 Key。
- **模型不存在 / 403**：確認模型名稱為 `qwen3-vl-embedding`，且帳號已開通該模型。
- **維度不符**：`.env` 的 `EMBEDDING_DIMENSION` 須與 Qdrant collection 一致（目前為 `2560`）。
