# KBSearch Qdrant

[繁體中文](README.md) | English

On-premises Qdrant vector database running in Docker. It is deployed on the same host and at the same directory level as `importer/` and `secure_backend/`, and shares the `kbsearch` network.

## Repository Directory

```text
qdrant/
  docker/
    docker-compose.yml
    qdrant_storage/          # Runtime data
```

## Build and Start

Create the service root directory at the same level as `importer/` and `secure_backend/`. Copy `qdrant/docker/docker-compose.yml` from the repository to `docker-compose.yml`, then create `qdrant_storage/`:

```text
qdrant/
  docker-compose.yml
  qdrant_storage/
```

```powershell
cd C:\path\to\qdrant
docker compose up -d
```

For local development, run `docker compose up -d` directly from `qdrant/docker/` in the repository.

The persistent container is named `kbsearch-qdrant`. Stop it with `docker compose down`; data in `qdrant_storage/` is retained.

Set `QDRANT_URL` for `importer` and `secure_backend` to `http://127.0.0.1:6333` for local conda or `uvicorn` development, and to `http://qdrant:6333` for production containers.
