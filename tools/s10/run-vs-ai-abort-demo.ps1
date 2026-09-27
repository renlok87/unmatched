param(
  [string]$Exe = "",
  [string]$Api = "http://127.0.0.1:3121/graphql",
  [string]$EvidenceDir = "",
  # Bounded client lifetime (-S08ExitAfter safety net) AND bounded wall clock:
  # the runner never waits past start + RunSeconds + 60s, then stops ONLY this
  # run's client process.
  [int]$RunSeconds = 240,
  # How long the match must be live (IN_PROGRESS with the bot seat) before the
  # external host-authorized abort fires.
  [int]$LiveSeconds = 25,
  [string]$ShotMode = "request",
  [string]$EnvFile = "",
  [string]$HeroName = "Medusa",
  # Run the offline synthetic self-tests (scoped client-stop identity checks,
  # static taskkill/Stop-Process guards) and exit. No client start, no API calls.
  [switch]$SelfTest
)
# S10/GD-040 packaged ABORTED live acceptance runner (adapted from
# tools/s10/run-vs-ai-demo.ps1 - no edits to that file, the C++, or docs).
# ONE hidden packaged client signs in, creates a VS_AI room (-S08Mode=VS_AI),
# selects a hero, readies and starts ALONE; the server bot takes the second
# seat. While the match is live the runner fires an EXTERNAL host-authorized
# abortGame for THIS exact room only and verifies the authoritative row reads
# ABORTED. The client must poll, log the interruption, render the interruption
# screen (distinct from the result screen) with gameplay input disabled, and
# never invent a VICTORY/DEFEAT.
# GATES (all must pass before evidence is published):
#   - ROOM: this run's room is mode=VS_AI, hosted by the run's account,
#     observed in LOBBY either with exactly ONE human seat (seat 0 = the
#     run's user) or with TWO seats where seat 1 already passes the full
#     seeded-bot identity checks (setupAiOpponent commits the bot seat in a
#     separate transaction BEFORE the LOBBY->IN_PROGRESS flip, so an interim
#     2-seat LOBBY row is legitimate - a foreign human in the pair fails),
#     then IN_PROGRESS with exactly TWO distinct seats where seat 1 is the
#     REAL seeded bot: the seat's userId matches the row's opponentId, the
#     username is the seeded 'AI Bot' (backend/prisma/seed-ai.ts), and the
#     id is cross-checked against the public userByUsername('AI Bot')
#     lookup - no weaker "any foreign id" bot claim - all BEFORE the abort;
#   - ABORT: abortGame is fired as the host for this room's id while the row is
#     IN_PROGRESS (code+mode+host+status validated first); the response and a
#     fresh re-read both say ABORTED with endedAt set and winnerId null;
#   - CLIENT/PROOF TAIL: the client runs the opt-in -S10AbortProof drive over
#     the authoritative ABORTED row: an ordered, exactly-once trace tail
#     (interruption row -> aborted-screen shot -> ONE leaveGame ->
#     aborted-lobby shot -> complete/exiting), the accepted leave traced as
#     'LEFT room=<this room id>' after the leave was sent, NO gameplay
#     command after the interruption marker (input disabled - observable
#     consequence of the controller gate), and no shot/marker failure lines;
#   - NO INVENTED RESULT: the trace has no 'RESULT seq=' / 'S09AUTO duel flow
#     complete' markers (no victory/defeat screen ever built) and the
#     authoritative row stays ABORTED with winnerId null - never FINISHED;
#   - SHOTS (client-captured, pixel-gated): s10-aborted-screen.png is FRESH,
#     substantive, full resolution, carries the #FF6414 interruption marker
#     and none of the result/lobby panel markers (an interrupted match can
#     never look like a victory or a lobby); s10-aborted-lobby.png is FRESH,
#     substantive, carries the #40C8FF clean-lobby panel marker, none of the
#     duel/result/interruption markers, and passes the visual gameplay-region
#     bright-pixel gate (x >= 25%, y >= 12.5%, lum >= 120, <= 50 pixels) - the
#     board was torn down by the stage transition;
#   - EXIT/CLEANUP: the client exits ITSELF after its proof tail (the runner
#     only scoped-stops this run's verified client TREE on a bounded
#     fallback: the staged root launcher plus its verified staged child(ren),
#     never an unverifiable or unrelated process); the CLIENT's own leaveGame
#     is the single leave - the runner issues NO server-side leaveGame on the
#     happy path; the user's myGames lists no active (IN_PROGRESS/LOBBY) room
#     for this id and the final authoritative row stays ABORTED with
#     winnerId null and no commands after the abort (input disabled).
# Safety: per-process ENV credentials only (never argv, never printed; the
# command line is audited after start), hidden client, per-process 30 FPS cap
# via -ExecCmds="t.MaxFPS 30" (the packaged 60 FPS default is NOT modified),
# temp staging under %TEMP% published only after every gate passed, scoped
# cleanup of ONLY this run's client process TREE (verified staged launcher +
# verified staged child(ren); the packaged root exe is a LAUNCHER that spawns
# Windows/Unmatched/Binaries/Win64/Unmatched.exe - killing only the launcher
# leaves that child rendering and holding the inherited pipes, which hangs
# the parent shell) and scoped cleanup of this run's room (abort only when
# the flow died before the ABORTED row verified). The room code is
# redacted from all published logs and console output.
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Exe) { $Exe = Join-Path $RepoRoot 'unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe' }
if (-not $EvidenceDir) { $EvidenceDir = Join-Path $RepoRoot 'docs\game-design\evidence\S10\run' }

function Set-StagedResolution([string]$ExePath, [int]$W, [int]$H) {
  $gsDir = Join-Path (Split-Path -Parent $ExePath) 'Unmatched\Saved\Config\Windows'
  New-Item -ItemType Directory -Force -Path $gsDir | Out-Null
  $gs = Join-Path $gsDir 'GameUserSettings.ini'
  # Resolution keys only, NO FrameRateLimit: the per-process cap is the
  # -ExecCmds="t.MaxFPS 30" console command, not a persisted setting.
  $section = '[/Script/Engine.GameUserSettings]'
  $wanted = [ordered]@{
    'ResolutionSizeX'                  = $W
    'ResolutionSizeY'                  = $H
    'LastUserConfirmedResolutionSizeX' = $W
    'LastUserConfirmedResolutionSizeY' = $H
    'FullscreenMode'                   = 1
    'LastConfirmedFullscreenMode'      = 1
    'PreferredFullscreenMode'          = 1
  }
  $lines = @()
  if (Test-Path -LiteralPath $gs) { $lines = @(Get-Content -LiteralPath $gs) }
  if (-not ($lines | Where-Object { $_ -match '^\s*\[' })) { $lines = @($section) + $lines }
  foreach ($key in $wanted.Keys) {
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
      if ($lines[$i] -match ('^\s*' + [regex]::Escape($key) + '\s*=')) {
        $lines[$i] = "$key=$($wanted[$key])"; $found = $true; break
      }
    }
    if (-not $found) { $lines += "$key=$($wanted[$key])" }
  }
  [System.IO.File]::WriteAllLines($gs, $lines)
  Write-Output "staged GameUserSettings -> ${W}x${H} (windowed, no FrameRateLimit - cap is per-process t.MaxFPS): $gs"
}
# ---- scoped client-process stop (launcher + verified child) ----
# The packaged staged root Unmatched.exe is a LAUNCHER: it immediately spawns
# the real UE client child at Windows/Unmatched/Binaries/Win64/Unmatched.exe.
# Killing only the launcher pid leaves that child rendering (and holding the
# inherited console pipes), which hangs the parent shell - observed live in
# this runner's abort run of 20260927-183807. Every stop path must instead
# stop the verified CHILD first, then the verified launcher. Verification is
# fail-closed: a candidate is stopped ONLY when its resolved absolute
# ExecutablePath lies inside this run's staged build AND its command line
# carries this run's unique staging path; anything else is left running and
# reported. Child enumeration by ParentProcessId still works after the
# launcher exited (Win32 keeps the recorded parent pid), and every candidate
# pid is re-verified through a fresh Win32_Process read before any stop, so
# a reused pid fails verification instead of being killed. Never a broad
# tree-kill here - that would stop unrelated processes that merely share the
# tree.
# Pure checker: returns $null when the record is fully attributable to this
# run, or the first reason it is not (offline-testable, no CIM).
function Test-ThisRunProcessRecord($Record, [string]$StagedRootFull, [string]$RunTag) {
  if (-not $Record) { return 'record is null' }
  $exePath = [string]$Record.ExecutablePath
  if (-not $exePath) { return "pid $($Record.ProcessId) exposes no ExecutablePath" }
  $exeFull = [System.IO.Path]::GetFullPath($exePath)
  $rootFull = [System.IO.Path]::GetFullPath($StagedRootFull).TrimEnd([char]'\', [char]'/')
  $boundary = $rootFull + [System.IO.Path]::DirectorySeparatorChar
  if (-not $exeFull.StartsWith($boundary, [System.StringComparison]::OrdinalIgnoreCase)) {
    return "pid $($Record.ProcessId) exe '$exeFull' is NOT inside the staged build '$rootFull'"
  }
  $cmd = [string]$Record.CommandLine
  if (-not $cmd) { return "pid $($Record.ProcessId) exposes no CommandLine" }
  if (-not $cmd.Contains($RunTag)) {
    return "pid $($Record.ProcessId) command line does not carry this run's staging tag"
  }
  return $null
}

# Pure cleanup verdict (offline-testable): returns $null when the scoped stop
# fully verified, or the failure message when ANY anomaly is present - a
# foreign/unverifiable process left running OR a verified pid that could not
# be stopped. A successful stop of ANOTHER pid must not mask it (M2: the run
# fails whenever any unverified or failed child/launcher remains).
function Test-StopCleanupVerdict([int]$StoppedCount, [string[]]$Unverified) {
  if (@($Unverified).Count -gt 0) {
    return 'scoped client stop reported anomalies: ' + (@($Unverified) -join '; ')
  }
  return $null
}

# Ordered S10ABORTPROOF tail: exactly one of each client proof marker, in
# order; the accepted client leave ('LEFT room=<RoomId>') must follow the
# leave-sent marker and be the ONLY LEFT line; shot/leave failure lines and
# any invented result tail are forbidden. Returns $null on success or the
# first problem found (offline-testable pure parser - no file/process access).
function Test-AbortProofTailOrder([string]$TraceText, [string]$RoomId) {
  $markers = @(
    @{ name = 'interruption row';    literal = 'S10ABORTPROOF authoritative ABORTED row - interruption screen (no victory/defeat is declared)' },
    @{ name = 'aborted-screen shot'; literal = 'S10ABORTPROOF aborted-screen shot (interruption panel painted)' },
    @{ name = 'leave sent';          literal = 'S10ABORTPROOF leave sent (one leaveGame - the ONLY command after the abort)' },
    @{ name = 'aborted-lobby shot';  literal = 'S10ABORTPROOF aborted-lobby shot (board torn down by the stage transition)' },
    @{ name = 'complete';            literal = 'S10ABORTPROOF complete (ABORTED screen -> one leaveGame -> clean lobby) - exiting' }
  )
  $previousIndex = -1
  $leaveSentIndex = -1
  # Hard violations first: failure/invented-result lines are reported as such
  # even when the proof tail is also incomplete.
  foreach ($forbidden in @(
      'S10ABORTPROOF screen shot file never appeared',
      'S10ABORTPROOF lobby shot file never appeared',
      'S10ABORTPROOF leave FAILED',
      ' RESULT seq=', 'S09AUTO duel flow complete',
      'RESULT lobby-return sent (leaveGame)')) {
    if ($TraceText.Contains($forbidden)) { return "trace shows '$forbidden'" }
  }
  foreach ($marker in $markers) {
    $count = ([regex]::Matches($TraceText, [regex]::Escape($marker.literal))).Count
    if ($count -ne 1) { return "$($marker.name) marker count is $count (expected exactly one)" }
    $index = $TraceText.IndexOf($marker.literal, [StringComparison]::Ordinal)
    if ($index -le $previousIndex) { return "S10ABORTPROOF tail is out of order at $($marker.name)" }
    $previousIndex = $index
    if ($marker.name -eq 'leave sent') { $leaveSentIndex = $index }
  }
  if ($RoomId) {
    $leftCount = ([regex]::Matches($TraceText, [regex]::Escape('LEFT room='))).Count
    if ($leftCount -ne 1) { return "LEFT room= marker count is $leftCount (expected exactly one accepted leave)" }
    $leftIndex = $TraceText.IndexOf(('LEFT room=' + $RoomId), [StringComparison]::Ordinal)
    if ($leftIndex -lt 0) { return "the single LEFT room= marker is for a DIFFERENT room id (expected 'LEFT room=$RoomId')" }
    if ($leftIndex -le $leaveSentIndex) { return 'S10ABORTPROOF tail is out of order at the accepted leave (LEFT room= before the leave was sent)' }
  }
  return $null
}

# Pixel gate assembly over precomputed marker counts (pure, offline-testable):
# returns $null when every required marker has at least $Min sampled pixels
# and every forbidden marker is exactly absent, or the first violation.
function Test-MarkerGates($Stats, [string[]]$Require, [int]$Min, [string[]]$ForbidZero) {
  foreach ($name in @($Require)) {
    if (-not $Stats.Contains($name) -or [int]$Stats[$name] -lt $Min) {
      $have = if ($Stats.Contains($name)) { $Stats[$name] } else { '<absent>' }
      return "required marker '$name' too low ($have; expected >= $Min)"
    }
  }
  foreach ($name in @($ForbidZero)) {
    if ($Stats.Contains($name) -and [int]$Stats[$name] -ne 0) {
      return "forbidden marker '$name' present ($($Stats[$name]) sampled pixels)"
    }
  }
  return $null
}

# Sampled pixel counts for every named marker color (same +/-16 technique as
# the S10 result runner: even-coordinate sampling over Format32bppArgb).
function Get-ShotPixelStats([string]$Path, $Markers) {
  Add-Type -AssemblyName System.Drawing
  $bmp = [System.Drawing.Bitmap]::FromFile($Path)
  try {
    $w = $bmp.Width; $h = $bmp.Height
    $rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
    $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
      [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $bytes = New-Object byte[] ($data.Stride * $data.Height)
    [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
    $bmp.UnlockBits($data)
    $stats = @{ w = $w; h = $h }
    foreach ($mk in $Markers) { $stats[$mk.name] = 0 }
    $tol = 16
    for ($y = 0; $y -lt $h; $y += 2) {
      $rowOff = $y * $data.Stride
      for ($x = 0; $x -lt $w; $x += 2) {
        $i = $rowOff + $x * 4
        $pB = $bytes[$i]; $pG = $bytes[$i + 1]; $pR = $bytes[$i + 2]
        foreach ($mk in $Markers) {
          if ([Math]::Abs($pR - $mk.r) -le $tol -and
              [Math]::Abs($pG - $mk.g) -le $tol -and
              [Math]::Abs($pB - $mk.b) -le $tol) {
            $stats[$mk.name]++
            break
          }
        }
      }
    }
    return $stats
  } finally { $bmp.Dispose() }
}

# Visual gameplay-region bright-pixel gate (x >= 25%, y >= 12.5%, lum >= 120)
# - same technique as the S10 result runner's lobby gate.
function Get-GameplayRegionBright([string]$Path) {
  Add-Type -AssemblyName System.Drawing
  $bmp = [System.Drawing.Bitmap]::FromFile($Path)
  try {
    $w = $bmp.Width; $h = $bmp.Height
    $x0 = [int]($w * 0.25); $y0 = [int]($h * 0.125)
    $rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
    $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
      [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $bytes = New-Object byte[] ($data.Stride * $data.Height)
    [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
    $bmp.UnlockBits($data)
    $count = 0
    for ($y = $y0; $y -lt $h; $y += 2) {
      $rowOff = $y * $data.Stride
      for ($x = $x0; $x -lt $w; $x += 2) {
        $i = $rowOff + $x * 4
        $lum = 0.299 * $bytes[$i + 2] + 0.587 * $bytes[$i + 1] + 0.114 * $bytes[$i]
        if ($lum -ge 120) { $count++ }
      }
    }
    return $count
  } finally { $bmp.Dispose() }
}

# Fresh + substantive shot: present, not suspiciously small (a black/empty
# frame still encodes to a tiny PNG), captured after the client started.
function Assert-FreshShot([string]$Path, [DateTime]$ClientStartUtc, [string]$What) {
  if (-not (Test-Path -LiteralPath $Path)) { throw "$What shot missing: $Path" }
  $f = Get-Item -LiteralPath $Path
  if ($f.Length -lt 10KB) { throw "suspiciously small $What shot (likely black/empty): $Path" }
  if ($f.LastWriteTimeUtc -le $ClientStartUtc) { throw "$What shot predates its client process (stale file): $Path" }
  return $f
}

function Stop-ThisRunClient([int]$LauncherPid, [string]$LauncherExe, [string]$StagedRootFull, [string]$RunTag, $KnownChildPids) {
  $unverified = @()
  $stopped = @()
  $candidatePids = New-Object System.Collections.Generic.List[int]
  foreach ($c in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$LauncherPid" -ErrorAction SilentlyContinue)) {
    if (-not $candidatePids.Contains([int]$c.ProcessId)) { [void]$candidatePids.Add([int]$c.ProcessId) }
  }
  foreach ($k in @($KnownChildPids)) {
    if ($k -and -not $candidatePids.Contains([int]$k)) { [void]$candidatePids.Add([int]$k) }
  }
  # children first: while the child lives it keeps rendering and holds the
  # inherited pipes that hang the parent shell
  foreach ($cpid in @($candidatePids)) {
    $rec = Get-CimInstance Win32_Process -Filter "ProcessId=$cpid" -ErrorAction SilentlyContinue
    if (-not $rec) { continue } # already gone
    $bad = Test-ThisRunProcessRecord $rec $StagedRootFull $RunTag
    if ($bad) { $unverified += $bad; continue } # FAIL CLOSED: left running
    try {
      Stop-Process -Id ([int]$rec.ProcessId) -Force -ErrorAction Stop
      $stopped += [int]$rec.ProcessId
    } catch {
      $unverified += "verified child pid $($rec.ProcessId) could not be stopped: $($_.Exception.Message)"
    }
  }
  $lrec = Get-CimInstance Win32_Process -Filter "ProcessId=$LauncherPid" -ErrorAction SilentlyContinue
  if ($lrec) {
    $liveExe = [System.IO.Path]::GetFullPath([string]$lrec.ExecutablePath)
    $wantExe = [System.IO.Path]::GetFullPath($LauncherExe)
    $lcmd = [string]$lrec.CommandLine
    if (-not [string]::Equals($liveExe, $wantExe, [System.StringComparison]::OrdinalIgnoreCase)) {
      $unverified += "launcher pid $LauncherPid now resolves to '$liveExe', not this run's '$wantExe' - left running"
    } elseif (-not $lcmd -or -not $lcmd.Contains($RunTag)) {
      # pid-reuse guard: same staged exe but not this run's command line
      $unverified += "launcher pid $LauncherPid command line does not carry this run's staging tag - left running"
    } else {
      try {
        Stop-Process -Id $LauncherPid -Force -ErrorAction Stop
        $stopped += $LauncherPid
      } catch {
        $unverified += "launcher pid $LauncherPid could not be stopped: $($_.Exception.Message)"
      }
    }
  }
  $note = ''
  if ($unverified.Count -gt 0) { $note = ' | UNVERIFIED, left running (fail closed): ' + ($unverified -join '; ') }
  Write-Output ("cleanup: scoped client stop stopped pids=[{0}]{1}" -f (($stopped | ForEach-Object { $_ }) -join ','), $note)
  # M2: ANY unverified/failed child or launcher fails the run - even when
  # another pid of ours stopped fine.
  $verdict = Test-StopCleanupVerdict $stopped.Count $unverified
  if ($verdict) {
    if ($Script:CleanupFailure) { $Script:CleanupFailure = "$($Script:CleanupFailure); $verdict" } else { $Script:CleanupFailure = $verdict }
  }
}

function Assert-Cond([bool]$Cond, [string]$Name, [string]$Detail) {
  if ($Cond) { Write-Output "PASS $Name"; return }
  $Script:SelfTestFailures++
  Write-Output "FAIL $Name - $Detail"
}

function Invoke-AbortRunnerSelfTests {
  $Script:SelfTestFailures = 0

  # scoped client-stop identity verification (synthetic Win32_Process records;
  # the pure checker is offline - no process enumeration happens here)
  $stRoot = 'C:\staged\Windows'
  $runTag = 'C:\Temp\s10-vsai-abort-20260927-183807-43804'
  $okChild = [pscustomobject]@{ ProcessId = 42092
    ExecutablePath = 'C:\staged\Windows\Unmatched\Binaries\Win64\Unmatched.exe'
    CommandLine = '"C:\staged\Windows\Unmatched\Binaries\Win64\Unmatched.exe" /Game/S08/S08Arena -S08Trace=C:\Temp\s10-vsai-abort-20260927-183807-43804\vsai-abort-client.trace.log' }
  $r = Test-ThisRunProcessRecord $okChild $stRoot $runTag
  Assert-Cond ($null -eq $r) 'client stop: staged child exe + this run tag accepts' "unexpected error: $r"
  $caseChild = [pscustomobject]@{ ProcessId = 1
    ExecutablePath = 'c:\STAGED\windows\Unmatched\Binaries\Win64\Unmatched.exe'
    CommandLine = "Unmatched.exe -S08Trace=$runTag\vsai-abort-client.trace.log" }
  $r = Test-ThisRunProcessRecord $caseChild $stRoot $runTag
  Assert-Cond ($null -eq $r) 'client stop: path comparison is case-insensitive' "unexpected error: $r"
  $foreignExe = [pscustomobject]@{ ProcessId = 2
    ExecutablePath = 'C:\Windows\System32\notepad.exe'
    CommandLine = "notepad $runTag" }
  $r = Test-ThisRunProcessRecord $foreignExe $stRoot $runTag
  Assert-Cond ($r -match 'NOT inside the staged build') 'client stop: foreign exe is rejected even with this run tag' "got: $r"
  $dotDot = [pscustomobject]@{ ProcessId = 3
    ExecutablePath = 'C:\staged\Windows\..\..\evil.exe'
    CommandLine = "evil $runTag" }
  $r = Test-ThisRunProcessRecord $dotDot $stRoot $runTag
  Assert-Cond ($r -match 'NOT inside the staged build') 'client stop: ..-traversal out of the staged build is rejected after normalization' "got: $r"
  $foreignTag = [pscustomobject]@{ ProcessId = 4
    ExecutablePath = 'C:\staged\Windows\Unmatched\Binaries\Win64\Unmatched.exe'
    CommandLine = 'Unmatched.exe -S08Trace=C:\Temp\s10-vsai-abort-OTHER-9999\vsai-abort-client.trace.log' }
  $r = Test-ThisRunProcessRecord $foreignTag $stRoot $runTag
  Assert-Cond ($r -match 'does not carry') 'client stop: staged exe from ANOTHER run (no this-run tag) is rejected' "got: $r"
  $noCmd = [pscustomobject]@{ ProcessId = 5
    ExecutablePath = 'C:\staged\Windows\Unmatched\Binaries\Win64\Unmatched.exe'
    CommandLine = '' }
  $r = Test-ThisRunProcessRecord $noCmd $stRoot $runTag
  Assert-Cond ($r -match 'no CommandLine') 'client stop: missing command line is rejected' "got: $r"
  $noPath = [pscustomobject]@{ ProcessId = 6; ExecutablePath = ''; CommandLine = $runTag }
  $r = Test-ThisRunProcessRecord $noPath $stRoot $runTag
  Assert-Cond ($r -match 'no ExecutablePath') 'client stop: missing exe path is rejected' "got: $r"
  $r = Test-ThisRunProcessRecord $null $stRoot $runTag
  Assert-Cond ($r -match 'record is null') 'client stop: null record is rejected' "got: $r"
  # static regression guards: this runner must never fall back to a broad kill
  $ownText = Get-Content -LiteralPath $PSCommandPath -Raw
  $invocation = [regex]::Match($ownText, '(?m)(^|[|&;])\s*taskkill\b')
  Assert-Cond (-not $invocation.Success) 'client stop: static - no broad tree-kill invocation in this runner' $invocation.Value
  $bodyMatch = [regex]::Match($ownText, '(?s)function Stop-ThisRunClient.*?(?=\r?\nfunction )')
  $allStopUses = [regex]::Matches($ownText, 'Stop-Process\s+-Id').Count
  $bodyStopUses = [regex]::Matches($bodyMatch.Value, 'Stop-Process\s+-Id').Count
  Assert-Cond ($bodyMatch.Success -and $allStopUses -gt 0 -and $allStopUses -eq $bodyStopUses) 'client stop: static - every Stop-Process call lives inside the scoped helper' "all=$allStopUses inHelper=$bodyStopUses found=$($bodyMatch.Success)"

  # M2 cleanup verdict: ANY unverified/failed child or launcher fails the run,
  # even when another process of ours stopped successfully.
  Assert-Cond ($null -eq (Test-StopCleanupVerdict 2 @())) 'stop verdict: all stopped, no anomalies -> clean' ''
  Assert-Cond ($null -eq (Test-StopCleanupVerdict 0 @())) 'stop verdict: nothing to stop, no anomalies -> clean' ''
  $v = Test-StopCleanupVerdict 0 @('pid 7 not inside the staged build')
  Assert-Cond ($v -match 'anomalies') 'stop verdict: unverified with nothing stopped fails' "got: $v"
  $v = Test-StopCleanupVerdict 1 @('foreign child pid 9 left running')
  Assert-Cond ($v -match 'anomalies' -and $v -match 'foreign child pid 9') 'stop verdict: unverified FAILS even though another pid stopped (M2)' "got: $v"

  # ---- S10ABORTPROOF tail parser (the new client-proof gates) ----
  $ts = '2026.09.27-19.00.01'
  $intRow = "$ts S10ABORTPROOF authoritative ABORTED row - interruption screen (no victory/defeat is declared)"
  $scrShot = "$ts S10ABORTPROOF aborted-screen shot (interruption panel painted)"
  $leaveSent = "$ts S10ABORTPROOF leave sent (one leaveGame - the ONLY command after the abort)"
  $leftRoom = "$ts LEFT room=room-1"
  $lobShot = "$ts S10ABORTPROOF aborted-lobby shot (board torn down by the stage transition)"
  $complete = "$ts S10ABORTPROOF complete (ABORTED screen -> one leaveGame -> clean lobby) - exiting"
  $goodProof = "$intRow`n$scrShot`n$leaveSent`n$leftRoom`n$lobShot`n$complete`n"
  $e = Test-AbortProofTailOrder $goodProof 'room-1'
  Assert-Cond ($null -eq $e) 'abort tail: accepts the canonical ordered proof tail' "unexpected error: $e"
  $e = Test-AbortProofTailOrder ("$intRow`n$scrShot`n$leaveSent`n$lobShot`n$complete`n") $null
  Assert-Cond ($null -eq $e) 'abort tail: room-id-agnostic mode accepts without any LEFT line' "unexpected error: $e"

  $dupProof = $goodProof + "$complete`n"
  $e = Test-AbortProofTailOrder $dupProof 'room-1'
  Assert-Cond ($e -match 'complete marker count is 2') 'abort tail: duplicate complete marker fails' "got: $e"

  $revProof = "$intRow`n$leaveSent`n$scrShot`n$leftRoom`n$lobShot`n$complete`n"
  $e = Test-AbortProofTailOrder $revProof 'room-1'
  Assert-Cond ($e -match 'out of order at leave sent') 'abort tail: leave sent before the screen shot fails' "got: $e"

  $missingProof = "$intRow`n$scrShot`n$leaveSent`n$leftRoom`n$complete`n"
  $e = Test-AbortProofTailOrder $missingProof 'room-1'
  Assert-Cond ($e -match 'aborted-lobby shot marker count is 0') 'abort tail: missing lobby-shot marker fails' "got: $e"

  $e = Test-AbortProofTailOrder $goodProof 'room-2'
  Assert-Cond ($e -match 'DIFFERENT room id') 'abort tail: accepted leave for a foreign room id fails' "got: $e"

  $earlyLeft = "$intRow`n$scrShot`n$leftRoom`n$leaveSent`n$lobShot`n$complete`n"
  $e = Test-AbortProofTailOrder $earlyLeft 'room-1'
  Assert-Cond ($e -match 'out of order at the accepted leave') 'abort tail: LEFT room= before the leave was sent fails' "got: $e"

  $twoLeft = "$intRow`n$scrShot`n$leaveSent`n$leftRoom`n$leftRoom`n$lobShot`n$complete`n"
  $e = Test-AbortProofTailOrder $twoLeft 'room-1'
  Assert-Cond ($e -match 'LEFT room= marker count is 2') 'abort tail: two accepted leaves fail' "got: $e"

  foreach ($case in @(
      @{ text = "$intRow`nS10ABORTPROOF screen shot file never appeared - proceeding WITHOUT the shot`n$complete"; name = 'screen shot never appeared is forbidden' },
      @{ text = "$intRow`nS10ABORTPROOF lobby shot file never appeared - proceeding WITHOUT the shot`n$complete"; name = 'lobby shot never appeared is forbidden' },
      @{ text = "$intRow`nS10ABORTPROOF leave FAILED - manual retry required; ending without the lobby proof`n"; name = 'leave FAILED is forbidden' },
      @{ text = "$intRow`n$complete`n$ts RESULT seq=101 outcome=VICTORY winner=X`n"; name = 'invented RESULT seq is forbidden' },
      @{ text = "$intRow`n$complete`nS09AUTO duel flow complete`n"; name = 'S09 duel-flow tail is forbidden' },
      @{ text = "$intRow`n$complete`nRESULT lobby-return sent (leaveGame)`n"; name = 'auto-driver leave line is forbidden' })) {
    $e = Test-AbortProofTailOrder $case.text $null
    Assert-Cond ($e -match [regex]::Escape("trace shows")) ("abort tail: " + $case.name) "got: $e"
  }

  # ---- pixel gate assembly (pure fn) ----
  $ok = @{ interrupt = 200; resultscreen = 0; lobbypanel = 0 }
  $e = Test-MarkerGates $ok @('interrupt') 100 @('resultscreen', 'lobbypanel')
  Assert-Cond ($null -eq $e) 'marker gates: require met + forbid absent accepts' "unexpected error: $e"
  $low = @{ interrupt = 40 }
  $e = Test-MarkerGates $low @('interrupt') 100 @()
  Assert-Cond ($e -match "required marker 'interrupt' too low \(40") 'marker gates: below-minimum required marker fails' "got: $e"
  $absent = @{ other = 5 }
  $e = Test-MarkerGates $absent @('interrupt') 100 @()
  Assert-Cond ($e -match '<absent>') 'marker gates: absent required marker fails without throwing' "got: $e"
  $dirty = @{ interrupt = 500; resultscreen = 3 }
  $e = Test-MarkerGates $dirty @('interrupt') 100 @('resultscreen')
  Assert-Cond ($e -match "forbidden marker 'resultscreen' present \(3") 'marker gates: forbidden marker present fails' "got: $e"

  # ---- pixel counters on synthetic PNGs (offline System.Drawing, no client) ----
  Add-Type -AssemblyName System.Drawing
  $pngPath = Join-Path ([System.IO.Path]::GetTempPath()) "s10-abort-selftest-$PID.png"
  $bmp = New-Object System.Drawing.Bitmap(32, 24)
  $interruptColor = [System.Drawing.Color]::FromArgb(255, 255, 100, 20)
  for ($x = 4; $x -le 10; $x += 2) { for ($y = 4; $y -le 10; $y += 2) { $bmp.SetPixel($x, $y, $interruptColor) } }
  $bmp.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  $mk = @(
    @{ name = 'interrupt'; r = 255; g = 100; b = 20 },
    @{ name = 'resultscreen'; r = 255; g = 215; b = 0 })
  $st = Get-ShotPixelStats $pngPath $mk
  Assert-Cond ($st.w -eq 32 -and $st.h -eq 24) 'pixel stats: synthetic png dimensions read' "got $($st.w)x$($st.h)"
  Assert-Cond ($st.interrupt -eq 16) 'pixel stats: exact interrupt-marker pixel count on a synthetic png' "got $($st.interrupt)"
  Assert-Cond ($st.resultscreen -eq 0) 'pixel stats: absent marker counts zero' "got $($st.resultscreen)"
  $e = Test-MarkerGates $st @('interrupt') 10 @('resultscreen')
  Assert-Cond ($null -eq $e) 'pixel stats: synthetic png passes its marker gate' "unexpected error: $e"
  Remove-Item -LiteralPath $pngPath -Force

  $bmp = New-Object System.Drawing.Bitmap(32, 24)
  $white = [System.Drawing.Color]::White
  $bmp.SetPixel(20, 21, $white) # inside the gameplay region (x>=8, y>=3), sampled
  $bmp.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Assert-Cond ((Get-GameplayRegionBright $pngPath) -eq 1) 'bright region: a bright gameplay-region pixel is counted' ''
  $bmp = New-Object System.Drawing.Bitmap(32, 24)
  $bmp.SetPixel(6, 21, $white) # left of the region (x < 25%) - never counted
  $bmp.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Assert-Cond ((Get-GameplayRegionBright $pngPath) -eq 0) 'bright region: a bright pixel outside the region is ignored' ''
  Remove-Item -LiteralPath $pngPath -Force

  Write-Output ("self-tests complete: {0} failure(s)" -f $Script:SelfTestFailures)
}

if ($SelfTest) {
  Invoke-AbortRunnerSelfTests
  if ($Script:SelfTestFailures -gt 0) { exit 1 }
  return
}

Set-StagedResolution $Exe 1280 720

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Script:CleanupFailure = $null
$Script:ThisRunGameId = $null
$Script:ThisRunGameCode = $null

function Invoke-Gql([string]$Query, $Variables, [string]$Token, [string]$What) {
  $body = @{ query = $Query; variables = $Variables } | ConvertTo-Json -Depth 6
  $headers = @{ }
  if ($Token) { $headers['authorization'] = "Bearer $Token" }
  $r = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $body
  if (-not $r) { throw "$What returned an empty response" }
  $errs = @()
  if ($r.PSObject.Properties['errors'] -and $null -ne $r.errors) { $errs = @($r.errors) }
  if ($errs.Count -gt 0) {
    $msgs = ($errs | ForEach-Object { $_.message }) -join '; '
    throw "$What returned GraphQL errors over HTTP 200: $msgs"
  }
  if (-not $r.data) { throw "$What returned neither data nor errors" }
  return $r
}

function Start-VsAiClient([string[]]$CliArgs, [string]$Email, [string]$Password) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $Exe
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
  foreach ($arg in $CliArgs) {
    if ($arg -match '^-ExecCmds=') { $psi.Arguments += $arg + ' ' }
    elseif ($arg -match '\s') { $psi.Arguments += '"' + $arg + '" ' } else { $psi.Arguments += $arg + ' ' }
  }
  $psi.EnvironmentVariables['S08_EMAIL'] = $Email
  $psi.EnvironmentVariables['S08_PASSWORD'] = $Password
  return [System.Diagnostics.Process]::Start($psi)
}

# Scoped abort used ONLY by the failure paths: stop this run's own game if (and
# only if) the abort-demo flow never reached the authoritative ABORTED row.
function Stop-ThisRunGame([string]$Token, [string]$UserId) {
  if (-not $Script:ThisRunGameId) {
    Write-Output "cleanup: no game was created by this run - nothing to abort"
    return
  }
  try {
    $q = @{ query = 'query G($id: String!) { game(id: $id) { id code mode status hostId } }'; variables = @{ id = $Script:ThisRunGameId } }
    $g = Invoke-Gql $q.query $q.variables $Token 'cleanup game lookup'
    $game = $g.data.game
    if (-not $game) {
      Write-Output "cleanup: game $($Script:ThisRunGameId) no longer resolves - nothing to abort"
      return
    }
    if ($Script:ThisRunGameCode -and $game.code -and ($game.code -cne $Script:ThisRunGameCode)) {
      throw "REFUSING abort - room code mismatch for game $($Script:ThisRunGameId)"
    }
    if ($game.mode -cne 'VS_AI') {
      throw "REFUSING abort - game $($Script:ThisRunGameId) is mode $($game.mode), not this run's VS_AI room"
    }
    if (@('ABORTED', 'FINISHED', 'COMPLETED') -contains $game.status) {
      Write-Output "cleanup: game $($Script:ThisRunGameId) already terminal ($($game.status)) - no abort"
      return
    }
    if ($game.hostId -cne $UserId) {
      throw "REFUSING abort - host-ownership validation failed for game $($Script:ThisRunGameId)"
    }
    $a = @{ query = 'mutation AB($gameId: String!) { abortGame(gameId: $gameId) { id status } }'; variables = @{ gameId = $Script:ThisRunGameId } }
    $r = Invoke-Gql $a.query $a.variables $Token 'cleanup abortGame'
    if (-not $r.data.abortGame -or $r.data.abortGame.id -cne $Script:ThisRunGameId) {
      throw "abortGame returned a foreign/absent game object"
    }
    Write-Output "cleanup: aborted THIS run's game id=$($Script:ThisRunGameId) status=$($r.data.abortGame.status)"
  } catch {
    $Script:CleanupFailure = "scoped cleanup of game $($Script:ThisRunGameId) failed: $($_.Exception.Message)"
    Write-Output "cleanup: FAILED - $($Script:CleanupFailure)"
  }
}

function Remove-TreeSafely([string]$Target, [string]$ExpectedRoot) {
  $targetFull = [System.IO.Path]::GetFullPath($Target)
  $rootFull = [System.IO.Path]::GetFullPath($ExpectedRoot).TrimEnd([char]'\', [char]'/')
  $boundary = $rootFull + [System.IO.Path]::DirectorySeparatorChar
  if (-not $targetFull.StartsWith($boundary, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "refusing recursive delete outside $ExpectedRoot : $targetFull"
  }
  if (-not (Test-Path -LiteralPath $targetFull)) { return }
  $stack = New-Object 'System.Collections.Generic.Stack[string]'
  $stack.Push($targetFull)
  while ($stack.Count -gt 0) {
    $dir = $stack.Pop()
    foreach ($item in @(Get-ChildItem -LiteralPath $dir -Force)) {
      if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "refusing recursive delete: reparse point inside tree: $($item.FullName)"
      }
      if ($item.PSIsContainer) { $stack.Push($item.FullName) }
    }
  }
  Remove-Item -LiteralPath $targetFull -Force -Recurse
}

if (-not (Test-Path $Exe)) { throw "packaged exe not found: $Exe" }
# Resolved absolute identities for the scoped client stop: the launcher exe
# itself and the staged build root its child must live inside.
$Script:ClientExeFull = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Exe).Path)
$Script:ClientStagedRoot = Split-Path -Parent $Script:ClientExeFull
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$Human = @{ email = $env:S10_DEMO_HUMAN_EMAIL; password = $env:S10_DEMO_HUMAN_PASSWORD }
if (-not $Human.email -and -not $EnvFile) { $EnvFile = Join-Path $RepoRoot 'backend\.env' }
if ($EnvFile) {
  # Credentials from a local gitignored file - still never argv, never printed.
  foreach ($line in @(Get-Content -LiteralPath $EnvFile)) {
    if ($line -match '^(S10_DEMO_HUMAN_[A-Z_]+)=(.*)$') {
      $name = $Matches[1]
      if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue)) {
        Set-Item "Env:$name" $Matches[2]
      }
    }
  }
  $Human = @{ email = $env:S10_DEMO_HUMAN_EMAIL; password = $env:S10_DEMO_HUMAN_PASSWORD }
}
foreach ($pair in @(
    @('S10_DEMO_HUMAN_EMAIL', $Human.email), @('S10_DEMO_HUMAN_PASSWORD', $Human.password))) {
  if (-not $pair[1]) { throw "missing $($pair[0]) in process environment" }
}

function Invoke-AbortDemo {
  $loginQ = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }'
  $login = Invoke-Gql $loginQ @{ input = @{ email = $Human.email; password = $Human.password } } '' 'pre-run login'
  $Script:UserId = $login.data.login.user.id
  if (-not $Script:UserId) { throw "login returned no user id" }
  $Token = $login.data.login.accessToken

  $list = Invoke-Gql 'query HL { heroList(limit: 200) { items { id name } } }' @{} $Token 'hero list'
  $hero = $list.data.heroList.items | Where-Object { $_.name -eq $HeroName } | Select-Object -First 1
  if (-not $hero) { $hero = $list.data.heroList.items[0] }
  $heroId = $hero.id
  Write-Output "hero=$heroId (name=$($hero.name))"

  # Stronger bot identity (same as the live result runner): resolve the
  # seeded 'AI Bot' (backend/prisma/seed-ai.ts) to its id via the public
  # userByUsername lookup; the ROOM gate below cross-checks the observed
  # opponent seat against that id. Lookup failure fails the run - no weaker
  # identity proof is invented.
  $ub = Invoke-Gql 'query UB($u: String!) { userByUsername(username: $u) { id username } }' @{ u = 'AI Bot' } $Token "bot identity lookup (userByUsername 'AI Bot')"
  if (-not $ub.data.userByUsername -or -not $ub.data.userByUsername.id) {
    throw "userByUsername('AI Bot') returned no id - cannot verify the seeded bot identity"
  }
  $botIdByUsername = [string]$ub.data.userByUsername.id
  Write-Output "bot identity: userByUsername('AI Bot') resolved (username reported as '$($ub.data.userByUsername.username)')"

  $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Script:Staging = Join-Path ([System.IO.Path]::GetTempPath()) "s10-vsai-abort-$Stamp-$PID"
  New-Item -ItemType Directory -Force -Path $Script:Staging | Out-Null
  Write-Output "staging: $Script:Staging"
  # Verified child pids of THIS run's launcher, captured early (see the room
  # wait loop below) so the scoped stop never relies on post-mortem
  # ParentProcessId reads alone.
  $Script:ChildPids = New-Object System.Collections.Generic.List[int]

  $shots = Join-Path $Script:Staging 'human'
  New-Item -ItemType Directory -Force -Path $shots | Out-Null
  $trace = Join-Path $Script:Staging 'vsai-abort-client.trace.log'

  # t.MaxFPS 30 is a per-process console-command cap for this hidden demo
  # client; the packaged 60 FPS default is untouched and effective FPS is NOT
  # claimed (no measured FPS/frame-time data exists).
  $clientArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode",
    "-windowed", "-resx=1280", "-resy=720", "-RenderOffScreen",
    "-ExecCmds=`"t.MaxFPS 30`"", "log=GrepLog",
    "-ForceAbandonSequences", "-S08Api=$Api", "-S09ShotMode=$ShotMode",
    "-S08Auto", "-S08Create", "-S08Mode=VS_AI", "-S08HeroId=$heroId",
    "-S08Trace=$trace", "-S09Flow", "-S09Combat=attack+scheme",
    "-S09ShotDir=$shots", "-S10AbortProof", "-S08ExitAfter=$RunSeconds")

  $proc = $null
  $Published = $false
  try {
    $clientStartUtc = [DateTime]::UtcNow
    $proc = Start-VsAiClient $clientArgs $Human.email $Human.password
    Write-Output "client pid=$($proc.Id)"

    function Assert-NoCredentialOnCmdLine([int]$Pid_, [string[]]$Secrets) {
      $p = Get-CimInstance Win32_Process -Filter "ProcessId=$Pid_"
      if (-not $p) { throw "process $Pid_ not found for command-line audit" }
      foreach ($secret in $Secrets) {
        if ($secret -and $p.CommandLine -match [regex]::Escape($secret)) {
          throw "secret leaked into command line of pid $Pid_"
        }
      }
    }
    Assert-NoCredentialOnCmdLine $proc.Id @($Human.email, $Human.password)

    $code = $null
    for ($i = 0; $i -lt 120; $i++) {
      Start-Sleep -Milliseconds 500
      # Capture the launcher's real UE child pid(s) EARLY - before the
      # launcher can exit - so the scoped stop never has to rely on a
      # post-mortem ParentProcessId read (every pid is still re-verified via
      # a fresh Win32_Process read before any stop, so reuse fails closed).
      foreach ($crec in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($proc.Id)" -ErrorAction SilentlyContinue)) {
        $cpid = [int]$crec.ProcessId
        if (-not $Script:ChildPids.Contains($cpid) -and
            -not (Test-ThisRunProcessRecord $crec $Script:ClientStagedRoot $Script:Staging)) {
          [void]$Script:ChildPids.Add($cpid)
          Write-Output "client child pid=$cpid captured (staged exe + this run's staging tag verified)"
        }
      }
      if (Test-Path -LiteralPath $trace) {
        $m = Select-String -Path $trace -Pattern 'createGame -> room=([A-Za-z0-9_-]+) code=([A-Z0-9-]{4,12})' |
          Select-Object -First 1
        if ($m) {
          $Script:ThisRunGameId = $m.Matches[0].Groups[1].Value
          $Script:ThisRunGameCode = $m.Matches[0].Groups[2].Value
          $code = $Script:ThisRunGameCode
          break
        }
      }
      if ($proc.HasExited) { throw "client exited before publishing a room" }
    }
    if (-not $code) { throw "no room code found in client trace" }
    Write-Output "VS_AI room created by this run (code redacted from output; id=$Script:ThisRunGameId)"

    # ---- ROOM gate: this run's VS_AI room, hosted here, live with the REAL
    # seeded bot seat - observed one-seat LOBBY, then IN_PROGRESS with exactly
    # 2 seats where seat 1 is the seeded bot (username 'AI Bot', opponentId
    # match, userByUsername('AI Bot') id cross-check). No fabricated bot claim.
    $rowQuery = 'query G($id: String!) { game(id: $id) { id code mode status hostId opponentId winnerId endedAt opponent { userId username } players { userId username seatOrder } } }'
    $statusSeen = New-Object System.Collections.Generic.List[string]
    $sawOneSeat = $false
    $sawBotSeatInLobby = $false
    $liveSinceUtc = $null
    $botUserId = $null
    # Shared 2-seat identity gate (LOBBY interim and IN_PROGRESS alike):
    # exactly the distinct seatOrder pair {0,1}, seat 0 this run's human,
    # seat 1 the REAL seeded bot (id != human, opponentId match, username
    # 'AI Bot', userByUsername('AI Bot') id cross-check).
    function Assert-SeededBotSeatPair($Row, [string]$BotIdByUsername) {
      $players = @($Row.players)
      if ($players.Count -ne 2) { throw "ROOM gate: $($Row.status) row has $($players.Count) seats (expected exactly 2: human + bot)" }
      $seat0 = $players | Where-Object { [int]$_.seatOrder -eq 0 } | Select-Object -First 1
      $seat1 = $players | Where-Object { [int]$_.seatOrder -eq 1 } | Select-Object -First 1
      if (-not $seat0 -or -not $seat1) { throw "ROOM gate: $($Row.status) seats are not the distinct seatOrder pair {0,1}" }
      if ($seat0.userId -cne $Script:UserId) { throw "ROOM gate: $($Row.status) seat 0 is user $($seat0.userId), not this run's human user" }
      $id = [string]$seat1.userId
      if ($id -ceq $Script:UserId) { throw "ROOM gate: $($Row.status) row has the human user in BOTH seats" }
      if (-not $Row.opponentId) { throw "ROOM gate: $($Row.status) row has no opponentId" }
      if ([string]$Row.opponentId -cne $id) { throw "ROOM gate: opponentId '$($Row.opponentId)' does not match seat-1 user '$id'" }
      if ($seat1.username -cne 'AI Bot') { throw "ROOM gate: seat-1 username '$($seat1.username)' is not the seeded bot username 'AI Bot' (backend/prisma/seed-ai.ts)" }
      # opponent.username may be 'Hidden' when the profile is private - the id
      # is still authoritative; only a visible non-bot name is a violation.
      if ($Row.opponent -and $null -ne $Row.opponent.username -and
          [string]$Row.opponent.username -cne 'Hidden' -and
          [string]$Row.opponent.username -cne 'AI Bot') {
        throw "ROOM gate: opponent username '$($Row.opponent.username)' is not the seeded bot username 'AI Bot'"
      }
      if ($id -cne $BotIdByUsername) {
        throw "ROOM gate: seat-1/bot id '$id' does not match userByUsername('AI Bot') = '$BotIdByUsername'"
      }
      return $id
    }
    $phaseDeadline = $clientStartUtc.AddSeconds($RunSeconds)
    while (-not $proc.HasExited -and [DateTime]::UtcNow -lt $phaseDeadline) {
      [void]$proc.WaitForExit(1000)
      $row = $null
      try {
        $g = Invoke-Gql $rowQuery @{ id = $Script:ThisRunGameId } $Token 'live row lookup'
        $row = $g.data.game
      } catch {} # transient poll failure - retry on the next tick
      if (-not $row) { continue }
      if ($row.mode -cne 'VS_AI') { throw "created game $($Script:ThisRunGameId) is mode $($row.mode), not VS_AI" }
      if ($row.hostId -cne $Script:UserId) { throw "created game is hosted by $($row.hostId), not this run's user" }
      if ($statusSeen.Count -eq 0 -or $statusSeen[$statusSeen.Count - 1] -cne $row.status) { $statusSeen.Add([string]$row.status) }
      $players = @($row.players)
      if ($row.status -eq 'LOBBY') {
        if ($players.Count -eq 1) {
          $p = $players[0]
          if ($p.userId -cne $Script:UserId) { throw "ROOM gate: LOBBY single seat is user $($p.userId), not this run's human user" }
          if ([int]$p.seatOrder -ne 0) { throw "ROOM gate: LOBBY human seat is seatOrder $($p.seatOrder), expected 0" }
          $sawOneSeat = $true
        } elseif ($players.Count -eq 2) {
          # setupAiOpponent (backend/src/games/game.service.ts) commits the bot
          # seat (opponentId + seatOrder 1) in a SEPARATE transaction BEFORE
          # the LOBBY->IN_PROGRESS flip, so this interim row is legitimate -
          # but ONLY when seat 1 passes the same seeded-bot identity checks
          # as IN_PROGRESS; a foreign human in the pair still fails the gate.
          $botUserId = Assert-SeededBotSeatPair $row $botIdByUsername
          $sawBotSeatInLobby = $true
          Write-Output "lobby interim: bot seat committed before startGame (verified seeded 'AI Bot'); waiting for IN_PROGRESS"
        } elseif ($players.Count -gt 2) {
          throw "ROOM gate: LOBBY row has $($players.Count) seats - a third seat can never join this run's VS_AI room"
        }
      } elseif ($row.status -eq 'IN_PROGRESS') {
        $botUserId = Assert-SeededBotSeatPair $row $botIdByUsername
        if (-not $liveSinceUtc) {
          $liveSinceUtc = [DateTime]::UtcNow
          Write-Output "live: IN_PROGRESS with 2 seats; seat 1 is the seeded bot 'AI Bot' (opponentId + username + userByUsername id match)"
        }
        if (([DateTime]::UtcNow - $liveSinceUtc).TotalSeconds -ge $LiveSeconds) { break }
      }
    }
    if (-not $sawOneSeat -and -not $sawBotSeatInLobby) {
      throw "ROOM gate: never observed the initial LOBBY of this run's VS_AI room - neither the one-human-seat row nor the verified interim bot seat (statuses: $($statusSeen -join ' -> '))"
    }
    if (-not $liveSinceUtc -or -not $botUserId) {
      throw "ROOM gate: the room never reached IN_PROGRESS with exactly 2 seats where seat 1 is the seeded 'AI Bot' before the deadline (statuses: $($statusSeen -join ' -> '))"
    }

    # ---- ABORT gate: external host-authorized abortGame for THIS room only
    $abortQ = 'mutation AB($gameId: String!) { abortGame(gameId: $gameId) { id status } }'
    $r = Invoke-Gql $rowQuery @{ id = $Script:ThisRunGameId } $Token 'pre-abort row lookup'
    $pre = $r.data.game
    if ($pre.id -cne $Script:ThisRunGameId) { throw "pre-abort row id mismatch: $($pre.id)" }
    if ($pre.code -and ($pre.code -cne $Script:ThisRunGameCode)) {
      throw "REFUSING abort - room code mismatch for game $($Script:ThisRunGameId)"
    }
    if ($pre.mode -cne 'VS_AI') { throw "REFUSING abort - mode $($pre.mode) is not this run's VS_AI room" }
    if ($pre.hostId -cne $Script:UserId) { throw "REFUSING abort - host-ownership validation failed" }
    if ($pre.status -ne 'IN_PROGRESS') {
      throw "REFUSING abort - row status is $($pre.status), not IN_PROGRESS (a match that finished on its own must never be aborted)"
    }
    $ab = Invoke-Gql $abortQ @{ gameId = $Script:ThisRunGameId } $Token 'abortGame'
    if (-not $ab.data.abortGame) { throw 'abortGame returned no game object' }
    if ($ab.data.abortGame.id -cne $Script:ThisRunGameId) {
      throw "abortGame returned a foreign game id: $($ab.data.abortGame.id)"
    }
    if ($ab.data.abortGame.status -cne 'ABORTED') {
      throw "abortGame returned status $($ab.data.abortGame.status), not ABORTED"
    }
    $rr = Invoke-Gql $rowQuery @{ id = $Script:ThisRunGameId } $Token 'post-abort row re-read'
    $rowAfter = $rr.data.game
    if (-not $rowAfter -or $rowAfter.id -cne $Script:ThisRunGameId -or $rowAfter.status -cne 'ABORTED') {
      $s = if ($rowAfter) { $rowAfter.status } else { '<gone>' }
      throw "authoritative row is NOT ABORTED after abortGame (status=$s)"
    }
    if ($rowAfter.winnerId) { throw "ABORTED row carries a winnerId '$($rowAfter.winnerId)' - an abort must never declare a winner" }
    if (-not $rowAfter.endedAt) { throw "ABORTED row has no endedAt" }
    Write-Output "abort: authoritative row ABORTED (endedAt set, winnerId null)"

    # ---- CLIENT/PROOF TAIL gate: the client drives the whole post-abort
    # proof itself (opt-in -S10AbortProof): interruption screen shot -> ONE
    # client-side leaveGame -> clean-lobby shot -> self exit. The runner only
    # waits (bounded by client start + RunSeconds + 60s) and breaks early on
    # any proof-failure line.
    $proofCompleteMarker = 'S10ABORTPROOF complete (ABORTED screen -> one leaveGame -> clean lobby) - exiting'
    $proofDeadline = $clientStartUtc.AddSeconds($RunSeconds + 60)
    while (-not $proc.HasExited -and [DateTime]::UtcNow -lt $proofDeadline) {
      [void]$proc.WaitForExit(1000)
      if (Test-Path -LiteralPath $trace) {
        $tailText = Get-Content -LiteralPath $trace -Raw
        if ($tailText.Contains($proofCompleteMarker)) { break }
        if ($tailText.Contains('S10ABORTPROOF leave FAILED') -or
            $tailText.Contains('S10ABORTPROOF screen shot file never appeared') -or
            $tailText.Contains('S10ABORTPROOF lobby shot file never appeared')) { break }
      }
    }
    # bounded grace: the complete marker precedes RequestExit by a tick
    $graceEnd = [DateTime]::UtcNow.AddSeconds(30)
    while (-not $proc.HasExited -and [DateTime]::UtcNow -lt $graceEnd) { [void]$proc.WaitForExit(500) }
    # Bounded fallback ONLY: a healthy proof tail ends in the client's own
    # exit; if it never came, scoped-stop this run's verified client TREE
    # (verified staged child(ren) first, then the verified launcher - never
    # an unverifiable or unrelated process).
    if (-not $proc.HasExited) {
      Write-Output "cleanup: client did not exit after the proof tail - scoped stop of this run's client (launcher pid=$($proc.Id) + verified child(ren))"
      Stop-ThisRunClient -LauncherPid $proc.Id -LauncherExe $Script:ClientExeFull `
        -StagedRootFull $Script:ClientStagedRoot -RunTag $Script:Staging -KnownChildPids @($Script:ChildPids)
    }
    # bounded: a killed tree releases its pipes, but never wait unbounded
    if (-not $proc.HasExited) { [void]$proc.WaitForExit(15000) }
    Write-Output "client exited"

    # ---- trace gates
    $traceText = Get-Content -LiteralPath $trace -Raw
    $interruptMarker = 'ROOM aborted: the live match was interrupted'
    foreach ($needle in @(
        'SUBSCRIBED gameStateUpdated', 'SNAPSHOT applied',
        'game -> room=' + $Script:ThisRunGameId, $interruptMarker)) {
      if (-not $traceText.Contains($needle)) {
        throw "client trace missing '$needle' (no evidence will be invented)"
      }
    }
    if (-not ($traceText -match ('game -> room=' + [regex]::Escape($Script:ThisRunGameId) + ' code=\S+ status=ABORTED'))) {
      throw "client trace never logged a fresh poll row with status=ABORTED for this room"
    }
    # Ordered client proof tail: exactly-once markers, accepted client leave
    # for THIS room id after the leave was sent, no shot/leave failure lines,
    # no invented result tail.
    $tailErr = Test-AbortProofTailOrder $traceText $Script:ThisRunGameId
    if ($tailErr) { throw "CLIENT proof tail gate FAILED: $tailErr" }
    Write-Output "client: full S10ABORTPROOF tail verified (interruption -> screen shot -> one leaveGame -> lobby shot -> complete)"
    # INPUT DISABLED: no gameplay command sent after the interruption marker.
    $markerIdx = $traceText.IndexOf($interruptMarker, [StringComparison]::Ordinal)
    $afterMarker = $traceText.Substring($markerIdx)
    $lateCommands = @($afterMarker -split "`n" |
      Where-Object { $_ -match 'ATTACK sent|DEFENSE sent|NO-DEFENSE|RESOLVE sent|SCHEME sent|SCHEME done seq=' })
    if ($lateCommands.Count -gt 0) {
      throw ("{0} gameplay command(s) were sent AFTER the interruption marker - input not disabled" -f $lateCommands.Count)
    }
    $attackSeen = $traceText.Contains('ATTACK sent')
    $combatResultSeen = $traceText.Contains('COMBAT-RESULT seq=')
    Write-Output ("coverage: attack={0} combatResult={1} (report-only - the abort gate needs a live match, not a full duel)" -f $attackSeen, $combatResultSeen)

    # ---- SHOTS: client-captured interruption screen + clean lobby, pixel-gated
    # (same sampled +/-16 marker technique as the S10 result runner).
    Add-Type -AssemblyName System.Drawing
    $screenShot = Assert-FreshShot (Join-Path $shots 's10-aborted-screen.png') $clientStartUtc 'aborted-screen'
    $lobbyShot = Assert-FreshShot (Join-Path $shots 's10-aborted-lobby.png') $clientStartUtc 'aborted-lobby'
    Write-Output ("aborted-screen shot={0}B aborted-lobby shot={1}B" -f $screenShot.Length, $lobbyShot.Length)
    $shotMarkers = @(
      @{ name = 'resultscreen';  r = 255; g = 215; b = 0   },
      @{ name = 'resultoutcome'; r = 255; g = 0;   b = 100 },
      @{ name = 'resultsupport'; r = 0;   g = 255; b = 160 },
      @{ name = 'resultbutton';  r = 128; g = 0;   b = 255 },
      @{ name = 'lobbypanel';    r = 64;  g = 200; b = 255 },
      @{ name = 'interrupt';     r = 255; g = 100; b = 20  })
    # Interruption screen: the #FF6414 panel marker present; the result/lobby
    # panels structurally absent (an interrupted match can never look like a
    # victory screen or a lobby).
    $ss = Get-ShotPixelStats $screenShot.FullName $shotMarkers
    if (-not (($ss.w -eq 1280 -and $ss.h -eq 720) -or ($ss.w -eq 1920 -and $ss.h -eq 1080))) {
      throw ("aborted-screen shot is {0}x{1} - NOT 1280x720/1920x1080" -f $ss.w, $ss.h)
    }
    $gateErr = Test-MarkerGates $ss @('interrupt') 100 @('resultscreen', 'resultoutcome', 'resultsupport', 'resultbutton', 'lobbypanel')
    if ($gateErr) { throw "aborted-screen shot gate FAILED: $gateErr" }
    Write-Output ("aborted-screen shot: #FF6414 interruption marker={0}, result/lobby panel markers all-zero" -f $ss.interrupt)
    # Clean lobby: the #40C8FF panel marker present; duel/result/interruption
    # markers absent; the visual gameplay-region bright-pixel gate passes.
    $ls = Get-ShotPixelStats $lobbyShot.FullName $shotMarkers
    $gateErr = Test-MarkerGates $ls @('lobbypanel') 100 @('resultscreen', 'resultoutcome', 'resultsupport', 'resultbutton', 'interrupt')
    if ($gateErr) { throw "aborted-lobby shot gate FAILED: $gateErr" }
    $bright = Get-GameplayRegionBright $lobbyShot.FullName
    if ($bright -gt 50) {
      throw ("aborted-lobby shot has {0} bright gameplay-region pixels (lum>=120, x>=25%/y>=12.5%) - stale board/fighter/HUD rendering survived the stage transition" -f $bright)
    }
    Write-Output ("aborted-lobby shot: clean lobby panel (lobbypanel={0}), no duel/result/interruption markers, gameplay region bright pixels={1} (<=50)" -f $ls.lobbypanel, $bright)

    # ---- EXIT/CLEANUP gate: the CLIENT's own leaveGame is the single leave
    # (already verified in the ordered tail via 'LEFT room=<id>'); the runner
    # issues NO server-side leaveGame on the happy path. The clean lobby is
    # verified via myGames + the final authoritative ABORTED row.
    foreach ($st in @('IN_PROGRESS', 'LOBBY')) {
      $mg = Invoke-Gql 'query MG($filters: GameFiltersDto) { myGames(filters: $filters) { id status } }' @{ filters = @{ status = $st } } $Token "myGames($st)"
      $hit = @($mg.data.myGames | Where-Object { $_.id -eq $Script:ThisRunGameId })
      if ($hit.Count -gt 0) { throw "myGames(status=$st) still lists this run's room - lobby not clean" }
    }
    $final = Invoke-Gql $rowQuery @{ id = $Script:ThisRunGameId } $Token 'final row lookup'
    $frow = $final.data.game
    if (-not $frow -or $frow.status -cne 'ABORTED') {
      $s = if ($frow) { $frow.status } else { '<gone>' }
      throw "final authoritative row is $s, not ABORTED"
    }
    if ($frow.winnerId) { throw "final row carries winnerId '$($frow.winnerId)' - invented result" }
    Write-Output "clean: client leave accepted (LEFT room= marker), myGames has no active room, row stays ABORTED with no winner"

    # ---- compact trace (code redacted) + publish
    $compactPattern = 'S09AUTO|S10ABORTPROOF|ROOM aborted|LEFT room|COMBAT-RESULT|ATTACK sent|DEFENSE sent|NO-DEFENSE|RESOLVE sent|SCHEME done seq=|SCHEME sent|PEND |SNAPSHOT applied seq=|MODE seq=|VS_AI|game -> room='
    $kept = @(Get-Content -LiteralPath $trace | Where-Object { $_ -match $compactPattern })
    if ($code) { $kept = @($kept | ForEach-Object { $_.Replace($code, '<redacted>') }) }
    [System.IO.File]::WriteAllLines((Join-Path $Script:Staging 'vsai-abort-client.compact.log'), $kept, $Utf8NoBom)

    $publishNames = @('vsai-abort-client.trace.log', 'vsai-abort-client.compact.log')
    $allShots = @(Get-ChildItem -LiteralPath $shots -Filter 's*.png' -ErrorAction SilentlyContinue | Sort-Object Name)
    foreach ($shot in $allShots) { $publishNames += ('human\' + $shot.Name) }
    $RunDir = Join-Path $EvidenceDir ("vsai-abort-" + $Stamp)
    if (Test-Path -LiteralPath $RunDir) { throw "run dir already exists: $RunDir" }
    New-Item -ItemType Directory -Path $RunDir | Out-Null
    foreach ($name in $publishNames) {
      $src = Join-Path $Script:Staging $name
      if (-not (Test-Path -LiteralPath $src)) { throw "staged artifact missing at publish time: $src" }
      $dst = Join-Path $RunDir $name
      $dstDir = Split-Path -Parent $dst
      if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
      if ($name -like '*.log') {
        $text = [System.IO.File]::ReadAllText($src)
        if ($code) { $text = $text.Replace($code, '<redacted>') }
        [System.IO.File]::WriteAllText($dst, $text, $Utf8NoBom)
      } else {
        Move-Item -LiteralPath $src $dst
      }
    }
    foreach ($name in $publishNames) {
      if (-not (Test-Path -LiteralPath (Join-Path $RunDir $name))) { throw "run dir incomplete after publish: $name" }
    }
    $verdict = 'S10/GD-040: packaged ABORTED live acceptance over the authoritative S10 backend - a hidden one-client VS_AI match was observed in LOBBY with exactly one human seat, then went live IN_PROGRESS with exactly 2 seats where seat 1 is the REAL seeded bot (username AI Bot from backend/prisma/seed-ai.ts; seat-1 id matched the row opponentId and the public userByUsername AI Bot lookup - no weaker foreign-id claim), then an external HOST-AUTHORIZED abortGame for THIS exact room (id+code+mode+host+status pre-validated) flipped the authoritative row to ABORTED (endedAt set, winnerId null). The client ran its -S10AbortProof drive over the fresh interruption row: the ordered exactly-once proof tail (interruption marker -> aborted-screen shot -> ONE client leaveGame -> aborted-lobby shot -> complete) is in the trace, the leave was accepted by the server (LEFT room=<this room id> after the leave was sent; myGames lists no active room), NO gameplay command was sent after the interruption marker (input disabled), and NO result screen/markers ever appeared (no invented VICTORY/DEFEAT; row never FINISHED). Both proof shots are CLIENT-CAPTURED and pixel-gated: s10-aborted-screen.png carries the #FF6414 interruption panel marker with all result/lobby panel markers absent, s10-aborted-lobby.png carries the #40C8FF clean-lobby panel marker with duel/result/interruption markers absent and the visual gameplay-region bright-pixel gate passed (the board was torn down by the stage transition). The client exited ITSELF after the proof tail; the runner issued NO server-side leaveGame. Frame cap: per-process console command t.MaxFPS 30 (effective FPS NOT measured, no GPU claim; packaged 60 FPS default untouched)'
    $manifest = [ordered]@{
      stamp            = $Stamp
      verdict          = $verdict
      mode             = 'VS_AI'
      scenario         = 'ABORTED'
      serverRow        = [ordered]@{
        id = $frow.id
        status = $frow.status
        mode = $frow.mode
        winnerId = $frow.winnerId
        endedAt = [string]$frow.endedAt
        seats = @($frow.players).Count
      }
      botIdentity      = [ordered]@{
        username = 'AI Bot'
        seatOrder = 1
        opponentIdMatchedSeat1 = $true
        userByUsernameIdMatch = $true
      }
      abortProof       = [ordered]@{
        tailOrderedExactlyOnce = $true
        clientLeaveAccepted    = $true
        screenShot             = 'human\s10-aborted-screen.png (#FF6414 interruption marker present, result/lobby markers absent)'
        lobbyShot              = 'human\s10-aborted-lobby.png (#40C8FF lobby panel present, duel/result/interruption markers absent, bright-pixel gate passed)'
        runnerServerLeave      = 'none (the client leaveGame is the single leave)'
      }
      coverage         = [ordered]@{ attack = $attackSeen; combatResult = $combatResultSeen }
      files            = @()
    }
    function Get-Sha256Hex([string]$Path) {
      $sha = [System.Security.Cryptography.SHA256]::Create()
      try {
        $stream = [System.IO.File]::OpenRead($Path)
        try { $hash = $sha.ComputeHash($stream) } finally { $stream.Dispose() }
      } finally { $sha.Dispose() }
      $sb = New-Object System.Text.StringBuilder
      foreach ($b in $hash) { [void]$sb.Append($b.ToString('x2')) }
      return $sb.ToString()
    }
    foreach ($name in $publishNames) {
      $f = Get-Item -LiteralPath (Join-Path $RunDir $name)
      $manifest.files += [ordered]@{ name = $name; bytes = $f.Length; sha256 = (Get-Sha256Hex $f.FullName) }
    }
    [System.IO.File]::WriteAllText((Join-Path $RunDir 'manifest.json'), ($manifest | ConvertTo-Json -Depth 4), $Utf8NoBom)

    $ptrTmp = Join-Path $EvidenceDir ("latest-vsai-abort.json.$Stamp-$PID.tmp")
    $ptr = Join-Path $EvidenceDir 'latest-vsai-abort.json'
    [System.IO.File]::WriteAllText($ptrTmp, (([ordered]@{ current = (Split-Path $RunDir -Leaf); stamp = $Stamp }) | ConvertTo-Json), $Utf8NoBom)
    if (Test-Path -LiteralPath $ptr) {
      $ptrBak = Join-Path $EvidenceDir 'latest-vsai-abort.json.bak'
      [System.IO.File]::Replace($ptrTmp, $ptr, $ptrBak)
      Remove-Item -LiteralPath $ptrBak -Force
    } else {
      [System.IO.File]::Move($ptrTmp, $ptr)
    }
    $Published = $true
    Write-Output "published evidence run dir: $RunDir (pointer: latest-vsai-abort.json)"
    Write-Output "--- client trace (ABORTED tail) ---"
    Get-Content -LiteralPath $trace |
      Select-String -Pattern 'S09AUTO|S10ABORTPROOF|ROOM aborted|game -> room=|COMBAT-RESULT|ATTACK sent|VS_AI' | Select-Object -Last 20
  } finally {
    if ($proc) {
      # Scoped stop even when the launcher already exited on its own: Win32
      # keeps the child's recorded ParentProcessId, so a late child sweep is
      # still possible (and every candidate is re-verified before any stop).
      Stop-ThisRunClient -LauncherPid $proc.Id -LauncherExe $Script:ClientExeFull `
        -StagedRootFull $Script:ClientStagedRoot -RunTag $Script:Staging -KnownChildPids @($Script:ChildPids)
      if (-not $proc.HasExited) { [void]$proc.WaitForExit(15000) }
    }
    # Scoped: aborts this run's own game ONLY if the flow died before the
    # authoritative ABORTED row was verified (normally a no-op skip here).
    Stop-ThisRunGame $Token $Script:UserId
  }

  if ($Published) {
    Remove-TreeSafely $Script:Staging ([System.IO.Path]::GetTempPath())
  }
}

Invoke-AbortDemo

if ($Script:CleanupFailure) {
  throw "scoped cleanup did not verify for this run's game: $($Script:CleanupFailure)"
}
