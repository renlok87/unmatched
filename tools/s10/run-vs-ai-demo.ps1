param(
  [string]$Exe = "",
  [string]$Api = "http://127.0.0.1:3121/graphql",
  [string]$EvidenceDir = "",
  [int]$RunSeconds = 600,
  [string]$ShotMode = "request",
  [string]$EnvFile = "",
  [string]$HeroName = "Medusa",
  # VS-2 exit frames (opt-in, docs/game-design/visual/05-production-plan.md s3 VS-2, set B "AI thinking"): -PlayerView
  # runs the client WITHOUT -S09Markers (the player's default view since HB-02). The result / lobby element-marker gates
  # need that debug layer and are skipped (reported in the output and the manifest); every other gate is unchanged.
  # Not a GD-039 acceptance run - the gate run keeps the markers. -FullHd: 1920x1080 instead of 1280x720.
  # -ClientExtraArgs: extra client arguments, '+'-separated (e.g. '-S08ExitShots+-S08UiScale=150+-S08BoardId=<id>').
  [switch]$PlayerView,
  [switch]$FullHd,
  [string]$ClientExtraArgs = '',
  # VS-3 SC-01 (ВР-SC14): -S08ScreenShots - one evidence frame per new 'SHOT widget id=UI-SCR-* state=<s>'
  [switch]$ScreenShots,
  # Fail fast when the one client is subscribed but no fresh
  # 'SNAPSHOT applied seq=' line appears for this many seconds (the server bot
  # drives the opponent seat, so a dead stream still means a stalled demo).
  # 0 disables it.
  [int]$StallSeconds = 120,
  # Run the offline parser/synthetic self-tests (redaction, tail ordering,
  # seat-row gate, early-exit measurement, ShotMode guard) and exit.
  # No client start, no API calls.
  [switch]$SelfTest
)
# S10/GD-039 one-client packaged VS_AI live acceptance runner (adapted from
# tools/s09/run-duel-demo.ps1). ONE hidden packaged client signs in, creates a
# VS_AI room (-S08Mode=VS_AI), selects a hero, readies and starts ALONE; the
# server bot takes the second seat inside startGame and plays the opponent
# (the human client drives attack+scheme through the S09AUTO plan). The run
# ends on the authoritative server-written GAME_OVER -> result screen ->
# leaveGame -> lobby return -> early exit.
# GATES (all must pass before evidence is published):
#   - BOT SEAT/START: the server row is mode=VS_AI, hosted by the run's
#     account, observed in LOBBY with exactly ONE human seat (seat 0 = the
#     run's user), then IN_PROGRESS with exactly TWO distinct seats where
#     seat 1 is the seeded bot: opponentId matches that seat's userId, the
#     username is the seeded 'AI Bot' (backend/prisma/seed-ai.ts), and the id
#     is cross-checked against the public userByUsername('AI Bot') lookup; a
#     foreign human in a seat fails the gate (a 2-seat LOBBY row is only
#     accepted as the mid-startGame window with the seat-1 bot already
#     verified). Post-exit the FINISHED row must show the SAME bot id in
#     opponentId and seat 1;
#   - TERMINAL: FINISHED observed live AND on the post-exit authoritative
#     row; ABORTED observed at ANY point = hard fail (a presented victory may
#     never come from the abort path);
#   - EARLY EXIT: the client's measured exit time must be < RunSeconds - the
#     S08ExitAfter timeout must not be what ended the run (the verdict claims
#     an early exit, so it is measured, not assumed);
#   - SHOTMODE: only ShotMode='request' is accepted; anything else fails
#     before the client starts (pixel state gates are mandatory);
#   - RESULT (no invented result): the client trace has exactly one ordered
#     RESULT -> leave request -> accepted leave -> clean-exit tail; the trace
#     outcome (VICTORY/DEFEAT/DRAW) must match the server row winnerId
#     (VICTORY => winnerId is the human uid; DEFEAT => winnerId is a
#     non-null foreign id = the bot; DRAW => winnerId may be null);
#   - COVERAGE: ATTACK sent + COMBAT-RESULT seq= observed (real duel
#     traffic); scheme/pending lines reported in the manifest;
#   - SHOTS: fresh result screen with all four result-panel element markers
#     and zero gameplay markers; fresh lobby shot with the clean lobby panel
#     and the visual gameplay-region bright-pixel gate (x >= 25%, y >= 12.5%).
# Safety: per-process ENV credentials only (never argv, never printed; the
# command line is audited after start), hidden client, per-process 30 FPS cap
# via -ExecCmds="t.MaxFPS 30" (the packaged 60 FPS default in
# DefaultGameUserSettings is NOT modified), staged evidence published only
# after every gate passed, scoped host-ownership-validated abort of THIS
# run's game (only when it did NOT finish on its own), bounded wall-clock
# timeout that stops ONLY this run's client process TREE: the staged root
# launcher plus its verified staged child(ren), never an unverifiable or
# unrelated process. The room code is
# redacted from all published logs and from console output (including the
# console trace tail). A transient failure of the cleanup row lookup cannot
# fail an already authoritatively-verified FINISHED run; cleanup failures on
# a nonterminal row still fail the script.
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Exe) { $Exe = Join-Path $RepoRoot 'unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe' }
if (-not $EvidenceDir) { $EvidenceDir = Join-Path $RepoRoot 'docs\game-design\evidence\S10\run' }

# ---- pure helpers (script scope so -SelfTest can exercise them offline) ----

function Get-RedactedText([string]$Text, [string]$Code) {
  if ($Code) { return $Text.Replace($Code, '<redacted>') }
  return $Text
}

function Assert-ShotModeSupported([string]$Mode) {
  if ($Mode -cne 'request') {
    throw "ShotMode='$Mode' rejected - pixel state gates are mandatory for published evidence (only 'request' is accepted)"
  }
}

function Test-EarlyExit([double]$ElapsedSeconds, [int]$RunSeconds) {
  return ($ElapsedSeconds -lt $RunSeconds)
}

# Ordered terminal tail: exactly one of each marker, in order.
# Returns $null on success or the first problem found.
function Test-TailOrder([string]$TraceText) {
  $tailMarkers = @(
    @{ name = 'result'; pattern = ' RESULT seq=\d+ outcome='; literal = ' RESULT seq=' },
    @{ name = 'leave request'; pattern = [regex]::Escape('RESULT lobby-return sent (leaveGame)'); literal = 'RESULT lobby-return sent (leaveGame)' },
    @{ name = 'accepted leave'; pattern = [regex]::Escape('LEFT room='); literal = 'LEFT room=' },
    @{ name = 'clean exit'; pattern = [regex]::Escape('S09AUTO duel flow complete'); literal = 'S09AUTO duel flow complete' }
  )
  $previousIndex = -1
  foreach ($marker in $tailMarkers) {
    $count = [regex]::Matches($TraceText, $marker.pattern).Count
    if ($count -ne 1) { return "$($marker.name) marker count is $count (expected exactly one)" }
    $index = $TraceText.IndexOf($marker.literal, [StringComparison]::Ordinal)
    if ($index -le $previousIndex) { return "terminal tail is out of order at $($marker.name)" }
    $previousIndex = $index
  }
  return $null
}

# Seat gate for one observed game row. Verdicts:
#   WAIT              - nothing decisive yet (transient read, unrelated
#                       status, or the bot committed but the LOBBY ->
#                       IN_PROGRESS transition is not visible yet)
#   LOBBY_ONE_SEAT    - LOBBY with exactly the run's human seat at seat 0
#   BOT_STARTED       - IN_PROGRESS/FINISHED with exactly 2 distinct seats,
#                       seat 0 human, seat 1 the seeded bot (opponentId match,
#                       username match, optional userByUsername id match)
#   FAIL (+reason)    - the row violates the gate (foreign human in a seat,
#                       wrong opponentId/username/seat ids, >2 seats)
function Test-VsAiSeatRow($Row, [string]$HumanUid, [string]$BotUsername, $BotIdByUsername) {
  $r = @{ verdict = 'WAIT'; reason = ''; botUserId = $null; botUsername = $null; botSeatOrder = $null }
  if (-not $Row) { $r.reason = 'row is null'; return $r }
  $players = @($Row.players)
  $status = [string]$Row.status
  if ($status -eq 'LOBBY') {
    if ($players.Count -eq 0) { $r.reason = 'LOBBY row with zero players (transient read)'; return $r }
    if ($players.Count -eq 1) {
      $p = $players[0]
      if ($p.userId -cne $HumanUid) {
        $r.verdict = 'FAIL'
        $r.reason = "LOBBY row's single seat is user {0} ({1}), not this run's human user" -f $p.userId, $p.username
        return $r
      }
      if ([int]$p.seatOrder -ne 0) {
        $r.verdict = 'FAIL'
        $r.reason = "LOBBY row's human seat is seatOrder $($p.seatOrder), expected 0"
        return $r
      }
      if ($Row.opponentId) {
        # setupAiOpponent writes opponentId and the bot seat in ONE
        # transaction, so a one-seat LOBBY with an opponentId means a
        # foreign human joined (no GamePlayer seat row yet) - and would also
        # block the bot from ever taking the seat.
        $r.verdict = 'FAIL'
        $r.reason = "LOBBY row has one human seat but opponentId '$($Row.opponentId)' is already set - a foreign human joined the room"
        return $r
      }
      $r.verdict = 'LOBBY_ONE_SEAT'; return $r
    }
    if ($players.Count -gt 2) {
      $seatList = ($players | ForEach-Object { '{0}({1})' -f $_.userId, $_.username }) -join ', '
      $r.verdict = 'FAIL'
      $r.reason = "LOBBY row has $($players.Count) seats [$seatList] - more than human + bot"
      return $r
    }
    # LOBBY with exactly 2 seats is legitimate ONLY as the mid-startGame
    # window: setupAiOpponent commits the bot seat in its own transaction
    # BEFORE the LOBBY->IN_PROGRESS transition. The shared two-seat checks
    # below must verify seat 1 is the bot - a foreign human join fails there.
  } elseif ($status -ne 'IN_PROGRESS' -and $status -ne 'FINISHED') {
    $r.reason = "status $status (no seat verdict yet)"
    return $r
  }
  if ($players.Count -ne 2) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row has $($players.Count) seats (expected exactly 2: human + bot)"
    return $r
  }
  $seat0 = $players | Where-Object { [int]$_.seatOrder -eq 0 } | Select-Object -First 1
  $seat1 = $players | Where-Object { [int]$_.seatOrder -eq 1 } | Select-Object -First 1
  if (-not $seat0 -or -not $seat1) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row seats are not the distinct seatOrder pair {0,1}"
    return $r
  }
  if ($seat0.userId -cne $HumanUid) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row seat 0 is user $($seat0.userId), not this run's human user"
    return $r
  }
  $botId = [string]$seat1.userId
  if ($botId -ceq $HumanUid) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row has the human user in BOTH seats"
    return $r
  }
  if (-not $Row.opponentId) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row has no opponentId"
    return $r
  }
  if ([string]$Row.opponentId -cne $botId) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row opponentId '$($Row.opponentId)' does not match seat-1 user '$botId'"
    return $r
  }
  if ($seat1.username -cne $BotUsername) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row seat-1 username '$($seat1.username)' is not the seeded bot username '$BotUsername' (backend/prisma/seed-ai.ts)"
    return $r
  }
  # opponent.username may be 'Hidden' when the profile is private - the id
  # is still authoritative; only a visible non-bot name is a violation.
  if ($Row.opponent -and $null -ne $Row.opponent.username -and
      [string]$Row.opponent.username -cne 'Hidden' -and
      [string]$Row.opponent.username -cne $BotUsername) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row opponent username '$($Row.opponent.username)' is not the seeded bot username '$BotUsername'"
    return $r
  }
  if ($BotIdByUsername -and $botId -cne $BotIdByUsername) {
    $r.verdict = 'FAIL'
    $r.reason = "$status row seat-1/bot id '$botId' does not match userByUsername('$BotUsername') = '$BotIdByUsername'"
    return $r
  }
  $r.botUserId = $botId
  $r.botUsername = [string]$seat1.username
  $r.botSeatOrder = [int]$seat1.seatOrder
  if ($status -eq 'LOBBY') {
    # Bot committed, IN_PROGRESS transition not yet visible - wait for it.
    $r.reason = 'LOBBY with the verified bot already seated (mid-startGame window)'
    return $r
  }
  $r.verdict = 'BOT_STARTED'
  return $r
}

# ---- scoped client-process stop (launcher + verified child) ----
# The packaged staged root Unmatched.exe is a LAUNCHER: it immediately spawns
# the real UE client child at Windows/Unmatched/Binaries/Win64/Unmatched.exe.
# Killing only the launcher pid leaves that child rendering (and holding the
# inherited console pipes), which hangs the parent shell - observed live in
# the abort run of 20260927-183807. Every stop path must instead stop the
# verified CHILD first, then the verified launcher. Verification is
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
    # run F (DE-031): a launcher record without ExecutablePath made GetFullPath("") throw and left the room IN_PROGRESS;
    # an empty path is "unverified, left running" like any other unattributable record (fail closed), not a crash.
    $liveExePath = [string]$lrec.ExecutablePath
    $liveExe = if ($liveExePath) { [System.IO.Path]::GetFullPath($liveExePath) } else { '' }
    $wantExe = [System.IO.Path]::GetFullPath($LauncherExe)
    $lcmd = [string]$lrec.CommandLine
    if (-not $liveExe) {
      $unverified += "launcher pid $LauncherPid exposes no ExecutablePath - left running"
    } elseif (-not [string]::Equals($liveExe, $wantExe, [System.StringComparison]::OrdinalIgnoreCase)) {
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

function Invoke-S10SelfTests {
  $Script:SelfTestFailures = 0

  # redaction
  $red = Get-RedactedText 'LEFT room=r1 code=AB12 done code=AB12' 'AB12'
  Assert-Cond ($red -eq 'LEFT room=r1 code=<redacted> done code=<redacted>') 'redaction: replaces every code occurrence' "got: $red"
  Assert-Cond ((Get-RedactedText 'no codes here' 'ZZ99') -eq 'no codes here') 'redaction: passthrough when code absent' ''
  Assert-Cond ((Get-RedactedText 'anything' '').Length -gt 0) 'redaction: empty code is a no-op' ''

  # tail ordering - fixtures use the real timestamped trace line shape
  # ('<stamp> RESULT seq=...'), which the live pattern (' RESULT seq=\d+')
  # requires (a leading space before RESULT).
  $goodTail = "2026.09.27-13.21.50 noise`n2026.09.27-13.21.50 RESULT seq=101 outcome=VICTORY winner=Medusa`n2026.09.27-13.21.52 RESULT lobby-return sent (leaveGame)`n2026.09.27-13.21.52 LEFT room=cmuX`n2026.09.27-13.21.56 S09AUTO duel flow complete (GAME_OVER -> result shown -> lobby return) - exiting`n"
  $e = Test-TailOrder $goodTail
  Assert-Cond ($null -eq $e) 'tail order: accepts the canonical ordered tail' "unexpected error: $e"
  $dupTail = $goodTail + "2026.09.27-13.22.01 RESULT seq=102 outcome=DRAW winner=(none)`n"
  $e = Test-TailOrder $dupTail
  Assert-Cond ($e -match 'exactly one') 'tail order: duplicate result marker fails' "got: $e"
  $revTail = "2026.09.27-13.21.50 noise`n2026.09.27-13.21.52 RESULT lobby-return sent (leaveGame)`n2026.09.27-13.21.50 RESULT seq=101 outcome=VICTORY winner=Medusa`n2026.09.27-13.21.52 LEFT room=cmuX`n2026.09.27-13.21.56 S09AUTO duel flow complete`n"
  $e = Test-TailOrder $revTail
  Assert-Cond ($e -match 'out of order') 'tail order: leave-before-result fails' "got: $e"
  $missingTail = "2026.09.27-13.21.50 noise`n2026.09.27-13.21.52 RESULT lobby-return sent (leaveGame)`n2026.09.27-13.21.52 LEFT room=cmuX`n2026.09.27-13.21.56 S09AUTO duel flow complete`n"
  $e = Test-TailOrder $missingTail
  Assert-Cond ($e -match 'exactly one') 'tail order: missing result marker fails' "got: $e"
  $e = Test-TailOrder 'RESULT seq=1 outcome=VICTORY winner=X RESULT lobby-return sent (leaveGame) LEFT room=r S09AUTO duel flow complete'
  Assert-Cond ($e -match 'exactly one') 'tail order: untimestamped/foreign trace shape is NOT accepted' "got: $e"

  # early exit measurement
  Assert-Cond (Test-EarlyExit 45 600) 'early exit: 45s < 600s passes' ''
  Assert-Cond (Test-EarlyExit 599.9 600) 'early exit: just under RunSeconds passes' ''
  Assert-Cond (-not (Test-EarlyExit 600 600)) 'early exit: exactly RunSeconds fails' ''
  Assert-Cond (-not (Test-EarlyExit 720 600)) 'early exit: hard-deadline kill window fails' ''

  # ShotMode guard
  $threw = $false
  try { Assert-ShotModeSupported 'none' } catch { $threw = $true }
  Assert-Cond $threw 'shot mode: non-request rejected' ''
  $threw = $false
  try { Assert-ShotModeSupported 'request' } catch { $threw = $true }
  Assert-Cond (-not $threw) 'shot mode: request accepted' ''

  # seat-row gate
  $human = 'user-human'
  $bot = 'user-bot-ai'
  $hSeat = [pscustomobject]@{ userId = $human; username = 'Human'; seatOrder = 0 }
  $bSeat = [pscustomobject]@{ userId = $bot; username = 'AI Bot'; seatOrder = 1 }
  $oppOk = [pscustomobject]@{ userId = $bot; username = 'AI Bot' }

  $v = Test-VsAiSeatRow @{ status = 'LOBBY'; players = @($hSeat); opponentId = $null; opponent = $null } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'LOBBY_ONE_SEAT') 'seat row: LOBBY with one human seat accepts' "verdict=$($v.verdict) reason=$($v.reason)"

  $v = Test-VsAiSeatRow @{ status = 'LOBBY'; players = @($hSeat, $bSeat); opponentId = $bot; opponent = $oppOk } $human 'AI Bot' $bot
  Assert-Cond ($v.verdict -eq 'WAIT' -and $v.botUserId -ceq $bot) 'seat row: LOBBY with the verified bot seated is WAIT (mid-startGame window)' "verdict=$($v.verdict) reason=$($v.reason)"

  $foreignSeat1 = [pscustomobject]@{ userId = 'user-foreign'; username = 'Stranger'; seatOrder = 1 }
  $v = Test-VsAiSeatRow @{ status = 'LOBBY'; players = @($hSeat, $foreignSeat1); opponentId = 'user-foreign'; opponent = [pscustomobject]@{ userId = 'user-foreign'; username = 'Stranger' } } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'FAIL' -and $v.reason -match 'seeded bot username') 'seat row: 2-seat LOBBY with a foreign human fails' "verdict=$($v.verdict) reason=$($v.reason)"

  $v = Test-VsAiSeatRow @{ status = 'LOBBY'; players = @($hSeat); opponentId = 'user-foreign'; opponent = $null } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'FAIL' -and $v.reason -match 'foreign human joined') 'seat row: one-seat LOBBY with foreign opponentId fails fast' "verdict=$($v.verdict) reason=$($v.reason)"

  $foreignSeat = [pscustomobject]@{ userId = 'user-foreign'; username = 'Stranger'; seatOrder = 0 }
  $v = Test-VsAiSeatRow @{ status = 'LOBBY'; players = @($foreignSeat); opponentId = $null; opponent = $null } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'FAIL' -and $v.reason -match "not this run's human user") 'seat row: foreign single LOBBY seat fails' "verdict=$($v.verdict) reason=$($v.reason)"

  $inProg = @{ status = 'IN_PROGRESS'; players = @($hSeat, $bSeat); opponentId = $bot; opponent = $oppOk }
  $v = Test-VsAiSeatRow $inProg $human 'AI Bot' $bot
  Assert-Cond ($v.verdict -eq 'BOT_STARTED' -and $v.botUserId -ceq $bot -and $v.botSeatOrder -eq 1 -and $v.botUsername -eq 'AI Bot') 'seat row: IN_PROGRESS human+AI Bot accepts' "verdict=$($v.verdict) reason=$($v.reason)"

  $v = Test-VsAiSeatRow @{ status = 'FINISHED'; players = @($hSeat, $bSeat); opponentId = $bot; opponent = $oppOk } $human 'AI Bot' $bot
  Assert-Cond ($v.verdict -eq 'BOT_STARTED') 'seat row: FINISHED re-verification accepts the same shape' "verdict=$($v.verdict) reason=$($v.reason)"

  $v = Test-VsAiSeatRow $inProg $human 'AI Bot' 'user-other'
  Assert-Cond ($v.verdict -eq 'FAIL' -and $v.reason -match 'userByUsername') 'seat row: bot id not matching userByUsername fails' "verdict=$($v.verdict) reason=$($v.reason)"

  $v = Test-VsAiSeatRow @{ status = 'IN_PROGRESS'; players = @($hSeat, $bSeat); opponentId = 'user-x'; opponent = $oppOk } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'FAIL' -and $v.reason -match 'does not match seat-1') 'seat row: opponentId != seat-1 fails' "verdict=$($v.verdict) reason=$($v.reason)"

  $wrongName = [pscustomobject]@{ userId = $bot; username = 'SomeUser'; seatOrder = 1 }
  $v = Test-VsAiSeatRow @{ status = 'IN_PROGRESS'; players = @($hSeat, $wrongName); opponentId = $bot; opponent = [pscustomobject]@{ userId = $bot; username = 'SomeUser' } } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'FAIL' -and $v.reason -match 'seeded bot username') 'seat row: foreign human username in seat 1 fails' "verdict=$($v.verdict) reason=$($v.reason)"

  $dupSeat = [pscustomobject]@{ userId = $bot; username = 'AI Bot'; seatOrder = 0 }
  $v = Test-VsAiSeatRow @{ status = 'IN_PROGRESS'; players = @($hSeat, $dupSeat); opponentId = $bot; opponent = $oppOk } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'FAIL' -and $v.reason -match 'distinct seatOrder') 'seat row: duplicated seatOrder fails' "verdict=$($v.verdict) reason=$($v.reason)"

  $third = [pscustomobject]@{ userId = 'user-3'; username = 'Third'; seatOrder = 2 }
  $v = Test-VsAiSeatRow @{ status = 'IN_PROGRESS'; players = @($hSeat, $bSeat, $third); opponentId = $bot; opponent = $oppOk } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'FAIL' -and $v.reason -match 'expected exactly 2') 'seat row: three seats fail' "verdict=$($v.verdict) reason=$($v.reason)"

  $v = Test-VsAiSeatRow @{ status = 'IN_PROGRESS'; players = @($hSeat, $bSeat); opponentId = $bot; opponent = [pscustomobject]@{ userId = $bot; username = 'Hidden' } } $human 'AI Bot' $bot
  Assert-Cond ($v.verdict -eq 'BOT_STARTED') 'seat row: privacy-hidden opponent username still accepts (id is authoritative)' "verdict=$($v.verdict) reason=$($v.reason)"

  $v = Test-VsAiSeatRow @{ status = 'WAITING'; players = @($hSeat); opponentId = $null; opponent = $null } $human 'AI Bot' $null
  Assert-Cond ($v.verdict -eq 'WAIT') 'seat row: unrelated status is WAIT, not FAIL' "verdict=$($v.verdict)"

  # scoped client-stop identity verification (synthetic Win32_Process records;
  # the pure checker is offline - no process enumeration happens here)
  $stRoot = 'C:\staged\Windows'
  $runTag = 'C:\Temp\s10-vsai-20260927-182105-43804'
  $okChild = [pscustomobject]@{ ProcessId = 42092
    ExecutablePath = 'C:\staged\Windows\Unmatched\Binaries\Win64\Unmatched.exe'
    CommandLine = '"C:\staged\Windows\Unmatched\Binaries\Win64\Unmatched.exe" /Game/S08/S08Arena -S08Trace=C:\Temp\s10-vsai-20260927-182105-43804\vsai-client.trace.log' }
  $r = Test-ThisRunProcessRecord $okChild $stRoot $runTag
  Assert-Cond ($null -eq $r) 'client stop: staged child exe + this run tag accepts' "unexpected error: $r"
  $caseChild = [pscustomobject]@{ ProcessId = 1
    ExecutablePath = 'c:\STAGED\windows\Unmatched\Binaries\Win64\Unmatched.exe'
    CommandLine = "Unmatched.exe -S08Trace=$runTag\vsai-client.trace.log" }
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
    CommandLine = 'Unmatched.exe -S08Trace=C:\Temp\s10-vsai-OTHER-9999\vsai-client.trace.log' }
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

  Write-Output ("self-tests complete: {0} failure(s)" -f $Script:SelfTestFailures)
}

if ($SelfTest) {
  Invoke-S10SelfTests
  if ($Script:SelfTestFailures -gt 0) { exit 1 }
  return
}

Assert-ShotModeSupported $ShotMode

function Set-StagedResolution([string]$ExePath, [int]$W, [int]$H) {
  $gsDir = Join-Path (Split-Path -Parent $ExePath) 'Unmatched\Saved\Config\Windows'
  New-Item -ItemType Directory -Force -Path $gsDir | Out-Null
  $gs = Join-Path $gsDir 'GameUserSettings.ini'
  # Resolution keys only. NO FrameRateLimit here: a persisted value would
  # override the packaged 60 FPS default outside this demo. The per-process
  # cap is -ExecCmds="t.MaxFPS 30" instead; effective FPS is NOT claimed
  # without measurement.
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
if ($FullHd) { Set-StagedResolution $Exe 1920 1080 } else { Set-StagedResolution $Exe 1280 720 }

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Script:CleanupFailure = $null
$Script:ThisRunGameId = $null
$Script:ThisRunGameCode = $null
# Set to $true only after the post-exit authoritative row gate verified
# FINISHED - from that point a transient cleanup lookup failure must not
# fail an already published run (nonterminal cleanup failures still fail).
$Script:RowVerifiedFinished = $false
$Script:BotUserId = $null
$Script:BotUsernameObserved = $null
$Script:BotSeatOrderObserved = $null
$Script:BotIdByUsername = $null

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
  if (-not $login.data.login.accessToken) { throw "login failed for the configured VS_AI account" }
  $listBody = @{ query = 'query HL { heroList(limit: 200) { items { id name } } }' } | ConvertTo-Json
  $list = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers @{ authorization = "Bearer $($login.data.login.accessToken)" } -Body $listBody
  $hero = $list.data.heroList.items | Where-Object { $_.name -eq $Name } | Select-Object -First 1
  if (-not $hero) { $hero = $list.data.heroList.items[0] }
  return $hero.id
}

function Start-VsAiClient([string[]]$CliArgs, [string]$Email, [string]$Password) {
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
  return [System.Diagnostics.Process]::Start($psi)
}

function Stop-ThisRunGame {
  if (-not $Script:ThisRunGameId) {
    Write-Output "cleanup: no game was created by this run - nothing to abort"
    return
  }
  try {
    $loginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }'; variables = @{ input = @{ email = $Human.email; password = $Human.password } } } | ConvertTo-Json -Depth 5
    $login = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBody
    Assert-GqlOk $login 'cleanup login'
    $token = $login.data.login.accessToken
    $uid = $login.data.login.user.id
    $headers = @{ authorization = "Bearer $token" }
    $q = @{ query = 'query G($id: String!) { game(id: $id) { id code mode status hostId } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
    $g = $null
    $lookupErr = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
      try {
        $g = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $q
        break
      } catch { $lookupErr = $_.Exception.Message; Start-Sleep -Seconds 2 }
    }
    if (-not $g) { throw "terminal row lookup failed after 3 attempts: $lookupErr" }
    $lookupErrors = @()
    if ($g.PSObject.Properties['errors'] -and $null -ne $g.errors) { $lookupErrors = @($g.errors) }
    $notFound = @($lookupErrors | Where-Object { $_.message -match 'не найдена|not found' }).Count -gt 0
    if ($notFound) {
      Write-Output "cleanup: game $($Script:ThisRunGameId) no longer resolves - nothing to abort"
      return
    }
    Assert-GqlOk $g 'cleanup game lookup'
    $game = $g.data.game
    if (-not $game) { Write-Output "cleanup: game $($Script:ThisRunGameId) no longer resolves - nothing to abort"; return }
    if ($Script:ThisRunGameCode -and $game.code -and ($game.code -cne $Script:ThisRunGameCode)) {
      throw "REFUSING abort - room code mismatch for game $($Script:ThisRunGameId)"
    }
    if ($game.mode -cne 'VS_AI') {
      throw "REFUSING abort - game $($Script:ThisRunGameId) is mode $($game.mode), not this run's VS_AI room"
    }
    # A match that reached GAME_OVER on its own is FINISHED: leaveGame (already
    # sent by the client) is the regular exit and must NEVER be aborted.
    if ($game.status -eq 'FINISHED') {
      Write-Output "cleanup: game $($Script:ThisRunGameId) is FINISHED - match completed on its own, no abort"
      return
    }
    if (@('ABORTED', 'COMPLETED') -contains $game.status) {
      Write-Output "cleanup: game $($Script:ThisRunGameId) already terminal ($($game.status))"
      return
    }
    if ($game.hostId -cne $uid) {
      throw "REFUSING abort - host-ownership validation failed for game $($Script:ThisRunGameId)"
    }
    $a = @{ query = 'mutation AB($gameId: String!) { abortGame(gameId: $gameId) { id status } }'; variables = @{ gameId = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
    $abortErr = $null
    $r = $null
    try {
      $r = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $a
      Assert-GqlOk $r 'cleanup abortGame'
    } catch {
      $abortErr = $_.Exception.Message
    }
    if ($abortErr) {
      # The server's 'a completed game cannot be aborted' rejection IS an
      # authoritative terminal verdict: re-read the row on ANY abort failure
      # and accept FINISHED as success.
      $g2 = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $q
      Assert-GqlOk $g2 'cleanup post-reject verification'
      $after = $g2.data.game
      $afterStatus = if ($after) { $after.status } else { '<gone>' }
      if ($afterStatus -eq 'FINISHED') {
        Write-Output "cleanup: abortGame rejected and the row reads FINISHED - match completed on its own (server-authoritative terminal verdict)"
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
      if (-not $after -or $after.id -cne $Script:ThisRunGameId -or $after.status -cne 'ABORTED') {
        $afterStatus = if ($after) { $after.status } else { '<gone>' }
        throw "game $($Script:ThisRunGameId) is NOT terminal ABORTED after abortGame (status=$afterStatus)"
      }
    }
    Write-Output "cleanup: aborted THIS run's game id=$($Script:ThisRunGameId) status=ABORTED (verified)"
  } catch {
    if ($Script:RowVerifiedFinished) {
      # The post-exit authoritative gate already verified FINISHED; a
      # transient lookup/verify failure here must not flip a published
      # successful run into an exit failure.
      Write-Output "cleanup: transient failure after FINISHED was already authoritatively verified - not failing the published run (error: $($_.Exception.Message))"
    } else {
      $Script:CleanupFailure = "scoped cleanup of game $($Script:ThisRunGameId) failed: $($_.Exception.Message)"
      Write-Output "cleanup: FAILED - $($Script:CleanupFailure)"
    }
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
      $name = $Matches[1]; $value = $Matches[2]
      if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue)) {
        Set-Item "Env:$name" $value
      }
    }
  }
  $Human = @{ email = $env:S10_DEMO_HUMAN_EMAIL; password = $env:S10_DEMO_HUMAN_PASSWORD }
}
foreach ($pair in @(
    @('S10_DEMO_HUMAN_EMAIL', $Human.email), @('S10_DEMO_HUMAN_PASSWORD', $Human.password))) {
  if (-not $pair[1]) { throw "missing $($pair[0]) in process environment" }
}

function Invoke-VsAiDemo {
  $heroId = Get-Hero $Human.email $Human.password $HeroName
  Write-Output "hero=$heroId (name=$HeroName)"

  $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Script:Staging = Join-Path ([System.IO.Path]::GetTempPath()) "s10-vsai-$Stamp-$PID"
  New-Item -ItemType Directory -Force -Path $Script:Staging | Out-Null
  Write-Output "staging: $Script:Staging"
  # Verified child pids of THIS run's launcher, captured early (see the room
  # wait loop below) so the scoped stop never relies on post-mortem
  # ParentProcessId reads alone.
  $Script:ChildPids = New-Object System.Collections.Generic.List[int]

  $shots = Join-Path $Script:Staging 'human'
  New-Item -ItemType Directory -Force -Path $shots | Out-Null
  $trace = Join-Path $Script:Staging 'vsai-client.trace.log'

  # t.MaxFPS 30 is a per-process console-command cap for this hidden demo
  # client; the packaged 60 FPS default is untouched and effective FPS is
  # NOT claimed (no measured FPS/frame-time data exists).
  $resX = if ($FullHd) { 1920 } else { 1280 }
  $resY = if ($FullHd) { 1080 } else { 720 }
  $common = @("-windowed", "-resx=$resX", "-resy=$resY", "-RenderOffScreen",
    "-ExecCmds=`"t.MaxFPS 30`"", "log=GrepLog",
    "-ForceAbandonSequences", "-S08Api=$Api", "-S09ShotMode=$ShotMode")
  if (-not $PlayerView) { $common += "-S09Markers" }  # HB-01: the marker pixel gates below need the debug layer (04-hud-spec s5.3)
  if ($FullHd) { $common += '-ForceRes' }  # as run-combat-demo -FullHd: without it the hidden window stays 888x500
  $clientArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08Create", "-S08Mode=VS_AI", "-S08HeroId=$heroId",
    "-S08Trace=$trace", "-S09Flow", "-S09Combat=attack+scheme",
    "-S09ShotDir=$shots", "-S08ExitAfter=$RunSeconds") + @($ClientExtraArgs -split '\+' | Where-Object { $_ })
  if ($ScreenShots) { $clientArgs += '-S08ScreenShots' }  # VS-3 SC-01

  $proc = $null
  $Published = $false
  try {
    # Pre-run login for the authoritative row polls.
    $loginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }'; variables = @{ input = @{ email = $Human.email; password = $Human.password } } } | ConvertTo-Json -Depth 5
    $login = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBody
    Assert-GqlOk $login 'pre-run login'
    $Script:UserId = $login.data.login.user.id
    if (-not $Script:UserId) { throw "login returned no user id" }
    $token = $login.data.login.accessToken
    $pollHeaders = @{ authorization = "Bearer $token" }

    # Stronger bot identity: the public userByUsername lookup resolves the
    # seeded 'AI Bot' (backend/prisma/seed-ai.ts) to its id; every seat gate
    # then cross-checks the observed opponent against that id. If the lookup
    # fails, the run fails - no weaker identity proof is invented.
    $ubBody = @{ query = 'query UB($u: String!) { userByUsername(username: $u) { id username } }'; variables = @{ u = 'AI Bot' } } | ConvertTo-Json -Depth 5
    $ub = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $ubBody
    Assert-GqlOk $ub "bot identity lookup (userByUsername 'AI Bot')"
    if (-not $ub.data.userByUsername.id) {
      throw "userByUsername('AI Bot') returned no id - cannot verify the seeded bot identity"
    }
    $Script:BotIdByUsername = [string]$ub.data.userByUsername.id
    Write-Output "bot identity: userByUsername('AI Bot') resolved (username reported as '$($ub.data.userByUsername.username)')"

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

    $rowQuery = @{ query = 'query G($id: String!) { game(id: $id) { id mode status hostId opponentId winnerId endedAt opponent { userId username } players { userId username seatOrder } } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 6
    $Script:StatusSeen = New-Object System.Collections.Generic.List[string]
    $sawOneSeat = $false
    $botStart = $null
    # Phase 1 - seat gate: this run's room must be VS_AI, hosted by the run's
    # account, observed in LOBBY with exactly ONE human seat (a 2-seat LOBBY
    # row is a foreign human join = fail), then IN_PROGRESS with exactly TWO
    # distinct seats where seat 1 is the seeded bot (opponentId match,
    # username 'AI Bot', id cross-checked via userByUsername). Bounded by the
    # client lifetime.
    $phase1Deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(60, $RunSeconds))
    while (-not $proc.HasExited -and [DateTime]::UtcNow -lt $phase1Deadline) {
      [void]$proc.WaitForExit(1000)
      $row = $null
      try {
        $g = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $pollHeaders -Body $rowQuery
        Assert-GqlOk $g 'lobby-phase row lookup'
        $row = $g.data.game
      } catch {} # transient poll failure - retry on the next tick
      if (-not $row) { continue }
      if ($row.mode -cne 'VS_AI') {
        throw "created game $($Script:ThisRunGameId) is mode $($row.mode), not VS_AI"
      }
      if ($row.hostId -cne $Script:UserId) {
        throw "created game $($Script:ThisRunGameId) is hosted by $($row.hostId), not this run's user"
      }
      if ($Script:StatusSeen.Count -eq 0 -or $Script:StatusSeen[$Script:StatusSeen.Count - 1] -cne $row.status) {
        $Script:StatusSeen.Add($row.status)
      }
      $v = Test-VsAiSeatRow $row $Script:UserId 'AI Bot' $Script:BotIdByUsername
      if ($v.verdict -eq 'FAIL') {
        throw "BOT SEAT/START gate: $($v.reason) (statuses: $($Script:StatusSeen -join ' -> '))"
      }
      if ($v.verdict -eq 'LOBBY_ONE_SEAT') { $sawOneSeat = $true }
      if ($v.verdict -eq 'BOT_STARTED' -and [string]$row.status -eq 'IN_PROGRESS') { $botStart = $v; break }
    }
    if (-not $sawOneSeat) {
      throw "BOT SEAT/START gate: never observed the VS_AI room in LOBBY with exactly ONE human seat (statuses: $($Script:StatusSeen -join ' -> '))"
    }
    if (-not $botStart) {
      throw "BOT SEAT/START gate: never observed IN_PROGRESS with exactly 2 seats where seat 1 is the seeded 'AI Bot' (statuses: $($Script:StatusSeen -join ' -> '))"
    }
    $Script:BotUserId = $botStart.botUserId
    $Script:BotUsernameObserved = $botStart.botUsername
    $Script:BotSeatOrderObserved = $botStart.botSeatOrder
    Write-Output ("bot seat gate: IN_PROGRESS observed with 2 seats; seat {0} is '{1}' and matches opponentId + userByUsername('AI Bot')" -f $Script:BotSeatOrderObserved, $Script:BotUsernameObserved)

    # Phase 2 - run: watch the row + the single-client stream watchdog until
    # the client exits on its own (S08ExitAfter) or its terminal tail lands.
    # Bounded wall-clock timeout: never wait longer than RunSeconds + 120s
    # from the client start, then stop ONLY this process.
    $wd = @{ subscribed = $false; terminal = $false; lastSeq = -1; lastProgressUtc = [DateTime]::UtcNow }
    $hardDeadline = $clientStartUtc.AddSeconds($RunSeconds + 120)
    while (-not $proc.HasExited) {
      if ([DateTime]::UtcNow -gt $hardDeadline) {
        Write-Output "bounded timeout: scoped stop of this run's client (launcher pid=$($proc.Id) + verified child(ren)) after $($RunSeconds + 120)s"
        Stop-ThisRunClient -LauncherPid $proc.Id -LauncherExe $Script:ClientExeFull `
          -StagedRootFull $Script:ClientStagedRoot -RunTag $Script:Staging -KnownChildPids @($Script:ChildPids)
        break
      }
      [void]$proc.WaitForExit(1000)
      try {
        $g = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $pollHeaders -Body $rowQuery
        if ($g.data.game -and $g.data.game.status) {
          if ($Script:StatusSeen.Count -eq 0 -or $Script:StatusSeen[$Script:StatusSeen.Count - 1] -cne $g.data.game.status) {
            $Script:StatusSeen.Add($g.data.game.status)
          }
        }
      } catch {}
      if ($StallSeconds -gt 0 -and (Test-Path -LiteralPath $trace)) {
        $text = Get-Content -LiteralPath $trace -Raw
        $nowUtc = [DateTime]::UtcNow
        if ($text.Contains('RESULT seq=')) { $wd.terminal = $true }
        elseif (-not $wd.subscribed) {
          if ($text.Contains('SUBSCRIBED gameStateUpdated')) {
            $wd.subscribed = $true
            $wd.lastProgressUtc = $nowUtc
          }
        } else {
          $maxSeq = -1
          foreach ($m in [regex]::Matches($text, 'SNAPSHOT applied seq=(\d+)')) {
            $s = [int]$m.Groups[1].Value
            if ($s -gt $maxSeq) { $maxSeq = $s }
          }
          if ($maxSeq -gt $wd.lastSeq) {
            $wd.lastSeq = $maxSeq
            $wd.lastProgressUtc = $nowUtc
          } elseif (($nowUtc - $wd.lastProgressUtc).TotalSeconds -gt $StallSeconds) {
            throw "stalled stream: subscribed but no new 'SNAPSHOT applied seq=' for $StallSeconds s (last max seq=$($wd.lastSeq))"
          }
        }
      }
    }
    # bounded: a killed tree releases its pipes, but never wait unbounded
    if (-not $proc.HasExited) { [void]$proc.WaitForExit(15000) }
    Write-Output "client exited; server statuses observed: [$($Script:StatusSeen -join ' -> ')]"

    # ---- early-exit measurement (the verdict claims it, so measure it) ----
    $exitElapsed = ([DateTime]::UtcNow - $clientStartUtc).TotalSeconds
    Write-Output ("client exit measured at {0:N1}s (RunSeconds={1})" -f $exitElapsed, $RunSeconds)
    if (-not (Test-EarlyExit $exitElapsed $RunSeconds)) {
      throw ("client exit at {0:N1}s is NOT earlier than RunSeconds={1} - the S08ExitAfter timeout (or the hard deadline) ended the run, so the early-exit claim would be false" -f $exitElapsed, $RunSeconds)
    }

    # ---- trace terminal gates ----
    $traceText = Get-Content -LiteralPath $trace -Raw

    foreach ($needle in @(
        'SUBSCRIBED gameStateUpdated', 'SNAPSHOT applied', 'HUD seq=',
        'RESULT seq=', 'RESULT lobby-return sent (leaveGame)', 'LEFT room=',
        'S09AUTO duel flow complete')) {
      if (-not $traceText.Contains($needle)) { throw "client trace missing '$needle' (full tail not achieved - no evidence will be invented)" }
    }
    # One ordered terminal result -> leave request -> accepted reply -> exit.
    $tailErr = Test-TailOrder $traceText
    if ($tailErr) { throw "client trace terminal tail gate FAILED: $tailErr" }
    if ($traceText -match '(ATTACK|DEFENSE|RESOLVE|SCHEME|PEND) sent .*card') {
      throw "trace appears to log card identities with a combat command"
    }
    $invalidPhase = @($traceText -split "`n" | Where-Object { $_ -match 'Invalid phase' })
    if ($invalidPhase.Count -gt 0) {
      throw ("trace shows {0} authoritative 'Invalid phase' rejection(s) - a client gate is still sending commands outside the action phases" -f $invalidPhase.Count)
    }

    # ---- RESULT outcome + no-invented-result cross-check vs the server row ----
    $mOut = [regex]::Match($traceText, ' RESULT seq=\d+ outcome=([A-Z]+) winner=([^\r\n]+)')
    if (-not $mOut.Success) { throw 'trace has a RESULT line without a parseable outcome/winner' }
    $outcome = $mOut.Groups[1].Value
    $winnerHero = $mOut.Groups[2].Value.Trim()
    Write-Output "client outcome=$outcome winnerHero=$winnerHero"
    if (@('VICTORY', 'DEFEAT', 'DRAW') -notcontains $outcome) {
      throw "unknown RESULT outcome word: $outcome"
    }
    if ($outcome -ne 'DRAW' -and $winnerHero -eq '(none)') {
      throw "RESULT outcome $outcome carries no winner - refusing to publish an underived result"
    }

    # ---- authoritative terminal row gate (post-exit) ----
    if (@($Script:StatusSeen) -contains 'ABORTED') {
      throw "game $($Script:ThisRunGameId) was ABORTED during the run (statuses: $($Script:StatusSeen -join ' -> ')) - a presented victory must never come from the abort path"
    }
    $rr = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $pollHeaders -Body $rowQuery
    Assert-GqlOk $rr 'post-exit row lookup'
    $row = $rr.data.game
    if (-not $row) { throw "post-exit authoritative check FAILED - the row did not resolve for game $($Script:ThisRunGameId)" }
    if ($row.id -cne $Script:ThisRunGameId) { throw "post-exit row id mismatch: $($row.id)" }
    if ($row.mode -cne 'VS_AI') { throw "post-exit row mode is $($row.mode), not VS_AI" }
    if ($row.status -cne 'FINISHED') {
      throw "post-exit authoritative status is $($row.status), NOT FINISHED - the presented result has no server-side FINISHED row"
    }
    if (-not (@($Script:StatusSeen) -contains 'FINISHED')) {
      throw "FINISHED was never observed live (statuses: $($Script:StatusSeen -join ' -> '))"
    }
    # Same-seat re-verification through the identical gate the live phases
    # used, plus id stability: the FINISHED row must still show seat 1 as
    # the SAME verified bot (opponentId + userByUsername cross-check).
    $pv = Test-VsAiSeatRow $row $Script:UserId 'AI Bot' $Script:BotIdByUsername
    if ($pv.verdict -ne 'BOT_STARTED') {
      throw "post-exit FINISHED row bot-seat re-verification FAILED: $($pv.reason)"
    }
    if ($pv.botUserId -cne $Script:BotUserId -or [string]$row.opponentId -cne $Script:BotUserId) {
      throw ("post-exit bot seat id changed: phase-1 bot={0}, post-exit opponentId={1}, seat-1={2}" -f $Script:BotUserId, $row.opponentId, $pv.botUserId)
    }
    $botId = $Script:BotUserId
    if (-not $row.endedAt) { throw "post-exit FINISHED row has no endedAt" }
    # From here the row is authoritatively FINISHED-verified; a transient
    # cleanup lookup failure must not flip this run into an exit failure.
    $Script:RowVerifiedFinished = $true

    # Winner cross-check: the trace outcome must match the server winnerId.
    $winnerSeat = $null
    if ($outcome -eq 'VICTORY') {
      if ($row.winnerId -cne $Script:UserId) {
        throw "trace outcome VICTORY but server winnerId '$($row.winnerId)' is not this run's human user - invented result"
      }
      $winnerSeat = 'human'
    } elseif ($outcome -eq 'DEFEAT') {
      if (-not $row.winnerId) {
        throw "trace outcome DEFEAT but server winnerId is null - no authoritative winner"
      }
      if ($row.winnerId -cne $botId) {
        throw "trace outcome DEFEAT but server winnerId '$($row.winnerId)' is not the bot seat '$botId' - invented result"
      }
      $winnerSeat = 'bot'
    } else {
      if ($row.winnerId) {
        throw "trace outcome DRAW but server winnerId is '$($row.winnerId)' - outcome mismatch"
      }
      $winnerSeat = 'draw'
    }
    Write-Output "server row gate: FINISHED (mode=VS_AI, 2 seats: human + bot, endedAt set); trace outcome $outcome matches server winner (winnerSeat=$winnerSeat)"

    # ---- duel coverage (real authoritative traffic) ----
    $attackSeen = $traceText.Contains('ATTACK sent')
    $combatResultSeen = $traceText.Contains('COMBAT-RESULT seq=')
    $schemeSeen = $traceText.Contains('SCHEME done seq=') -or $traceText.Contains('SCHEME sent')
    Write-Output ("duel coverage: attack={0} combatResult={1} scheme={2}" -f $attackSeen, $combatResultSeen, $schemeSeen)
    if (-not $attackSeen) { throw 'no ATTACK sent this run - not a real duel' }
    if (-not $combatResultSeen) { throw 'no COMBAT-RESULT line this run - no damage ever landed' }

    # ---- shots: fresh result screen + clean lobby return ----
    function Assert-FreshShot([string]$Path, [DateTime]$ClientStartUtc, [string]$What) {
      if (-not (Test-Path -LiteralPath $Path)) { throw "$What shot missing: $Path" }
      $f = Get-Item -LiteralPath $Path
      if ($f.Length -lt 10KB) { throw "suspiciously small $What shot (likely black/empty): $Path" }
      if ($f.LastWriteTimeUtc -le $ClientStartUtc) { throw "$What shot predates its client process (stale file): $Path" }
      return $f
    }
    $resultShot = Assert-FreshShot (Join-Path $shots 's09-result-screen.png') $clientStartUtc 'result-screen'
    $lobbyShot = Assert-FreshShot (Join-Path $shots 's09-lobby-return.png') $clientStartUtc 'lobby-return'
    Write-Output ("result shot={0}B lobby shot={1}B" -f $resultShot.Length, $lobbyShot.Length)

    if ($PlayerView) {
      Write-Output 'PlayerView: result / lobby element-marker gates skipped (the client ran without -S09Markers); not a GD-039 acceptance run'
    } elseif ($ShotMode -eq 'request') {
      # unreachable after the top-level guard, kept as defense in depth
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
        @{ name = 'blocked'; r = 255; g = 64;  b = 176 }
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
          foreach ($mk in $Markers) { $stats[$mk.name + 'All'] = 0 }
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
                  $stats[$mk.name + 'All']++
                  break
                }
              }
            }
          }
          return $stats
        } finally { $bmp.Dispose() }
      }
      # Result screen: the COMPLETE panel - one marker per REQUIRED element;
      # every gameplay marker must be absent.
      $rs = Get-MarkerStats $resultShot.FullName
      if (-not (($rs.w -eq 1280 -and $rs.h -eq 720) -or ($rs.w -eq 1920 -and $rs.h -eq 1080))) {
        throw ("result shot is {0}x{1} - NOT 1280x720/1920x1080" -f $rs.w, $rs.h)
      }
      foreach ($part in @('resultscreen', 'resultoutcome', 'resultsupport', 'resultbutton')) {
        if ($rs[$part + 'All'] -lt 100) {
          throw ("result shot incomplete - '{0}' element marker too low ({1}); the panel was captured mid-paint or truncated" -f $part, $rs[$part + 'All'])
        }
      }
      foreach ($other in @('attack', 'defense', 'resolve', 'boost', 'pending', 'maneuver', 'discard', 'blocked', 'lobbypanel')) {
        if ($rs[$other + 'All'] -ne 0) {
          throw ("result shot shows a gameplay/lobby state marker: {0}={1}" -f $other, $rs[$other + 'All'])
        }
      }
      Write-Output ("result shot markers: header={0} outcome={1} support={2} button={3} (gameplay markers all-zero)" -f `
        $rs.resultscreenAll, $rs.resultoutcomeAll, $rs.resultsupportAll, $rs.resultbuttonAll)
      # Lobby: clean panel present, no in-duel markers, visual gameplay-region
      # gate (no bright pixels in x >= 25% / y >= 12.5%).
      $ls = Get-MarkerStats $lobbyShot.FullName
      if ($ls.lobbypanelAll -lt 100) {
        throw ("lobby shot missing the clean lobby entry panel (lobbypanel={0})" -f $ls.lobbypanelAll)
      }
      foreach ($duel in @('resultscreen', 'resultoutcome', 'resultsupport', 'resultbutton', 'pending', 'attack', 'defense', 'resolve', 'maneuver', 'discard')) {
        if ($ls[$duel + 'All'] -ne 0) {
          throw ("lobby shot still shows an in-duel marker: {0}={1}" -f $duel, $ls[$duel + 'All'])
        }
      }
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
      $bright = Get-GameplayRegionBright $lobbyShot.FullName
      if ($bright -gt 50) {
        throw ("lobby shot has {0} bright gameplay-region pixels (lum>=120, x>=25%/y>=12.5%) - stale board/fighter/HUD rendering survived the lobby return" -f $bright)
      }
      Write-Output ("lobby shot: clean lobby panel (lobbypanel={0}), no in-duel markers, gameplay region bright pixels={1} (<=50)" -f $ls.lobbypanelAll, $bright)
    } else {
      throw "ShotMode '$ShotMode' rejected - pixel state gates are mandatory (accepted: 'request')"
    }

    # ---- seq convergence (single client) ----
    $seqs = Select-String -Path $trace -Pattern 'SNAPSHOT applied seq=(\d+)' -AllMatches |
      ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value }
    $maxSeq = ($seqs | Measure-Object -Maximum).Maximum
    Write-Output "convergence: client maxSeq=$maxSeq"
    if (-not $maxSeq) { throw "missing applied seq in trace" }
    if ($maxSeq -lt 12) { throw "match did not run long enough: maxSeq=$maxSeq" }

    # ---- compact traces (code redacted) ----
    $compactPattern = 'S09AUTO|RESULT |LEFT room|COMBAT-RESULT|ATTACK sent|DEFENSE sent|NO-DEFENSE|RESOLVE sent|SCHEME done seq=|SCHEME sent|PEND |SNAPSHOT applied seq=|MODE seq=|VS_AI'
    $srcLines = Get-Content -LiteralPath $trace
    $kept = @($srcLines | Where-Object { $_ -match $compactPattern })
    if ($code) { $kept = @($kept | ForEach-Object { $_.Replace($code, '<redacted>') }) }
    [System.IO.File]::WriteAllLines((Join-Path $Script:Staging 'vsai-client.compact.log'), $kept, $Utf8NoBom)

    # ---- publish ----
    $publishNames = @('vsai-client.trace.log', 'vsai-client.compact.log')
    $allShots = @(Get-ChildItem -LiteralPath $shots -Filter 's09-*.png' -ErrorAction SilentlyContinue | Sort-Object Name)
    foreach ($shot in $allShots) { $publishNames += ('human\' + $shot.Name) }
    $RunDir = Join-Path $EvidenceDir ("vsai-" + $Stamp)
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
    $verdict = 'S10/GD-039: one-client packaged VS_AI live acceptance over the authoritative S10 backend - hidden client created a VS_AI room (one human seat in LOBBY, hosted by this run; any foreign join fails), the server bot took the second seat at startGame (row reached IN_PROGRESS with exactly 2 seats: seat 1 username AI Bot, opponentId matching that seat, id cross-checked against userByUsername(AI Bot), and the SAME bot id re-verified on the post-exit FINISHED row), the human driver played attack+scheme while the bot answered, the server-written GAME_OVER rendered a COMPLETE result screen (element markers present, gameplay markers absent), leaveGame returned the client to a CLEAN lobby (panel marker, no in-duel markers, zero bright gameplay-region pixels), the row is authoritative FINISHED with the trace outcome cross-checked against server winnerId (no invented result), never ABORTED, and the driver exited early (measured exit time < RunSeconds) instead of burning the timeout. Frame cap: per-process console command t.MaxFPS 30 (effective FPS NOT measured, no GPU claim; packaged 60 FPS default untouched)'
    if ($PlayerView) { $verdict = "VS-2 player view (no -S09Markers, result/lobby marker gates skipped; extra client args '$ClientExtraArgs', ${resX}x${resY}) - " + $verdict }
    $manifest = [ordered]@{
      stamp          = $Stamp
      verdict        = $verdict
      mode           = 'VS_AI'
      outcome        = $outcome
      winnerHero     = $winnerHero
      winnerSeat     = $winnerSeat
      serverStatuses = @($Script:StatusSeen)
      serverRow      = [ordered]@{
        id = $row.id
        status = $row.status
        mode = $row.mode
        seats = @($row.players).Count
        botSeat = [ordered]@{
          present = ($null -ne $Script:BotUserId)
          username = $Script:BotUsernameObserved
          seatOrder = $Script:BotSeatOrderObserved
          idMatchesUserByUsername = ($row.opponentId -ceq $Script:BotIdByUsername)
        }
        winnerIdRedacted = ($row.winnerId -ne $null)
        endedAt = [string]$row.endedAt
      }
      coverage       = [ordered]@{
        attack = $attackSeen; combatResult = $combatResultSeen; scheme = $schemeSeen
      }
      convergence    = [ordered]@{ clientMaxSeq = $maxSeq }
      files          = @()
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

    $ptrTmp = Join-Path $EvidenceDir ("latest-vsai.json.$Stamp-$PID.tmp")
    $ptr = Join-Path $EvidenceDir 'latest-vsai.json'
    [System.IO.File]::WriteAllText($ptrTmp, (([ordered]@{ current = (Split-Path $RunDir -Leaf); stamp = $Stamp }) | ConvertTo-Json), $Utf8NoBom)
    if (Test-Path -LiteralPath $ptr) {
      $ptrBak = Join-Path $EvidenceDir 'latest-vsai.json.bak'
      [System.IO.File]::Replace($ptrTmp, $ptr, $ptrBak)
      Remove-Item -LiteralPath $ptrBak -Force
    } else {
      [System.IO.File]::Move($ptrTmp, $ptr)
    }
    $Published = $true
    Write-Output "published evidence run dir: $RunDir (pointer: latest-vsai.json)"
    Write-Output "--- client trace (VS_AI tail) ---"
    Get-Content -LiteralPath $trace |
      Select-String -Pattern 'S09AUTO|RESULT|COMBAT-RESULT|LEFT room|VS_AI' | Select-Object -Last 20 |
      ForEach-Object { Get-RedactedText $_.Line $code }
  } finally {
    if ($proc) {
      # Scoped stop even when the launcher already exited on its own: Win32
      # keeps the child's recorded ParentProcessId, so a late child sweep is
      # still possible (and every candidate is re-verified before any stop).
      Stop-ThisRunClient -LauncherPid $proc.Id -LauncherExe $Script:ClientExeFull `
        -StagedRootFull $Script:ClientStagedRoot -RunTag $Script:Staging -KnownChildPids @($Script:ChildPids)
      if (-not $proc.HasExited) { [void]$proc.WaitForExit(15000) }
    }
    Stop-ThisRunGame
  }

  if ($Published) {
    Remove-TreeSafely $Script:Staging ([System.IO.Path]::GetTempPath())
  }
}

Invoke-VsAiDemo

if ($Script:CleanupFailure) {
  throw "scoped cleanup did not verify for this run's game: $($Script:CleanupFailure)"
}
