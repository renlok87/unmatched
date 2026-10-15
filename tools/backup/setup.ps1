[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [string]$StateDir = (Join-Path $env:USERPROFILE '.unmatched-backup'),
    [switch]$RegisterTasks
)
$ErrorActionPreference = 'Stop'
# Packaged desktop apps can virtualize AppData for their child processes.
# A profile directory is also visible to the Windows Task Scheduler.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
if (-not $ProjectRoot) { $ProjectRoot = (Join-Path $PSScriptRoot '..\..') }
$StateDir = [IO.Path]::GetFullPath($StateDir)
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
[void][IO.Directory]::CreateDirectory($StateDir)
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetOwner($identity.User)
$acl.SetAccessRuleProtection($true, $false)
foreach ($sid in @($identity.User, (New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $StateDir -AclObject $acl
$utf8 = New-Object Text.UTF8Encoding($false)
foreach ($directory in @('bin', 'downloads', 'logs')) {
    [void][IO.Directory]::CreateDirectory((Join-Path $StateDir $directory))
}

# Official HTTPS releases only; verify the vendor's published SHA256 before use.
$packages = @(
    @{name = 'restic'; archive = 'restic_0.19.1_windows_amd64.zip'; base = 'https://github.com/restic/restic/releases/download/v0.19.1/'},
    @{name = 'rclone'; archive = 'rclone-v1.75.2-windows-amd64.zip'; base = 'https://github.com/rclone/rclone/releases/download/v1.75.2/'}
)
foreach ($package in $packages) {
    $exe = Join-Path $StateDir ('bin\' + $package.name + '.exe')
    if (Test-Path -LiteralPath $exe) { continue }
    $zip = Join-Path $StateDir ('downloads\' + $package.archive)
    Invoke-WebRequest ($package.base + $package.archive) -OutFile $zip -UseBasicParsing
    $sums = (Invoke-WebRequest ($package.base + 'SHA256SUMS') -UseBasicParsing).Content
    if ($sums -is [byte[]]) { $sums = [Text.Encoding]::UTF8.GetString($sums) }
    $lines = @($sums -split "`n" | Where-Object { $_ -match ([regex]::Escape($package.archive) + '$') })
    if ($lines.Count -ne 1) { throw 'Missing unique release checksum.' }
    $expected = ($lines[0].Trim() -split '\s+')[0]
    if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ine $expected) {
        throw 'Release checksum mismatch; installation stopped.'
    }
    $extract = Join-Path $StateDir ('downloads\extract-' + [Guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $zip -DestinationPath $extract
    $found = @(Get-ChildItem -LiteralPath $extract -Recurse -Filter ($package.name + '*.exe'))
    if ($found.Count -ne 1) { throw 'Unexpected release executable count.' }
    Copy-Item -LiteralPath $found[0].FullName -Destination $exe
}

$settingsPath = Join-Path $StateDir 'settings.json'
if (-not (Test-Path -LiteralPath $settingsPath)) {
    $settings = [ordered]@{
        project_root = $ProjectRoot
        repository = 'rclone:unmatched-gdrive:Unmatched-Backups/Assets'
        tag = 'unmatched-assets'
        restic_exe = (Join-Path $StateDir 'bin\restic.exe')
        rclone_exe = (Join-Path $StateDir 'bin\rclone.exe')
        use_vss = $true
    }
    [IO.File]::WriteAllText($settingsPath, ($settings | ConvertTo-Json), $utf8)
} else {
    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    if ($settings.project_root -ne $ProjectRoot) { throw 'Existing settings belong to a different project.' }
}
# Run a stable local copy: changing branches or moving a worktree cannot break tasks.
foreach ($file in @('backup.ps1', 'policy.json', 'README.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $StateDir $file) -Force
}

if ($RegisterTasks) {
    if (-not $settings.PSObject.Properties['repository_id'] -or -not $settings.repository_id) {
        throw 'Initialize and verify the repository before enabling scheduled tasks.'
    }
    Import-Module ScheduledTasks -ErrorAction Stop
    $shell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $runner = Join-Path $StateDir 'backup.ps1'
    $principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Highest
    $taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 15) -ExecutionTimeLimit (New-TimeSpan -Days 3)
    $backupAction = New-ScheduledTaskAction -Execute $shell -Argument `
        ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Action Backup -StateDir "{1}"' -f $runner, $StateDir)
    $interval = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 1)
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
    Register-ScheduledTask -TaskName 'Unmatched-Assets-Backup' -Action $backupAction -Trigger @($interval, $logon) `
        -Principal $principal -Settings $taskSettings -Description 'Encrypted hourly restic backup of project assets to Google Drive.' -Force | Out-Null
    $maintenanceAction = New-ScheduledTaskAction -Execute $shell -Argument `
        ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Action Maintain -StateDir "{1}"' -f $runner, $StateDir)
    $daily = New-ScheduledTaskTrigger -Daily -At '03:30'
    Register-ScheduledTask -TaskName 'Unmatched-Assets-Maintenance' -Action $maintenanceAction -Trigger $daily `
        -Principal $principal -Settings $taskSettings -Description 'Check backup data and keep 24 recent, 14 daily, 8 weekly and 12 monthly restore points.' -Force | Out-Null
    Write-Output 'Scheduled hourly backup and daily maintenance for the current signed-in Windows user.'
}
Write-Output ('Backup files installed in ' + $StateDir)
