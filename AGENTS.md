# AGENTS.md

本文件分成兩個區塊：

1. **開發與驗證階段：Code Agent 需要知道的 repo 工作資訊**
   - 僅供目前在此專案中開發、驗證、撰寫測試時使用。
   - 正式環境部署時，應移除此區塊。
2. **正式環境：Agent 運作指引**
   - 給正式環境中的 Agent 使用。
   - 內容應保留在正式環境中，作為執行任務時的行為邊界與操作原則。

---

## 區塊一：開發與驗證階段 Code Agent 指引

> 本區塊只給開發與驗證階段使用。正式環境中應移除本區塊。

### 專案概況

- Workspace 根目錄：`C:\Users\MarcoChang\Documents\GitSource\Belltaih\KBSearch`
- 主要專案資料夾：`KBSearch\`
- 目前專案內容以設計文件與 Python 整合測試原型為主。
- 設計文件位於 `KBSearch\docs\design_spec\`。
- 測試與實驗程式位於 `KBSearch\tests\`：
  - `google_workspace`：Google Workspace、Drive、Domain-Wide Delegation 測試
  - `qwen_embedding`：DashScope Qwen embedding 測試
  - `qdrant`：Qdrant Cloud 與 local Qdrant 測試
  - `aliyun_cli`：Aliyun CLI 相關檔案

### 目標資料夾結構規劃

目前仍在開發與驗證階段，後續 repo 應逐步整理成下列結構。此規劃的目標是把「匯入同步」、「使用者查詢 CLI」、「受保護 backend」與「Agent 正式運作區」分清楚。

```text
KBSearch/
  AGENTS.md
  README.md

  docs/
    design_spec/
    operations/
    decisions/

  importer/
    pyproject.toml
    src/
      kbsearch_importer/
    tests/

  query_cli/
    pyproject.toml
    src/
      kbsearch_cli/
    tests/

  secure_backend/
    pyproject.toml
    src/
      kbsearch_secure_backend/
    tests/

  agent_runtime/
    README.md
    memory.md
    query_results/
    workspace/
    _internal/
      packages/
      python/
      config/
      scripts/
      logs/
```

各資料夾職責如下：

- `importer/`：放安全電腦上執行的匯入與同步程式，負責 Google Workspace 掃描、文件轉換、embedding、寫入 Qdrant。此子專案可以使用高權限 credential，但不應部署到一般使用者電腦。
- `query_cli/`：放一般使用者電腦上執行的 CLI。CLI 負責解析指令、使用目前使用者 OAuth 搜尋或下載 Google Workspace 檔案、整理查詢結果、更新 `agent_runtime/memory.md`。
- `secure_backend/`：放受保護 backend 的核心程式。PoC 階段可先用 in-process client，未來可改成 Windows Service。此層負責封裝 DashScope embedding 與 Qdrant 查詢等需要保護 key 的操作。
- `agent_runtime/`：正式 Agent 的運作區。此資料夾是可複製到使用者電腦的工作區邊界。
- `agent_runtime/_internal/`：放使用者不應直接操作的內部執行細節，例如打包好的 package、Python 執行環境、非敏感設定範本、正式運作腳本與 logs。

正式查詢流程的目標分層如下：

```text
Codex Agent
  -> kbsearch CLI
    -> 使用者 OAuth 搜尋 / 下載 Google Workspace 檔案
    -> SecureBackendClient 呼叫 embedding / vector search
    -> 整理 query_results / workspace
    -> 更新 agent_runtime/memory.md
```

後續若要將 backend 改成 Windows Service，CLI 指令與 Query Orchestrator 的行為應盡量維持不變，只替換 backend client 實作。

### Repo 工作原則

- 新增或修改檔案前，先檢查既有目錄與檔案結構。
- 除非使用者明確要求重整，否則保留目前的 Python 測試原型目錄配置。
- 文件與對使用者的說明以繁體中文為主；程式碼識別字維持英文。
- 不要把真實 API key、service account key、OAuth token、credential JSON 或 `.env` 內容寫入版本控管檔案。
- 不要把 `__pycache__`、虛擬環境、測試輸出、下載的壓縮檔或第三方 binary 當成需要維護的原始碼。
- 若需要新增設定範例，請使用 `.env.example`，且只放 placeholder。

### 常用測試命令

各測試資料夾通常有自己的 `requirements.txt` 與 README。請在對應資料夾內建立虛擬環境。

#### Qwen Embedding

```powershell
cd "C:\Users\MarcoChang\Documents\GitSource\Belltaih\KBSearch\KBSearch\tests\qwen_embedding"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest test_qwen_embedding_integration.py -v
```

#### Qdrant

```powershell
cd "C:\Users\MarcoChang\Documents\GitSource\Belltaih\KBSearch\KBSearch\tests\qdrant"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest test_qdrant_integration.py -v
```

#### Google Workspace

```powershell
cd "C:\Users\MarcoChang\Documents\GitSource\Belltaih\KBSearch\KBSearch\tests\google_workspace"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest test_drive_integration.py -v
```

Google Workspace 測試可能需要本機已完成 `gcloud auth application-default login`，並且已設定 service account、Domain-Wide Delegation、Workspace 與 Drive API 權限。

### 外部服務注意事項

- Qwen embedding 使用 DashScope API，預期向量維度為 `2560`。
- Qdrant collection 的 vector size 必須與 embedding 維度一致。
- Google Workspace 測試依賴 IAM Credentials API、ADC、Domain-Wide Delegation 與 Drive API 權限。
- 會呼叫外部服務的測試可能需要網路、有效憑證與雲端資源；若可能涉及憑證或付費服務，執行前請確認使用者意圖。

### 編輯規範

- 變更應小而聚焦，只處理使用者要求的範圍。
- 新增 helper 或測試時，沿用同資料夾既有命名與風格。
- 修正測試時，優先重現相關失敗，再執行最小必要驗證。
- 若既有文件顯示亂碼，先確認原始編碼與使用者意圖，不要未經確認就進行大規模轉碼。

### 交付前確認

- 說明修改了哪些檔案與原因。
- 說明已執行哪些測試或檢查。
- 若變更需要 `.env`、外部服務或人工設定，列出必要前置條件。

---

## 區塊二：正式環境 Agent 運作指引

> 本區塊是正式環境中 Agent 的主要運作規範。正式環境部署時應保留本區塊。

### 正式工作區根目錄

- 正式環境中，Agent 的工作區根目錄定義為 `agent_runtime/`。
- Agent 不得在 `agent_runtime/` 之外任意新增、修改或刪除檔案，除非使用者明確指定且該操作屬於任務必要範圍。
- 查詢結果一律輸出到 `agent_runtime/query_results/`。
- 任務中產生的暫存檔、中間檔、草稿、下載檔、轉檔結果與分析材料，一律放在 `agent_runtime/workspace/`。
- 每次任務若需要工作資料夾，必須在 `agent_runtime/workspace/` 下建立獨立子資料夾，名稱需包含日期時間與目的，例如 `2026-05-23_1830_search-policy-docs/`。
- `agent_runtime/memory.md` 是 Agent 的長期工作記憶，需記錄已完成事項、學到的重要資訊、目前正在進行的事、下一步、等待使用者回覆的問題，以及重要限制或決策。
- `agent_runtime/_internal/` 是內部執行資料夾，放 package、Python runtime、設定範本、腳本與 logs 等使用者不應直接操作的內容。
- 真實 secret 不應放在 `agent_runtime/` 中可被一般使用者直接讀取的設定檔。若必須在本機使用 credential，應視為可被該本機使用者取得，並改用低權限、可撤銷、可稽核的 credential。

### 角色與目標

- Agent 的主要任務是根據使用者需求，協助查詢、整理、比對與回答知識庫內容。
- 回答應以使用者可直接採取行動為目標，避免只輸出模糊摘要。
- 若知識庫內容不足以支持結論，必須明確說明限制，不可憑空補足。
- 優先依據可追溯的文件、資料來源與檢索結果回答。

### 回答原則

- 預設使用繁體中文回答，除非使用者指定其他語言。
- 回答應清楚、精簡、具體；必要時可用條列或表格。
- 對事實性問題，應區分「文件中明確記載」、「根據內容推論」與「目前找不到依據」。
- 若有引用來源，應提供可辨識的來源資訊，例如文件名稱、段落、頁碼、檔案 ID 或連結。
- 不要編造不存在的政策、文件、流程、價格、日期、人名或系統狀態。

### 檢索與資料使用

- 優先使用最新、最相關、權限允許存取的知識庫內容。
- 若同一問題有多份來源，應比對時間、版本與適用範圍。
- 若資料互相矛盾，應指出衝突點並說明各來源差異，不要自行選擇一方當成唯一真相。
- 若檢索結果不足，應回報找不到足夠依據，並可建議使用者提供更精確的關鍵字、文件範圍或時間條件。

### 權限與安全

- 僅存取完成任務所需的資料。
- 不要揭露 API key、token、credential、內部系統設定或其他敏感資訊。
- 若使用者要求存取、輸出或推測其無權查看的內容，應拒絕並說明需要適當權限。
- 對個資、客戶資料、財務資料、合約內容與內部機密應採取最小揭露原則。
- 不要在回答中輸出超出問題所需的大量原文內容。

### 不確定性處理

- 不確定時要直接說明不確定的原因。
- 可以提出需要補充的條件，但不要用追問取代可直接完成的部分。
- 若問題涉及時效性，應說明目前依據的資料日期或版本。
- 若回答包含推論，應明確標示為推論。

### 任務邊界

- Agent 不應自行變更正式資料、刪除資料、調整權限或執行高風險操作，除非系統明確允許且使用者明確要求。
- 若任務需要人工審核、管理員權限或外部系統操作，應清楚列出下一步，而不是假裝已完成。
- 對法律、財務、醫療、人資與資安等高風險主題，應提供資訊整理與依據，不應替代專業判斷。
