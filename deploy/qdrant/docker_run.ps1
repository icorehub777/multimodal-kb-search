$ErrorActionPreference = 'Stop'
& docker compose --project-directory $PSScriptRoot -f (Join-Path $PSScriptRoot 'docker-compose.yml') up -d
exit $LASTEXITCODE
