param(
    [switch]$Clean,
    [string]$DistPath = (Join-Path $PSScriptRoot '..\dist'),
    [string]$WorkPath = (Join-Path $PSScriptRoot '..\build')
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$projectExe = [IO.Path]::GetFullPath((Join-Path $DistPath 'AtlasXCursorStudio\AtlasXCursorStudio.exe'))
$running = Get-Process AtlasXCursorStudio -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $projectExe }
if ($running) {
    throw "Build destination is running. Exit it or select a different -DistPath: $projectExe"
}

Write-Host "Building Atlas-X Cursor Studio with PyInstaller..."
$buildArgs = @('-m', 'PyInstaller', '--noconfirm', '--distpath', $DistPath, '--workpath', $WorkPath, (Join-Path $root 'atlas_cursor_studio.spec'))
if ($Clean) {
    $buildArgs += "--clean"
}
Push-Location $root
$originalPath = $env:PATH
try {
    $python = (Get-Command python -ErrorAction Stop).Source
    $runtimeDirs = (& $python -c 'import json,sys; print(json.dumps([sys.prefix, sys.base_prefix]))') | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve Python runtime paths' }
    # Do not collect unrelated DLLs from other tools on the caller's PATH.
    $env:PATH = (@((Split-Path -Parent $python)) + @($runtimeDirs) + @(
        (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot
    ) | Select-Object -Unique) -join [IO.Path]::PathSeparator
    & $python @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $projectExe)) { throw "Missing executable: $projectExe" }
} finally {
    $env:PATH = $originalPath
    Pop-Location
}
Write-Host "Build complete: $projectExe"
