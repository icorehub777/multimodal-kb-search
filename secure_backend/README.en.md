# KBSearch Secure Backend

[繁體中文](README.md) | English

`secure_backend/` is KBSearch's internal FastAPI service. It encapsulates DashScope embedding model and Qdrant vector store operations and protects its APIs with an API key.

## Directories and Configuration

Source is in `secure_backend/src/kbsearch_backend/`, tests are in `tests/secure_backend/`, and image build files are in the root `build_scripts/` directory. Local execution uses `deploy/secure_backend/`; see the [deployment guide](../deploy/README.en.md#directories-and-preparation) for its directory layout.

Settings in `config/.env`:

| Setting | Purpose |
|---------|---------|
| `SECURE_BACKEND_API_KEY` | Shared API key used to call the service |
| `DASHSCOPE_API_KEY` | DashScope API key |
| `DASHSCOPE_EMBEDDING_MODEL` | Embedding model name |
| `KBSEARCH_VECTOR_SIZE` | Positive integer dimension shared by embedding and Qdrant; must match the importer |
| `DASHSCOPE_IMAGE_MAX_BYTES` | Maximum image size sent to DashScope |
| `DASHSCOPE_JPEG_QUALITY` | Initial JPEG quality used when compressing images |
| `QDRANT_URL` | Use `http://qdrant:6333` inside containers |
| `QDRANT_API_KEY` | Qdrant API key; may be left empty when authentication is disabled |
| `QDRANT_COLLECTION` | Collection used for search |
| `SECURE_BACKEND_MAX_QUERY_LENGTH` | Maximum query text length; defaults to `4000` |
| `SECURE_BACKEND_MAX_IMAGES` | Maximum number of images per query; defaults to `5` |
| `SECURE_BACKEND_MAX_SEARCH_LIMIT` | Maximum number of results per query; defaults to `100` |
| `SECURE_BACKEND_LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`; defaults to `INFO` |

Application logs are written to `logs/secure_backend.log` in the service directory and stdout. Timestamps and daily rotation use UTC; 14 rotated files are retained.

## Development and Testing

Offline unit tests use the conda environment in the [root README](../README.en.md#local-development-environment). From the repository root:

```powershell
conda activate kbsearch
python -m pip install -e "./secure_backend[dev]"
python -m unittest discover -s tests/secure_backend -t .
```

### Build the Image

Install Docker and start its engine. Build from the repository root before first use or when pyproject.toml or the Dockerfile change:

```powershell
./build_scripts/docker_build_secure_backend.ps1
```

The image is named `kbsearch-secure-backend`.

### Configure and Start

From the repository root:

```powershell
Copy-Item deploy/secure_backend/config/.env.example deploy/secure_backend/config/.env
```

Configure the API key, DashScope, and test collection. Start Qdrant using the [deployment guide](../deploy/README.en.md#starting-and-stopping), then run:

```powershell
./deploy/secure_backend/docker_run.ps1 -Dev
```

The API is available at `http://localhost:8000` after startup.

`-Dev` loads `deploy/secure_backend/docker-compose.dev.yml`, mounts `secure_backend/src/kbsearch_backend/` read-only, and enables reload. This lets development run directly in Docker, with automatic restarts after source changes and no need to rebuild the image each time.

Startup checks configuration, DashScope, and the Qdrant collection; failures exit and are logged.

## Production Deployment

See the [deployment guide](../deploy/README.en.md) for image export/import, deployment preparation, and service startup/shutdown.

## API Contract

Every endpoint requires this header:

```http
X-API-Key: <SECURE_BACKEND_API_KEY>
```

Health check:

```http
GET /healthz
```

Vector search:

```http
POST /search/vector
Content-Type: application/json
```

Request:

```json
{
  "query": "query text",
  "images": [
    {
      "filename": "query.png",
      "mime_type": "image/png",
      "base64_data": "iVBORw0KGgo..."
    }
  ],
  "limit": 10,
  "min_score": 0.5
}
```

At least one of `query` and `images` is required. Query text length, image count, and result count must not exceed the server settings. `limit` must be a positive integer. When supplied, `min_score` must be a finite number between `-1` and `1`.

The response groups results by Google file ID. Files are ordered by their highest similarity score, and pages within each file are ordered by similarity score.

Errors use a stable response structure:

```json
{
  "error": "invalid_request",
  "field": "limit",
  "message": "limit must be between 1 and 100."
}
```

`field` is included only when the error can be associated with a specific request field. `message` includes the constraint needed by the caller to correct the input.

| HTTP status | `error` | Condition |
|-------------|---------|-----------|
| `401` | `authentication` | API key is missing or invalid |
| `400` | `invalid_request` | Request does not satisfy query constraints |
| `413` | `payload_too_large` | An image exceeds processing limits |
| `502` | `external_service` | DashScope or Qdrant call failed |
| `500` | `internal` | Other service error |

`5xx` responses do not expose raw DashScope, Qdrant, or internal connection errors. Full details are recorded in the server log.
