# KBSearch Query CLI

[繁體中文](README.md) | English

`query_cli/` provides the `kbsearch` command as a set of tools for Agent.

Available commands include:

- Google Drive login: the current user completes OAuth authorization in a browser.
- Similarity and keyword search: runs multimodal vector similarity search through the secure_backend API and Google Drive keyword search through the Google Drive API, then downloads and processes result files.
- PDF page image export: exports a specified PDF page to PNG.
- Search-results viewer: starts the web page for viewing search results.

## Development and Test Setup

Offline unit tests and development tools use the shared conda environment specified in the [root README](../README.en.md#local-development-environment). From the repository root, activate it and install the CLI package and wheel build tools:

```powershell
conda activate kbsearch
cd query_cli
python -m pip install -e ".[dev]"
```

Manual testing uses `agent_runtime/_internal/.venv` with an editable install of this subproject. See [Agent Runtime](../agent_runtime/README.en.md#4-create-venv-and-install-the-cli) for setup.

### Install Document Processing Tools

Install LibreOffice and add its `program` directory to the Windows system `PATH`. query_cli invokes `soffice` directly to convert DOC, DOCX, PPT, and PPTX into intermediate PDFs.

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

Manual tests use the `agent_runtime/` workspace. Create the local configuration file from this workspace root:

```powershell
Copy-Item _internal\config\.env.example _internal\config\.env
```

Example `config/.env`:

```env
KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000
KBSEARCH_SECURE_BACKEND_API_KEY=
GOOGLE_OAUTH_CLIENT_CONFIG=config/oauth_client.json
KBSEARCH_VIEWER_PORT=8501
KBSEARCH_QUERY_LOG_RETENTION_DAYS=14
KBSEARCH_LOG_LEVEL=INFO
KBSEARCH_CJK_FONT_PATH=C:\Windows\Fonts\msjh.ttc
```

Settings reside in the workspace's `_internal/config/.env`. All task data is stored under `tasks/` in the workspace root.

`KBSEARCH_SECURE_BACKEND_API_KEY` must match `SECURE_BACKEND_API_KEY` in `secure_backend`.

`GOOGLE_OAUTH_CLIENT_CONFIG` points to the Google OAuth **Desktop client credentials** file `oauth_client.json`. It is maintained by the **internal Google / GCP administrator** following the [Google setup guide](../docs/google-setup.en.md) and supplied with the CLI deployment; users do not need to request or place it themselves.

## Manual Testing

Using the prepared `agent_runtime/_internal/.venv`, switch from the repository root to the execution directory:

```powershell
cd agent_runtime/_internal
```

### Google Drive Login

Run this before first use or when the CLI explicitly reports an `authentication` error:

```powershell
.\.venv\Scripts\kbsearch.exe login
```

The command opens a browser for the current user to authorize Google OAuth. On success, it writes JSON to stdout and stores the token in Windows Credential Manager. The token is removed only when Google explicitly reports that it is invalid or revoked. When Agent runs this command, it must use approval to execute outside the sandbox and ask the user to complete authorization in a browser on the same machine.

Windows Credential Manager does not isolate credentials exclusively to the CLI. Other processes running as the same Windows user, including Agent, can also read them.

### Similarity / Keyword Search

Before similarity search, verify that `secure_backend` is running locally and reachable.

Create a task directory with a name of your choice under the workspace root's `tasks/`. Place any query images directly in that task directory:

```text
agent_runtime/tasks/<task-name>/<image-file>
```

Run the following command:

```powershell
.\.venv\Scripts\kbsearch.exe query `
  --task-name "20260613-130000-manual-test" `
  --query-name "20260613-131500-initial-query" `
  --vector-query "附圖為產品外觀，請找出操作手冊中與此零件安裝相關的說明" `
  --drive-query "(fullText contains '推車' or name contains '推車') and trashed = false" `
  --image "photo.png" `
  --limit 10 `
  --min-score 0.5
```

Options:

- `--task-name`: Required task directory name. Reuse it for searches within the same task.
- `--query-name`: Required directory name for this search. Both names must be valid single directory names; the search directory must not exist before execution.
- `--vector-query`: Semantic query text. Send it to `secure_backend` alone or together with `--image` for similarity search.
- `--drive-query`: Google Drive API `q` syntax, sent unchanged for keyword search on file names, full text, or metadata. Search scope follows the current user's Drive permissions and is not limited to importer source directories. Omitting it disables keyword search.
- `--image`: Image filename directly within the task directory, such as PNG or JPEG; may be specified repeatedly. Only single filenames are accepted. Send images to `secure_backend` alone or with `--vector-query` for similarity search.
- `--limit`: Result count limit for each of similarity search and keyword search; defaults to `10`.
- `--min-score`: Minimum similarity score; omitting it disables filtering of low-score results.

Similarity search covers only documents synchronized by importer. It is skipped when both `--vector-query` and `--image` are omitted. At least one of `--vector-query`, `--drive-query`, and `--image` is required; the command fails if all are omitted.

Before searching, the CLI checks the Google Drive token in Windows Credential Manager, `secure_backend /healthz` when `--vector-query` or `--image` is supplied, `soffice` in the system `PATH`, and the CJK font. A missing or explicitly invalid token ends the command with an `authentication` error and prompts `kbsearch login`.

Search results are stored at:

```text
agent_runtime/tasks/<task-name>/query_results/<query-name>
```

After the checks pass, the CLI creates missing parent directories and the directory for this search. If the query fails, existing directories and partial artifacts are retained; retries require a new query name.

See the [design specification](../docs/design_spec/en/01-high-level-design.md) for details of search-result downloads and conversion.

Progress is written to **stderr**. Downloading begins with a union-level `phase=download status=started` event containing summaries such as `union_count`. Each successful file download emits `phase=download status=started` and `phase=download status=finished`; completion includes text-page and rendered-page counts. A failed file emits `phase=download status=failed`. Use `file_id`, `index`, and `total` to distinguish per-file events from union-level progress.

Command-level failures return exit code `1`. The final stderr event identifies `error_kind` as `input_or_config`, `authentication`, `external_service`, or `internal`, and includes `run_id` and `log_path` when available. Backend `invalid_request` and `payload_too_large` responses are classified as `input_or_config`, preserving the field and constraint information needed to correct the input.

After configuration and the dedicated log have been initialized, stderr emits a parseable query-start event:

```json
{"event":"query_started","status":"started","run_id":"a1b2c3d4","output_dir":"C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query","log_path":"C:/path/to/_internal/logs/kbsearch-20260622-083245-123456-a1b2c3d4.log","monitor":"log","stdout":"final_json_on_success"}
```

`monitor=log` means that progress during long-running operations should be monitored through `log_path`. `stdout=final_json_on_success` means stdout provides no startup summary while the process runs; it emits the following final JSON only on successful or partially successful completion:

```json
{
  "status": "finished_with_errors",
  "run_id": "a1b2c3d4",
  "log_path": "C:/path/to/_internal/logs/kbsearch-20260622-083245-123456-a1b2c3d4.log",
  "output_dir": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query",
  "full_text_count": 1,
  "vector_count": 4,
  "download_count": 3,
  "downloaded_files_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/downloaded_files.json",
  "downloaded_files": [
    {
      "google_file_id": "file-1",
      "name": "Alpha.pdf",
      "directory": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde",
      "source_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde/Alpha.pdf",
      "pdf_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde/pdf/document.pdf",
      "text_paths": [
        "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde/text/0001.txt"
      ],
      "page_paths": [
        "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/Alpha.pdf-abcde/pages/0003.png"
      ]
    }
  ],
  "download_failure_count": 1,
  "download_failures_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/download_failures.json",
  "warning_count": 1,
  "warnings_path": "C:/path/to/tasks/20260613-130000-manual-test/query_results/20260613-131500-initial-query/warnings.json",
  "download_failures": [
    {
      "google_file_id": "file-4",
      "name": "Broken.pdf",
      "stage": "process",
      "error_type": "DocumentRenderError",
      "message": "PDF text extraction failed",
      "google_drive_url": "https://drive.google.com/file/d/file-4/view",
      "vector_page_numbers": [3, 5],
      "full_text_query": "fullText contains 'Broken' and trashed = false"
    }
  ],
  "warnings": [
    {
      "code": "vector_pages_unrendered",
      "google_file_id": "file-5",
      "name": "Archive.zip",
      "mime_type": "application/zip",
      "google_drive_url": "https://drive.google.com/file/d/file-5/view",
      "vector_page_numbers": [7],
      "message": "Vector search matched pages, but no page images were rendered for this file."
    }
  ]
}
```

All subsequent progress includes the `run_id` reported in the startup event. Execution always ends with one of these terminal states:

```text
Query progress: phase=query status=finished run_id=a1b2c3d4 ...
Query progress: phase=query status=finished_with_errors run_id=a1b2c3d4 ...
Query progress: phase=query status=failed run_id=a1b2c3d4 ...
```

If every file succeeds, `status` is `finished` and `download_failure_count` is `0`. If an individual file fails during additional metadata lookup, artifact-directory creation, download, or document processing, that file is skipped and the others continue. The command still returns a successful exit code, with `status` set to `finished_with_errors`.

`download_count` counts successfully downloaded files and excludes `download_failure_count`. `downloaded_files` lists files successfully downloaded and processed, including `google_file_id`, original name, document `directory`, downloaded `source_path`, standard `pdf_path`, per-page `text_paths`, and matched `page_paths`. The full list is also written to `downloaded_files.json`.

Each failure includes `google_file_id`, file name, stage, error type, message, and `google_drive_url`, allowing the user to inspect the original in Google Drive. For vector results, `vector_page_numbers` lists matched pages; for keyword results, `full_text_query` preserves the search condition. Both are included when a file matched both searches. The full list is also written to `download_failures.json`. Partial artifacts from failed files are retained for troubleshooting.

`warnings` records conditions that do not count as failures but affect reading completeness; the full list is also written to `warnings.json`. For example, `vector_pages_unrendered` indicates matched vector page numbers without corresponding `pages/*.png`. A common cause is a Drive file with the same `file_id` changing to a MIME type unsupported for document processing after synchronization. The download still counts as successful, but Agent should read the original file or use other tools and, when necessary, explain that the matched vector pages cannot be read directly.

After configuration loads successfully, each query creates a separate log under `_internal/logs/` named `kbsearch-<datetime>-<run_id>.log`. Timestamps use UTC and the level is controlled by `KBSEARCH_LOG_LEVEL`.

`KBSEARCH_QUERY_LOG_RETENTION_DAYS` controls per-run log retention, defaulting to `14` days. Older `kbsearch-*.log` files are deleted at query startup; `0` disables automatic cleanup. Cleanup failures are logged and stop the query.

The result directory contains failure lists. Each successfully downloaded file's subdirectory retains the download and produces the following artifacts according to its Google Drive MIME type and export result:

```text
<output_dir>/
  query_plan.json
  full_text_results.json
  vector_results.json
  downloaded_files.json
  download_failures.json
  warnings.json
  <safe_file_name_prefix>-<google_file_id_prefix>/
    <downloaded file>
    pdf/
      document.pdf
    text/
      0001.txt
      0002.txt
    pages/
      0003.png
```

#### Document Subdirectory Artifacts

- Each document directory is named `<safe_file_name_prefix>-<google_file_id_prefix>`, with the file-name prefix first and a maximum total length of 48 characters. The Google file ID prefix starts with five characters; collisions within a query extend it one character at a time until distinguishable, shortening the file-name prefix accordingly.
- PDF, Word, PowerPoint, TXT, MD, Google Docs, and Google Slides produce `pdf/document.pdf` and page-numbered UTF-8 files `text/000N.txt`.
- `pages/` automatically produced by `query` contains only pages matched by the current similarity search or located by full-text keywords. A page matched by both shares one `000N.png`; an existing target PNG is reused within the query workflow.
- PNG, JPG, JPEG, and WEBP are single-page documents, but produce `pages/0001.png` only when matched by similarity search. Drive full-text or OCR image matches retain file-level results because no per-page text is available for locating matches.
- Google Sheets exports to XLSX. Other MIME types unsupported for conversion and page processing retain only the original download. Missing PDF, per-page text, or PNG artifacts does not make those downloads failures.

#### `full_text_results.json`

`full_text_results.json` preserves the Google Drive keyword-search file order. Drive's original results contain no page numbers. After download and per-page text extraction, only positive `fullText contains '<keyword>'` values in the Drive query are used to locate pages. `name`, metadata, and other conditions are not used for page location.

Pages are located using case-insensitive literal substring matching, without inferring synonyms or simulating Drive indexing rules. Each located page is written to that file's `pages`: `page_number` is its number and `keyword` contains the full-text keywords matched there. Multiple keywords on a page are deduplicated in query order and joined with a comma and space. Pages are ordered by ascending `page_number`.

If the query has no `fullText contains`, no per-page text matches, or the file cannot produce per-page text, `pages` is empty while the file-level result remains. `source_location` is the Google Drive display path; the My Drive root appears as `雲端硬碟`, and a shared-drive root appears as its drive name. The structure is:

```json
[
  {
    "google_file_id": "file-1",
    "name": "Alpha.pdf",
    "mime_type": "application/pdf",
    "web_url": "https://drive.google.com/file/d/file-1/view",
    "source_location": "ExampleDrive/Products/Alpha.pdf",
    "pages": [
      {
        "page_number": 1,
        "keyword": "推車"
      },
      {
        "page_number": 6,
        "keyword": "推車, 安裝"
      }
    ]
  }
]
```

#### `vector_results.json`

`vector_results.json` preserves the file order returned by `secure_backend`. File-level `score` is the file's overall similarity score; scores within `pages` are for individual matched pages. The structure is:

```json
[
  {
    "google_file_id": "file-1",
    "source_name": "Alpha.pdf",
    "source_location": "ExampleDrive/Products/Alpha.pdf",
    "source_url": "https://drive.google.com/file/d/file-1/view",
    "google_drive_version": "7",
    "google_drive_modified_time": "2026-05-24T00:00:00Z",
    "score": 0.91,
    "pages": [
      {
        "page_number": 3,
        "score": 0.88
      }
    ]
  }
]
```

### Open the Search-Results Viewer

After a query completes, start the results viewer using the port specified by `KBSEARCH_VIEWER_PORT`:

```powershell
.\.venv\Scripts\kbsearch.exe view-results
```

The command reports `viewer_url` and an example URL that preselects a task and query. If a KBSearch viewer already occupies the port, it is stopped and restarted. If another service occupies it, the command stops and prompts a change to `KBSEARCH_VIEWER_PORT`.

```json
{
  "status": "starting",
  "viewer_url": "http://127.0.0.1:8501/",
  "task_query_url_example": "http://127.0.0.1:8501/?task=<task-name>&query=<query-name>",
  "tasks_dir": "C:\\path\\to\\tasks",
  "restarted_process_count": 0
}
```

### Render Specified PDF Pages

Specify a document from the search results and page numbers to render additional pages to PNG:

```powershell
.\.venv\Scripts\kbsearch.exe render-pdf-pages `
  --task-name "<task-name>" `
  --query-name "<query-name>" `
  --document-name "<safe_file_name_prefix>-<google_file_id_prefix>" `
  --pages "3,5,8-10"
```

- `--task-name` and `--query-name`: Names of the task and query directories containing the document.
- `--document-name`: Document directory name. For example, if `directory` in `downloaded_files.json` is `…/query_results/search-01/Alpha.pdf-abcde`, use `Alpha.pdf-abcde`.
- `--pages`: One-based page numbers, supporting comma-separated lists and ranges.

The directory arguments above accept names, not paths.

The command reads `tasks/<task-name>/query_results/<query-name>/<document-name>/pdf/document.pdf` and writes to the same document's `pages/`, creating that directory when needed.

Existing PNGs for the specified pages are overwritten; other pages remain unaffected. Success writes JSON with page numbers and PNG paths to stdout.

## Offline Unit Tests

Run from the repository root:

```powershell
python -m unittest discover -s tests/query_cli -t .
```

## Production Deployment

In production, Agent uses `agent_runtime/` rather than executing source code from `query_cli/`. Build a wheel before deployment.

Using the development environment above, run from the repository root:

```powershell
cd C:\path\to\KBSearch
python -m build query_cli --wheel
```

`python -m build` creates `query_cli/build/` for temporary build files and `query_cli/dist/kbsearch_cli-*.whl`.

Deploy `query_cli/dist/kbsearch_cli-*.whl` to `agent_runtime`.
