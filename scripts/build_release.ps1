param(
    [string]$ReleaseName = "xPano-release",
    [string]$Version = "0.1.1-portable",
    [switch]$SkipTauriBuild,
    [switch]$SkipDensifyVenv
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistRoot = Join-Path $Root "dist"
$ReleaseDir = Join-Path $DistRoot $ReleaseName

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

function Copy-PortableDirectory {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [string[]]$ExcludeNames = @(),
        [string[]]$ExcludeExtensions = @()
    )
    if (-not (Test-Path $Source)) {
        throw "Required release dependency is missing: $Source"
    }
    if (Test-Path $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    $SourceRoot = [System.IO.Path]::GetFullPath((Resolve-Path $Source).Path).TrimEnd("\", "/")
    Get-ChildItem -LiteralPath $Source -Recurse -Force | ForEach-Object {
        $full = [System.IO.Path]::GetFullPath($_.FullName)
        $relative = $full.Substring($SourceRoot.Length).TrimStart("\", "/")
        if (-not $relative) {
            return
        }
        $parts = $relative -split '[\\/]'
        if ($parts | Where-Object { $ExcludeNames -contains $_ }) {
            return
        }
        if (-not $_.PSIsContainer -and ($ExcludeExtensions -contains $_.Extension.ToLowerInvariant())) {
            return
        }
        $target = Join-Path $Destination $relative
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
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

function Copy-DensifyRuntime {
    param(
        [Parameter(Mandatory=$true)][string]$SourceVenv,
        [Parameter(Mandatory=$true)][string]$DestinationVenv,
        [Parameter(Mandatory=$true)][string]$EmbeddedPythonSource
    )
    $SourceSitePackages = Join-Path $SourceVenv "Lib\site-packages"
    if (-not (Test-Path $SourceSitePackages)) {
        throw "LichtFeld densification dependencies are missing: $SourceSitePackages"
    }
    if (-not (Test-Path (Join-Path $EmbeddedPythonSource "python.exe"))) {
        throw "Embedded Python runtime is missing: $EmbeddedPythonSource"
    }
    if (Test-Path $DestinationVenv) {
        Remove-Item -LiteralPath $DestinationVenv -Recurse -Force
    }
    $DestinationSitePackages = Join-Path $DestinationVenv "Lib\site-packages"
    New-Item -ItemType Directory -Force -Path $DestinationSitePackages | Out-Null
    & robocopy $SourceSitePackages $DestinationSitePackages /E /XD __pycache__ /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Failed to copy LichtFeld densification dependencies with robocopy exit code $LASTEXITCODE"
    }

    $DestinationScripts = Join-Path $DestinationVenv "Scripts"
    New-Item -ItemType Directory -Force -Path $DestinationScripts | Out-Null
    Get-ChildItem -LiteralPath $EmbeddedPythonSource -File | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $DestinationScripts $_.Name) -Force
    }
    $Pth = Get-ChildItem -LiteralPath $DestinationScripts -Filter "python*._pth" -File | Select-Object -First 1
    if (-not $Pth) {
        throw "Embedded Python _pth file was not found in $DestinationScripts"
    }
    @(
        "python312.zip",
        ".",
        "..\Lib\site-packages",
        "import site"
    ) | Set-Content -LiteralPath $Pth.FullName -Encoding ASCII
}

function Get-LocalPathLeakPatterns {
    $paths = New-Object System.Collections.Generic.List[string]
    $paths.Add((Resolve-Path $Root).Path)
    if ($env:USERPROFILE) {
        $paths.Add($env:USERPROFILE)
    }
    foreach ($cfg in @(
        (Join-Path $Root ".venv-densify\pyvenv.cfg")
    )) {
        if (-not (Test-Path $cfg)) {
            continue
        }
        foreach ($line in Get-Content -LiteralPath $cfg -ErrorAction SilentlyContinue) {
            if ($line -match '=\s*([A-Za-z]:\\.+)$') {
                $value = $Matches[1].Trim()
                if ($value) {
                    $paths.Add($value)
                    $parent = Split-Path -Parent $value -ErrorAction SilentlyContinue
                    if ($parent) {
                        $paths.Add($parent)
                    }
                }
            }
        }
    }
    $paths |
        Where-Object { $_ } |
        Select-Object -Unique |
        ForEach-Object { [regex]::Escape($_) }
}

function Test-DensifyRuntimePortability {
    param(
        [Parameter(Mandatory=$true)][string]$DestinationVenv
    )
    if (-not (Test-Path $DestinationVenv)) {
        return
    }
    $PyVenvCfg = Join-Path $DestinationVenv "pyvenv.cfg"
    if (Test-Path $PyVenvCfg) {
        throw "Densification runtime must not contain pyvenv.cfg because it can pin a local Python path: $PyVenvCfg"
    }
    $Pth = Get-ChildItem -LiteralPath (Join-Path $DestinationVenv "Scripts") -Filter "python*._pth" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $Pth) {
        throw "Densification runtime embedded Python _pth file is missing."
    }
    $PthText = Get-Content -LiteralPath $Pth.FullName -Raw
    if ($PthText -notmatch [regex]::Escape("..\Lib\site-packages")) {
        throw "Densification runtime _pth does not point to ..\Lib\site-packages."
    }
    $BadArtifacts = Get-ChildItem -LiteralPath $DestinationVenv -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Name -eq "__pycache__") -or
            (-not $_.PSIsContainer -and ($_.Extension.ToLowerInvariant() -in @(".pyc", ".pyo")))
        }
    if ($BadArtifacts) {
        $Examples = ($BadArtifacts | Select-Object -First 10 | ForEach-Object { $_.FullName }) -join "`n"
        throw "Densification runtime contains non-portable Python cache files:`n$Examples"
    }
}

function Get-ImportedDllNames {
    param(
        [Parameter(Mandatory=$true)][string]$BinaryPath
    )
    $Objdump = Get-Command llvm-objdump.exe -ErrorAction SilentlyContinue
    if (-not $Objdump) {
        $Objdump = Get-Command objdump.exe -ErrorAction SilentlyContinue
    }
    if (-not $Objdump) {
        return @()
    }
    $Output = & $Objdump.Source -p $BinaryPath 2>$null
    $Names = New-Object System.Collections.Generic.List[string]
    foreach ($line in $Output) {
        if ($line -match 'DLL\s+[Nn]ame:\s*(\S+\.dll)') {
            $Names.Add($Matches[1])
        }
    }
    $Names | Select-Object -Unique
}

function Test-WindowsSystemDllName {
    param(
        [Parameter(Mandatory=$true)][string]$Name
    )
    $Lower = $Name.ToLowerInvariant()
    if ($Lower.StartsWith("api-ms-") -or $Lower.StartsWith("ext-ms-")) {
        return $true
    }
    $SystemDlls = @(
        "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "comctl32.dll",
        "comdlg32.dll", "crypt32.dll", "dwmapi.dll", "gdi32.dll", "imm32.dll",
        "kernel32.dll", "msvcrt.dll", "ntdll.dll", "ole32.dll", "oleaut32.dll",
        "rpcrt4.dll", "secur32.dll", "shell32.dll", "shlwapi.dll", "user32.dll",
        "userenv.dll", "version.dll", "winhttp.dll", "winmm.dll", "ws2_32.dll"
    )
    return $SystemDlls -contains $Lower
}

function Get-ToolchainRuntimeSearchDirs {
    param(
        [Parameter(Mandatory=$true)][string]$SourceDir
    )
    $Dirs = New-Object System.Collections.Generic.List[string]
    $Dirs.Add($SourceDir)

    foreach ($tool in @("rustc.exe", "llvm-objdump.exe", "objdump.exe")) {
        $Command = Get-Command $tool -ErrorAction SilentlyContinue
        if ($Command -and $Command.Source) {
            $Dirs.Add((Split-Path -Parent $Command.Source))
        }
    }

    $WingetRoot = Join-Path $env:USERPROFILE "AppData\Local\Microsoft\WinGet\Packages"
    if (Test-Path $WingetRoot) {
        Get-ChildItem -LiteralPath $WingetRoot -Directory -Filter "MartinStorsjo.LLVM-MinGW*" -ErrorAction SilentlyContinue |
            ForEach-Object {
                Get-ChildItem -LiteralPath $_.FullName -Directory -Filter "llvm-mingw*" -ErrorAction SilentlyContinue |
                    ForEach-Object {
                        $Dirs.Add((Join-Path $_.FullName "bin"))
                        $Dirs.Add((Join-Path $_.FullName "x86_64-w64-mingw32\bin"))
                    }
            }
    }

    foreach ($dir in ($env:PATH -split ";")) {
        if (-not $dir -or $dir -match "(?i)android|andriod") {
            continue
        }
        try {
            if (Test-Path $dir) {
                $Dirs.Add($dir)
            }
        } catch {
        }
    }

    $Dirs.Add((Join-Path $Root "tools\colmap\bin"))
    $Dirs |
        Where-Object { $_ -and (Test-Path $_) } |
        ForEach-Object { [System.IO.Path]::GetFullPath($_).TrimEnd("\", "/") } |
        Select-Object -Unique
}

function Resolve-PortableRuntimeDll {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string[]]$SearchDirs
    )
    foreach ($dir in $SearchDirs) {
        $Candidate = Join-Path $dir $Name
        if (Test-Path $Candidate) {
            return (Resolve-Path $Candidate).Path
        }
    }
    return $null
}

function Deploy-WindowsRuntime {
    param([Parameter(Mandatory=$true)][string[]]$DestinationDirs)
    $Arguments = @(
        (Join-Path $Root "scripts\windows_runtime.py"),
        "deploy",
        "--root", $Root
    )
    foreach ($DestinationDir in $DestinationDirs) {
        $Arguments += @("--destination", $DestinationDir)
    }
    python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Bundled Windows runtime deployment failed." }
}

function Remove-ReleaseJunk {
    param(
        [Parameter(Mandatory=$true)][string]$RootDir
    )
    foreach ($dir in @(
        (Join-Path $RootDir "tools\colmap\_downloads")
    )) {
        if (Test-Path $dir) {
            Remove-Item -LiteralPath $dir -Recurse -Force
        }
    }

    foreach ($pattern in @("tools\colmap\bin\*_test.exe", "tools\colmap\plugins\*.pdb")) {
        Get-ChildItem -LiteralPath $RootDir -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object {
                $relative = $_.FullName.Substring([System.IO.Path]::GetFullPath($RootDir).TrimEnd("\", "/").Length).TrimStart("\", "/")
                $relative -like $pattern
            } |
            Remove-Item -Force
    }
}

function Copy-TauriRuntimeFiles {
    param(
        [Parameter(Mandatory=$true)][string]$SourceDir,
        [Parameter(Mandatory=$true)][string]$DestinationDir
    )
    $SearchDirs = @(Get-ToolchainRuntimeSearchDirs $SourceDir)
    $Required = New-Object System.Collections.Generic.List[string]
    $Required.Add("WebView2Loader.dll")
    foreach ($name in (Get-ImportedDllNames (Join-Path $DestinationDir "xPano.exe"))) {
        if (-not (Test-WindowsSystemDllName $name)) {
            $Required.Add($name)
        }
    }

    foreach ($name in @("libunwind.dll", "libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll")) {
        if (Resolve-PortableRuntimeDll $name $SearchDirs) {
            $Required.Add($name)
        }
    }

    $Copied = New-Object System.Collections.Generic.HashSet[string]
    $Queue = New-Object System.Collections.Generic.Queue[string]
    $Required | Select-Object -Unique | ForEach-Object { $Queue.Enqueue($_) }

    while ($Queue.Count -gt 0) {
        $Name = $Queue.Dequeue()
        if (Test-WindowsSystemDllName $Name) {
            continue
        }
        $LowerName = $Name.ToLowerInvariant()
        if ($Copied.Contains($LowerName)) {
            continue
        }
        $Source = Resolve-PortableRuntimeDll $Name $SearchDirs
        if (-not $Source) {
            throw "Required Tauri/runtime DLL is missing: $Name"
        }
        $Destination = Join-Path $DestinationDir $Name
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        [void]$Copied.Add($LowerName)

        foreach ($Imported in (Get-ImportedDllNames $Destination)) {
            if (-not (Test-WindowsSystemDllName $Imported)) {
                $Queue.Enqueue($Imported)
            }
        }
    }
}

function Test-PortableResourcePortability {
    param(
        [Parameter(Mandatory=$true)][string]$ResourceRoot
    )
    if (-not (Test-Path $ResourceRoot)) {
        return
    }
    $ForbiddenNames = @(".git", ".hg", ".svn", "__pycache__")
    $ForbiddenExtensions = @(".pyc", ".pyo")
    $Forbidden = @(Get-LocalPathLeakPatterns)
    $Pattern = ($Forbidden -join "|")

    $BadArtifacts = Get-ChildItem -LiteralPath $ResourceRoot -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object {
            ($ForbiddenNames -contains $_.Name) -or
            (-not $_.PSIsContainer -and ($ForbiddenExtensions -contains $_.Extension.ToLowerInvariant()))
        }
    if ($BadArtifacts) {
        $Examples = ($BadArtifacts | Select-Object -First 10 | ForEach-Object { $_.FullName }) -join "`n"
        throw "Portable resource contains non-portable cache/VCS files:`n$Examples"
    }

    $Files = Get-ChildItem -LiteralPath $ResourceRoot -Recurse -File -Include *.cfg,*.pth,*.txt,*.cmd,*.bat,*.ps1,*.py,*.json,*.md -ErrorAction SilentlyContinue
    $Leaks = $Files | Select-String -Pattern $Pattern -List -ErrorAction SilentlyContinue
    if ($Leaks) {
        $Examples = ($Leaks | Select-Object -First 10 | ForEach-Object { $_.Path }) -join "`n"
        throw "Portable resource contains local machine paths:`n$Examples"
    }
}

Write-Host "[1/8] Preparing release folder..."
if (Test-Path $ReleaseDir) {
    Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

if (-not $SkipTauriBuild) {
    Write-Host "[2/8] Building Tauri desktop application..."
    $UiDir = Join-Path $Root "xpano-ui"
    Push-Location $UiDir
    try {
        & pnpm.cmd install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) {
            throw "pnpm install failed with exit code $LASTEXITCODE"
        }
        & pnpm.cmd exec tauri build --no-bundle
        if ($LASTEXITCODE -ne 0) {
            throw "Tauri build failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
    $BuiltExe = Join-Path $UiDir "src-tauri\target\release\xPano.exe"
    if (-not (Test-Path $BuiltExe)) {
        $BuiltExe = Join-Path $UiDir "src-tauri\target\release\xpano-ui.exe"
    }
    if (-not (Test-Path $BuiltExe)) {
        throw "Tauri executable was not found under $UiDir\src-tauri\target\release"
    }
    Copy-Item -LiteralPath $BuiltExe -Destination (Join-Path $ReleaseDir "xPano.exe") -Force
    Copy-TauriRuntimeFiles (Split-Path -Parent $BuiltExe) $ReleaseDir
} else {
    Write-Host "[2/8] Skipping Tauri build."
    $BuiltExe = Join-Path $Root "xpano-ui\src-tauri\target\release\xPano.exe"
    if (-not (Test-Path $BuiltExe)) {
        $BuiltExe = Join-Path $Root "xpano-ui\src-tauri\target\release\xpano-ui.exe"
    }
    if (-not (Test-Path $BuiltExe)) {
        throw "Tauri executable was not found under $Root\xpano-ui\src-tauri\target\release. Build once without -SkipTauriBuild first."
    }
    Copy-Item -LiteralPath $BuiltExe -Destination (Join-Path $ReleaseDir "xPano.exe") -Force
    Copy-TauriRuntimeFiles (Split-Path -Parent $BuiltExe) $ReleaseDir
}

$Internal = $ReleaseDir

Write-Host "[4/8] Copying project modules and documentation..."
Copy-PortableDirectory (Join-Path $Root "scripts") (Join-Path $Internal "scripts") @("__pycache__") @(".pyc", ".pyo")
Copy-Directory (Join-Path $Root "images") (Join-Path $Internal "images")
Copy-PortableDirectory (Join-Path $Root "docs") (Join-Path $ReleaseDir "docs") @("__pycache__") @(".pyc", ".pyo")
Copy-FileIfExists (Join-Path $Root "README.md") (Join-Path $ReleaseDir "README.md")
Copy-FileIfExists (Join-Path $Root "README.zh-CN.md") (Join-Path $ReleaseDir "README.zh-CN.md")
Copy-FileIfExists (Join-Path $Root "LICENSE") (Join-Path $ReleaseDir "LICENSE")
Copy-FileIfExists (Join-Path $Root "requirements.txt") (Join-Path $ReleaseDir "requirements.txt")
Copy-FileIfExists (Join-Path $Root "metashape_requirements.txt") (Join-Path $ReleaseDir "metashape_requirements.txt")

Write-Host "[5/8] Copying bundled external tools..."
$EmbeddedPython = Join-Path $Root "binaries\python"
if (Test-Path (Join-Path $EmbeddedPython "python.exe")) {
    Copy-PortableDirectory $EmbeddedPython (Join-Path $Internal "binaries\python") @("__pycache__") @(".pyc", ".pyo")
} else {
    throw "Embedded Python is missing. Run scripts\install_embedded_python.ps1 before building an offline release."
}
Copy-Directory (Join-Path $Root "tools\colmap") (Join-Path $Internal "tools\colmap")
Deploy-WindowsRuntime @(
    (Join-Path $Internal "tools\colmap\bin"),
    (Join-Path $Internal "binaries\python")
)
Remove-ReleaseJunk $Internal
$OfflineWheels = Join-Path $Root "tools\offline-wheels"
if (Test-Path $OfflineWheels) {
    Copy-PortableDirectory $OfflineWheels (Join-Path $Internal "tools\offline-wheels") @("__pycache__") @(".pyc", ".pyo")
}
$PortableExcludeNames = @(".git", ".hg", ".svn", "__pycache__")
$PortableExcludeExtensions = @(".pyc", ".pyo")
Copy-PortableDirectory (Join-Path $Root "tools\lichtfeld-densification-plugin") (Join-Path $Internal "tools\lichtfeld-densification-plugin") $PortableExcludeNames $PortableExcludeExtensions
Copy-PortableDirectory (Join-Path $Root "tools\torch-cache") (Join-Path $Internal "tools\torch-cache") $PortableExcludeNames $PortableExcludeExtensions
Test-PortableResourcePortability (Join-Path $Internal "tools\lichtfeld-densification-plugin")
Test-PortableResourcePortability (Join-Path $Internal "tools\torch-cache")
$WebView2Source = Join-Path $Root "tools\webview2\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
if (Test-Path $WebView2Source) {
    Copy-FileIfExists $WebView2Source (Join-Path $Internal "tools\webview2\MicrosoftEdgeWebView2RuntimeInstallerX64.exe")
}

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
    Write-Host "[6/8] Copying LichtFeld densification dependency bundle..."
    $DensifyRuntime = Join-Path $Internal ".venv-densify"
    Copy-DensifyRuntime (Join-Path $Root ".venv-densify") $DensifyRuntime (Join-Path $Root "binaries\python")
    Test-DensifyRuntimePortability $DensifyRuntime
} else {
    Write-Host "[6/8] Skipping .venv-densify dependency copy."
}

Write-Host "[7/8] Writing release launchers..."
$DensifyReadmeLine = ""
if (-not $SkipDensifyVenv) {
    $DensifyReadmeLine = "- LichtFeld densification Python packages under .venv-densify\Lib\site-packages"
} else {
    $DensifyReadmeLine = "- LichtFeld densification Python runtime is not bundled. xPano will reuse an existing compatible Python/torch environment or configure one when network is available."
}
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

@(
    "# xPano Portable Release $Version"
    ""
    "Run RUN_XPANO.bat to start the GUI."
    "Run RUN_XPANO_DEBUG.bat if the GUI exits immediately and you need the console log."
    ""
    "Bundled:"
    "- Tauri GUI executable"
    "- WebView2Loader.dll and Rust/MinGW runtime DLLs next to xPano.exe"
    "- embedded Python under binaries\python"
    "- Python scripts under scripts"
    "- COLMAP under tools\colmap"
    "- ffmpeg/ffprobe under tools\ffmpeg"
    "- offline Python wheels under tools\offline-wheels"
    "- LichtFeld densification plugin under tools\lichtfeld-densification-plugin"
    "- RoMa/DINO model cache under tools\torch-cache"
    "- WebView2 Evergreen Standalone Installer under tools\webview2 when available"
    $DensifyReadmeLine
    ""
    "Offline-ready features:"
    "- GUI startup"
    "- OSV/INSV frame extraction"
    "- COLMAP backend"
    "- point cloud preview"
    "- Metashape backend when the target PC already has licensed Metashape installed"
    ""
    "The light package does not bundle the full torch/Open3D densification runtime."
    "Use the full package for fully offline LichtFeld densification, or let xPano"
    "configure/reuse a compatible densification environment when network is available."
    "For the light package, one-click densification setup requires Python 3.10-3.12"
    "with venv support on the target PC. The bundled app Python is an embeddable"
    "runtime for xPano scripts and does not include pip/venv."
    ""
    "Metashape backend still requires a local Metashape installation. Put metashape.exe"
    "on PATH or set XPANO_METASHAPE to the full executable path. xPano installs the"
    "required Metashape Python packages into tools\metashape-python and injects that"
    "path at runtime, so it does not need to modify the Metashape installation folder."
) | Set-Content -LiteralPath (Join-Path $ReleaseDir "RELEASE_README.md") -Encoding UTF8

Write-Host "[8/8] Release ready:"
Write-Host $ReleaseDir
