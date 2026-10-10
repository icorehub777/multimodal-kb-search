$ErrorActionPreference = 'Stop'
$buildContext = Join-Path $PSScriptRoot '../src/secure_backend'
& docker build -f (Join-Path $PSScriptRoot 'Dockerfile.secure_backend') -t kbsearch-secure-backend $buildContext
exit $LASTEXITCODE
