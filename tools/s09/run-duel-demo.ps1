param(
  [string]$Exe = "",
  [string]$Api = "http://localhost:3120/graphql",
  [string]$EvidenceDir = "",
  [int]$RunSeconds = 480,
  [string]$ShotMode = "request",
  [string]$EnvFile = "",
  # Fail fast when a seat is subscribed but no fresh 'SNAPSHOT applied' line
  # appears for it (per seat) for this many seconds (the 2026-09-27 packaged
  # run stalled silently at seq 1 for the full timeout). 0 disables it.
  [int]$StallSeconds = 90,
  # Script-level probe of the per-seat watchdog logic only (no clients, no
  # exe, no credentials): runs synthetic trace states and exits non-zero on a
  # wrong verdict.
  [switch]$ProbeWatchdog,
  # VS-4 HB-48 (docs/game-design/visual/04-hud-spec.md s5.3): the rollback of the gate - both clients get -S09Markers
  # and the result / lobby marker pixel gates run as before. Without it (the default since HB-48) the result screen is
  # gated by the trace (RESULT summary + 'RESULT view mode=results' before the shot) and its SHOT widget lines
  # (UI-SCR-GAME state=over, no gameplay block of the HUD visible), the lobby shot by SHOT widget (no UI-HUD block
  # visible) - the GAMEOVER and LOBBY screens are still Slate until VS-7 (screens.csv) - plus the privacy rules over both
  # traces. VS-7 Frames (ВР-VS7-68, ВР-VS7-77): since SC-02 the menu backdrop (the Marmoreal K1 scene without figures)
  # lies behind the lobby, so the bright gameplay-region pixel gate of the lobby shot runs with -S09Markers only; the
  # default gate reads the trace instead - after 'LEFT room=' the menu backdrop is back with 'fighters=0' (no stale
  # board / fighter of the match survived the lobby return).
  [switch]$S09Markers,
  # VS-4 HB-48 (opt-in): the board row of the room (-S08BoardId on the host, verified on the game row; empty = the
  # backend default board, Marmoreal original) and extra client arguments for BOTH clients, '+'-separated.
  [string]$BoardId = '',
  [string]$ClientExtraArgs = ''
)
# GD-036 two-client packaged FULL-DUEL demo against the S09 worktree-local
# backend. Both clients play the whole duel through the S09AUTO driver
# (maneuver / attack / defense / resolve / schemes / pending answers) until
# the authoritative server writes GAME_OVER, then the built-in result tail
# runs on each seat: result screen shot (#FFD700 marker) -> leaveGame ->
# lobby-arrival shot -> early RequestExit (the 10:37 lesson: never burn the
# full timeout after the evidence exists).
# GATES (all must pass before evidence is published):
#   - BOTH traces saw 'RESULT seq=' with a derived outcome, exactly one
#     VICTORY and one DEFEAT across the two seats (server winnerId projected
#     to both viewers; winner parse is covered by Unmatched.S09.RESULT tests);
#   - both: 'RESULT lobby-return sent (leaveGame)' + 'duel flow complete';
#   - s09-result-screen.png + s09-lobby-return.png on BOTH seats, fresh and
#     non-trivial; result screen passes the #FFD700 marker gate with all
#     gameplay state markers absent (no draft/pending/combat UI over result);
#   - lobby shots pass the VISUAL gameplay-region gate: zero bright pixels
#     (lum >= 120) in x >= 25% / y >= 12.5% (marker-only checks missed the
#     stale board/fighter actors of the 2026-09-27 first duel - the 3D scene
#     carries none of the UI marker colors);
#   - SERVER row check: FINISHED observed live AND a POST-LEAVE authoritative
#     lookup REQUIREs the row to still exist, be FINISHED, carry winnerId and
#     BOTH seats (leaveGame no longer deletes a terminal row); never ABORTED
#     (a presented victory may not come from an abort path). User stats are
#     sampled before/after and checked against the winner/loser ELO formula;
#   - traces privacy-clean (no card ids with combat commands), room code
#     redacted everywhere, seq convergence, full-duel coverage lines
#     (ATTACK sent / DEFENSE-or-NO-DEFENSE / RESOLVE sent observed).
# Safety: per-process ENV credentials only, hidden clients, staged evidence
# published only after every assertion passed, scoped host-ownership-validated
# abort of THIS run's game (only when the duel did NOT finish on its own).
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'HudShotGate.ps1')  # VS-4 HB-48
if ($BoardId -and $BoardId -cnotmatch '^c[a-z0-9]{24}$') { throw "BoardId '$BoardId' is not a Board row id (cuid)" }
if (-not $Exe) { $Exe = Join-Path $RepoRoot 'unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe' }
if (-not $EvidenceDir) { $EvidenceDir = Join-Path $RepoRoot 'docs\game-design\evidence\S09\run' }

# Per-seat stall watchdog state and evaluation (S10 review P2: the old
# any-seat arming/disarming violated the two-seat contract - a watchdog armed
# by ONE seat's subscription was silenced by the OTHER seat's progress or
# terminal line, letting a dead seat ride along to the full timeout).
function New-SeatWatchdogState {
  return @{ subscribed = $false; terminal = $false; lastSeq = -1;
            lastProgressUtc = [DateTime]::UtcNow }
}

function Update-SeatWatchdog {
  # Mutates $State in place from one poll's trace text; returns $true when
  # THIS seat is stalled (subscribed, not terminal, no fresh 'SNAPSHOT
  # applied seq=' for $StallSeconds).
  param([hashtable]$State, [string]$Text, [datetime]$NowUtc, [int]$StallSeconds)
  if ($Text.Contains('RESULT seq=')) { $State.terminal = $true; return $false }
  if ($State.terminal) { return $false }
  if (-not $State.subscribed) {
    if ($Text.Contains('SUBSCRIBED gameStateUpdated')) {
      $State.subscribed = $true
      $State.lastProgressUtc = $NowUtc
    }
    return $false
  }
  $maxSeq = -1
  foreach ($m in [regex]::Matches($Text, 'SNAPSHOT applied seq=(\d+)')) {
    $s = [int]$m.Groups[1].Value
    if ($s -gt $maxSeq) { $maxSeq = $s }
  }
  if ($maxSeq -gt $State.lastSeq) {
    $State.lastSeq = $maxSeq
    $State.lastProgressUtc = $NowUtc
    return $false
  }
  return (($NowUtc - $State.lastProgressUtc).TotalSeconds -gt $StallSeconds)
}

function Invoke-WatchdogProbe {
  # Script-level proof of the per-seat contract without clients. Exit code
  # carries the verdict; output documents each scenario.
  $failures = 0

  # 1) One seat streaming, the other subscribed-but-stale: the STALE seat
  #    must trip even though the other one keeps making progress (the old
  #    any-seat progress reset masked exactly this).
  $healthy = New-SeatWatchdogState
  $dead = New-SeatWatchdogState
  $t0 = [DateTime]::UtcNow
  $healthyText = 'SUBSCRIBED gameStateUpdated since=0'
  $deadText = 'SUBSCRIBED gameStateUpdated since=0'
  foreach ($seat in @($healthy, $dead)) { [void](Update-SeatWatchdog $seat $deadText $t0 90) }
  for ($i = 1; $i -le 6; $i++) {
    $now = $t0.AddSeconds(20 * $i)
    $healthyText += "`nSNAPSHOT applied seq=$i"
    $h = Update-SeatWatchdog $healthy $healthyText $now 90
    $d = Update-SeatWatchdog $dead $deadText $now 90
    if ($i -le 4 -and ($h -or $d)) {
      Write-Output "PROBE1 FAIL: false stall at step $i (healthy=$h dead=$d)"; $failures++
      break
    }
    if ($i -ge 5 -and -not $d) {
      Write-Output "PROBE1 FAIL: dead seat (subscribed, seq never advanced past 0, >90s) was NOT flagged at step $i"; $failures++
      break
    }
    if ($i -ge 5 -and $h) {
      Write-Output "PROBE1 FAIL: healthy seat flagged at step $i"; $failures++
      break
    }
  }
  if ($failures -eq 0) { Write-Output 'PROBE1 ok: stalled seat trips while the streaming seat does not (per-seat progress)' }

  # 2) A seat's OWN terminal line disarms only THAT seat: the terminal seat
  #    goes silent forever without tripping; the live seat still trips on its
  #    own stall.
  $terminal = New-SeatWatchdogState
  $live = New-SeatWatchdogState
  $t0 = [DateTime]::UtcNow
  $terminalText = "SUBSCRIBED gameStateUpdated since=0`nSNAPSHOT applied seq=9`n RESULT seq=9 outcome=VICTORY winner=X"
  $liveText = 'SUBSCRIBED gameStateUpdated since=0'
  foreach ($seat in @($terminal, $live)) { [void](Update-SeatWatchdog $seat 'SUBSCRIBED gameStateUpdated since=0' $t0 90) }
  $tripped = $false
  for ($i = 1; $i -le 6; $i++) {
    $now = $t0.AddSeconds(20 * $i)
    if (Update-SeatWatchdog $terminal $terminalText $now 90) {
      Write-Output 'PROBE2 FAIL: TERMINAL seat tripped after its own RESULT line (must disarm per seat)'; $failures++
      break
    }
    if (Update-SeatWatchdog $live $liveText $now 90) { $tripped = $true }
  }
  if (-not $tripped) {
    Write-Output 'PROBE2 FAIL: live seat never tripped after 120s of no progress'; $failures++
  } elseif ($failures -eq 0) {
    Write-Output 'PROBE2 ok: terminal disarm is per seat; the quiet live seat still trips'
  }

  # 3) Unsubscribed seat never trips (subscription is the arming condition).
  $cold = New-SeatWatchdogState
  $t0 = [DateTime]::UtcNow
  $tripped = $false
  for ($i = 1; $i -le 6; $i++) {
    if (Update-SeatWatchdog $cold 'BOOT' $t0.AddSeconds(20 * $i) 90) { $tripped = $true }
  }
  if ($tripped) { Write-Output 'PROBE3 FAIL: unsubscribed seat tripped'; $failures++ }
  elseif ($failures -eq 0) { Write-Output 'PROBE3 ok: no subscription -> no arming' }

  if ($failures -gt 0) { throw "watchdog probe failed ($failures failure(s))" }
  Write-Output 'watchdog probe: all per-seat scenarios verified'
}

if ($ProbeWatchdog) {
  Invoke-WatchdogProbe
  exit 0
}

function Set-StagedResolution([string]$ExePath, [int]$W, [int]$H) {
  $gsDir = Join-Path (Split-Path -Parent $ExePath) 'Unmatched\Saved\Config\Windows'
  New-Item -ItemType Directory -Force -Path $gsDir | Out-Null
  $gs = Join-Path $gsDir 'GameUserSettings.ini'
  # Resolution keys only (the packaged build honors the SAVED resolution, not
  # -resx/-resy). NO FrameRateLimit here: the 2026-09-27 run wrote 30 into the
  # staged file, but the key was absent after the run (unverified effect) and a
  # persisted value can override the packaged default of 60 outside the demo.
  # The frame cap is per-process via -ExecCmds="t.MaxFPS 30" instead; actual
  # effective FPS is NOT claimed without measurement.
  $section = '[/Script/Engine.GameUserSettings]'
  $wanted = [ordered]@{
    'ResolutionSizeX'                   = $W
    'ResolutionSizeY'                   = $H
    'LastUserConfirmedResolutionSizeX'  = $W
    'LastUserConfirmedResolutionSizeY'  = $H
    'FullscreenMode'                    = 1
    'LastConfirmedFullscreenMode'       = 1
    'PreferredFullscreenMode'           = 1
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
Set-StagedResolution $Exe 1280 720

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Script:CleanupFailure = $null

function Assert-GqlOk($Response, [string]$What) {
  if (-not $Response) { throw "$What returned an empty response" }
  $errs = @()
  if ($Response.PSObject.Properties['errors'] -and $null -ne $Response.errors) {
    $errs = @($Response.errors)
  }
  if ($errs.Count -gt 0) {
    $msgs = ($errs | ForEach-Object { $_.message }) -join '; '
    throw "$What returned GraphQL errors over HTTP 200: $msgs"
  }
  if (-not $Response.data) { throw "$What returned neither data nor errors" }
}

function Get-Hero([string]$Email, [string]$Password, [string]$Name) {
  $loginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken } }'; variables = @{ input = @{ email = $Email; password = $Password } } } | ConvertTo-Json -Depth 5
  $login = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBody
  if (-not $login.data.login.accessToken) { throw "login failed for the configured host account" }
  $listBody = @{ query = 'query HL { heroList(limit: 200) { items { id name } } }' } | ConvertTo-Json
  $list = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers @{ authorization = "Bearer $($login.data.login.accessToken)" } -Body $listBody
  $hero = $list.data.heroList.items | Where-Object { $_.name -eq $Name } | Select-Object -First 1
  if (-not $hero) { $hero = $list.data.heroList.items[0] }
  return $hero.id
}

function Start-S09Client([string[]]$CliArgs, [string]$Email, [string]$Password, [string]$RoomCode = '') {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $Exe
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
  foreach ($arg in $CliArgs) {
    # ExecCmds needs quotes around its value so UE reads the full console command.
    if ($arg -match '^-ExecCmds=') { $psi.Arguments += $arg + ' ' }
    elseif ($arg -match '\s') { $psi.Arguments += '"' + $arg + '" ' } else { $psi.Arguments += $arg + ' ' }
  }
  $psi.EnvironmentVariables['S08_EMAIL'] = $Email
  $psi.EnvironmentVariables['S08_PASSWORD'] = $Password
  if ($RoomCode) { $psi.EnvironmentVariables['S08_ROOM_CODE'] = $RoomCode }
  return [System.Diagnostics.Process]::Start($psi)
}

function Stop-ThisRunGame {
  if (-not $Script:ThisRunGameId) {
    Write-Output "cleanup: no game was created by this run - nothing to abort"
    return
  }
  try {
    $loginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }'; variables = @{ input = @{ email = $AccountA.email; password = $AccountA.password } } } | ConvertTo-Json -Depth 5
    $login = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBody
    Assert-GqlOk $login 'cleanup login'
    $token = $login.data.login.accessToken
    $uid = $login.data.login.user.id
    $headers = @{ authorization = "Bearer $token" }
    $q = @{ query = 'query G($id: String!) { game(id: $id) { id code status hostId } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
    $g = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $q
    $lookupErrors = @()
    if ($g.PSObject.Properties['errors'] -and $null -ne $g.errors) { $lookupErrors = @($g.errors) }
    $notFound = @($lookupErrors | Where-Object { $_.message -match 'не найдена|not found' }).Count -gt 0
    if ($notFound) {
      # Terminal rows are PRESERVED after leaveGame now; a 404 here means an
      # unexpected deletion - reported (the post-leave gate already required
      # the FINISHED row with winner + both seats, so evidence is not affected).
      Write-Output "cleanup: game $($Script:ThisRunGameId) no longer resolves (UNEXPECTED for a terminal row - leaveGame preserves FINISHED rows) - nothing to abort"
      return
    }
    Assert-GqlOk $g 'cleanup game lookup'
    $game = $g.data.game
    if (-not $game) { Write-Output "cleanup: game $($Script:ThisRunGameId) no longer resolves - nothing to abort"; return }
    if ($Script:ThisRunGameCode -and $game.code -and ($game.code -cne $Script:ThisRunGameCode)) {
      throw "REFUSING abort - room code mismatch for game $($Script:ThisRunGameId)"
    }
    # A duel that reached GAME_OVER on its own is FINISHED: leaveGame (already
    # sent by both clients) is the regular exit and must NEVER be aborted; the
    # FINISHED row (winner + both seats) stays for history/recovery.
    # Ownership is NOT asserted for a FINISHED row: the deployed backend's
    # leaveGame transfers hostId to the opponent when the host leaves a
    # FINISHED room, so hostId here may legitimately be the joiner's uid.
    if ($game.status -eq 'FINISHED') {
      Write-Output "cleanup: game $($Script:ThisRunGameId) is FINISHED - duel completed on its own, no abort (hostId may have been transferred by leaveGame)"
      return
    }
    if ($game.hostId -cne $uid) {
      throw "REFUSING abort - host-ownership validation failed for game $($Script:ThisRunGameId)"
    }
    if (@('ABORTED', 'COMPLETED') -contains $game.status) {
      Write-Output "cleanup: game $($Script:ThisRunGameId) already terminal ($($game.status))"
      return
    }
    $a = @{ query = 'mutation AB($gameId: String!) { abortGame(gameId: $gameId) { id status } }'; variables = @{ gameId = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
    $abortErr = $null
    try {
      $r = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $a
      Assert-GqlOk $r 'cleanup abortGame'
    } catch {
      $abortErr = $_.Exception.Message
    }
    if ($abortErr) {
      # The deployed backend's game-lookup cache can still serve a stale
      # non-terminal status while the row is already FINISHED; the server's
      # 'a completed game cannot be aborted' rejection IS an authoritative
      # terminal verdict. Re-read the row on ANY abort failure and accept a
      # FINISHED row as success (the text match is encoding-unsafe here).
      $g2 = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $q
      Assert-GqlOk $g2 'cleanup post-reject verification'
      $after = $g2.data.game
      $afterStatus = if ($after) { $after.status } else { '<gone>' }
      if ($afterStatus -eq 'FINISHED') {
        Write-Output "cleanup: abortGame rejected and the row reads FINISHED - duel completed on its own (server-authoritative terminal verdict)"
        return
      }
      throw "abortGame rejected ('$abortErr') and the row is not FINISHED (status=$afterStatus)"
    }
    if (-not $r.data.abortGame) { throw 'abortGame returned no game object' }
    if ($r.data.abortGame.id -cne $Script:ThisRunGameId) {
      throw "abortGame returned a foreign game id: $($r.data.abortGame.id)"
    }
    if ($r.data.abortGame.status -cne 'ABORTED') {
      $g2 = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $q
      Assert-GqlOk $g2 'cleanup post-abort verification'
      $after = $g2.data.game
      $afterStatus = if ($after) { $after.status } else { '<gone>' }
      if (-not $after -or $after.id -cne $Script:ThisRunGameId -or $after.status -cne 'ABORTED') {
        throw "game $($Script:ThisRunGameId) is NOT terminal ABORTED after abortGame (status=$afterStatus)"
      }
    }
    Write-Output "cleanup: aborted THIS run's game id=$($Script:ThisRunGameId) status=ABORTED (verified)"
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
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$AccountA = @{ email = $env:S09_DEMO_HOST_EMAIL; password = $env:S09_DEMO_HOST_PASSWORD }
$AccountB = @{ email = $env:S09_DEMO_JOINER_EMAIL; password = $env:S09_DEMO_JOINER_PASSWORD }
if (-not $AccountA.email -and -not $EnvFile) { $EnvFile = Join-Path $RepoRoot 'backend\.env' }
if ($EnvFile) {
  # Credentials from a local gitignored file - still never argv, never printed.
  foreach ($line in @(Get-Content -LiteralPath $EnvFile)) {
    if ($line -match '^(S09_DEMO_[A-Z_]+)=(.*)$') {
      $name = $Matches[1]; $value = $Matches[2]
      if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue)) {
        Set-Item "Env:$name" $value
      }
    }
  }
  $AccountA = @{ email = $env:S09_DEMO_HOST_EMAIL; password = $env:S09_DEMO_HOST_PASSWORD }
  $AccountB = @{ email = $env:S09_DEMO_JOINER_EMAIL; password = $env:S09_DEMO_JOINER_PASSWORD }
}
foreach ($pair in @(
    @('S09_DEMO_HOST_EMAIL', $AccountA.email), @('S09_DEMO_JOINER_EMAIL', $AccountB.email),
    @('S09_DEMO_HOST_PASSWORD', $AccountA.password), @('S09_DEMO_JOINER_PASSWORD', $AccountB.password))) {
  if (-not $pair[1]) { throw "missing $($pair[0]) in process environment" }
}

function Invoke-DuelDemo {
  $heroA = Get-Hero $AccountA.email $AccountA.password 'Medusa'
  $heroB = Get-Hero $AccountB.email $AccountB.password 'King Arthur'
  Write-Output "heroA=$heroA heroB=$heroB"

  $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Script:Staging = Join-Path ([System.IO.Path]::GetTempPath()) "s09-duel-$Stamp-$PID"
  New-Item -ItemType Directory -Force -Path $Script:Staging | Out-Null
  Write-Output "staging: $Script:Staging"

  $hostShots = Join-Path $Script:Staging 'host'
  $joinShots = Join-Path $Script:Staging 'joiner'
  New-Item -ItemType Directory -Force -Path $hostShots, $joinShots | Out-Null
  $hostTrace = Join-Path $Script:Staging 'duel-client-host.trace.log'
  $joinTrace = Join-Path $Script:Staging 'duel-client-joiner.trace.log'

  $Script:ThisRunGameId = $null
  $Script:ThisRunGameCode = $null

  # Full-duel auto plans: the host drives attacks + schemes, the joiner drives
  # defense/no-defense + resolve + schemes, both answer pending heads.
  # t.MaxFPS 30 is a per-process console-command cap (two offscreen rendered
  # clients overload one GPU without it); effective FPS is not claimed -
  # no measured FPS/frame-time data exists. DefaultGameUserSettings stays 60.
  $common = @("-windowed", "-resx=1280", "-resy=720", "-RenderOffScreen",
    "-ExecCmds=`"t.MaxFPS 30`"", "log=GrepLog",
    "-ForceAbandonSequences", "-S08Api=$Api", "-S09ShotMode=$ShotMode")
  # HB-01 / VS-4 HB-48: only the marker gate rollback draws the debug layer; the default gates read SHOT widget + trace
  if ($S09Markers) { $common += '-S09Markers' }
  foreach ($extra in @($ClientExtraArgs -split '\+' | Where-Object { $_ })) { $common += $extra }
  $hostArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08Create", "-S08HeroId=$heroA", "-S08Trace=$hostTrace",
    "-S09Flow", "-S09Combat=attack+scheme", "-S09ShotDir=$hostShots", "-S08ExitAfter=$RunSeconds")
  if ($BoardId) { $hostArgs += "-S08BoardId=$BoardId" }
  $joinArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08HeroId=$heroB", "-S08Trace=$joinTrace",
    "-S09Flow", "-S09Combat=defend+resolve+scheme", "-S09ShotDir=$joinShots", "-S08ExitAfter=$RunSeconds")

  $hostProc = $null
  $joinProc = $null
  $Published = $false
  try {
    # Pre-run stats snapshot (both seats). Terminal save updates UserStats;
    # the post-run gate checks both counters and the exact ELO result.
    function Get-StatsSnapshot([string]$Token, [string]$UserId) {
      $q = @{ query = 'query S($userId: String!) { stats(userId: $userId) { gamesPlayed gamesWon gamesLost currentElo } }'; variables = @{ userId = $UserId } } | ConvertTo-Json -Depth 5
      $r = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers @{ authorization = "Bearer $Token" } -Body $q
      Assert-GqlOk $r "stats lookup ($UserId)"
      return $r.data.stats
    }
    $loginBodyA = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }'; variables = @{ input = @{ email = $AccountA.email; password = $AccountA.password } } } | ConvertTo-Json -Depth 5
    $loginA = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBodyA
    Assert-GqlOk $loginA 'host pre-run login'
    $loginBodyB = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }'; variables = @{ input = @{ email = $AccountB.email; password = $AccountB.password } } } | ConvertTo-Json -Depth 5
    $loginB = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBodyB
    Assert-GqlOk $loginB 'joiner pre-run login'
    $Script:UserIdA = $loginA.data.login.user.id
    $Script:UserIdB = $loginB.data.login.user.id
    if (-not $Script:UserIdA -or -not $Script:UserIdB -or $Script:UserIdA -eq $Script:UserIdB) {
      throw "seat user ids invalid (host=$Script:UserIdA joiner=$Script:UserIdB)"
    }
    $tokenA = $loginA.data.login.accessToken
    $StatsBefore = @{
      host   = Get-StatsSnapshot $tokenA $Script:UserIdA
      joiner = Get-StatsSnapshot $tokenA $Script:UserIdB
    }
    Write-Output ("stats before: host played={0} won={1} elo={2}; joiner played={3} won={4} elo={5}" -f `
      $StatsBefore.host.gamesPlayed, $StatsBefore.host.gamesWon, $StatsBefore.host.currentElo,
      $StatsBefore.joiner.gamesPlayed, $StatsBefore.joiner.gamesWon, $StatsBefore.joiner.currentElo)

    $hostStartUtc = [DateTime]::UtcNow
    $hostProc = Start-S09Client $hostArgs $AccountA.email $AccountA.password
    Write-Output "host pid=$($hostProc.Id)"

    function Assert-NoCredentialOnCmdLine([int]$Pid_, [string[]]$Secrets) {
      $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$Pid_"
      if (-not $proc) { throw "process $Pid_ not found for command-line audit" }
      foreach ($secret in $Secrets) {
        if ($secret -and $proc.CommandLine -match [regex]::Escape($secret)) {
          throw "secret leaked into command line of pid $Pid_"
        }
      }
    }
    Assert-NoCredentialOnCmdLine $hostProc.Id @($AccountA.email, $AccountA.password)

    $code = $null
    for ($i = 0; $i -lt 120; $i++) {
      Start-Sleep -Milliseconds 500
      if (Test-Path -LiteralPath $hostTrace) {
        $m = Select-String -Path $hostTrace -Pattern 'createGame -> room=([A-Za-z0-9_-]+) code=([A-Z0-9-]{4,12})' |
          Select-Object -First 1
        if ($m) {
          $Script:ThisRunGameId = $m.Matches[0].Groups[1].Value
          $Script:ThisRunGameCode = $m.Matches[0].Groups[2].Value
          $code = $Script:ThisRunGameCode
          break
        }
      }
      if ($hostProc.HasExited) { throw "host client exited before publishing a code" }
    }
    if (-not $code) { throw "no room code found in host trace" }
    Write-Output "room created by this run (code redacted from output; id=$Script:ThisRunGameId)"

    $joinStartUtc = [DateTime]::UtcNow
    $joinProc = Start-S09Client $joinArgs $AccountB.email $AccountB.password $code
    Write-Output "joiner pid=$($joinProc.Id)"
    Assert-NoCredentialOnCmdLine $joinProc.Id @($AccountB.email, $AccountB.password, $code)

    # Server-row observation DURING the run (informational): poll ~1s and
    # record every status. leaveGame from a FINISHED room no longer deletes
    # the row (terminal rows are preserved with winner + both seats), so
    # FINISHED is expected to appear here AND to survive the post-leave
    # authoritative check below.
    $pollHeaders = @{ authorization = "Bearer $tokenA" }
    $pollQuery = @{ query = 'query G($id: String!) { game(id: $id) { id status } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
    $Script:StatusSeen = New-Object System.Collections.Generic.List[string]
    # Per-seat stall watchdog (S10 review P2): a seat's stream must keep
    # advancing once THAT seat subscribed; its own 'RESULT seq=' disarms only
    # it (the result tail may go quiet). The other seat's progress or terminal
    # line must never mask a dead seat - the 2026-09-27 run stalled like this
    # at seq 1 on one seat until the full timeout. -ProbeWatchdog probes this
    # logic without clients.
    $seatWatchdogs = @{
      host    = New-SeatWatchdogState
      joiner  = New-SeatWatchdogState
    }
    $seatTraces = @{ host = $hostTrace; joiner = $joinTrace }
    $watchdogArmed = $StallSeconds -gt 0
    while (-not $hostProc.HasExited) {
      [void]$hostProc.WaitForExit(500)
      try {
        $pg = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $pollHeaders -Body $pollQuery
        if ($pg.data.game -and $pg.data.game.status) {
          if ($Script:StatusSeen.Count -eq 0 -or $Script:StatusSeen[$Script:StatusSeen.Count - 1] -ne $pg.data.game.status) {
            $Script:StatusSeen.Add($pg.data.game.status)
          }
        }
      } catch {}
      if ($watchdogArmed -and (Test-Path -LiteralPath $hostTrace) -and (Test-Path -LiteralPath $joinTrace)) {
        $nowUtc = [DateTime]::UtcNow
        foreach ($seatName in @('host', 'joiner')) {
          $text = Get-Content -LiteralPath $seatTraces[$seatName] -Raw
          if (Update-SeatWatchdog -State $seatWatchdogs[$seatName] -Text $text -NowUtc $nowUtc -StallSeconds $StallSeconds) {
            throw "stalled stream on the $seatName seat: subscribed but no new 'SNAPSHOT applied seq=' for $StallSeconds s (last max seq=$($seatWatchdogs[$seatName].lastSeq); the other seat's progress must not mask this)"
          }
        }
      }
    }
    $joinProc.WaitForExit()
    Write-Output "both clients exited; server statuses observed: [$($Script:StatusSeen -join ' -> ')]"

    # ---- terminal result gates over both traces ----
    $hostText = Get-Content -LiteralPath $hostTrace -Raw
    $joinText = Get-Content -LiteralPath $joinTrace -Raw
    $both = $hostText + "`n" + $joinText

    foreach ($t in @(@('host', $hostText), @('joiner', $joinText))) {
      foreach ($needle in @(
          'SNAPSHOT applied', 'SUBSCRIBED gameStateUpdated', 'HUD seq=',
          'RESULT seq=', 'RESULT lobby-return sent (leaveGame)', 'LEFT room=',
          'S09AUTO duel flow complete')) {
        if (-not $t[1].Contains($needle)) { throw "$($t[0]) trace missing '$needle'" }
      }
      # A trace containing each marker is insufficient: a retry loop could
      # leave twice yet still satisfy the old gate. Require one ordered
      # terminal result -> leave request -> accepted reply -> clean exit.
      $tailMarkers = @(
        @{ name = 'result'; pattern = ' RESULT seq=\d+ outcome='; literal = ' RESULT seq=' },
        @{ name = 'leave request'; pattern = [regex]::Escape('RESULT lobby-return sent (leaveGame)'); literal = 'RESULT lobby-return sent (leaveGame)' },
        @{ name = 'accepted leave'; pattern = [regex]::Escape('LEFT room='); literal = 'LEFT room=' },
        @{ name = 'clean exit'; pattern = [regex]::Escape('S09AUTO duel flow complete'); literal = 'S09AUTO duel flow complete' }
      )
      $previousIndex = -1
      foreach ($marker in $tailMarkers) {
        $count = [regex]::Matches($t[1], $marker.pattern).Count
        if ($count -ne 1) { throw "$($t[0]) trace has $count $($marker.name) markers (expected exactly one)" }
        $index = $t[1].IndexOf($marker.literal, [StringComparison]::Ordinal)
        if ($index -le $previousIndex) {
          throw "$($t[0]) terminal tail is out of order at $($marker.name)"
        }
        $previousIndex = $index
      }
      if ($t[1] -match '(ATTACK|DEFENSE|RESOLVE|SCHEME|PEND) sent .*card') {
        throw "$($t[0]) trace appears to log card identities with a combat command"
      }
      # The 11:47 run sent 8 endTurn mutations from COMBAT/COMBAT_RESOLVE and
      # burned authoritative rejections; the phase gate must keep the proof
      # free of that server-rejection loop.
      $invalidPhase = @($t[1] -split "`n" | Where-Object { $_ -match 'Invalid phase' })
      if ($invalidPhase.Count -gt 0) {
        throw ("{0} trace shows {1} authoritative 'Invalid phase' rejection(s) - a client gate is still sending commands outside the action phases" -f $t[0], $invalidPhase.Count)
      }
    }

    # Outcome derivation: exactly one VICTORY and one DEFEAT across seats.
    $hostOutcome = $null; $joinOutcome = $null
    $mH = [regex]::Match($hostText, 'RESULT seq=\d+ outcome=([A-Z]+) winner=')
    $mJ = [regex]::Match($joinText, 'RESULT seq=\d+ outcome=([A-Z]+) winner=')
    if (-not $mH.Success) { throw 'host trace has RESULT line without a parseable outcome' }
    if (-not $mJ.Success) { throw 'joiner trace has RESULT line without a parseable outcome' }
    $hostOutcome = $mH.Groups[1].Value
    $joinOutcome = $mJ.Groups[1].Value
    Write-Output "outcomes: host=$hostOutcome joiner=$joinOutcome"
    if ($BoardId) {
      # VS-4 HB-48 -BoardId: the host created the room on that board (client trace) and both clients show its profile
      if (-not $hostText.Contains("CREATE boardId=$BoardId source=S08BoardId")) { throw "host trace has no 'CREATE boardId=$BoardId source=S08BoardId'" }
      foreach ($t in @(@('host', $hostText), @('joiner', $joinText))) {
        $prof = [regex]::Match($t[1], 'ARTPREVIEW board active profile=(\S+)')
        if (-not $prof.Success) { throw "$($t[0]) trace has no 'ARTPREVIEW board active profile='" }
        Write-Output "board: $($t[0]) profile=$($prof.Groups[1].Value) boardId=$BoardId"
      }
    }
    if (-not (($hostOutcome -eq 'VICTORY' -and $joinOutcome -eq 'DEFEAT') -or
              ($hostOutcome -eq 'DEFEAT' -and $joinOutcome -eq 'VICTORY'))) {
      throw "outcomes are not one VICTORY + one DEFEAT (host=$hostOutcome joiner=$joinOutcome) - the duel did not end in a decided win"
    }

    # ---- full-duel coverage lines (authoritative commands observed) ----
    $attackSeen = $both.Contains('ATTACK sent')
    $defenseSeen = $both.Contains('DEFENSE sent')
    $noDefenseSeen = $both.Contains('NO-DEFENSE sent')
    $resolveSeen = $both.Contains('RESOLVE sent')
    # The automated path logs successful authoritative applies, while the
    # manual picker logs "SCHEME sent" before the server responds.
    $schemeSeen = $both.Contains('SCHEME done seq=')
    $pendingResolvedSeen = $both.Contains('PEND resolve done seq=')
    $combatResultSeen = $both.Contains('COMBAT-RESULT seq=')
    Write-Output ("duel coverage: attack={0} defense={1} noDefense={2} resolve={3} scheme={4} pendingResolved={5} combatResult={6}" -f `
      $attackSeen, $defenseSeen, $noDefenseSeen, $resolveSeen, $schemeSeen, $pendingResolvedSeen, $combatResultSeen)
    if (-not $attackSeen) { throw 'no ATTACK sent this run - not a full duel' }
    if (-not ($defenseSeen -or $noDefenseSeen)) { throw 'no DEFENSE sent and no NO-DEFENSE sent this run - defense window never exercised' }
    if (-not $resolveSeen) { throw 'no RESOLVE sent this run - combat never resolved' }
    if (-not $combatResultSeen) { throw 'no COMBAT-RESULT line this run - no damage ever landed' }

    # ---- result/lobby shots on BOTH seats ----
    Add-Type -AssemblyName System.Drawing
    $Markers = @(
      @{ name = 'resultscreen'; r = 255; g = 215; b = 0   },
      @{ name = 'resultoutcome'; r = 255; g = 0;  b = 100 },
      @{ name = 'resultsupport'; r = 0;   g = 255; b = 160 },
      @{ name = 'resultbutton'; r = 128; g = 0;   b = 255 },
      @{ name = 'lobbypanel';  r = 64;  g = 200; b = 255 },
      @{ name = 'pending'; r = 64;  g = 128; b = 255 },
      @{ name = 'attack';  r = 255; g = 128; b = 0   },
      @{ name = 'defense'; r = 255; g = 64;  b = 64  },
      @{ name = 'resolve'; r = 64;  g = 255; b = 64  },
      @{ name = 'boost';   r = 255; g = 255; b = 64  },
      @{ name = 'combatresult'; r = 64; g = 255; b = 128 },
      @{ name = 'maneuver';r = 255; g = 0;   b = 255 },
      @{ name = 'discard'; r = 0;   g = 255; b = 255 },
      @{ name = 'revealline'; r = 128; g = 64; b = 255 },
      @{ name = 'blocked'; r = 255; g = 64;  b = 176 },
      @{ name = 'revealtext'; r = 124; g = 252; b = 0 }
    )
    function Get-MarkerStats([string]$Path) {
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
        foreach ($m in $Markers) { $stats[$m.name + 'All'] = 0 }
        $tol = 16
        for ($y = 0; $y -lt $h; $y += 2) {
          $row = $y * $data.Stride
          for ($x = 0; $x -lt $w; $x += 2) {
            $i = $row + $x * 4
            $pB = $bytes[$i]; $pG = $bytes[$i + 1]; $pR = $bytes[$i + 2]
            foreach ($m in $Markers) {
              if ([Math]::Abs($pR - $m.r) -le $tol -and
                  [Math]::Abs($pG - $m.g) -le $tol -and
                  [Math]::Abs($pB - $m.b) -le $tol) {
                $stats[$m.name + 'All']++
                break
              }
            }
          }
        }
        return $stats
      } finally { $bmp.Dispose() }
    }
    function Assert-FreshShot([string]$Path, [DateTime]$ClientStartUtc, [string]$What) {
      if (-not (Test-Path -LiteralPath $Path)) { throw "$What shot missing: $Path" }
      $f = Get-Item -LiteralPath $Path
      if ($f.Length -lt 10KB) { throw "suspiciously small $What shot (likely black/empty): $Path" }
      if ($f.LastWriteTimeUtc -le $ClientStartUtc) { throw "$What shot predates its client process (stale file): $Path" }
      return $f
    }
    $hostResultShot = Assert-FreshShot (Join-Path $hostShots 's09-result-screen.png') $hostStartUtc 'host result-screen'
    $joinResultShot = Assert-FreshShot (Join-Path $joinShots 's09-result-screen.png') $joinStartUtc 'joiner result-screen'
    $hostLobbyShot = Assert-FreshShot (Join-Path $hostShots 's09-lobby-return.png') $hostStartUtc 'host lobby-return'
    $joinLobbyShot = Assert-FreshShot (Join-Path $joinShots 's09-lobby-return.png') $joinStartUtc 'joiner lobby-return'
    Write-Output ("result shots: host={0}B joiner={1}B; lobby shots: host={2}B joiner={3}B" -f `
      $hostResultShot.Length, $joinResultShot.Length, $hostLobbyShot.Length, $joinLobbyShot.Length)

    $ShotGateLines = @()
    if (-not $S09Markers) {
      # ---- VS-4 HB-48: the result screen and the lobby by trace + SHOT widget (GAMEOVER / LOBBY are Slate until VS-7) ----
      foreach ($pair in @(@('host', $hostTrace, $hostResultShot.FullName), @('joiner', $joinTrace, $joinResultShot.FullName))) {
        $lines = [System.IO.File]::ReadAllLines($pair[1])
        $shotAt = -1
        for ($k = $lines.Length - 1; $k -ge 0; $k--) { if ($lines[$k] -match 'SHOT request file=s09-result-screen\.png ') { $shotAt = $k; break } }
        if ($shotAt -lt 0) { throw "$($pair[0]) trace never requested s09-result-screen.png" }
        $summary = $null; $view = $null
        for ($k = $shotAt; $k -ge 0; $k--) {
          if (-not $view -and $lines[$k] -match 'RESULT view mode=(\w+) ') { $view = $Matches[1] }
          if (-not $summary -and $lines[$k] -match 'RESULT summary outcome=(VICTORY|DEFEAT) ') { $summary = $Matches[1] }
          if ($view -and $summary) { break }
        }
        if ($view -ne 'results') { throw "$($pair[0]) result shot: the last RESULT view before it is '$view', not the results screen" }
        if (-not $summary) { throw "$($pair[0]) result shot: no 'RESULT summary outcome=VICTORY|DEFEAT' before it" }
        $s = Get-MarkerStats $pair[2]
        if (-not (($s.w -eq 1280 -and $s.h -eq 720) -or ($s.w -eq 1920 -and $s.h -eq 1080))) {
          throw ("{0} result shot is {1}x{2} - NOT 1280x720/1920x1080" -f $pair[0], $s.w, $s.h)
        }
        $ShotGateLines += "$($pair[0]) result screen: RESULT summary outcome=$summary, RESULT view mode=results before the shot"
        $ShotGateLines += Assert-HudShotGate -TracePath $pair[1] -Who $pair[0] -Privacy -Rules @(
          's09-result-screen.png: need UI-SCR-GAME state=over; deny UI-HUD-PENDING; deny UI-HUD-COMBAT-EDGE; deny UI-HUD-ACTIONS; deny UI-HUD-HAND',
          's09-lobby-return.png: deny UI-HUD-*')
        $ShotGateLines += Assert-HudShotGateFails $pair[1] 's09-lobby-return.png: need UI-SCR-GAME state=over' "$($pair[0]) lobby shot as the result screen"
      }
      foreach ($l in $ShotGateLines) { Write-Output $l }
    }
    if ($ShotMode -eq 'request' -and $S09Markers) {
      # Result screen: the COMPLETE panel on both seats - one marker per
      # REQUIRED element (header #FFD700, outcome, supporting line, button).
      # A capture caught mid-Slate-paint misses the later elements (the
      # 11:47 host shot carried only header+outcome) - gold presence alone
      # is NOT acceptance. Every gameplay/draft marker must be absent too.
      foreach ($pair in @(@('host', $hostResultShot.FullName), @('joiner', $joinResultShot.FullName))) {
        $s = Get-MarkerStats $pair[1]
        if (-not (($s.w -eq 1280 -and $s.h -eq 720) -or ($s.w -eq 1920 -and $s.h -eq 1080))) {
          throw ("{0} result shot is {1}x{2} - NOT 1280x720/1920x1080" -f $pair[0], $s.w, $s.h)
        }
        foreach ($part in @('resultscreen', 'resultoutcome', 'resultsupport', 'resultbutton')) {
          if ($s[$part + 'All'] -lt 100) {
            throw ("{0} result shot incomplete - '{1}' element marker too low ({2}={3}); the panel was captured mid-paint or truncated" -f `
              $pair[0], $part, $part, $s[$part + 'All'])
          }
        }
        foreach ($other in @('attack', 'defense', 'resolve', 'boost', 'pending', 'maneuver', 'discard', 'blocked', 'revealline', 'lobbypanel')) {
          if ($s[$other + 'All'] -ne 0) {
            throw ("{0} result shot shows a gameplay state marker: {1}={2}" -f $pair[0], $other, $s[$other + 'All'])
          }
        }
        Write-Output ("{0} result shot markers: header={1} outcome={2} support={3} button={4} (gameplay markers all-zero)" -f `
          $pair[0], $s.resultscreenAll, $s.resultoutcomeAll, $s.resultsupportAll, $s.resultbuttonAll)
      }
    }
    if ($ShotMode -eq 'request') {
      # Lobby shots: the CLEAN user-facing lobby panel present (lobbypanel (-S09Markers only, VS-4 HB-48)
      # marker) and EVERY in-duel marker gone - result, combat, drafts; the
      # stale runtime board/fighters are torn down at the stage change.
      # PLUS the VISUAL gameplay-region gate: marker-only checks missed the
      # stale board + four fighter actors of the 2026-09-27 first duel (the
      # 3D scene carries none of the UI marker colors). The lobby entry panel
      # lives top-LEFT; the gameplay region (x >= 25%, y >= 12.5%) must carry
      # NO bright pixels (lum >= 120) - a live board shot measures thousands
      # of samples there (calibrated on run duel-20260927-091740: board
      # ~5-9k per 16th of the frame vs 0 in the clean lobby shot).
      function Get-GameplayRegionBright([string]$Path) {
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
            $row = $y * $data.Stride
            for ($x = $x0; $x -lt $w; $x += 2) {
              $i = $row + $x * 4
              $lum = 0.299 * $bytes[$i + 2] + 0.587 * $bytes[$i + 1] + 0.114 * $bytes[$i]
              if ($lum -ge 120) { $count++ }
            }
          }
          return $count
        } finally { $bmp.Dispose() }
      }
      foreach ($pair in @(@('host', $hostLobbyShot.FullName), @('joiner', $joinLobbyShot.FullName))) {
        $s = Get-MarkerStats $pair[1]
        if ($S09Markers -and $s.lobbypanelAll -lt 100) {
          throw ("{0} lobby shot missing the clean lobby entry panel (lobbypanel={1})" -f $pair[0], $s.lobbypanelAll)
        }
        foreach ($duel in @('resultscreen', 'resultoutcome', 'resultsupport', 'resultbutton', 'pending', 'attack', 'defense', 'resolve', 'maneuver', 'discard')) {
          if ($S09Markers -and $s[$duel + 'All'] -ne 0) {
            throw ("{0} lobby shot still shows an in-duel marker: {1}={2}" -f $pair[0], $duel, $s[$duel + 'All'])
          }
        }
        if ($S09Markers) {
          $bright = Get-GameplayRegionBright $pair[1]
          if ($bright -gt 50) {
            throw ("{0} lobby shot has {1} bright gameplay-region pixels (lum>=120, x>=25%/y>=12.5%) - stale board/fighter/HUD rendering survived the lobby return (visual gate)" -f $pair[0], $bright)
          }
          Write-Output ("{0} lobby shot: clean lobby panel (lobbypanel={1}), no in-duel markers, gameplay region bright pixels={2} (<=50)" -f $pair[0], $s.lobbypanelAll, $bright)
        } else {
          # VS-7 (ВР-VS7-77): the menu backdrop rebuilt without figures after the leave (SCREEN-BG, UI/UmMenuBackdrop.h)
          $seatTrace = if ($pair[0] -eq 'host') { $hostTrace } else { $joinTrace }
          $tail = (Get-Content -LiteralPath $seatTrace -Raw) -split "`n"
          $leftAt = -1
          for ($li = 0; $li -lt $tail.Count; $li++) { if ($tail[$li] -match 'LEFT room=') { $leftAt = $li } }
          $bg = @(if ($leftAt -ge 0) { $tail[$leftAt..($tail.Count - 1)] | Where-Object { $_ -match 'SCREEN-BG .*fighters=0 .*stage=Lobby state=menu' } })
          if ($bg.Count -eq 0) {
            throw ("{0} lobby return: no 'SCREEN-BG ... fighters=0 ... stage=Lobby state=menu' after LEFT room= - the match board / fighters may have survived the lobby return" -f $pair[0])
          }
          Write-Output ("{0} lobby shot: SHOT widget gate above; the menu backdrop is back without figures after the leave ({1})" -f $pair[0], ($bg[0].Trim() -replace '^\S+ ', ''))
        }
      }
    } else {
      Write-Output "WARN ShotMode=$ShotMode - pixel state gates skipped"
    }

    # ---- server row gate over the DURING-RUN observations ----
    # leaveGame from a FINISHED room deletes the row once the last player
    # leaves, so a post-exit lookup can 404; the FINISHED status itself was
    # observed live by the ~1s poll. ABORTED at any point = the presented
    # victory came from the abort path = hard fail.
    $statusLine = ($Script:StatusSeen -join ' -> ')
    if (@($Script:StatusSeen) -contains 'ABORTED') {
      throw "game $($Script:ThisRunGameId) was ABORTED during the run (statuses: $statusLine) - a presented victory must never come from the abort path"
    }

    # ---- POST-LEAVE authoritative row check (HARD GATE) ----
    # leaveGame no longer deletes a terminal row: both seats left a FINISHED
    # room, so the row MUST still resolve as FINISHED with winnerId and BOTH
    # seats. The victory is proven from the server row, not from client traces.
    $rowQuery = @{ query = 'query G($id: String!) { game(id: $id) { id status winnerId endedAt players { userId seatOrder } } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 6
    $rowErr = $null
    $row = $null
    try {
      $rr = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $pollHeaders -Body $rowQuery
      Assert-GqlOk $rr 'post-leave row lookup'
      $row = $rr.data.game
    } catch { $rowErr = $_.Exception.Message }
    if (-not $row) {
      throw "post-leave authoritative check FAILED - the FINISHED row was not preserved after both seats left (lookup error: $rowErr)"
    }
    if ($row.id -cne $Script:ThisRunGameId) { throw "post-leave row id mismatch: $($row.id)" }
    if ($row.status -cne 'FINISHED') {
      throw "post-leave authoritative status is $($row.status), NOT FINISHED - the presented victory has no server-side FINISHED row"
    }
    $rowPlayerIds = @($row.players | ForEach-Object { $_.userId })
    foreach ($uid in @($Script:UserIdA, $Script:UserIdB)) {
      if ($rowPlayerIds -notcontains $uid) {
        throw "post-leave FINISHED row lost a seat: user $uid not in players ($($rowPlayerIds -join ','))"
      }
    }
    if (@($row.players).Count -lt 2) {
      throw "post-leave FINISHED row has fewer than 2 seats ($(@($row.players).Count))"
    }
    if (-not $row.winnerId) {
      throw "post-leave FINISHED row has no winnerId"
    }
    if (@($Script:UserIdA, $Script:UserIdB) -notcontains $row.winnerId) {
      throw "post-leave winnerId $($row.winnerId) is not one of this run's two seats"
    }
    if (-not $row.endedAt) {
      throw "post-leave FINISHED row has no endedAt"
    }
    $rowWinnerSeat = if ($row.winnerId -eq $Script:UserIdA) { 'host' } else { 'joiner' }
    $traceWinnerSeat = if ($hostOutcome -eq 'VICTORY') { 'host' } else { 'joiner' }
    if ($rowWinnerSeat -cne $traceWinnerSeat) {
      throw "server row winner ($rowWinnerSeat) contradicts the client-presented outcomes (VICTORY on $traceWinnerSeat)"
    }
    $liveFinished = @($Script:StatusSeen) -contains 'FINISHED'
    $serverVerdict = "post-leave authoritative row: FINISHED, winner=$rowWinnerSeat seat, both seats present, endedAt set (FINISHED also observed live: $liveFinished)"
    Write-Output "server row gate: $serverVerdict (statuses observed during run: $statusLine)"

    # ---- stats after (terminal transaction gate) ----
    $StatsAfter = @{
      host   = Get-StatsSnapshot $tokenA $Script:UserIdA
      joiner = Get-StatsSnapshot $tokenA $Script:UserIdB
    }
    $statsChanged = (($StatsAfter.host.gamesPlayed -ne $StatsBefore.host.gamesPlayed) -or
                     ($StatsAfter.joiner.gamesPlayed -ne $StatsBefore.joiner.gamesPlayed) -or
                     ($StatsAfter.host.currentElo -ne $StatsBefore.host.currentElo) -or
                     ($StatsAfter.joiner.currentElo -ne $StatsBefore.joiner.currentElo))
    Write-Output ("stats after: host played={0} won={1} elo={2}; joiner played={3} won={4} elo={5}; changed={6}" -f `
      $StatsAfter.host.gamesPlayed, $StatsAfter.host.gamesWon, $StatsAfter.host.currentElo,
      $StatsAfter.joiner.gamesPlayed, $StatsAfter.joiner.gamesWon, $StatsAfter.joiner.currentElo, $statsChanged)
    $winnerBefore = if ($rowWinnerSeat -eq 'host') { $StatsBefore.host } else { $StatsBefore.joiner }
    $loserBefore = if ($rowWinnerSeat -eq 'host') { $StatsBefore.joiner } else { $StatsBefore.host }
    $winnerAfter = if ($rowWinnerSeat -eq 'host') { $StatsAfter.host } else { $StatsAfter.joiner }
    $loserAfter = if ($rowWinnerSeat -eq 'host') { $StatsAfter.joiner } else { $StatsAfter.host }
    $winnerExpected = 1.0 / (1.0 + [Math]::Pow(10.0, (($loserBefore.currentElo - $winnerBefore.currentElo) / 400.0)))
    $loserExpected = 1.0 / (1.0 + [Math]::Pow(10.0, (($winnerBefore.currentElo - $loserBefore.currentElo) / 400.0)))
    # JavaScript Math.round uses floor(x + 0.5) for positive ELO values.
    $expectedWinnerElo = [Math]::Floor($winnerBefore.currentElo + 32.0 * (1.0 - $winnerExpected) + 0.5)
    $expectedLoserElo = [Math]::Floor($loserBefore.currentElo - 32.0 * $loserExpected + 0.5)
    if ($winnerAfter.gamesPlayed -ne $winnerBefore.gamesPlayed + 1 -or
        $winnerAfter.gamesWon -ne $winnerBefore.gamesWon + 1 -or
        $winnerAfter.gamesLost -ne $winnerBefore.gamesLost -or
        $winnerAfter.currentElo -ne $expectedWinnerElo -or
        $loserAfter.gamesPlayed -ne $loserBefore.gamesPlayed + 1 -or
        $loserAfter.gamesWon -ne $loserBefore.gamesWon -or
        $loserAfter.gamesLost -ne $loserBefore.gamesLost + 1 -or
        $loserAfter.currentElo -ne $expectedLoserElo) {
      throw "terminal UserStats mismatch: expected winner +1 played/+1 won/ELO $expectedWinnerElo, loser +1 played/+1 lost/ELO $expectedLoserElo"
    }
    Write-Output "stats gate: winner/loser counters and ELO match the terminal outcome"

    # ---- seq convergence ----
    function Get-MaxSeq([string]$Path) {
      $seqs = Select-String -Path $Path -Pattern 'SNAPSHOT applied seq=(\d+)' -AllMatches |
        ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value }
      return ($seqs | Measure-Object -Maximum).Maximum
    }
    $hostSeq = Get-MaxSeq $hostTrace
    $joinSeq = Get-MaxSeq $joinTrace
    Write-Output "convergence: host maxSeq=$hostSeq joiner maxSeq=$joinSeq"
    if (-not $hostSeq -or -not $joinSeq) { throw "missing applied seq in traces" }
    if ($hostSeq -lt 12 -or $joinSeq -lt 12) { throw "match did not run long enough: host=$hostSeq joiner=$joinSeq" }
    if ([Math]::Abs($hostSeq - $joinSeq) -gt 4) { throw "clients diverged: host seq=$hostSeq joiner seq=$joinSeq" }

    # ---- compact traces (hash-verified evidence of the requested proof) ----
    $compactPattern = 'S09AUTO|RESULT |LEFT room|COMBAT-RESULT|PEND |SCHEME done seq=|SCHEME sent|ATTACK sent|DEFENSE sent|NO-DEFENSE|RESOLVE sent|PENDING panel revealed|RESOLVE panel|SNAPSHOT applied seq=|MODE seq='
    foreach ($pair in @(@('duel-client-host.trace.log', 'duel-client-host.compact.log'),
                        @('duel-client-joiner.trace.log', 'duel-client-joiner.compact.log'))) {
      $srcLines = Get-Content -LiteralPath (Join-Path $Script:Staging $pair[0])
      $kept = @($srcLines | Where-Object { $_ -match $compactPattern })
      if ($code) { $kept = @($kept | ForEach-Object { $_.Replace($code, '<redacted>') }) }
      [System.IO.File]::WriteAllLines((Join-Path $Script:Staging $pair[1]), $kept, $Utf8NoBom)
    }

    # ---- publish ----
    $publishNames = @(
      'duel-client-host.trace.log', 'duel-client-joiner.trace.log',
      'duel-client-host.compact.log', 'duel-client-joiner.compact.log'
    )
    # Full-journey UI shots: entry/maneuver/discard/combat/pending staging shots
    # plus the terminal result-screen and lobby-return captures on both seats.
    $allStageShots = @(Get-ChildItem -LiteralPath $hostShots, $joinShots -Filter 's09-*.png' -ErrorAction SilentlyContinue |
      Sort-Object Name)
    foreach ($shot in $allStageShots) {
      $who = if ($shot.FullName.StartsWith($hostShots)) { 'host' } else { 'joiner' }
      $publishNames += ($who + '\' + $shot.Name)
    }
    $RunDir = Join-Path $EvidenceDir ("duel-" + $Stamp)
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
    $verdict = 'GD-036: full two-client packaged PvP duel over the authoritative server - sign-in, room join, placement, maneuvers, attack/defense resolves, card effects and pending answers, then the server-written GAME_OVER rendered a COMPLETE result screen on BOTH seats (one VICTORY, one DEFEAT; header+outcome+support+button element markers all present after a UI-settle delay, gameplay markers absent, stale gameplay action toast cleared at the terminal apply, no Invalid-phase rejection loop in the traces), leaveGame returned both clients to a CLEAN lobby (board/fighters torn down at the stage change, user-facing room-entry panel, fresh lobby shots with no in-duel markers AND zero bright pixels in the gameplay region - the visual gate added after the 2026-09-27 stale-fighter miss), the server row is authoritative FINISHED after both seats left (winnerId matching the presented VICTORY seat, both seats present, endedAt set; never ABORTED), and the driver exited early instead of burning the timeout. Frame cap: per-process console command t.MaxFPS 30 (effective FPS NOT measured, no GPU claim). Stats: terminal save transaction updates both players; winner/loser counters and exact ELO are gated'
    $manifest = [ordered]@{
      stamp         = $Stamp
      verdict       = $verdict
      hostOutcome   = $hostOutcome
      joinerOutcome = $joinOutcome
      serverStatuses = @($Script:StatusSeen)
      serverVerdict = $serverVerdict
      serverRow     = [ordered]@{
        id = $row.id
        status = $row.status
        winnerSeat = $rowWinnerSeat
        winnerIdRedacted = ($row.winnerId -ne $null)
        seats = @($rowPlayerIds).Count
        endedAt = [string]$row.endedAt
      }
      statsSample   = [ordered]@{
        note = 'terminal save transaction updates UserStats; winner/loser counters and exact ELO are gated'
        changed = $statsChanged
        hostBefore = $StatsBefore.host
        hostAfter = $StatsAfter.host
        joinerBefore = $StatsBefore.joiner
        joinerAfter = $StatsAfter.joiner
      }
      coverage      = [ordered]@{
        attack = $attackSeen; defense = $defenseSeen; noDefense = $noDefenseSeen
        resolve = $resolveSeen; scheme = $schemeSeen
        pendingResolved = $pendingResolvedSeen; combatResult = $combatResultSeen
      }
      convergence   = [ordered]@{ hostMaxSeq = $hostSeq; joinerMaxSeq = $joinSeq }
      files         = @()
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

    $ptrTmp = Join-Path $EvidenceDir ("latest-duel.json.$Stamp-$PID.tmp")
    $ptr = Join-Path $EvidenceDir 'latest-duel.json'
    [System.IO.File]::WriteAllText($ptrTmp, (([ordered]@{ current = (Split-Path $RunDir -Leaf); stamp = $Stamp }) | ConvertTo-Json), $Utf8NoBom)
    if (Test-Path -LiteralPath $ptr) {
      $ptrBak = Join-Path $EvidenceDir 'latest-duel.json.bak'
      [System.IO.File]::Replace($ptrTmp, $ptr, $ptrBak)
      Remove-Item -LiteralPath $ptrBak -Force
    } else {
      [System.IO.File]::Move($ptrTmp, $ptr)
    }
    $Published = $true
    Write-Output "published evidence run dir: $RunDir (pointer: latest-duel.json)"
    Write-Output "--- host trace (duel tail) ---"
    Get-Content -LiteralPath $hostTrace |
      Select-String -Pattern 'S09AUTO|RESULT|COMBAT-RESULT|LEFT room' | Select-Object -Last 20
    Write-Output "--- joiner trace (duel tail) ---"
    Get-Content -LiteralPath $joinTrace |
      Select-String -Pattern 'S09AUTO|RESULT|COMBAT-RESULT|LEFT room' | Select-Object -Last 20
  } finally {
    foreach ($p in @($hostProc, $joinProc)) {
      if ($p -and -not $p.HasExited) {
        Stop-Process -Id $p.Id -Force
        Write-Output "cleanup: killed still-running client pid=$($p.Id)"
      }
    }
    Stop-ThisRunGame
  }

  if ($Published) {
    Remove-TreeSafely $Script:Staging ([System.IO.Path]::GetTempPath())
  }
}

Invoke-DuelDemo

if ($Script:CleanupFailure) {
  throw "scoped cleanup did not verify for this run's game: $($Script:CleanupFailure)"
}
