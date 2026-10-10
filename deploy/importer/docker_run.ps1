param([switch]$Dev)

$ErrorActionPreference = 'Stop'
$composeFiles = @('-f', (Join-Path $PSScriptRoot 'docker-compose.yml'))
if ($Dev) {
    $composeFiles += @('-f', (Join-Path $PSScriptRoot 'docker-compose.dev.yml'))
}
& docker compose --project-directory $PSScriptRoot @composeFiles run --rm importer
exit $LASTEXITCODE
