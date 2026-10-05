# 參與開發

繁體中文 | [English](CONTRIBUTING.en.md)

## 提出問題與修改

透過 GitHub Issue 提出問題或建議；問題請附重現步驟、執行環境、預期與實際結果，並移除憑證及個人或內部敏感資料。涉及需求或對外契約的修改，先在 Issue 中確認方向，再提出 Pull Request。

Pull Request 說明修改目的與驗證結果。工程規範見根目錄及所屬子專案的 `AGENTS.md`；需求、功能與對外契約見 [設計規格](docs/design_spec/01-高階設計規劃.md)與各子專案 README。

## 開發與驗證

依 [根 README](README.md#本機開發測試環境準備)準備環境，再依所屬子專案 README 安裝依賴與執行離線測試。需要真實服務的驗證使用獨立測試環境與資料。

[基本 CI](.github/workflows/ci.yml) 在 push 至 `main`、提出或更新以 `main` 為目標的 PR，以及手動觸發時執行：使用 Python 3.12，在 Linux 執行 importer／secure_backend 離線測試，在 Windows 執行 query_cli 離線測試與 wheel 建置、獨立環境安裝及指令 help 檢查，不使用真實服務憑證。
