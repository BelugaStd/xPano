param(
    [string]$ReleaseName = "xPano-release",
    [string]$Version = "0.1.1-portable",
    [switch]$SkipPyInstaller,
    [switch]$SkipDensifyVenv
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistRoot = Join-Path $Root "dist"
$ReleaseDir = Join-Path $DistRoot $ReleaseName
$BuildDir = Join-Path $Root "build"
$SpecDir = Join-Path $BuildDir "spec"

function Copy-Directory {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    if (-not (Test-Path $Source)) {
        throw "Required release dependency is missing: $Source"
    }
    if (Test-Path $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Copy-FileIfExists {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    if (Test-Path $Source) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
    }
}

Write-Host "[1/7] Preparing release folder..."
if (Test-Path $ReleaseDir) {
    Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

if (-not $SkipPyInstaller) {
    Write-Host "[2/7] Building GUI executable with PyInstaller..."
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --onedir `
        --name xPano `
        --distpath $DistRoot `
        --workpath (Join-Path $BuildDir "pyinstaller") `
        --specpath $SpecDir `
        (Join-Path $Root "app.py")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    $BuiltDir = Join-Path $DistRoot "xPano"
    if (-not (Test-Path $BuiltDir)) {
        throw "PyInstaller output was not found: $BuiltDir"
    }
    Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
    Move-Item -LiteralPath $BuiltDir -Destination $ReleaseDir
} else {
    Write-Host "[2/7] Skipping PyInstaller build."
    New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir "_internal") | Out-Null
}

$Internal = Join-Path $ReleaseDir "_internal"
if (-not (Test-Path $Internal)) {
    New-Item -ItemType Directory -Force -Path $Internal | Out-Null
}

Write-Host "[3/7] Copying project modules and documentation..."
Copy-Directory (Join-Path $Root "scripts") (Join-Path $Internal "scripts")
Copy-Directory (Join-Path $Root "images") (Join-Path $Internal "images")
Copy-Directory (Join-Path $Root "docs") (Join-Path $ReleaseDir "docs")
Copy-FileIfExists (Join-Path $Root "README.md") (Join-Path $ReleaseDir "README.md")
Copy-FileIfExists (Join-Path $Root "README.zh-CN.md") (Join-Path $ReleaseDir "README.zh-CN.md")
Copy-FileIfExists (Join-Path $Root "GUI_QUICKSTART.md") (Join-Path $ReleaseDir "GUI_QUICKSTART.md")
Copy-FileIfExists (Join-Path $Root "LICENSE") (Join-Path $ReleaseDir "LICENSE")
Copy-FileIfExists (Join-Path $Root "requirements.txt") (Join-Path $ReleaseDir "requirements.txt")
Copy-FileIfExists (Join-Path $Root "metashape_requirements.txt") (Join-Path $ReleaseDir "metashape_requirements.txt")

Write-Host "[4/7] Copying bundled external tools..."
Copy-Directory (Join-Path $Root "tools\colmap") (Join-Path $Internal "tools\colmap")
Copy-Directory (Join-Path $Root "tools\lichtfeld-densification-plugin") (Join-Path $Internal "tools\lichtfeld-densification-plugin")
Copy-Directory (Join-Path $Root "tools\torch-cache") (Join-Path $Internal "tools\torch-cache")

$FfmpegSource = Join-Path $Root "tools\ffmpeg"
if (Test-Path $FfmpegSource) {
    Copy-Directory $FfmpegSource (Join-Path $Internal "tools\ffmpeg")
} else {
    $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    $ffprobe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
    if (-not $ffmpeg -or -not $ffprobe) {
        throw "ffmpeg/ffprobe not found. Install ffmpeg or place it under tools\ffmpeg before building release."
    }
    $ffmpegDir = Join-Path $Internal "tools\ffmpeg\bin"
    New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null
    Copy-Item -LiteralPath $ffmpeg.Source -Destination (Join-Path $ffmpegDir "ffmpeg.exe") -Force
    Copy-Item -LiteralPath $ffprobe.Source -Destination (Join-Path $ffmpegDir "ffprobe.exe") -Force
}

if (-not $SkipDensifyVenv) {
    Write-Host "[5/7] Copying LichtFeld densification Python environment..."
    Copy-Directory (Join-Path $Root ".venv-densify") (Join-Path $Internal ".venv-densify")
} else {
    Write-Host "[5/7] Skipping .venv-densify copy."
}

Write-Host "[6/7] Writing release launchers..."
@'
@echo off
setlocal
cd /d "%~dp0"
start "" "%~dp0xPano.exe"
'@ | Set-Content -LiteralPath (Join-Path $ReleaseDir "RUN_XPANO.bat") -Encoding ASCII

@'
@echo off
setlocal
cd /d "%~dp0"
"%~dp0xPano.exe"
pause
'@ | Set-Content -LiteralPath (Join-Path $ReleaseDir "RUN_XPANO_DEBUG.bat") -Encoding ASCII

@"
# xPano Portable Release $Version

Run `RUN_XPANO.bat` to start the GUI.

Bundled:
- GUI executable and Python runtime
- COLMAP under `_internal\tools\colmap`
- ffmpeg/ffprobe under `_internal\tools\ffmpeg`
- LichtFeld densification plugin under `_internal\tools\lichtfeld-densification-plugin`
- LichtFeld Python environment under `_internal\.venv-densify`
- RoMa/DINO model cache under `_internal\tools\torch-cache`

Metashape backend still requires a local Metashape installation. Put `metashape.exe`
on PATH or set `XPANO_METASHAPE` to the full executable path.
"@ | Set-Content -LiteralPath (Join-Path $ReleaseDir "RELEASE_README.md") -Encoding UTF8

Write-Host "[7/7] Release ready:"
Write-Host $ReleaseDir
