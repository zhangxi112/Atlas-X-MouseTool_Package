param(
    [switch]$Clean,
    [switch]$SkipPortableZip,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $version = (python -c 'from core.constants import APP_VERSION; print(APP_VERSION)')
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Cannot resolve release version' }
    $releaseDir = Join-Path $root "release\$version"
    $distRoot = Join-Path $releaseDir 'dist'
    $distDir = Join-Path $distRoot 'AtlasXCursorStudio'
    $portableZip = Join-Path $releaseDir "AtlasXCursorStudio-portable-$version.zip"
    $installerPath = Join-Path $releaseDir "AtlasXCursorStudio-Setup-$version.exe"
    foreach ($artifact in @($portableZip, $installerPath)) {
        if (Test-Path -LiteralPath $artifact) { throw "Preserving existing release artifact: $artifact" }
    }
    $iscc = $null
    if (-not $SkipInstaller) {
        $isccCandidates = @(
            (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
            'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
            'C:\Program Files\Inno Setup 6\ISCC.exe',
            (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
        ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
        $iscc = $isccCandidates | Select-Object -First 1
        if (-not $iscc) { throw 'Inno Setup is required. Use -SkipInstaller only when a portable build is intended.' }
    }
    New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
    & (Join-Path $PSScriptRoot 'build.ps1') -Clean:$Clean -DistPath $distRoot -WorkPath (Join-Path $root "build\release-$version")

    $reportPath = Join-Path $releaseDir ('package-self-test-' + [guid]::NewGuid().ToString('N') + '.json')
    $exe = Join-Path $distDir 'AtlasXCursorStudio.exe'
    $check = Start-Process -FilePath $exe -ArgumentList @('--self-test', "`"$reportPath`"") -PassThru -WindowStyle Hidden
    if (-not $check.WaitForExit(120000)) {
        $check.Kill()
        throw 'Packaged application self-test timed out'
    }
    if (-not (Test-Path -LiteralPath $reportPath)) { throw "Packaged application self-test produced no report (exit code $($check.ExitCode))" }
    $report = Get-Content -LiteralPath $reportPath -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($check.ExitCode -ne 0 -or $report.status -ne 'passed' -or $report.version -ne $version -or -not $report.frozen) {
        throw "Unexpected package self-test result: $($report | ConvertTo-Json -Compress)"
    }
    Write-Host "Packaged application self-test passed: $version"
    $artifacts = @()
    if (-not $SkipPortableZip) {
        Compress-Archive -Path (Join-Path $distDir '*') -DestinationPath $portableZip -CompressionLevel Optimal
        $artifacts += $portableZip
    }
    if (-not $SkipInstaller) {
        & $iscc "/DAppVersion=$version" "/DDistDir=$distDir" "/DReleaseDir=$releaseDir" (Join-Path $PSScriptRoot 'installer.iss')
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
        $artifacts += $installerPath
    }
    $hashes = foreach ($artifact in $artifacts) {
        if (-not (Test-Path -LiteralPath $artifact) -or (Get-Item -LiteralPath $artifact).Length -eq 0) {
            throw "Missing or empty artifact: $artifact"
        }
        '{0}  {1}' -f (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant(), (Split-Path $artifact -Leaf)
    }
    $hashes | Set-Content -LiteralPath (Join-Path $releaseDir 'SHA256SUMS.txt') -Encoding ascii
    Write-Host "Release artifacts ready: $releaseDir"
} finally {
    Pop-Location
}
