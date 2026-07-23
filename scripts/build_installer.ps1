param(
    [string]$FfmpegExe = "",
    [string]$FfprobeExe = "",
    [string]$LichtfeldArchive = "",
    [switch]$SkipVerification,
    [switch]$DevelopmentBuild,
    [switch]$FullOffline
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Resolve-Path (Join-Path $PSScriptRoot "..")).Path)
$UiDir = Join-Path $Root "xpano-ui"
$TauriDir = Join-Path $UiDir "src-tauri"
$Stage = Join-Path $Root "build\release-stage"
$Dist = Join-Path $Root "dist"

function Assert-InWorkspace {
    param([Parameter(Mandatory=$true)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($Root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify path outside workspace: $full"
    }
}

function Resolve-RealExecutable {
    param([string]$Requested, [string]$Name)
    $candidate = $Requested
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $command = Get-Command "$Name.exe" -ErrorAction SilentlyContinue
        if (-not $command) { throw "$Name.exe was not found. Pass -${Name}Exe explicitly." }
        $candidate = $command.Source
    }
    if (-not (Test-Path -LiteralPath $candidate)) { throw "$Name.exe was not found: $candidate" }
    $item = Get-Item -LiteralPath $candidate -Force
    if ($item.LinkType -and $item.Target) {
        $candidate = $item.Target[0]
    }
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if ((Get-Item -LiteralPath $resolved).Length -le 0) { throw "$Name.exe resolved to an empty file: $resolved" }
    return $resolved
}

function Resolve-PinnedLichtfeldArchive {
    param([string]$Requested)
    $candidate = $Requested
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = $env:XPANO_LICHTFELD_ARCHIVE
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        if ($DevelopmentBuild) {
            return ""
        }
        throw "-LichtfeldArchive is required for a production installer build. Set XPANO_LICHTFELD_ARCHIVE or pass the pinned v0.5.3 archive explicitly."
    }
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw "Pinned LichtFeld archive was not found: $candidate"
    }
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if ((Get-Item -LiteralPath $resolved).Length -le 0) {
        throw "Pinned LichtFeld archive is empty: $resolved"
    }
    return $resolved
}

function Assert-ReleaseDllClosure {
    param(
        [string]$Entry = "",
        [string]$WebViewLoader = "",
        [string]$TreeRoot = ""
    )
    $Arguments = @((Join-Path $Root "scripts\windows_dll_closure.py"))
    if (-not [string]::IsNullOrWhiteSpace($Entry)) {
        $Arguments += @("--entry", $Entry, "--app-local", $WebViewLoader)
    }
    if (-not [string]::IsNullOrWhiteSpace($TreeRoot)) {
        $Arguments += @("--tree-root", $TreeRoot)
    }
    python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Windows DLL dependency closure validation failed." }
}

if ($SkipVerification -and -not $DevelopmentBuild) {
    throw "-SkipVerification is allowed only together with -DevelopmentBuild."
}

$Config = Get-Content -Raw -Encoding UTF8 (Join-Path $TauriDir "tauri.conf.json") | ConvertFrom-Json
$CargoText = Get-Content -Raw -Encoding UTF8 (Join-Path $TauriDir "Cargo.toml")
if ($CargoText -notmatch '(?ms)^\[package\].*?^version\s*=\s*"([^"]+)"') {
    throw "Cargo package version was not found."
}
$Version = $Matches[1]
if ($Config.version -ne $Version) {
    throw "Version mismatch: tauri.conf.json=$($Config.version), Cargo.toml=$Version"
}

$Ffmpeg = Resolve-RealExecutable $FfmpegExe "ffmpeg"
$Ffprobe = Resolve-RealExecutable $FfprobeExe "ffprobe"
$PinnedLichtfeldArchive = Resolve-PinnedLichtfeldArchive $LichtfeldArchive

Assert-InWorkspace $Stage
if (Test-Path -LiteralPath $Stage) {
    Remove-Item -LiteralPath $Stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

if (-not $SkipVerification) {
    Push-Location $Root
    try {
        python -m unittest discover -s tests
        if ($LASTEXITCODE -ne 0) { throw "Python tests failed." }
    } finally { Pop-Location }
    Push-Location $UiDir
    try {
        & pnpm.cmd install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw "pnpm install failed." }
        & pnpm.cmd run test:unit
        if ($LASTEXITCODE -ne 0) { throw "Node tests failed." }
        & pnpm.cmd run lint
        if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
    } finally { Pop-Location }
}

Push-Location $TauriDir
try {
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "Release runtime prebuild failed." }
} finally { Pop-Location }
$WebView2Loader = Join-Path $TauriDir "target\release\WebView2Loader.dll"
if (-not (Test-Path -LiteralPath $WebView2Loader) -or (Get-Item -LiteralPath $WebView2Loader).Length -le 0) {
    throw "Fresh WebView2Loader.dll was not produced: $WebView2Loader"
}
$ReleaseExe = Join-Path $TauriDir "target\release\xpano-ui.exe"
Assert-ReleaseDllClosure -Entry $ReleaseExe -WebViewLoader $WebView2Loader

Push-Location $Root
try {
    $StagingArgs = @(
        "scripts\release_staging.py",
        "--root", $Root,
        "--destination", $Stage,
        "--ffmpeg", $Ffmpeg,
        "--ffprobe", $Ffprobe,
        "--webview2-loader", $WebView2Loader,
        "--version", $Version
    )
    if ($FullOffline) {
        $StagingArgs += @(
            "--full-offline-artifacts",
            (Join-Path $Root "tools\offline-densify-artifacts\sha256")
        )
    }
    if (-not [string]::IsNullOrWhiteSpace($PinnedLichtfeldArchive)) {
        $StagingArgs += @("--lichtfeld-archive", $PinnedLichtfeldArchive)
    }
    python @StagingArgs
    if ($LASTEXITCODE -ne 0) { throw "Release staging failed." }
} finally { Pop-Location }

Assert-ReleaseDllClosure -TreeRoot (Join-Path $Stage "binaries\python")
Assert-ReleaseDllClosure -TreeRoot (Join-Path $Stage "tools\colmap")
Assert-ReleaseDllClosure -TreeRoot (Join-Path $Stage "runtime\lichtfeld-studio")

$BuildStarted = Get-Date
Push-Location $UiDir
try {
    & pnpm.cmd exec tauri build --bundles nsis --config src-tauri\tauri.release.conf.json
    if ($LASTEXITCODE -ne 0) { throw "Tauri NSIS build failed." }
} finally { Pop-Location }

# NOTE: Tauri performs its own release build, so validate the exact binary used by NSIS as well.
Assert-ReleaseDllClosure -Entry $ReleaseExe -WebViewLoader $WebView2Loader

$Installer = Get-ChildItem -LiteralPath (Join-Path $TauriDir "target\release\bundle\nsis") -File -Filter "*.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $Installer -or $Installer.LastWriteTime -lt $BuildStarted) {
    throw "A fresh NSIS installer was not produced."
}
$Flavor = if ($FullOffline) { "-full-offline" } else { "" }
$Output = Join-Path $Dist "xPano-$Version$Flavor-windows-x64-setup.exe"
Copy-Item -LiteralPath $Installer.FullName -Destination $Output -Force
$Hash = Get-FileHash -LiteralPath $Output -Algorithm SHA256
"$($Hash.Hash.ToLowerInvariant())  $(Split-Path -Leaf $Output)" |
    Set-Content -LiteralPath "$Output.sha256" -Encoding ASCII

Write-Host "Installer ready: $Output"
Write-Host "SHA-256: $($Hash.Hash)"
