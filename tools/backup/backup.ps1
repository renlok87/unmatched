[CmdletBinding()]
param(
    [ValidateSet('Initialize', 'Backup', 'Check', 'Maintain', 'Snapshots', 'Restore', 'Status')]
    [string]$Action = 'Backup',
    [string]$StateDir = (Join-Path $env:USERPROFILE '.unmatched-backup'),
    [string]$Snapshot = 'latest',
    [string]$Target,
    [string[]]$Include,
    [switch]$DryRun,
    [switch]$ReadAllData
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
# A Python/Codex parent can pass PS7's module path to Windows PowerShell 5.
# Select its inbox security module explicitly, without changing user settings.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
$StateDir = [IO.Path]::GetFullPath($StateDir)
$utf8 = New-Object Text.UTF8Encoding($false)
$lockHandle = $null
$exitCode = 0
$savedEnvironment = @{}

function Save-Json($Value, [string]$Path) {
    $temporary = $Path + '.new'
    [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 12), $utf8)
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Invoke-Restic([string[]]$Arguments) {
    $script:commandNumber++
    $script:stdoutPath = Join-Path $logDir ('{0:D2}.out.log' -f $script:commandNumber)
    $script:stderrPath = Join-Path $logDir ('{0:D2}.err.log' -f $script:commandNumber)
    # restic parses this option as a command line: backslashes are escapes.
    # Forward slashes plus single quotes preserve Windows paths with spaces.
    $rcloneProgram = "'" + $settings.rclone_exe.Replace('\', '/').Replace("'", "'\''") + "'"
    $common = @('--repo', $settings.repository, '--cache-dir', (Join-Path $StateDir 'cache'),
        '--retry-lock', '1m', '-o', ('rclone.program=' + $rcloneProgram))
    # Redirection streams output to disk. Exit 3 (partial backup) remains a failure.
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $settings.restic_exe @common @Arguments 1> $script:stdoutPath 2> $script:stderrPath
        $script:nativeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $oldPreference }
    if ($script:nativeExit -ne 0) {
        throw ('restic {0} exited {1}; see {2}' -f $Arguments[0], $script:nativeExit, $script:stderrPath)
    }
}

function Assert-Repository {
    if (-not $settings.PSObject.Properties['repository_id'] -or -not $settings.repository_id) {
        throw 'Repository is not initialized. Run Initialize first.'
    }
    Invoke-Restic @('cat', 'config')
    $actual = Get-Content -LiteralPath $script:stdoutPath -Raw | ConvertFrom-Json
    if ($actual.id -ne $settings.repository_id) { throw 'Repository identity changed; refusing to continue.' }
}

try {
    if ($Action -eq 'Status') {
        Get-Content -LiteralPath (Join-Path $StateDir 'status.json') -Raw
        exit 0
    }
    if (-not (Test-Path -LiteralPath (Join-Path $StateDir 'settings.json'))) {
        throw 'Missing local settings.json. Run setup.ps1 first.'
    }
    # An open file handle, rather than a stale PID file, serializes all sessions.
    try {
        $lockHandle = [IO.File]::Open((Join-Path $StateDir 'run.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    } catch [IO.IOException] {
        Write-Output 'Another backup operation is running; this invocation was skipped.'
        exit 75
    }
    $settings = Get-Content -LiteralPath (Join-Path $StateDir 'settings.json') -Raw | ConvertFrom-Json
    $policy = Get-Content -LiteralPath (Join-Path $StateDir 'policy.json') -Raw | ConvertFrom-Json
    foreach ($exe in @($settings.restic_exe, $settings.rclone_exe)) {
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw ('Missing executable: ' + $exe) }
    }
    if (-not (Test-Path -LiteralPath $settings.project_root -PathType Container)) {
        throw 'The source project is unavailable; refusing an empty backup.'
    }
    $statusPath = Join-Path $StateDir 'status.json'
    $status = @{state = 'running'; action = $Action; started_at = (Get-Date).ToString('o'); pid = $PID}
    if (Test-Path -LiteralPath $statusPath) {
        $previous = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
        foreach ($name in @('last_backup', 'last_check', 'last_maintenance')) {
            if ($previous.PSObject.Properties[$name]) { $status[$name] = $previous.$name }
        }
    }
    $logDir = Join-Path $StateDir ('logs\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + $Action)
    [void][IO.Directory]::CreateDirectory($logDir)
    $status.log_directory = $logDir
    Save-Json $status $statusPath
    $commandNumber = 0

    $passwordPath = Join-Path $StateDir 'password.dpapi'
    if (-not (Test-Path -LiteralPath $passwordPath)) {
        if ($Action -ne 'Initialize') { throw 'Missing repository password; refusing to generate a replacement.' }
        $random = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($random) } finally { $rng.Dispose() }
        $password = [Convert]::ToBase64String($random)
        $secure = ConvertTo-SecureString $password -AsPlainText -Force
        [IO.File]::WriteAllText($passwordPath, ($secure | ConvertFrom-SecureString), $utf8)
        $recovery = "RESTIC BACKUP RECOVERY - KEEP OUTSIDE THIS COMPUTER`r`n" +
            "Repository: $($settings.repository)`r`nPassword: $password`r`n`r`n" +
            "Keep this file in your password manager or on an offline device.`r`n" +
            "DPAPI files alone cannot recover backups after losing this Windows account.`r`n" +
            "Install restic/rclone, authorize Google Drive, then use this password to restore.`r`n"
        [IO.File]::WriteAllText((Join-Path $StateDir 'RECOVERY-KEY.txt'), $recovery, $utf8)
        $password = $null
        $recovery = $null
    }
    $secure = Get-Content -LiteralPath $passwordPath -Raw | ConvertTo-SecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    foreach ($name in @('RESTIC_PASSWORD', 'RCLONE_CONFIG', 'GOMAXPROCS', 'RCLONE_TPSLIMIT')) {
        $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    try { $env:RESTIC_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $env:RCLONE_CONFIG = Join-Path $StateDir 'rclone.conf'
    $env:GOMAXPROCS = '2'
    $env:RCLONE_TPSLIMIT = '8'

    if ($Action -eq 'Initialize') {
        if ($settings.PSObject.Properties['repository_id'] -and $settings.repository_id) {
            Assert-Repository
        } else {
            Invoke-Restic @('init')
            Invoke-Restic @('cat', 'config')
            $repositoryConfig = Get-Content -LiteralPath $stdoutPath -Raw | ConvertFrom-Json
            $settings | Add-Member -MemberType NoteProperty -Name repository_id -Value $repositoryConfig.id -Force
            Save-Json $settings (Join-Path $StateDir 'settings.json')
        }
    } else {
        Assert-Repository
        switch ($Action) {
            'Backup' {
                $sourceRoot = [IO.Path]::GetFullPath($settings.project_root).TrimEnd('\', '/')
                $patterns = @($policy.exclude_names) + @($policy.exclude_file_patterns)
                foreach ($relative in $policy.exclude_relative_paths) {
                    $patterns += ($sourceRoot.Replace('\', '/') + '/' + $relative)
                }
                $excludeFile = Join-Path $logDir 'excludes.txt'
                [IO.File]::WriteAllLines($excludeFile, [string[]]$patterns, $utf8)
                $arguments = @('backup', '--json', '--host', [Environment]::MachineName, '--tag', $settings.tag,
                    '--iexclude-file', $excludeFile, '--read-concurrency', '2')
                $vss = $false
                $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
                if ($settings.use_vss -and $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
                    $arguments += '--use-fs-snapshot'
                    $vss = $true
                }
                if ($DryRun) { $arguments += '--dry-run' }
                $arguments += $sourceRoot
                Invoke-Restic $arguments
                $summary = @(Get-Content -LiteralPath $stdoutPath | ForEach-Object {
                    $entry = $_ | ConvertFrom-Json
                    if ($entry.message_type -eq 'summary') { $entry }
                }) | Select-Object -Last 1
                if (-not $summary) { throw 'Backup did not produce a summary.' }
                if (-not $DryRun) {
                    if (-not $summary.snapshot_id -or $summary.total_files_processed -lt 1) {
                        throw 'Backup produced no usable snapshot.'
                    }
                    $status.last_backup = @{snapshot_id = $summary.snapshot_id;
                        completed_at = (Get-Date).ToString('o'); files = $summary.total_files_processed;
                        bytes = $summary.total_bytes_processed; data_added = $summary.data_added; vss = $vss}
                    Save-Json $status.last_backup (Join-Path $StateDir 'last-success.json')
                }
            }
            'Snapshots' {
                Invoke-Restic @('snapshots', '--tag', $settings.tag, '--json')
                Get-Content -LiteralPath $stdoutPath -Raw | Write-Output
            }
            'Restore' {
                if (-not $Target) { throw 'Specify a new, empty restore target with -Target.' }
                $destination = [IO.Path]::GetFullPath($Target)
                $live = [IO.Path]::GetFullPath($settings.project_root).TrimEnd('\')
                if ($destination -eq $live -or $destination.StartsWith($live + '\', [StringComparison]::OrdinalIgnoreCase)) {
                    throw 'Restore target must be outside the live project.'
                }
                if ((Test-Path -LiteralPath $destination) -and @(Get-ChildItem -LiteralPath $destination -Force).Count) {
                    throw 'Restore target must be empty.'
                }
                $arguments = @('restore', $Snapshot, '--tag', $settings.tag, '--target', $destination, '--verify')
                foreach ($item in $Include) { $arguments += @('--include', $item) }
                Invoke-Restic $arguments
            }
            'Check' {
                $arguments = @('check')
                if ($ReadAllData) { $arguments += '--read-data' }
                Invoke-Restic $arguments
                $status.last_check = @{completed_at = (Get-Date).ToString('o'); all_data = [bool]$ReadAllData}
            }
            'Maintain' {
                $part = ((Get-Date).DayOfYear % 30) + 1
                Invoke-Restic @('check', '--read-data-subset', "$part/30")
                $keep = $policy.retention
                Invoke-Restic @('forget', '--tag', $settings.tag, '--group-by', 'host,paths,tags',
                    '--keep-last', [string]$keep.last, '--keep-daily', [string]$keep.daily,
                    '--keep-weekly', [string]$keep.weekly, '--keep-monthly', [string]$keep.monthly, '--prune')
                $status.last_maintenance = @{completed_at = (Get-Date).ToString('o'); data_subset = "$part/30"}
            }
        }
    }
    $status.state = 'succeeded'
    $status.completed_at = (Get-Date).ToString('o')
    Save-Json $status $statusPath
    Write-Output ("{0} succeeded. Status: {1}" -f $Action, $statusPath)
} catch {
    $exitCode = 1
    if (Get-Variable status -ErrorAction SilentlyContinue) {
        $status.state = 'failed'
        $status.error = $_.Exception.Message
        $status.completed_at = (Get-Date).ToString('o')
        Save-Json $status $statusPath
    }
    [Console]::Error.WriteLine($_.Exception.Message)
} finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    if ($lockHandle) { $lockHandle.Dispose() }
}
exit $exitCode
