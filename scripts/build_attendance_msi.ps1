param([string]$OutputDir = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$version = (Get-Content -LiteralPath (Join-Path $root "VERSION") -Raw).Trim()
if (-not $OutputDir) { $OutputDir = Join-Path $root "dist" }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$buildDir = Join-Path $root "build\attendance-query"
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
& pyinstaller --noconfirm --clean --onefile --windowed --name AttendanceQuery --distpath $buildDir --workpath (Join-Path $buildDir "work") --specpath $buildDir (Join-Path $root "client\attendance_query.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
$exe = Join-Path $buildDir "AttendanceQuery.exe"
$msi = Join-Path $OutputDir "AttendanceQuery-$version.msi"
& wix build (Join-Path $root "installer\attendance_query.wxs") -d "ExePath=$exe" -d "Version=$version" -o $msi
if ($LASTEXITCODE -ne 0) { throw "WiX build failed" }
Write-Host "Installer: $msi"
