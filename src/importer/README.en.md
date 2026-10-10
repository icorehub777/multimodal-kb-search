# KBSearch Importer

[繁體中文](README.md) | English

Scans configured Google Workspace sources, downloads or exports documents, converts them into pages, generates multimodal embeddings, and writes them to Qdrant.

Synchronization compares Google file IDs and Drive `modifiedTime`: new files are fully imported, deleted files have their vectors removed, changed files are deleted and reimported, and unchanged files are skipped. Drive `version` is retained only in vector metadata for troubleshooting and is not used to detect changes.

Scanning is recursive and includes only supported Google Drive MIME types: PDF, Google Docs, Google Slides, Word, PowerPoint, TXT, Markdown, PNG, JPEG, and WebP. Unsupported MIME types are logged as skipped; they are neither downloaded nor converted and do not count as import failures.

Among supported types, only TXT and Markdown may require encoding detection. The importer supports BOM-marked UTF-8, UTF-16, and UTF-32, followed by UTF-8 and CP950 without a BOM. The selected encoding is recorded in the importer log. If none can strictly decode a document, its import fails; content is not changed using replacement characters.

If a document fails during download, conversion, pagination, embedding, or vector writing, the failure is recorded and other documents continue. After all documents have been processed, the importer process exits with a nonzero exit code. If the complete source list or index state cannot be obtained, or vector deletion fails, synchronization stops immediately.

## Directories and Configuration

### Development Repository Layout

```text
importer/
  main.py                           # Entry point: python main.py
  app/                              # Application modules
  config/
    .env                            # Settings and secrets; not tracked
    .env.example                    # .env template
    gcp-adc.json                     # Service Account JSON; not tracked
    google_drive_sources.example.yaml  # Source configuration template
    google_drive_sources.yaml       # Scan sources; not tracked
  docker/
    Dockerfile                      # Image build definition
    docker-compose.yml              # Local build and execution
  logs/                             # Execution logs; not tracked
  work/                             # Synchronization temporary files; not tracked
  tests/                            # Unit tests
  requirements.txt                  # Python dependencies
```

### Production Deployment Layout

Copy `docker/docker-compose.yml` from the repository to the service root and create `config/`, `logs/`, and `work/`:

```text
importer/
  docker-compose.yml
  config/
    .env
    gcp-adc.json
    google_drive_sources.yaml
  logs/
  work/
```

### `.env`

Copy `config/.env.example` to `config/.env`. File paths are relative to the `importer/` root, except `KBSEARCH_CJK_FONT_PATH`, which must be absolute.

| Variable | Description |
|----------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Service Account JSON path |
| `GOOGLE_DRIVE_SOURCE_CONFIG` | Scan-source YAML path; `sources` may contain multiple entries with unique names and source identifiers; see `google_drive_sources.example.yaml` |
| `GOOGLE_DWD_SUBJECT_EMAIL` | User impersonated through Domain-Wide Delegation |
| `DASHSCOPE_API_KEY` | DashScope API key |
| `DASHSCOPE_EMBEDDING_MODEL` | Embedding model |
| `DASHSCOPE_VECTOR_SIZE` | Positive integer vector dimension; must match `QDRANT_VECTOR_SIZE` |
| `DASHSCOPE_IMAGE_MAX_BYTES` | Image size limit for the Qwen embedding API; range 1–10,485,760 bytes, default 9,728,000. Tests against the real DashScope API confirm that this applies to decoded image bytes, not the base64 string or total request payload |
| `DASHSCOPE_JPEG_QUALITY` | Initial JPEG quality when an image exceeds the limit; range 1–100, default 95, to preserve embedding detail |
| `QDRANT_URL` | Use `http://127.0.0.1:6333` for local tests and `http://qdrant:6333` for Docker deployment |
| `QDRANT_API_KEY` | Optional; on-premises deployment has no API key by default; set it for hosted deployments when needed |
| `QDRANT_COLLECTION` | Collection name |
| `QDRANT_VECTOR_SIZE` | Positive integer vector dimension of the collection |
| `KBSEARCH_CJK_FONT_PATH` | Absolute CJK font path |
| `IMPORTER_PDF_RENDER_TARGET_DPI` | Target rendering resolution for ordinary PDF pages; range 72–600, default 200. Extremely large pages use lower effective DPI to meet the pixel limit |
| `IMPORTER_PDF_RENDER_MAX_PIXELS` | Maximum pixels per rendered PDF page; range 1–89,000,000, default 80,000,000, to avoid Pillow safety limits and excessive memory usage |
| `IMPORTER_KEEP_SUCCESS_WORK_FILES` | Retain temporary `work/` files after successful imports; default `false` |
| `IMPORTER_KEEP_FAILED_WORK_FILES` | Retain temporary `work/` files after failed imports; default `true` |
| `IMPORTER_LOG_RETENTION_DAYS` | Execution log retention in days; older `logs/importer-*.log` files are removed at startup; `0` disables automatic cleanup |
| `IMPORTER_LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`; default `INFO` |

Google access uses Service Account JSON with Domain-Wide Delegation. See the [Google setup guide](../docs/google-setup.en.md) for administrator configuration.

### Qwen Image Preprocessing

PDF pages are normally rendered to PNG at `IMPORTER_PDF_RENDER_TARGET_DPI`. Effective DPI is reduced only when estimated pixels exceed `IMPORTER_PDF_RENDER_MAX_PIXELS`. When sent to `qwen3-vl-embedding`, images below `DASHSCOPE_IMAGE_MAX_BYTES` retain their original files and are uploaded by the DashScope SDK. Larger images first use lower JPEG quality at the same dimensions, then proportional downscaling if still too large. These limits accommodate Qwen's hard 10,240 KB image limit and prevent Pillow decompression-bomb protection from being triggered by enormous images.

Each run writes to `logs/importer-YYYYMMDD-HHMMSS-ffffff-pPID.log` and stdout. Timestamps use UTC; the level is controlled by `IMPORTER_LOG_LEVEL`. Old logs are removed according to `IMPORTER_LOG_RETENTION_DAYS`, which defaults to 14 days. Cleanup failures are logged and stop the import.

## Development and Test Setup

### Create the Base Environment

Local development uses the repository's shared `kbsearch` conda environment. Check whether it exists:

```powershell
conda env list | Select-String kbsearch
```

Create it when necessary:

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

Activate the environment and install dependencies from `importer/`:

```powershell
conda activate kbsearch
cd importer
python -m pip install -r requirements.txt
```

### Install Document Processing Tools

Install LibreOffice and add its `program` directory to the Windows system `PATH`. The importer invokes LibreOffice through `soffice`.

```powershell
Test-Path "C:\Program Files\LibreOffice\program\soffice.exe"
Get-Command soffice
soffice --version
```

Provide a CJK font for TXT/MD-to-PDF conversion and set its absolute path in `KBSEARCH_CJK_FONT_PATH`.

```powershell
Test-Path "C:\Windows\Fonts\msjh.ttc"
```

### Create Local Configuration

Create the local configuration files:

```powershell
cd importer
Copy-Item config\.env.example config\.env
Copy-Item config\google_drive_sources.example.yaml config\google_drive_sources.yaml
```

### Other Prerequisites

- Verify the Google Drive synchronization sources in `google_drive_sources.yaml`.
- Verify that the font configured in `.env` exists. Otherwise use another installed font such as `mingliu.ttc` or `kaiu.ttf`.
- Obtain the Service Account JSON credential file from the GCP administrator, place it in `config/`, and verify that its path matches `.env`.
- Verify that the Google Workspace user in `GOOGLE_DWD_SUBJECT_EMAIL` has access to all synchronization sources.
- Start Qdrant first and set `QDRANT_URL` to `http://127.0.0.1:6333` in `.env`.
- Verify the DashScope settings in `.env`.

Edit `config/.env` and `config/google_drive_sources.yaml`, and provide `config/gcp-adc.json`.

### Run Synchronization

```powershell
cd importer
python main.py
```

### Run Tests

```powershell
python -m unittest discover -s tests
```

## Production Deployment

Docker must be installed on the production host, with its engine running during image creation and scheduled execution.

Build the image, prepare the environment, and complete a manual test before scheduling execution. Each scheduled run starts a container from this image, performs synchronization, and exits as a batch job.

### Build, Export, and Import the Image

```powershell
cd importer/docker
docker compose build
```

The resulting local image is named `kbsearch-importer`.

Export it on the build machine for transfer to production:

```powershell
docker save -o kbsearch-importer.tar kbsearch-importer:latest
```

Copy `kbsearch-importer.tar` to the production machine, then import it:

```powershell
docker load -i kbsearch-importer.tar
```

### Prepare Production

Create the `importer/` service root in production with this structure. Keep only the listed files in its subdirectories:

```text
importer/
  docker-compose.yml
  config/
    .env
    gcp-adc.json
    google_drive_sources.yaml
  logs/
  work/
```

Follow the configuration and prerequisite instructions under "Development and Test Setup". In production:

- Set `QDRANT_URL` to `http://qdrant:6333`.
- The test environment uses Windows fonts, while production uses a Linux image. Set `KBSEARCH_CJK_FONT_PATH` to:

```env
KBSEARCH_CJK_FONT_PATH=/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc
```

### Manual Test

Run synchronization from the service root:

```powershell
cd C:\path\to\importer
docker compose run --rm importer
```

`docker compose run --rm` starts the container, executes `python main.py`, and removes the container when it exits. Logs are written to `logs/importer-YYYYMMDD-HHMMSS-ffffff-pPID.log`.

### Schedule Execution

Use the operating system scheduler to run `docker compose run --rm importer` from the service root. Only one synchronization run may execute at a time.

**Windows Task Scheduler**

1. Open Task Scheduler and choose Create Task or Create Basic Task.
2. **General**: Use a name such as `KBSearch Importer`. For an unattended host, select "Run whether user is logged on or not". The task account must be able to run Docker.
3. **Triggers**: Set the required schedule, such as daily.
4. **Actions** → "Start a program":
   - **Program/script**: `docker`; if unavailable, use its full path, such as `C:\Program Files\Docker\Docker\resources\bin\docker.exe`.
   - **Add arguments**: `compose run --rm importer`.
   - **Start in**: The full service root path, such as `C:\deploy\kbsearch\importer`, containing `docker-compose.yml` and `config/`.
5. **Settings**: If the task is already running, select "Do not start a new instance" to prevent overlap when synchronization takes longer than the trigger interval.
6. Docker must be installed and its engine running when the task is triggered, typically through Docker Desktop or an equivalent service on Windows.
7. The scheduled action is the same as the manual test. Complete that test before enabling the schedule. After saving, run the task from Task Scheduler and inspect the latest `importer-*.log` under `logs/`.
