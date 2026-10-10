# Google Administrator Setup

[繁體中文](google-setup.md) | English

The deployment organization's Google / GCP administrator completes the following setup. Both authentication methods use the read-only scope `https://www.googleapis.com/auth/drive.readonly`.

## Shared Prerequisite

Create or select a GCP project and enable the Google Drive API.

## Importer: Service Account

Create a Service Account and generate a JSON key. A Google Workspace super administrator authorizes its client ID and the scope above through Domain-Wide Delegation. Set `GOOGLE_DWD_SUBJECT_EMAIL` to a user in the same Workspace domain with access to the synchronization sources. See the importer README for credential placement.

See Google's [Service Account and Domain-Wide Delegation guide](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority). Source configuration and other settings are described in the [importer README](../src/importer/README.en.md).

## Query CLI: Desktop OAuth

Configure the OAuth consent screen's audience and required scope; add test users when using testing mode. Create an OAuth client of type Desktop app, download its JSON file, and supply it with the CLI deployment. Set `GOOGLE_OAUTH_CLIENT_CONFIG` to its path. Each user completes their own authorization through `kbsearch login`.

See Google's [Desktop OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app#prerequisites). CLI configuration and login are described in the [query_cli README](../src/query_cli/README.en.md).
