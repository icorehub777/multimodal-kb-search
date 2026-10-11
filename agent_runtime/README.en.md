# Agent Runtime

[繁體中文](README.md) | English

This document is for **IT staff** who need to understand the `agent_runtime/` subproject structure and deployment steps within the repository. The root of the user-side Agent workspace is `agent_runtime/`; its operating rules are defined in [`AGENTS.md`](AGENTS.md), which is deployed with the workspace.

## Build and Runtime Directory Structure

```text
agent_runtime/
  requirements.txt                # Packages required by the Codex PDF skill
  tasks/                          # User task workspaces
  AGENTS.md                       # Agent operating rules deployed to the user environment
  _internal/
    .venv/                        # Locally created Python environment; not tracked or copied between machines
    config/
      .env.example                # kbsearch configuration template
      .env                        # kbsearch settings
      oauth_client.json           # Google OAuth Desktop client credentials; not tracked
    packages/                     # kbsearch_cli wheel
    logs/                         # Per-query kbsearch-<datetime>-<run_id>.log files
```

---

## Local Test Setup: Preparing agent_runtime

Before moving the directory to production, use these steps on the development machine to create an `agent_runtime/` structure equivalent to production.

### 1. Install LibreOffice; optionally install Poppler

Install LibreOffice on the target machine. The default path to `soffice.exe` is usually `C:\Program Files\LibreOffice\program\soffice.exe`.

```powershell
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"
```

After it returns `True`, add LibreOffice's `program` directory to the Windows system `PATH` and restart Codex Desktop. Both `query_cli` and the Documents Skill invoke `soffice` directly and do not accept a separate executable-path setting. Verify the setup with:

```powershell
Get-Command soffice
soffice --version
```

`kbsearch` itself handles PDF and PNG processing for search results. Install Poppler only if the Codex PDF Skill or Documents Skill must independently render PDF pages to PNG in the future.

To install and configure Poppler:

1. Obtain a Windows Poppler build from a trusted distribution source and extract or install it to a stable location such as `C:\Program Files\poppler\`.
2. Find the directory that contains `pdfinfo.exe` and `pdftoppm.exe`, such as `C:\Program Files\poppler\Library\bin\`.
3. Add that directory to the Windows system `PATH`.
4. Restart Codex Desktop so the Agent process receives the updated `PATH`.
5. Verify from a new PowerShell window:

```powershell
Get-Command pdfinfo
Get-Command pdftoppm
pdfinfo -v
pdftoppm -v
```

Optional: install a compatible `unzip` CLI and add its directory to the Windows system `PATH` if the Presentations Skill needs full PPTX package inspection. It is not required for basic PPTX import or slide rendering; it lets the Skill inspect internal PPTX packages, such as extracting embedded media from `ppt/media/`, scanning fonts, and analyzing charts or slide XML parts.

```powershell
Get-Command unzip
unzip -v
```

### 2. Prepare the CLI package

Follow the [query_cli build instructions](../query_cli/README.en.md#production-deployment) to prepare `_internal/packages/kbsearch_cli-*.whl` for delivery verification and production deployment.

### 3. Prepare configuration

Follow ["Create Local Configuration" in `query_cli/README.en.md`](../query_cli/README.en.md#create-local-configuration) to prepare `_internal/config/.env` and `oauth_client.json`. Development and deployment both use configuration from this location.

The same document lists all settings and supported values. When using the directory structure recommended here, verify these deployment-related settings:

- `KBSEARCH_CJK_FONT_PATH`: Set this to the absolute path of a CJK font file (`.ttf` or `.ttc`) present on the machine. `msjh.ttc` is only a common Traditional Chinese Windows example. If unavailable, use another CJK font in the same directory, such as `msyh.ttc` or `mingliu.ttc`, or install a font such as Noto Sans CJK and use its path:

```powershell
Test-Path "C:\Windows\Fonts\msjh.ttc"
Get-ChildItem "C:\Windows\Fonts" -Include *.ttf,*.ttc -Recurse | Select-Object -ExpandProperty FullName
```

- `KBSEARCH_SECURE_BACKEND_BASE_URL`: Set to a backend URL reachable from the runtime machine.
- `KBSEARCH_SECURE_BACKEND_API_KEY`: Set to the same value as `SECURE_BACKEND_API_KEY` in `secure_backend`.
- `KBSEARCH_VIEWER_PORT`: Port used by the search-results viewer; defaults to Streamlit's standard port `8501`.

### 4. Create .venv and install the CLI

Create `.venv` and install the base dependencies:

```powershell
cd agent_runtime\_internal
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r ..\requirements.txt
```

Use an editable install during development so source changes do not require rebuilding the package:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ../../query_cli
```

Install the wheel for delivery verification and production deployment:

```powershell
.\.venv\Scripts\python.exe -m pip install --force-reinstall (Get-ChildItem .\packages\kbsearch_cli-*.whl).FullName
```

Do not copy an entire `.venv` from another computer or development environment for direct use, because it is bound to the Python path on the machine where it was created.

---

## Production Transfer and Setup

The following files are transferred to the production machine. Do not copy `.venv`; recreate it in production. Keep only the files listed below in each subdirectory.

```text
agent_runtime/
  AGENTS.md
  requirements.txt
  tasks/
  _internal/
    config/
      .env
      oauth_client.json
    packages/
      kbsearch_cli-*.whl
    logs/
```

After transfer, follow the preceding "Local Test Setup: Preparing agent_runtime" steps to set up the production environment. Once setup is complete, `requirements.txt` and `_internal/packages/` may be removed.
