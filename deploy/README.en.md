# KBSearch Deployment

[繁體中文](README.md) | English

`deploy/` provides local execution and deployment directories for Qdrant, importer, and secure_backend. The three services run on the same Docker host and share the `kbsearch` network. Local and production environments use the same directory structure with separate settings and data.

## Directories and Preparation

```text
deploy/
  qdrant/
    docker-compose.yml
    docker_run.ps1
    qdrant_storage/
  importer/
    docker-compose.yml
    docker-compose.dev.yml
    docker_run.ps1
    config/
    logs/
    work/
  secure_backend/
    docker-compose.yml
    docker-compose.dev.yml
    docker_run.ps1
    config/
    logs/
```

Install Docker and start its engine on the deployment host. Copy the services' Compose files, launchers, and configuration templates using the layout above. Do not use actual development settings, credentials, or runtime data as deployment templates.

Importer requires `.env`, `google_drive_sources.yaml`, and the administrator-provided `gcp-adc.json` under `config/`; backend requires `config/.env`. For settings and image building, see the [importer README](../src/importer/README.en.md) and [secure_backend README](../src/secure_backend/README.en.md).

## Image Export and Import

After building the images, export them on the build machine:

```powershell
docker save -o kbsearch-importer.tar kbsearch-importer:latest
docker save -o kbsearch-secure-backend.tar kbsearch-secure-backend:latest
```

Transfer the tar files to the deployment host and import them. Compose obtains the Qdrant image from the registry:

```powershell
docker load -i kbsearch-importer.tar
docker load -i kbsearch-secure-backend.tar
```

## Starting and Stopping

From `deploy/`, start Qdrant to create the shared network, then start the backend:

```powershell
./qdrant/docker_run.ps1
./secure_backend/docker_run.ps1
```

Run importer on demand or through an external scheduler. Its container is removed after each synchronization batch:

```powershell
./importer/docker_run.ps1
```

For local development, importer and backend support `-Dev` to mount source. Production and release verification run the code packaged in the images without this option.

The persistent containers are named `kbsearch-qdrant` and `kbsearch-secure-backend`. From each service directory, use `docker compose logs -f` to inspect output or `docker compose down` to stop it. Before stopping Qdrant, ensure importer has finished and stop the backend.

## Importer Scheduling

Use Windows Task Scheduler to invoke the same launcher:

- Program: `powershell.exe`.
- Arguments: `-NoProfile -File "C:\deploy\kbsearch\importer\docker_run.ps1"`, adjusted to the actual deployment path.
- Set the required schedule and select "Do not start a new instance" when the task is already running.
- The task account must have Docker access and the engine must remain running. Complete manual verification before scheduling.

## Connectivity and Runtime Data

Containers access the vector database at `http://qdrant:6333`; the host endpoint `http://127.0.0.1:6333` is available only for local inspection. The backend exposes port `8000` on the host. Qdrant's container soft and hard open-file limits are both 65,536.

Qdrant data is stored in `qdrant/qdrant_storage/` and survives container shutdown. Importer and backend keep logs in their respective `logs/` directories; importer working files are stored in `importer/work/`. Actual settings, credentials, and runtime artifacts are not tracked by Git.
