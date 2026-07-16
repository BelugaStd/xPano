param(
    [string]$FfmpegExe = "",
    [string]$FfprobeExe = "",
    [switch]$SkipVerification,
    [switch]$DevelopmentBuild
)

$ErrorActionPreference = "Stop"
$builder = Join-Path $PSScriptRoot "build_installer.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $builder `
    -FfmpegExe $FfmpegExe `
    -FfprobeExe $FfprobeExe `
    -SkipVerification:$SkipVerification `
    -DevelopmentBuild:$DevelopmentBuild
exit $LASTEXITCODE
