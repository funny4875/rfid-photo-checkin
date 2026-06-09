param(
    [string]$RepoRoot,
    [string]$RepoUrl = "https://github.com/funny4875/rfid-photo-checkin.git",
    [string]$OwnerRepo = "funny4875/rfid-photo-checkin",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

function Show-Question($message, $title) {
    Add-Type -AssemblyName PresentationFramework
    $result = [System.Windows.MessageBox]::Show(
        $message,
        $title,
        [System.Windows.MessageBoxButton]::YesNo,
        [System.Windows.MessageBoxImage]::Question
    )
    return $result -eq [System.Windows.MessageBoxResult]::Yes
}

function Show-Info($message, $title = "RFID Photo Check-in") {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        $message,
        $title,
        [System.Windows.MessageBoxButton]::OK,
        [System.Windows.MessageBoxImage]::Information
    ) | Out-Null
}

function Get-LocalVersion {
    $versionPath = Join-Path $RepoRoot "VERSION"
    if (Test-Path -LiteralPath $versionPath) {
        return (Get-Content -LiteralPath $versionPath -Raw).Trim()
    }
    return "0.0.0"
}

function Get-RemoteVersion {
    param([string]$OwnerRepo, [string]$Branch)
    $versionUrl = "https://raw.githubusercontent.com/$OwnerRepo/$Branch/VERSION"
    try {
        return (Invoke-RestMethod -Uri $versionUrl -Headers @{ "User-Agent" = "rfid-photo-checkin-updater" } -TimeoutSec 8).Trim()
    }
    catch {
        return ""
    }
}

function Write-UpdateHeader {
    param([string]$LocalVersion)
    Write-Host "連至 GitHub 檢查版本是否為最新..."
    Write-Host ("GitHub repo: https://github.com/" + $OwnerRepo + "/")
    Write-Host "目前版本為：$LocalVersion"
}

function Write-RemoteVersion {
    param([string]$RemoteVersion)
    if ($RemoteVersion) {
        Write-Host "GitHub 版本為：$RemoteVersion"
    }
    else {
        Write-Host "GitHub 版本為：無法讀取"
    }
}

function Test-GitAvailable {
    $null = Get-Command git -ErrorAction SilentlyContinue
    return $null -ne $false
}

function Update-WithGit {
    Push-Location $RepoRoot
    $protectedFiles = @("server/場域對應.txt")
    $protectedBackupDir = Join-Path ([System.IO.Path]::GetTempPath()) ("rfid-photo-checkin-protected-" + [guid]::NewGuid().ToString("N"))
    try {
        $localVersion = Get-LocalVersion
        Write-UpdateHeader -LocalVersion $localVersion

        git remote get-url origin 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            git remote add origin $RepoUrl
        }

        git fetch origin $Branch --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Host "GitHub 檢查結果：git 讀取失敗，改用下載檢查。"
            return $false
        }

        $remoteVersion = Get-RemoteVersion -OwnerRepo $OwnerRepo -Branch $Branch
        Write-RemoteVersion -RemoteVersion $remoteVersion
        $local = (git rev-parse HEAD).Trim()
        $remote = (git rev-parse "origin/$Branch").Trim()
        if ($local -eq $remote) {
            if ($remoteVersion -and $localVersion -ne $remoteVersion) {
                Write-Host "GitHub 檢查結果：程式碼已同步，但本機版本檔與 GitHub 版本不一致。"
            }
            else {
                Write-Host "GitHub 檢查結果：目前已是最新版本。"
            }
            return $true
        }

        git merge-base --is-ancestor HEAD "origin/$Branch"
        if ($LASTEXITCODE -ne 0) {
            Show-Info "GitHub 有新版，但本機版本包含不同變更，無法自動更新。請手動備份後再處理。" "無法自動更新"
            return $true
        }

        $versionText = if ($remoteVersion) { "目前版本：$localVersion`nGitHub 版本：$remoteVersion`n`n" } else { "目前版本：$localVersion`n`n" }
        $yes = Show-Question "GitHub 有新版，是否立即更新？`n`n$versionText更新會保留 student_data、照片、門禁紀錄與 client 設定。" "發現新版本"
        if (-not $yes) {
            return $true
        }

        New-Item -ItemType Directory -Path $protectedBackupDir -Force | Out-Null
        foreach ($relative in $protectedFiles) {
            $source = Join-Path $RepoRoot $relative
            if (Test-Path -LiteralPath $source) {
                $backup = Join-Path $protectedBackupDir $relative
                New-Item -ItemType Directory -Path (Split-Path $backup -Parent) -Force | Out-Null
                Copy-Item -LiteralPath $source -Destination $backup -Force
                git checkout -- $relative 2>&1 | Out-Null
            }
        }

        git pull --ff-only origin $Branch
        if ($LASTEXITCODE -ne 0) {
            Show-Info "更新失敗，請稍後再試或手動執行 git pull。" "更新失敗"
            return $true
        }

        foreach ($relative in $protectedFiles) {
            $backup = Join-Path $protectedBackupDir $relative
            if (Test-Path -LiteralPath $backup) {
                $destination = Join-Path $RepoRoot $relative
                New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
                Copy-Item -LiteralPath $backup -Destination $destination -Force
            }
        }

        Show-Info "已更新到 GitHub 最新版本。請重新執行啟動檔。" "更新完成"
        exit 10
    }
    finally {
        Remove-Item -LiteralPath $protectedBackupDir -Recurse -Force -ErrorAction SilentlyContinue
        Pop-Location
    }
}

function Should-SkipRelativePath($relativePath) {
    $p = $relativePath -replace "\\", "/"
    if ($p -eq ".git" -or $p.StartsWith(".git/")) { return $true }
    if ($p -eq ".github_version") { return $true }
    if ($p -eq "server/student_data.txt") { return $true }
    if ($p -eq "server/場域對應.txt") { return $true }
    if ($p -eq "client/config.txt") { return $true }
    if ($p -eq "server/ccsh_data" -or $p.StartsWith("server/ccsh_data/")) { return $true }
    if ($p -eq "server/backups" -or $p.StartsWith("server/backups/")) { return $true }
    if ($p -match '^server/[0-9]{4}(/|$)') { return $true }
    if ($p -match '^server/門禁記錄.*\.txt$') { return $true }
    if ($p -match '^server/.*\.log$') { return $true }
    if ($p -match '^server/(preview|admin_check)\.') { return $true }
    if ($p -match '(^|/)__pycache__(/|$)') { return $true }
    if ($p -match '\.pyc$') { return $true }
    if ($p -match '^(rfid_fullscreen_preview|admin_student_import_check).*\.png$') { return $true }
    return $false
}

function Copy-UpdateFiles($sourceRoot, $targetRoot) {
    Get-ChildItem -LiteralPath $sourceRoot -Recurse -Force | ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath($sourceRoot, $_.FullName)
        if (Should-SkipRelativePath $relative) {
            return
        }

        $destination = Join-Path $targetRoot $relative
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
        }
        else {
            New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
        }
    }
}

function Update-WithZip {
    $tempDir = $null
    $localVersion = Get-LocalVersion
    Write-UpdateHeader -LocalVersion $localVersion
    $latestVersion = Get-RemoteVersion -OwnerRepo $OwnerRepo -Branch $Branch
    Write-RemoteVersion -RemoteVersion $latestVersion
    if (-not $latestVersion) {
        Write-Host "GitHub 檢查結果：無法讀取 GitHub 版本，略過更新。"
        return
    }
    $versionPath = Join-Path $RepoRoot ".github_version"
    $currentSha = if (Test-Path $versionPath) { (Get-Content $versionPath -Raw).Trim() } else { "" }

    if ($currentSha -eq $latestVersion -or $localVersion -eq $latestVersion) {
        Write-Host "GitHub 檢查結果：目前已是最新版本。"
        return
    }

    $yes = Show-Question "GitHub 有新版，是否下載並更新？`n`n目前版本：$localVersion`nGitHub 版本：$latestVersion`n`n更新會保留 student_data、照片、門禁紀錄與 client 設定。" "發現新版本"
    if (-not $yes) {
        return
    }

    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("rfid-photo-checkin-update-" + [guid]::NewGuid().ToString("N"))
    $zipPath = Join-Path $tempDir "source.zip"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    try {
        Invoke-WebRequest -Uri "https://github.com/$OwnerRepo/archive/refs/heads/$Branch.zip" -OutFile $zipPath -TimeoutSec 30
        Expand-Archive -LiteralPath $zipPath -DestinationPath $tempDir -Force
        $sourceRoot = Get-ChildItem -LiteralPath $tempDir -Directory | Where-Object { $_.Name -like "rfid-photo-checkin-*" } | Select-Object -First 1
        if (-not $sourceRoot) {
            throw "找不到下載後的專案資料夾"
        }
        Copy-UpdateFiles $sourceRoot.FullName $RepoRoot
        Set-Content -Path $versionPath -Value $latestVersion -Encoding UTF8
        Show-Info "已下載並更新到 GitHub 最新版本。請重新執行啟動檔。" "更新完成"
        exit 10
    }
    finally {
        if ($tempDir) {
            Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

try {
    if (-not $RepoRoot) {
        $RepoRoot = Split-Path -Parent $PSScriptRoot
    }
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

    $gitDir = Join-Path $RepoRoot ".git"
    if ((Test-Path $gitDir) -and (Get-Command git -ErrorAction SilentlyContinue)) {
        Update-WithGit | Out-Null
    }
    else {
        Update-WithZip
    }
}
catch {
    # Startup should not fail only because update checks are temporarily unavailable.
    Write-Host "GitHub update check skipped: $($_.Exception.Message)"
}
