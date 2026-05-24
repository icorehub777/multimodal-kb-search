# AGENTS.md

本文件提供 KBSearch repo 的跨專案工程規範。各子專案的專屬規則寫在該子專案自己的 `AGENTS.md`；根目錄不放子專案實作細節。

## 子專案邊界

- 修改程式前先確認變更屬於哪個子專案，不要把子專案責任混在一起。
- 子專案之間應透過明確介面、CLI、client 或資料契約銜接，不直接跨層依賴內部實作。
- 核心邏輯不應依賴 CLI `print`、`argparse`、terminal output 或 Agent 文字格式。
- Request / response contract 應保持穩定，並優先使用 typed dataclass、Pydantic model 或等價的明確結構。

## 開發規範

- 採測試驅動開發。新增或修改行為時，優先先寫可重現需求或問題的測試。
- 遵循紅綠燈規則：
  - Red：先寫出失敗測試，明確定義需求或問題。
  - Green：以最小必要變更讓測試通過。
  - Refactor：在測試保護下整理命名、結構與重複邏輯。
- 不得自行在程式中加入 fallback 策略。若判斷某處需要 fallback 策略，必須先明確與開發人員確認預期行為、觸發條件、錯誤處理與可觀測性後再實作。
- 除非使用者特別指示，否則修改程式時完全不需考慮與之前設計相容之設計。
- 變更應小而聚焦，只處理目前需求範圍；不要順手重構無關模組。

## 文件規範

- 文件以繁體中文為主，程式識別字、package name、module name、class name、function name 使用英文。
- 撰寫或修改任何文檔或程式碼註解時，除非使用者特別指示，否則撰寫內容應描述真實運作流程與當前事實，不放入修正歷史、設計討論背景或只屬於開發測試的指示。
- 子專案細節應寫在該子專案的 README / AGENTS / TASKS 或設計文件，不要塞進根目錄規範。
- 若既有文件顯示亂碼，先確認原始編碼與使用者意圖，不要未經確認就進行大規模轉碼。

## Secret 與產物

- 不提交 `.env`、credential、token、service account key、OAuth secret、venv、cache、binary、zip、測試輸出或 runtime 產物。
- 不在 log、錯誤訊息、測試輸出或文件範例中揭露 secret。
- 根目錄 `tests/` 是本機驗證與 spike 測試資料夾，不納入 Git 版控。

## 測試規範

- 單元測試不得依賴真實 Google OAuth token、阿里雲、Qdrant credential 或實際 backend service。
- 需要真實外部服務的探查測試必須明確命名，與離線單元測試分開，且不得輸出 secret 或個人敏感資料。