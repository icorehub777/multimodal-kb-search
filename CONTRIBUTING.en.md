# Contributing

[繁體中文](CONTRIBUTING.md) | English

## Issues and Changes

Use GitHub Issues for problems and suggestions. Include reproduction steps, environment, and expected and actual results; remove credentials and personal or internal sensitive information. Discuss changes to requirements or external contracts in an Issue before submitting a Pull Request.

Describe the purpose and validation results in the Pull Request. Engineering rules are in the root and relevant subproject `AGENTS.md`; requirements, functionality, and external contracts are in the [design specification](docs/design_spec/en/01-high-level-design.md) and subproject READMEs.

## Development and Validation

Prepare the environment using the [root README](README.en.md#local-development-environment), then follow the relevant subproject README to install dependencies and run offline tests. CLI release validation also includes building and installing the actual wheel. Use a separate test environment and data for verification involving real services.
