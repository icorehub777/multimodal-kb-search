param(
    [ValidatePattern('^https?://[A-Za-z0-9._:/-]+$')]
    [string]$DebianMirror = 'http://deb.debian.org/debian'
)

$ErrorActionPreference = 'Stop'
$buildContext = Join-Path $PSScriptRoot '../src/importer'
& docker build -f (Join-Path $PSScriptRoot 'Dockerfile.importer') -t kbsearch-importer --build-arg "DEBIAN_MIRROR=$($DebianMirror.TrimEnd('/'))" $buildContext
exit $LASTEXITCODE
