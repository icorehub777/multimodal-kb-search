# KBSearch Secure Backend

[繁體中文](README.md) | English

`secure_backend/` is KBSearch's internal FastAPI service. It encapsulates DashScope embedding model and Qdrant vector store operations and protects its APIs with an API key.

## Directory Structure

```text
secure_backend/
  main.py              # uvicorn entry point: main:app
  app/                 # Application modules
    factory.py         # create_app()
    config.py
    ...
  config/
    .env
  docker/              # Production image and Compose files
  tests/
  requirements.txt
```

## Development and Test Setup

Local development uses the repository's shared `kbsearch` conda environment. Check whether it exists:

```powershell
conda env list | Select-String kbsearch
```

Create it when necessary:

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

Activate the environment and install external dependencies:

```powershell
conda activate kbsearch
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` from the `secure_backend/` directory:

```powershell
cd secure_backend
Copy-Item config\.env.example config\.env
```

The settings in `config/.env` are:

| Setting | Purpose |
|---------|---------|
| `SECURE_BACKEND_API_KEY` | Shared API key used to call the service |
| `DASHSCOPE_API_KEY` | DashScope API key |
| `DASHSCOPE_EMBEDDING_MODEL` | Embedding model name |
| `DASHSCOPE_VECTOR_SIZE` | Positive integer vector dimension; must match `QDRANT_VECTOR_SIZE` |
| `DASHSCOPE_IMAGE_MAX_BYTES` | Maximum image size sent to DashScope |
| `DASHSCOPE_JPEG_QUALITY` | Initial JPEG quality used when compressing images |
| `QDRANT_URL` | Qdrant URL; defaults locally to `http://127.0.0.1:6333` |
| `QDRANT_API_KEY` | Qdrant API key; may be left empty when authentication is disabled |
| `QDRANT_COLLECTION` | Collection used for search |
| `QDRANT_VECTOR_SIZE` | Positive integer vector dimension of the collection |
| `SECURE_BACKEND_MAX_QUERY_LENGTH` | Maximum query text length; defaults to `4000` |
| `SECURE_BACKEND_MAX_IMAGES` | Maximum number of images per query; defaults to `5` |
| `SECURE_BACKEND_MAX_SEARCH_LIMIT` | Maximum number of results per query; defaults to `100` |
| `SECURE_BACKEND_LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`; defaults to `INFO` |

Application logs are written to `logs/secure_backend.log` and stdout. Timestamps and daily rotation use UTC, and 14 rotated files are retained. With Docker deployment, logs are available under `docker/logs/`.

Start the local API from `secure_backend/`. At startup, the service validates its settings, the DashScope embedding service, and the Qdrant collection. If a check fails, the process exits and records an error summary in the log.

```powershell
cd secure_backend
uvicorn main:app --host 127.0.0.1 --port 8000
```

Run the offline unit tests:

```powershell
cd secure_backend
python -m unittest discover -s tests
```

## Production Deployment

`secure_backend/docker/` contains the files needed to build and run the service image.

Build the image:

```powershell
cd secure_backend/docker
docker compose build
```

The resulting local image is named `kbsearch-secure-backend`.

Export the image on the build machine to produce a tar file for transfer:

```powershell
docker save -o kbsearch-secure-backend.tar kbsearch-secure-backend:latest
```

After copying `kbsearch-secure-backend.tar` to the production machine, import it:

```powershell
docker load -i kbsearch-secure-backend.tar
```

Create the following `secure_backend` directory structure in production:

```text
secure_backend/
  docker-compose.yml
  config/
    .env
  logs/
```

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Copy from the project's `docker/` directory; builds, starts, and manages the service |
| `config/.env` | Copy from the project's `config/` directory; contains secret settings |
| `logs/` | Service log output directory |

Adjust `.env` for the production environment, including setting `QDRANT_URL` to `http://qdrant:6333`, then start the container from the service root:

```powershell
docker compose up -d
```

The persistent container is named `kbsearch-secure-backend` and is visible in `docker ps`.

View logs or stop the service:

```powershell
docker compose logs -f
docker compose down
```

## API Contract

Every endpoint requires this header:

```http
X-API-Key: <SECURE_BACKEND_API_KEY>
```

This service is intended for a trusted internal environment. The shared API key protects the service endpoint but does not represent individual Google Drive permissions. Callers holding the key can retrieve search metadata; `query_cli` performs user-permission filtering.

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
