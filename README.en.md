# KBSearch

[繁體中文](README.md) | English

KBSearch is designed to:

1. Synchronize Google Workspace documents with a multimodal vector database.
2. Let Codex Agent use tools for GCP keyword search and vector similarity search to answer user questions.

## Directory Structure

```text
KBSearch/
  docs/
  qdrant/
  importer/
  query_cli/
  secure_backend/
  agent_runtime/
```

- `docs/`: Design documents.
- `qdrant/`: On-premises Qdrant vector database.
- `importer/`: Subproject that synchronizes Google Workspace documents with the vector database.
- `query_cli/`: Command-line tools that let Agent search Google Workspace by keyword and query the vector database. It accesses the embedding model and vector store through `secure_backend`.
- `secure_backend/`: FastAPI subproject that encapsulates access to the Alibaba Cloud embedding model and Qdrant vector store. These services are isolated behind this API because their API keys must not be exposed to regular users.
- `agent_runtime/`: Production workspace for Agent, including the packaged `query_cli` command-line tools.

## Documentation

- Repository-wide engineering rules: `AGENTS.md`
- System requirements and design: start with [Project Goals](docs/design_spec/en/00-project-goals.md) and [High-Level Design](docs/design_spec/en/01-high-level-design.md)
- Google administrator setup: [`docs/google-setup.en.md`](docs/google-setup.en.md)
- Contributing: [`CONTRIBUTING.en.md`](CONTRIBUTING.en.md)
- Subproject usage: each subproject's `README.en.md`
- Subproject engineering rules: each subproject's `AGENTS.md`
- Agent workspace rules: `agent_runtime/AGENTS.md`

## Development Principles

This project uses a documentation-driven Agent development model. `docs/` defines system-level requirements and designs, each subproject's README defines its features, configuration, operation, and external contracts, and `AGENTS.md` defines the engineering rules for development.

Development Agents implement the code from these documents using test-driven development (TDD): tests first make requirements concrete, implementation and refactoring follow, and the tests verify conformance with the defined requirements and engineering rules.

## Runtime Responsibilities

- `importer/`: Runs as a container in production and is started by an external scheduler for synchronization jobs.
- `secure_backend/`: Runs as a container in production and provides a persistent FastAPI service.
- `query_cli/`: Is packaged as a Python package and installed in the Python environment used by `agent_runtime`, providing the `kbsearch` command.
- `agent_runtime/`: Is the production working directory where Agent performs KB searches. At runtime it only requires this directory and the installed `kbsearch` command.

## Local Development Environment

All Python subprojects use the shared `kbsearch` conda environment except `agent_runtime/`, which uses `agent_runtime/_internal/.venv`.

Check whether the environment exists:

```powershell
conda env list | Select-String kbsearch
```

Create it when necessary:

```powershell
conda create -n kbsearch python=3.12 pip setuptools wheel
```

Activate the environment and install repository-wide development and test dependencies from the repository root:

```powershell
conda activate kbsearch
python -m pip install -r requirements-dev.txt
```

Each subproject's README describes its development setup and production deployment.

## Additional Notes

- This README provides only a project overview. See the subproject documentation for details.
- The root `tests/` directory is used for local verification and is not tracked by Git.

## License

Copyright (C) 2026 iCoreHub contributors

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE). It uses [PyMuPDF](https://github.com/pymupdf/PyMuPDF), offered by Artifex Software, Inc. under the GNU AGPL v3 or a commercial license, under the terms of the GNU AGPL v3. Other third-party components remain subject to their respective licenses.
