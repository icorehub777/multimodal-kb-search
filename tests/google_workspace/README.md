# Google Workspace Domain-Wide Delegation 串接測試

驗證「無 JSON 金鑰」架構：以本機 **Application Default Credentials** 透過 **IAM Credentials API** 動態簽署 JWT，再以服務帳戶 **Domain-Wide Delegation** 模擬指定員工身分存取 Google Drive。

## 前置狀態

| 步驟 | 說明 | 狀態 |
|------|------|------|
| 1 | GCP 啟用 **IAM Service Account Credentials API** | 已完成 |
| 2 | 本機 `gcloud auth application-default login` | 請在本機執行 |
| 3 | 安裝 Python 相依套件 | 見下方 |
| 4 | 設定 `.env` 並執行測試 | 見下方 |

## 第二步：本機登入（ADC）

在 PowerShell 執行（請使用已在 IAM 具 **Service Account Token Creator** 的 Google 帳號）：

```powershell
gcloud auth application-default login
```

瀏覽器完成登入後，本機會有代表您個人的短期憑證，供程式呼叫 `signJwt` 使用。

## 第三步：安裝套件

建議使用虛擬環境：

```powershell
cd "C:\Users\MarcoChang\Documents\GitSource\Belltaih\KBSearch\KBSearch\tests\google_workspace"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 第四步：設定並執行

1. 複製環境變數範本：

   ```powershell
   Copy-Item .env.example .env
   ```

2. 編輯 `.env`，至少設定：

   - `GOOGLE_SERVICE_ACCOUNT_EMAIL`：服務帳戶（預設已填 `kbsearch-indexer@kbsearch-agent.iam.gserviceaccount.com`）
   - `GOOGLE_DWD_SUBJECT_EMAIL`：**要被模擬的 Workspace 使用者**（公司內真實帳號，建議第一次先用您自己的 Email）

3. 執行手動串接腳本：

   ```powershell
   python test_dwd.py
   ```

   成功時會印出該帳號雲端硬碟前 5 筆檔案名稱與 ID。

4. 或以 pytest 執行（同樣需 `.env`）：

   ```powershell
   pytest test_drive_integration.py -v
   ```

5. 驗證查詢路徑四種 Drive API 行為（關鍵字預設：`推車輪組`）：

   ```powershell
   python test_drive_four_behaviors.py
   ```

   產物寫入 `.output/`（下載的 PDF 等）。

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `dwd_auth.py` | 無金鑰 DWD Token 取得邏輯（可給正式 indexer 重用） |
| `test_dwd.py` | 可獨立執行的端到端驗證腳本 |
| `test_drive_integration.py` | pytest 串接測試 |
| `.env.example` | 環境變數範本 |

## 常見錯誤

- **403 / Permission denied on signJwt**：您的 Google 帳號未具該服務帳戶的「憑證建立者」角色，或 ADC 未登入。
- **403 / unauthorized_client（換 token 時）**：Workspace 管理員尚未在管理控制台為服務帳戶設定 Domain-Wide Delegation，或 scope 不符。
- **404 / 使用者不存在**：`GOOGLE_DWD_SUBJECT_EMAIL` 不是公司 Workspace 內帳號。

## 與產品設計的關係

此測試對應 [01-高階設計規劃](../../docs/design_spec/01-高階設計規劃.md) 中背景 indexer 以服務帳戶掃描指定範圍文件的需求；查詢路徑仍會使用**使用者 OAuth**，與本測試路徑不同。
