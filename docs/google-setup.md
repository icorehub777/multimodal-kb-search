# Google 管理端設定

繁體中文 | [English](google-setup.en.md)

由部署單位的 Google / GCP 管理者完成以下設定；兩種認證都使用唯讀 scope `https://www.googleapis.com/auth/drive.readonly`。

## 共通準備

建立或選用 GCP project，啟用 Google Drive API。

## Importer：Service Account

建立 Service Account 並產生 JSON key，由 Google Workspace 超級管理員在 Domain-Wide Delegation 中授權其 client ID 與上述 scope。指定同一 Workspace 網域內、可存取同步來源的使用者為 `GOOGLE_DWD_SUBJECT_EMAIL`；憑證檔的部署位置見 importer README。

操作方向見 [Google Service Account 與 Domain-Wide Delegation 文件](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority)；來源與其他設定見 [importer README](../src/importer/README.md)。

## Query CLI：Desktop OAuth

設定 OAuth consent screen 的使用對象與所需 scope；測試模式下須加入測試使用者。建立 Desktop app 類型的 OAuth client，下載 JSON 並隨 CLI 部署提供，將其路徑填入 `GOOGLE_OAUTH_CLIENT_CONFIG`。每位使用者透過 `kbsearch login` 完成自己的授權。

操作方向見 [Google Desktop OAuth 文件](https://developers.google.com/identity/protocols/oauth2/native-app#prerequisites)；CLI 設定與登入方式見 [query_cli README](../src/query_cli/README.md)。
