param(
    [string]$PluginUrl = "https://github.com/shadygm/Lichtfeld-Densification-Plugin.git",
    [string]$PluginRef = "main",
    [string]$Python = "python",
    [string]$PipIndex = "https://pypi.tuna.tsinghua.edu.cn/simple",
    [switch]$UseCudaTorch,
    [switch]$SkipDeps
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Tools = Join-Path $Root "tools"
$PluginDir = Join-Path $Tools "lichtfeld-densification-plugin"
$VenvDir = Join-Path $Root ".venv-densify"

New-Item -ItemType Directory -Force -Path $Tools | Out-Null

if (-not (Test-Path (Join-Path $PluginDir "densify.py"))) {
    git clone --depth 1 --branch $PluginRef $PluginUrl $PluginDir
} else {
    Push-Location $PluginDir
    git fetch --depth 1 origin $PluginRef
    git checkout FETCH_HEAD
    Pop-Location
}

if ($SkipDeps) {
    Write-Host "Plugin installed at $PluginDir"
    Write-Host "Skipped dependency installation."
    exit 0
}

if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    & $Python -m venv $VenvDir
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Command,
        [Parameter(ValueFromRemainingArguments=$true)]
        [string[]]$CommandArgs
    )
    & $Command @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Command $CommandArgs"
    }
}

Invoke-Checked $VenvPython -m pip install --upgrade pip -i $PipIndex

if ($UseCudaTorch) {
    Invoke-Checked $VenvPython -m pip install `
        --index-url https://download.pytorch.org/whl/cu128 `
        torch==2.8.0+cu128 `
        torchvision==0.23.0+cu128
} else {
    Invoke-Checked $VenvPython -m pip install `
        -i $PipIndex `
        torch==2.8.0 `
        torchvision==0.23.0
}

Invoke-Checked $VenvPython -m pip install `
    -i $PipIndex `
    numpy `
    pycolmap==4.0.4 `
    Pillow `
    scipy `
    tqdm `
    "einops>=0.8.1" `
    "rich>=14.2.0" `
    open3d

Write-Host "LichtFeld densification plugin installed at $PluginDir"
Write-Host "Python environment: $VenvPython"
