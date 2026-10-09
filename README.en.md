# KBSearch

[繁體中文](README.md) | English

KBSearch is designed to:

1. Synchronize Google Workspace documents with a multimodal vector database.
2. Let Codex Agent use tools for GCP keyword search and vector similarity search to answer user questions.

## Directory Structure

```text
KBSearch/
  docs/
  docker/
  src/
    importer/
    query_cli/
    secure_backend/
  agent_runtime/
  deploy/
```

- `docs/`: Design documents.
- `docker/`: Dockerfiles and image build launchers.
- `src/importer/`: Subproject that synchronizes Google Workspace documents with the vector database.
- `src/query_cli/`: Command-line tools that let Agent search Google Workspace by keyword and query the vector database. It accesses the embedding model and vector store through `secure_backend`.
- `src/secure_backend/`: FastAPI subproject that encapsulates access to the Alibaba Cloud embedding model and Qdrant vector store. These services are isolated behind this API because their API keys must not be exposed to regular users.
- `agent_runtime/`: Production workspace for Agent, including the packaged `query_cli` command-line tools.
- `deploy/`: Local execution and deployment directories for Qdrant, importer, and secure_backend, containing Compose files, launchers, and configuration templates. Actual settings, credentials, and runtime artifacts are not tracked.

## Documentation

- Repository-wide engineering rules: `AGENTS.md`
- System requirements and design: start with [Project Goals](docs/design_spec/en/00-project-goals.md) and [High-Level Design](docs/design_spec/en/01-high-level-design.md)
- Google administrator setup: [`docs/google-setup.en.md`](docs/google-setup.en.md)
- Contributing: [`CONTRIBUTING.en.md`](CONTRIBUTING.en.md)
- Service deployment: [`deploy/README.en.md`](deploy/README.en.md)
- Subproject usage: each subproject's `README.en.md`
- Subproject engineering rules: each subproject's `AGENTS.md`
- Agent workspace rules: `agent_runtime/AGENTS.md`

## Development Principles

This project uses a documentation-driven Agent development model. `docs/` defines system-level requirements and designs, each subproject's README defines its features, configuration, operation, and external contracts, and `AGENTS.md` defines the engineering rules for development.

Development Agents implement the code from these documents using test-driven development (TDD): tests first make requirements concrete, implementation and refactoring follow, and the tests verify conformance with the defined requirements and engineering rules.

## Runtime Responsibilities

- `src/importer/`: Runs in a container during development and deployment; an external scheduler starts production synchronization jobs.
- `src/secure_backend/`: Runs in a container during development and deployment and provides a persistent FastAPI service.
- `src/query_cli/`: Is packaged as a Python package and installed in the Python environment used by `agent_runtime`, providing the `kbsearch` command.
- `agent_runtime/`: Is the production working directory where Agent performs KB searches. At runtime it only requires this directory and the installed `kbsearch` command.

## Local Development Environment

The supported and validated Python version is 3.12.

`agent_runtime/` uses `agent_runtime/_internal/.venv`.

Offline unit tests and development tools for the other Python subprojects use the shared `kbsearch` conda environment.

Importer and secure_backend service execution and real-flow verification use Docker.

Check whether the `kbsearch` environment exists:

```powershell
conda env list | Select-String kbsearch
```

Create it when necessary:

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

Each subproject's README describes its development setup. See the [deployment guide](deploy/README.en.md) for production deployment of backend services.

## Additional Notes

- This README provides only a project overview. See the subproject documentation for details.
- The root `tests/` directory is used for local verification and is not tracked by Git.

## License

Copyright (C) 2026 iCoreHub contributors

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE), primarily because its dependency [PyMuPDF](https://github.com/pymupdf/PyMuPDF) is offered by Artifex Software, Inc. under either the GNU AGPL v3 or a commercial license. This project uses PyMuPDF under the GNU AGPL v3. Other third-party components remain subject to their respective licenses.
