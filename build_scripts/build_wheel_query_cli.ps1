$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$projectRoot = Join-Path $repoRoot 'query_cli'
$packagesRoot = Join-Path $repoRoot 'agent_runtime/_internal/packages'
New-Item -ItemType Directory -Path $packagesRoot -Force | Out-Null
$stagingPath = Join-Path $packagesRoot ('.wheel-build-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stagingPath | Out-Null

try {
    & python -m build $projectRoot --wheel --outdir $stagingPath
    if ($LASTEXITCODE -ne 0) { throw "query_cli wheel build failed (exit code $LASTEXITCODE)." }

    $wheels = @(Get-ChildItem -LiteralPath $stagingPath -Filter '*.whl' -File)
    if ($wheels.Count -ne 1 -or $wheels[0].Name -notlike 'kbsearch_cli-*.whl') {
        throw 'Expected exactly one kbsearch_cli wheel.'
    }
    $wheel = $wheels[0]
    Copy-Item -LiteralPath $wheel.FullName -Destination (Join-Path $packagesRoot $wheel.Name) -Force
    Get-ChildItem -LiteralPath $packagesRoot -Filter 'kbsearch_cli-*.whl' -File |
        Where-Object { $_.Name -ne $wheel.Name } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName }
    Write-Host "Wheel ready: $(Join-Path $packagesRoot $wheel.Name)"
}
finally {
    $resolvedStaging = [IO.Path]::GetFullPath($stagingPath)
    $resolvedPackages = [IO.Path]::GetFullPath($packagesRoot) + [IO.Path]::DirectorySeparatorChar
    if (!$resolvedStaging.StartsWith($resolvedPackages, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Wheel staging directory must remain inside the package output directory.'
    }
    Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
}
