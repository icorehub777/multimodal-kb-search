# KBSearch Importer

[繁體中文](README.md) | English

Scans configured Google Workspace sources, downloads or exports documents, converts them into pages, generates multimodal embeddings, and writes them to Qdrant.

Synchronization compares Google file IDs and Drive `modifiedTime`: new files are fully imported, deleted files have their vectors removed, changed files are deleted and reimported, and unchanged files are skipped. Drive `version` is retained only in vector metadata for troubleshooting and is not used to detect changes.

Scanning is recursive and includes only supported Google Drive MIME types: PDF, Google Docs, Google Slides, Word, PowerPoint, TXT, Markdown, PNG, JPEG, and WebP. Unsupported MIME types are logged as skipped; they are neither downloaded nor converted and do not count as import failures.

Among supported types, only TXT and Markdown may require encoding detection. The importer supports BOM-marked UTF-8, UTF-16, and UTF-32, followed by UTF-8 and CP950 without a BOM. The selected encoding is recorded in the importer log. If none can strictly decode a document, its import fails; content is not changed using replacement characters.

If a document fails during download, conversion, pagination, embedding, or vector writing, the failure is recorded and other documents continue. After all documents have been processed, the importer process exits with a nonzero exit code. If the complete source list or index state cannot be obtained, or vector deletion fails, synchronization stops immediately.

## Directories and Configuration

Source is in `src/importer/`, tests are in `tests/importer/`, and image build files are in the root `docker/` directory. Local execution uses `deploy/importer/`; see the [deployment guide](../../deploy/README.en.md#directories-and-preparation) for its directory layout.

### `.env`

Copy `config/.env.example` to `config/.env` and fill in the following settings.

| Variable | Description |
|----------|-------------|
| `GOOGLE_DWD_SUBJECT_EMAIL` | User impersonated through Domain-Wide Delegation |
| `DASHSCOPE_API_KEY` | DashScope API key |
| `DASHSCOPE_EMBEDDING_MODEL` | Embedding model |
| `KBSEARCH_VECTOR_SIZE` | Positive integer dimension shared by embedding and Qdrant; must match the backend |
| `DASHSCOPE_IMAGE_MAX_BYTES` | Image size limit for the Qwen embedding API; range 1–10,485,760 bytes, default 9,728,000. Tests against the real DashScope API confirm that this applies to decoded image bytes, not the base64 string or total request payload |
| `DASHSCOPE_JPEG_QUALITY` | Initial JPEG quality when an image exceeds the limit; range 1–100, default 95, to preserve embedding detail |
| `QDRANT_URL` | Use `http://qdrant:6333` inside containers |
| `QDRANT_API_KEY` | Optional; on-premises deployment has no API key by default; set it for hosted deployments when needed |
| `QDRANT_COLLECTION` | Collection name |
| `IMPORTER_PDF_RENDER_TARGET_DPI` | Target rendering resolution for ordinary PDF pages; range 72–600, default 200. Extremely large pages use lower effective DPI to meet the pixel limit |
| `IMPORTER_PDF_RENDER_MAX_PIXELS` | Maximum pixels per rendered PDF page; range 1–89,000,000, default 80,000,000, to avoid Pillow safety limits and excessive memory usage |
| `IMPORTER_KEEP_SUCCESS_WORK_FILES` | Retain temporary `work/` files after successful imports; default `false` |
| `IMPORTER_KEEP_FAILED_WORK_FILES` | Retain temporary `work/` files after failed imports; default `true` |
| `IMPORTER_LOG_RETENTION_DAYS` | Execution log retention in days; older `logs/importer-*.log` files are removed at startup; `0` disables automatic cleanup |
| `IMPORTER_LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`; default `INFO` |

Google access uses Service Account JSON in `config/gcp-adc.json` with Domain-Wide Delegation. See the [Google setup guide](../../docs/google-setup.en.md) for administrator configuration.

The `sources` list in `config/google_drive_sources.yaml` supports multiple entries with unique names and source identifiers (see the example). `GOOGLE_DWD_SUBJECT_EMAIL` must have access to these sources.

### Qwen Image Preprocessing

PDF pages are normally rendered to PNG at `IMPORTER_PDF_RENDER_TARGET_DPI`. Effective DPI is reduced only when estimated pixels exceed `IMPORTER_PDF_RENDER_MAX_PIXELS`. When sent to `qwen3-vl-embedding`, images below `DASHSCOPE_IMAGE_MAX_BYTES` retain their original files and are uploaded by the DashScope SDK. Larger images first use lower JPEG quality at the same dimensions, then proportional downscaling if still too large. These limits accommodate Qwen's hard 10,240 KB image limit and prevent Pillow decompression-bomb protection from being triggered by enormous images.

Each run writes to `logs/importer-YYYYMMDD-HHMMSS-ffffff-pPID.log` and stdout. Timestamps use UTC; the level is controlled by `IMPORTER_LOG_LEVEL`. Old logs are removed according to `IMPORTER_LOG_RETENTION_DAYS`, which defaults to 14 days. Cleanup failures are logged and stop the import.

## Development and Testing

Offline unit tests use the conda environment in the [root README](../../README.en.md#local-development-environment). From the repository root:

```powershell
conda activate kbsearch
python -m pip install -e ./src/importer
python -m unittest discover -s tests/importer -t .
```

### Build the Image

Install Docker and start its engine. Build from the repository root before first use or when pyproject.toml or the Dockerfile change:

```powershell
./docker/docker_build_importer.ps1
```

The image is named `kbsearch-importer`, built on Python 3.12 / Debian 12 (Bookworm), and includes headless LibreOffice. TXT/Markdown-to-PDF conversion uses the bundled WenQuanYi Zen Hei font. Debian packages are downloaded from the official source by default; if downloads are slow, specify a mirror, for example `./docker/docker_build_importer.ps1 -DebianMirror http://ftp.tw.debian.org/debian`.

### Configure and Run

From the repository root, create the development configuration:

```powershell
Copy-Item deploy/importer/config/.env.example deploy/importer/config/.env
Copy-Item deploy/importer/config/google_drive_sources.example.yaml deploy/importer/config/google_drive_sources.yaml
```

Prepare test settings and credentials as described above. Start Qdrant using the [deployment guide](../../deploy/README.en.md#starting-and-stopping), then run:

```powershell
./deploy/importer/docker_run.ps1 -Dev
```

`-Dev` loads `deploy/importer/docker-compose.dev.yml`, mounts `src/importer/kbsearch_importer/` read-only, and runs `python -m kbsearch_importer` inside the container. Rerun after source changes.

Configuration, logs, and temporary files are stored under `deploy/importer/config/`, `logs/`, and `work/`.

## Production Deployment

See the [deployment guide](../../deploy/README.en.md) for image export/import, deployment preparation, execution, and scheduling.
