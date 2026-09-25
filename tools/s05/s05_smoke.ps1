param([int]$TimeoutSeconds = 90, [switch]$SelfTest)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$work = "$root/unreal/Unmatched"
$exe = "$work/Artifacts/S05/Windows/Unmatched/Binaries/Win64/Unmatched.exe"
$log = "$work/s05-runtime-output.txt"
$shots = "$work/Artifacts/S05/Windows/Unmatched/Saved/Screenshots/Windows"
$evidence = "$root/docs/game-design/evidence/S05/art-references/frames"
. "$PSScriptRoot/s05_validate.ps1"

# ---------------------------------------------------------------------------
# Atomic evidence publication (P2 2026-09-25): the three frame-K*.png copies and
# the run-summary.json write are one transaction. Before the first write the
# exact four prior files are backed up to a task-scoped temp dir together with
# their per-file existence state. On ANY publication exception the prior files
# are restored byte-for-byte (newly created files whose prior counterpart was
# absent are removed) and the exception is rethrown. Rollback only ever touches
# the exact backed-up paths, and only after asserting each one resolves inside
# the evidence root - no wildcard or recursive target deletion.
# ---------------------------------------------------------------------------

function Assert-S05PathInside([string]$Path, [string]$RootDir) {
    $full = [IO.Path]::GetFullPath($Path)
    $rootFull = [IO.Path]::GetFullPath($RootDir).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing evidence rollback: '$full' resolves outside evidence root '$RootDir'"
    }
}

function Restore-S05Evidence($State, [string]$BackupDir, [string]$EvidenceRoot) {
    foreach ($t in @($State.Keys)) { Assert-S05PathInside $t $EvidenceRoot }
    foreach ($t in @($State.Keys)) {
        $full = [IO.Path]::GetFullPath($t)
        if ($State[$t]) {
            Copy-Item -LiteralPath (Join-Path $BackupDir (Split-Path $t -Leaf)) -Destination $full -Force
        } elseif (Test-Path -LiteralPath $full) {
            Remove-Item -LiteralPath $full -Force
        }
    }
}

function Publish-S05Evidence {
    param(
        [Parameter(Mandatory = $true)][string[]]$StagedFiles,
        [Parameter(Mandatory = $true)][string[]]$TargetFiles,
        [Parameter(Mandatory = $true)][string]$SummaryPath,
        [Parameter(Mandatory = $true)][string]$SummaryJson,
        [Parameter(Mandatory = $true)][string]$EvidenceRoot,
        [int]$FaultAfterStep = 0
    )
    if ($StagedFiles.Count -ne $TargetFiles.Count) { throw 'Publish-S05Evidence: staged/target count mismatch' }
    $targets = @($TargetFiles) + @($SummaryPath)
    $backupDir = Join-Path ([IO.Path]::GetTempPath()) ('s05-evidence-bak-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $prior = @{}
    try {
        foreach ($t in $targets) {
            $prior[$t] = Test-Path -LiteralPath $t -PathType Leaf
            if ($prior[$t]) { Copy-Item -LiteralPath $t -Destination (Join-Path $backupDir (Split-Path $t -Leaf)) -Force }
        }
        $step = 0
        for ($i = 0; $i -lt $StagedFiles.Count; $i++) {
            Copy-Item -LiteralPath $StagedFiles[$i] -Destination $TargetFiles[$i] -Force
            $step++
            if ($FaultAfterStep -gt 0 -and $step -eq $FaultAfterStep) { throw "S05-INJECTED-FAULT after publication step $step (frame copy)" }
        }
        Set-Content -LiteralPath $SummaryPath -Value $SummaryJson -Encoding UTF8
        $step++
        if ($FaultAfterStep -gt 0 -and $step -eq $FaultAfterStep) { throw "S05-INJECTED-FAULT after publication step $step (summary write)" }
    } catch {
        Restore-S05Evidence -State $prior -BackupDir $backupDir -EvidenceRoot $EvidenceRoot
        throw
    } finally {
        Remove-Item -LiteralPath $backupDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    return $targets
}

# ---------------------------------------------------------------------------
# Self-test: deterministic fault injection on a sandboxed temp evidence copy.
# The real evidence directory is never opened for writing.
# ---------------------------------------------------------------------------

function Get-S05Sha256([string]$Path) {
    # SHA256 hex string via .NET directly: module cmdlets (Get-FileHash) are unavailable when
    # PSModulePath is stripped (bash-spawned powershell on this host).
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        try {
            $hash = $sha.ComputeHash($stream)
            return ([System.BitConverter]::ToString($hash)).Replace('-', '')
        } finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
}

function Get-S05FileState([string[]]$Paths) {
    $h = @{}
    foreach ($p in $Paths) {
        if (Test-Path -LiteralPath $p -PathType Leaf) { $h[$p] = Get-S05Sha256 $p }
        else { $h[$p] = $null }
    }
    $h
}

function Compare-S05FileState($Before, $After, [string]$Label) {
    $bad = @()
    foreach ($k in @($Before.Keys)) {
        if ($null -ne $Before[$k] -and $null -eq $After[$k]) { $bad += "${Label}: $k existed before, missing after" }
        elseif ($null -eq $Before[$k] -and $null -ne $After[$k]) { $bad += "${Label}: $k absent before, present after" }
        elseif ($null -ne $Before[$k] -and $Before[$k] -ne $After[$k]) { $bad += "${Label}: $k SHA256 changed" }
    }
    if ($bad.Count -gt 0) { throw ($bad -join "`n") }
}

function Invoke-S05PublishSelfTest {
    $sandbox = Join-Path ([IO.Path]::GetTempPath()) ('s05-pubselftest-' + [Guid]::NewGuid().ToString('N'))
    $evRoot = Join-Path $sandbox 'art-references'
    $framesDir = Join-Path $evRoot 'frames'
    $stageDir = Join-Path $sandbox 'stage'
    New-Item -ItemType Directory -Force -Path $framesDir, $stageDir | Out-Null
    $names = @('frame-K1-overview.png', 'frame-K2-closeup.png', 'frame-K3-combat.png')
    $targets = @($names | ForEach-Object { Join-Path $framesDir $_ })
    $staged = @($names | ForEach-Object { Join-Path $stageDir $_ })
    $summary = Join-Path $evRoot 'run-summary.json'
    $unrelated = Join-Path $framesDir 'frame-K9-unrelated.png'
    $all = @($targets) + @($summary) + @($unrelated)
    $ok = @()
    try {
        # fault injected after each of the 4 publication steps (1st/2nd/3rd frame copy,
        # summary write): every prior file must come back byte-for-byte and the
        # unrelated evidence file must not change
        foreach ($fault in 1, 2, 3, 4) {
            foreach ($t in $targets) { Set-Content -LiteralPath $t -Value ('PRIOR-' + (Split-Path $t -Leaf) + '-' + $fault) -Encoding ASCII }
            Set-Content -LiteralPath $summary -Value "PRIOR-SUMMARY-$fault" -Encoding ASCII
            Set-Content -LiteralPath $unrelated -Value 'UNRELATED-NEVER-TOUCHED' -Encoding ASCII
            for ($i = 0; $i -lt 3; $i++) { Set-Content -LiteralPath $staged[$i] -Value ('FRESH-' + $names[$i] + '-' + $fault) -Encoding ASCII }
            $before = Get-S05FileState $all
            $threw = $false
            try { Publish-S05Evidence -StagedFiles $staged -TargetFiles $targets -SummaryPath $summary -SummaryJson "FRESH-SUMMARY-$fault" -EvidenceRoot $evRoot -FaultAfterStep $fault | Out-Null }
            catch { $threw = $true }
            if (-not $threw) { throw "fault-after-step-${fault}: expected exception was not thrown" }
            Compare-S05FileState $before (Get-S05FileState $all) "fault-after-step-$fault"
            $ok += "rollback-after-step-$fault"
        }
        # prior-absent variant: K3 + run-summary had no prior file; fault after the
        # summary write -> the newly created files must be removed, absent stays absent
        Remove-Item -LiteralPath $targets[2], $summary -Force
        for ($i = 0; $i -lt 3; $i++) { Set-Content -LiteralPath $staged[$i] -Value ('FRESH2-' + $names[$i]) -Encoding ASCII }
        $before = Get-S05FileState $all
        $threw = $false
        try { Publish-S05Evidence -StagedFiles $staged -TargetFiles $targets -SummaryPath $summary -SummaryJson 'FRESH2-SUMMARY' -EvidenceRoot $evRoot -FaultAfterStep 4 | Out-Null }
        catch { $threw = $true }
        if (-not $threw) { throw 'prior-absent: expected exception was not thrown' }
        Compare-S05FileState $before (Get-S05FileState $all) 'prior-absent-rollback'
        $ok += 'prior-absent-rollback'
        # success path: no fault -> all four targets published byte-for-byte,
        # unrelated file unchanged
        for ($i = 0; $i -lt 3; $i++) { Set-Content -LiteralPath $staged[$i] -Value ('FRESH3-' + $names[$i]) -Encoding ASCII }
        $expected = Join-Path $stageDir 'expected-summary.json'
        Set-Content -LiteralPath $expected -Value 'FRESH3-SUMMARY' -Encoding UTF8
        $unrelatedHash = Get-S05Sha256 $unrelated
        Publish-S05Evidence -StagedFiles $staged -TargetFiles $targets -SummaryPath $summary -SummaryJson 'FRESH3-SUMMARY' -EvidenceRoot $evRoot | Out-Null
        for ($i = 0; $i -lt 3; $i++) {
            if ((Get-S05Sha256 $targets[$i]) -ne (Get-S05Sha256 $staged[$i])) {
                throw "success: $($names[$i]) was not published byte-for-byte"
            }
        }
        if ((Get-S05Sha256 $summary) -ne (Get-S05Sha256 $expected)) {
            throw 'success: run-summary.json was not published byte-for-byte'
        }
        if ((Get-S05Sha256 $unrelated) -ne $unrelatedHash) {
            throw 'success: unrelated evidence file changed'
        }
        $ok += 'success-publication'
        # containment guard: a rollback target outside the evidence root must throw
        # before any move/removal happens, leaving the outside file untouched
        $outside = Join-Path $sandbox 'outside-evidence.txt'
        Set-Content -LiteralPath $outside -Value 'OUTSIDE' -Encoding ASCII
        $threw = $false
        try { Restore-S05Evidence -State @{ $outside = $true } -BackupDir $stageDir -EvidenceRoot $evRoot }
        catch { $threw = $true }
        if (-not $threw) { throw 'containment guard: rollback of a path outside the evidence root did not throw' }
        if (-not (Test-Path -LiteralPath $outside -PathType Leaf)) { throw 'containment guard: outside file must remain untouched' }
        $ok += 'containment-guard'
    } finally {
        Remove-Item -LiteralPath $sandbox -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Output ('S05 publish self-test PASS: ' + ($ok -join ', '))
}

if ($SelfTest) { Invoke-S05PublishSelfTest; return }

New-Item -ItemType Directory -Force -Path $evidence | Out-Null
# Fresh-capture contract: remove only this run's three exact screenshot outputs from the packaged
# Saved dir. The evidence copies are NOT touched here — frames are staged in TEMP and replace the
# three exact evidence names only after the packaged run + validation pass, so a failed run never
# erases the prior evidence and no unrelated frame-K*.png is ever swept (P2 2026-09-25 review).
$expected = @('S05_K1_overview.png', 'S05_K2_closeup.png', 'S05_K3_combat.png')
foreach ($f in $expected) { $p = Join-Path $shots $f; if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force } }
if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
if (Test-Path -LiteralPath "$work/s05-runtime-exit.txt") { Remove-Item -LiteralPath "$work/s05-runtime-exit.txt" -Force }
$runStartedUtc = [DateTime]::UtcNow
$process = Start-Process -FilePath $exe -ArgumentList @('/Game/S05/Reference','-S05Ref','-unattended','-nosplash','-windowed','-RenderOffscreen','-ResX=1920','-ResY=1080',('-abslog="'+$log+'"')) -WindowStyle Hidden -PassThru
# PID-scoped kill on timeout: never kill by process name (a sibling run may exist).
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
 try { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue } catch {}
 throw "S05 packaged run $($process.Id) did not exit within $TimeoutSeconds seconds. Inspect $log"
}
if ($process.ExitCode -ne 0) { throw "S05 packaged run failed: exit $($process.ExitCode). See $log" }
if (-not (Test-Path -LiteralPath $log -PathType Leaf)) { throw "Fresh run output missing: $log" }
$file = Get-Item -LiteralPath $log
if ($file.Length -eq 0 -or $file.LastWriteTimeUtc -lt $runStartedUtc.AddSeconds(-2)) { throw "Run output empty or stale: $log" }
$text = Get-Content $log -Raw
$frameMap = @{'S05_K1_overview.png'='frame-K1-overview.png'; 'S05_K2_closeup.png'='frame-K2-closeup.png'; 'S05_K3_combat.png'='frame-K3-combat.png'}
# stage the fresh captures in TEMP; the evidence dir is only written after validation passes
$stage = Join-Path ([IO.Path]::GetTempPath()) ('s05-smoke-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $stage | Out-Null
try {
 $staged = @()
 foreach ($src in $frameMap.Keys | Sort-Object) {
  $from = Join-Path $shots $src
  if (-not (Test-Path -LiteralPath $from -PathType Leaf)) { throw "Screenshot missing: $from" }
  $to = Join-Path $stage $frameMap[$src]
  Copy-Item $from $to -Force
  $staged += $to
 }
 $validation = Assert-S05Run -LogText $text -FramePaths $staged
 # compute the full summary payload BEFORE publishing so the three frame copies and the
 # run-summary.json write happen as one transaction (backup + rollback on any failure)
 $copied = @($frameMap.Keys | Sort-Object | ForEach-Object { Join-Path $evidence $frameMap[$_] })
 $markerNames = @('S05_REF_READY', 'S05_REF_SCENE', 'S05_K3_HUD', 'S05_MEDUSA_RM', 'S05_RM_CLIP',
                  'S05_RM_SKEL', 'S05_ROOTMOTION_START', 'S05_ROOTMOTION_RESULT', 'S05_FRAME_STATS',
                  'S05_REF_COMPLETE')
 $markers = @{}
 foreach ($m in $markerNames) {
  $hit = ($text -split "`r?`n") | Where-Object { $_ -match [regex]::Escape($m) } | Select-Object -First 1
  if ($hit) { $markers[$m] = $hit.Substring($hit.IndexOf($m)).Trim() }
 }
 $k3Pose = ($text -split "`r?`n") | Where-Object { $_ -match 'S05_K3_POSE' -and $_ -match 'after_eval' } |
     ForEach-Object { $_.Substring($_.IndexOf('S05_K3_POSE')).Trim() }
 $relFrames = $copied | ForEach-Object { $_.Substring($root.Length + 1) }
 $summaryJson = @{
     stage = 'packaged-smoke'
     buildConfig = 'Development'
     exitCode = $process.ExitCode
     startedUtc = $runStartedUtc.ToString('o')
     finishedUtc = ([DateTime]::UtcNow).ToString('o')
     frames = $relFrames
     validation = $validation
     markers = $markers
     k3PoseAfterEval = $k3Pose
 } | ConvertTo-Json -Depth 4
 $evidenceRoot = (Resolve-Path (Join-Path $evidence '..')).Path
 Publish-S05Evidence -StagedFiles $staged -TargetFiles $copied `
     -SummaryPath "$root/docs/game-design/evidence/S05/art-references/run-summary.json" `
     -SummaryJson $summaryJson -EvidenceRoot $evidenceRoot
} finally {
 Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
@{
    exitCode = $process.ExitCode
    startedUtc = $runStartedUtc.ToString('o')
    finishedUtc = ([DateTime]::UtcNow).ToString('o')
    log = $log
    frames = $copied
    validation = $validation
} | ConvertTo-Json | Set-Content "$work/s05-runtime-exit.txt" -Encoding UTF8
Write-Output "S05 packaged smoke PASS: exit 0; numeric gates passed; frames verified 1920x1080; evidence published atomically (backup + rollback on failure). Started UTC: $($runStartedUtc.ToString('o'))"
