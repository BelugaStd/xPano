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
$ReleaseVenv = Join-Path $Root ".venv-release"
$ReleasePython = Join-Path $ReleaseVenv "Scripts\python.exe"
$ReleaseRequirements = Join-Path $Root "requirements-release.txt"

function Resolve-ReleaseHostPython {
    if ($env:XPANO_RELEASE_PYTHON) {
        if (-not (Test-Path $env:XPANO_RELEASE_PYTHON)) {
            throw "XPANO_RELEASE_PYTHON does not exist: $env:XPANO_RELEASE_PYTHON"
        }
        return $env:XPANO_RELEASE_PYTHON
    }

    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $candidate = & $pyLauncher.Source -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) {
            return $candidate.Trim()
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Python 3.12 was not found. Install Python or set XPANO_RELEASE_PYTHON."
}

function Install-ReleasePythonEnvironment {
    if (-not (Test-Path $ReleaseRequirements)) {
        throw "Missing release requirements: $ReleaseRequirements"
    }

    $env:PYTHONNOUSERSITE = "1"
    $env:PYTHONPATH = ""
    $env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
    $env:PIP_NO_INPUT = "1"
    $env:PIP_DEFAULT_TIMEOUT = "45"

    if (-not (Test-Path $ReleasePython)) {
        $HostPython = Resolve-ReleaseHostPython
        Write-Host "Creating release virtual environment with $HostPython"
        & $HostPython -m venv $ReleaseVenv
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create release virtual environment with exit code $LASTEXITCODE"
        }
    }

    & $ReleasePython -m pip install --upgrade --no-input --timeout 45 --retries 2 pip setuptools wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade release pip with exit code $LASTEXITCODE"
    }

    $InstallArgs = @(
        "-m", "pip", "install",
        "--upgrade",
        "--no-input",
        "--prefer-binary",
        "--only-binary", ":all:",
        "--timeout", "45",
        "--retries", "2",
        "-r", $ReleaseRequirements
    )
    & $ReleasePython @InstallArgs -i "https://pypi.tuna.tsinghua.edu.cn/simple"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Tsinghua PyPI mirror install failed; retrying with default PyPI..."
        & $ReleasePython @InstallArgs
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install release requirements with exit code $LASTEXITCODE"
    }

    $CheckCode = @'
import json
import site
import sys
import cv2
import numpy
import PIL
import piexif
import viser

payload = {
    "executable": sys.executable,
    "version": sys.version,
    "enable_user_site": site.ENABLE_USER_SITE,
    "numpy": numpy.__version__,
    "cv2": cv2.__version__,
    "PIL": PIL.__version__,
    "piexif": getattr(piexif, "__version__", "n/a"),
    "viser": getattr(viser, "__version__", "n/a"),
}
print(json.dumps(payload, ensure_ascii=False))
assert site.ENABLE_USER_SITE in (False, None)
assert numpy.__version__ == "1.26.4"
assert cv2.__version__ == "4.10.0"
'@
    New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
    $CheckScript = Join-Path $BuildDir "verify_release_env.py"
    $CheckCode | Set-Content -LiteralPath $CheckScript -Encoding UTF8
    try {
        & $ReleasePython $CheckScript
        if ($LASTEXITCODE -ne 0) {
            throw "Release Python environment verification failed with exit code $LASTEXITCODE"
        }
    } finally {
        Remove-Item -LiteralPath $CheckScript -Force -ErrorAction SilentlyContinue
    }
}

function Test-PackagedRuntime {
    param(
        [Parameter(Mandatory=$true)][string]$ReleaseDirectory
    )

    $Exe = Join-Path $ReleaseDirectory "xPano.exe"
    if (-not (Test-Path $Exe)) {
        throw "Packaged executable was not found: $Exe"
    }

    $InternalDir = Join-Path $ReleaseDirectory "_internal"
    $BadNumpy = Get-ChildItem -LiteralPath $InternalDir -Directory -Filter "numpy-2*.dist-info" -ErrorAction SilentlyContinue
    if ($BadNumpy) {
        throw "Packaged release contains unexpected NumPy 2 metadata: $($BadNumpy.Name -join ', ')"
    }

    $NumpyMetadata = Get-ChildItem -LiteralPath $InternalDir -Directory -Filter "numpy-1.26.4.dist-info" -ErrorAction SilentlyContinue
    if (-not $NumpyMetadata) {
        throw "Packaged release does not contain numpy-1.26.4.dist-info"
    }

    $ReportPath = Join-Path $ReleaseDirectory "runtime_import_check.json"
    if (Test-Path $ReportPath) {
        Remove-Item -LiteralPath $ReportPath -Force
    }

    $Process = Start-Process -FilePath $Exe -ArgumentList @("--self-test-imports", $ReportPath) -Wait -PassThru -WindowStyle Hidden
    if ($Process.ExitCode -ne 0) {
        throw "Packaged runtime import check failed with exit code $($Process.ExitCode)"
    }
    if (-not (Test-Path $ReportPath)) {
        throw "Packaged runtime import check did not write: $ReportPath"
    }

    $Report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
    if (-not $Report.ok) {
        throw "Packaged runtime import check reported failure"
    }
    if ($Report.modules.numpy.version -ne "1.26.4") {
        throw "Packaged NumPy version is $($Report.modules.numpy.version), expected 1.26.4"
    }
    if ($Report.modules.cv2.version -ne "4.10.0") {
        throw "Packaged OpenCV version is $($Report.modules.cv2.version), expected 4.10.0"
    }
}

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

Write-Host "[1/8] Preparing release folder..."
if (Test-Path $ReleaseDir) {
    Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

if (-not $SkipPyInstaller) {
    Write-Host "[2/8] Preparing clean release Python environment..."
    Install-ReleasePythonEnvironment

    Write-Host "[3/8] Building GUI executable with PyInstaller..."
    $PyInstallerArgs = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--noupx",
        "--name", "xPano",
        "--distpath", $DistRoot,
        "--workpath", (Join-Path $BuildDir "pyinstaller"),
        "--specpath", $SpecDir,
        "--add-data", "$Root\xpano_workbench\assets;xpano_workbench\assets",
        "--collect-all", "PySide6.QtWebEngineCore",
        "--collect-all", "PySide6.QtWebEngineWidgets",
        "--collect-all", "numpy",
        "--collect-all", "cv2",
        "--collect-all", "viser",
        "--copy-metadata", "numpy",
        "--copy-metadata", "opencv-python-headless",
        "--copy-metadata", "viser",
        "--hidden-import", "numpy",
        "--hidden-import", "numpy.core._multiarray_umath",
        "--hidden-import", "cv2",
        "--hidden-import", "PySide6.QtWebEngineCore",
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "viser",
        "--hidden-import", "app",
        "--hidden-import", "xpano_workbench.main",
        "--hidden-import", "xpano_workbench.reconstruction_scene",
        "--hidden-import", "xpano_workbench.viser_bridge",
        (Join-Path $Root "xpano_workbench\__main__.py")
    )
    & $ReleasePython -m PyInstaller @PyInstallerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    $BuiltDir = Join-Path $DistRoot "xPano"
    if (-not (Test-Path $BuiltDir)) {
        throw "PyInstaller output was not found: $BuiltDir"
    }
    Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
    Move-Item -LiteralPath $BuiltDir -Destination $ReleaseDir
    Test-PackagedRuntime -ReleaseDirectory $ReleaseDir
} else {
    Write-Host "[2/8] Skipping PyInstaller build."
    New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir "_internal") | Out-Null
}

$Internal = Join-Path $ReleaseDir "_internal"
if (-not (Test-Path $Internal)) {
    New-Item -ItemType Directory -Force -Path $Internal | Out-Null
}

Write-Host "[4/8] Copying project modules and documentation..."
Copy-Directory (Join-Path $Root "scripts") (Join-Path $Internal "scripts")
Copy-Directory (Join-Path $Root "images") (Join-Path $Internal "images")
Copy-Directory (Join-Path $Root "docs") (Join-Path $ReleaseDir "docs")
Copy-FileIfExists (Join-Path $Root "README.md") (Join-Path $ReleaseDir "README.md")
Copy-FileIfExists (Join-Path $Root "README.zh-CN.md") (Join-Path $ReleaseDir "README.zh-CN.md")
Copy-FileIfExists (Join-Path $Root "GUI_QUICKSTART.md") (Join-Path $ReleaseDir "GUI_QUICKSTART.md")
Copy-FileIfExists (Join-Path $Root "LICENSE") (Join-Path $ReleaseDir "LICENSE")
Copy-FileIfExists (Join-Path $Root "requirements.txt") (Join-Path $ReleaseDir "requirements.txt")
Copy-FileIfExists (Join-Path $Root "requirements-release.txt") (Join-Path $ReleaseDir "requirements-release.txt")
Copy-FileIfExists (Join-Path $Root "metashape_requirements.txt") (Join-Path $ReleaseDir "metashape_requirements.txt")

Write-Host "[5/8] Copying bundled external tools..."
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
    Write-Host "[6/8] Copying LichtFeld densification Python environment..."
    Copy-Directory (Join-Path $Root ".venv-densify") (Join-Path $Internal ".venv-densify")
} else {
    Write-Host "[6/8] Skipping .venv-densify copy."
}

Write-Host "[7/8] Writing release launchers..."
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

Write-Host "[8/8] Release ready:"
Write-Host $ReleaseDir
