[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'profiles.json')
)

$ErrorActionPreference = 'Stop'
$dataRoot = Join-Path $env:LOCALAPPDATA 'SaveHarbor'
$logRoot = Join-Path $dataRoot 'Pro\logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$logPath = Join-Path $logRoot ("scheduled-{0}.log" -f (Get-Date -Format 'yyyy-MM-dd'))

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    Write-Output $line
}

function Get-ProfileSlug([string]$Name) {
    $slug = [regex]::Replace($Name.Trim(), '[^A-Za-z0-9._-]+', '-').Trim('.-_')
    if ([string]::IsNullOrWhiteSpace($slug)) { throw "Profile name has no usable characters: $Name" }
    if ($slug.Length -gt 80) { $slug = $slug.Substring(0, 80) }
    return $slug
}

try {
    $config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $config.Python) { throw 'Set Python to the full path of python.exe in profiles.json.' }
    if (-not (Test-Path -LiteralPath $config.Python -PathType Leaf)) { throw "Python executable not found: $($config.Python)" }
    if (-not $config.Profiles -or $config.Profiles.Count -eq 0) { throw 'Add at least one profile to profiles.json.' }
    $backupRoot = Join-Path $dataRoot 'backups'
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    $backupRoot = (Resolve-Path -LiteralPath $backupRoot).Path.TrimEnd('\')
    $failures = 0

    foreach ($profile in $config.Profiles) {
        try {
            if ([string]::IsNullOrWhiteSpace([string]$profile.Name) -or [string]::IsNullOrWhiteSpace([string]$profile.Folder)) {
                throw 'Each profile needs a Name and Folder.'
            }
            $folder = [Environment]::ExpandEnvironmentVariables([string]$profile.Folder)
            if (-not (Test-Path -LiteralPath $folder -PathType Container)) { throw "Save folder not found: $folder" }
            $keepLast = [int]$profile.KeepLast
            if ($keepLast -lt 2 -or $keepLast -gt 365) { throw 'KeepLast must be between 2 and 365.' }
            Write-Log "Starting '$($profile.Name)' from $folder"
            $backupOutput = & $config.Python -m saveharbor backup $folder ([string]$profile.Name) 2>&1
            $backupExit = $LASTEXITCODE
            $backupOutput | ForEach-Object { Write-Log ([string]$_) }
            if ($backupExit -ne 0) { throw "SaveHarbor backup returned exit code $backupExit." }
            $archiveLine = $backupOutput | Where-Object { [string]$_ -match '^Snapshot created: ' } | Select-Object -Last 1
            if (-not $archiveLine) { throw 'Could not locate the new archive path in SaveHarbor output.' }
            $archivePath = ([string]$archiveLine) -replace '^Snapshot created: ', ''
            if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) { throw "New archive was not found: $archivePath" }
            $verifyOutput = & $config.Python -m saveharbor verify $archivePath 2>&1
            $verifyExit = $LASTEXITCODE
            $verifyOutput | ForEach-Object { Write-Log ([string]$_) }
            if ($verifyExit -ne 0) { throw "SaveHarbor verification returned exit code $verifyExit; retention cleanup was skipped." }

            $profileBackup = Join-Path $backupRoot (Get-ProfileSlug ([string]$profile.Name))
            $resolvedProfileBackup = (Resolve-Path -LiteralPath $profileBackup).Path
            if (-not $resolvedProfileBackup.StartsWith($backupRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing retention outside the configured backup folder: $resolvedProfileBackup"
            }
            $archives = @(Get-ChildItem -LiteralPath $resolvedProfileBackup -File -Filter '*.saveharbor.zip' | Sort-Object LastWriteTime -Descending)
            $oldArchives = @($archives | Select-Object -Skip $keepLast)
            foreach ($oldArchive in $oldArchives) {
                $resolvedArchive = $oldArchive.FullName
                if (-not $resolvedArchive.StartsWith($resolvedProfileBackup + '\', [StringComparison]::OrdinalIgnoreCase)) {
                    throw "Refusing to remove a path outside the profile archive folder: $resolvedArchive"
                }
                Remove-Item -LiteralPath $resolvedArchive -Force
                Write-Log "Retention removed old snapshot: $($oldArchive.Name)"
            }
            Write-Log "Completed '$($profile.Name)'; retained $([Math]::Min($keepLast, $archives.Count)) snapshot(s)."
        }
        catch {
            $failures++
            Write-Log "FAILED '$($profile.Name)': $($_.Exception.Message)"
        }
    }
    if ($failures -gt 0) { exit 1 }
    exit 0
}
catch {
    Write-Log "FAILED: $($_.Exception.Message)"
    exit 1
}
