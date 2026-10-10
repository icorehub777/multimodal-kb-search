$ErrorActionPreference = 'Stop'
$buildContext = Join-Path $PSScriptRoot '../secure_backend'
& docker build -f (Join-Path $PSScriptRoot 'Dockerfile.secure_backend') -t kbsearch-secure-backend $buildContext
exit $LASTEXITCODE
