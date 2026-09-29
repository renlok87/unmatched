param(
  [string]$Exe = "",
  [string]$Api = "http://localhost:3100/graphql",
  [string]$EvidenceDir = "",
  [int]$RunSeconds = 120,
  [ValidateRange(1, 60)][int]$ClientFps = 30,
  [int]$JoinerDropWsAfter = 12,
  [int]$HostManeuverAfter = 25,
  # Opt-in ART-004/005 review on an explicitly selected art board: a Board row
  # id registered in unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json
  # (boards[].match.boardIds: the 5x6 Cobble review board or a T3.2 art
  # fixture). Its W x H, zone counts and light profile come from that data and
  # gate the traces ('BOARD WxH'). The default S08 20x20 path is unchanged.
  [string]$ArtPreviewBoardId = "",
  # Optional K2 review: zoom toward the selected host hero while the joiner
  # stays at K1. 1.6 is the written proposal; larger values are diagnostic.
  [double]$ArtPreviewFocusZoom = 0,
  # Opt-in ART-004 comparison: which isolated /Game/ArtPreview Medusa candidate
  # both clients load in the same live board/HUD path. Production is untouched.
  [ValidateSet('face-neck-v2', 'head-tilt-v3')][string]$ArtPreviewMedusaVariant = 'face-neck-v2',
  # Seconds after each client's game-mode start when the ArtPreview evidence
  # shot fires (the K2 hero selection happens at ShotAfter - 2). startGame must
  # land before ShotAfter - 2 for the camera to arrive; RunSeconds must leave
  # at least 10 s after the shot for the PNG write and the joiner's later start.
  [ValidateRange(4, 600)][int]$ArtPreviewShotAfter = 30,
  # Opt-in per-client frame timing in the trace (PERF config/window/summary:
  # effective fps, frame/GPU/game/render ms). Measurement only.
  [switch]$ClientPerf,
  # Opt-in CSV profiler capture per client (-csvCaptureFrames + -csvGpuStats):
  # per-frame FrameTime/GameThreadTime/RenderThreadTime and per-pass GPU busy
  # times in <stage>/Unmatched/Saved/Profiling/CSV. 0 = off.
  [ValidateRange(0, 100000)][int]$ClientCsvFrames = 0,
  # ART-004 stage 3 T2.2 (all opt-in, ArtPreviewBoardId only):
  # every live fighter of BOTH clients carries the Medusa candidate (team MI,
  # hero/sidekick scale) - the six-copies review; asserted as six
  # 'ARTPREVIEW allMedusa copy ... visual=1 mesh=' lines per client.
  [switch]$ArtPreviewAllMedusa,
  # Host-only flag input emulation after its evidence shot ('+'-separated:
  # wheelin, wheelout, space, clickhero, clickabove, clickcell, token*N). Every
  # step is traced 'INPUT ... src=flag'; real OS input is T4.3.
  [string]$ArtPreviewInputPlan = '',
  # Host-only exact-size HUD combat icon (24/32/48 px); 0 = client default 32.
  [ValidateSet(0, 24, 32, 48)][int]$ArtPreviewIconSize = 0,
  # Host-only icon probe: the host's nearest enemy carries the combat icon
  # without a combat (src=flag), so QA-010 can measure it on a K2 frame.
  [switch]$ArtPreviewIconProbe,
  # Offline probe of the scoped-cleanup state machine only (no backend, no
  # clients): drives Stop-ThisRunGame against a mocked Invoke-RestMethod that
  # returns scripted HTTP-200 responses (including errors[]) and asserts the
  # success/failure propagation of each scenario. Exit 0 = all probe cases ok.
  [switch]$ProbeCleanupOnly,
  # W4-A render reference (user decision 2026-09-28: DX12/SM6 + Lumen, High).
  # Both clients get -S08RenderPreset=<preset> (sg.* of the preset before the
  # first frame; None = keep the saved GameUserSettings). The trace of every
  # SHOT carries a 'RENDER tag=SHOT ... reference=0|1' fingerprint.
  [ValidateSet('None', 'Low', 'Medium', 'High', 'Epic')][string]$ClientRenderPreset = 'High',
  # Fail the run unless both clients' SHOT fingerprints are on the reference
  # (docs/art-pipeline/render-reference.json; acceptance runs pass this).
  [switch]$RequireRenderReference,
  # Extra client arguments, '+'-separated (diagnostics only, e.g. -dx11+-S08LegacyRender).
  [string]$ClientExtraArgs = ''
)
# GD-030/GD-031 two-client packaged demo: both clients hidden (-RenderOffScreen)
# against the SAME real backend. Sequence under test:
#   host   -> login, create, hero, ready, start, ONE legal maneuver
#             (beginManeuver + maneuver) at HostManeuverAfter
#   joiner -> login, join by code, hero, ready, WS DROPPED at
#             JoinerDropWsAfter, bounded-backoff reconnect, refetch +
#             resubscribe from applied seq, then convergence to the maneuver.
# Both take a 1920x1080 HighResShot after the board settles.
#
# S08 hardening:
#   - Credentials AND the joiner room code come from the orchestrator's
#     environment (S08_DEMO_HOST_EMAIL/PASSWORD, S08_DEMO_JOINER_EMAIL/
#     PASSWORD for the driver; S08_EMAIL/S08_PASSWORD + S08_ROOM_CODE are
#     injected per client PROCESS) - never hard-coded, never on the argv,
#     never echoed, and the room code is redacted from published traces.
#   - Evidence is staged in a UNIQUE temporary run directory and published to
#     EvidenceDir only after every assertion passed.
#   - Each client must produce its OWN explicit shot file fresh from THIS run
#     (file mtime after that client's process start). There is deliberately
#     NO fallback that copies staged HighresScreenshot*.png leftovers: such
#     files can be stale from a previous run and cannot be mapped to a client
#     unambiguously - a missing shot fails the run.
#   - The game created by THIS run is aborted in a finally block (scoped to
#     the exact game id parsed from this run's host trace, host-ownership and
#     code validated against the API before abortGame), so repeat runs never
#     pile up toward the five-active-game cap. No other room is touched.
#     GraphQL failures arrive as HTTP 200 + errors[]: every cleanup response
#     is checked for an errors[] array, the abort is only counted as done
#     after the terminal ABORTED status was verified for precisely THIS game
#     (from the abortGame response, or a game(id) re-query when the mutation
#     response does not carry ABORTED), and any cleanup failure propagates:
#     $Script:CleanupFailure is rethrown after the finally block, so a failed
#     scoped cleanup makes the whole demo exit nonzero.
$ErrorActionPreference = 'Stop'
if ($ArtPreviewFocusZoom -gt 0 -and (-not $ArtPreviewBoardId -or $ArtPreviewFocusZoom -le 1)) {
  throw 'ArtPreviewFocusZoom requires ArtPreviewBoardId and a zoom greater than 1'
}
# An explicitly passed variant (even face-neck-v2) reaches the clients, so an
# explicit v2 run is distinguishable from the no-flag default path in traces.
$MedusaVariantExplicit = $PSBoundParameters.ContainsKey('ArtPreviewMedusaVariant')
if (($ArtPreviewMedusaVariant -ne 'face-neck-v2' -or $MedusaVariantExplicit) -and -not $ArtPreviewBoardId) {
  throw 'ArtPreviewMedusaVariant requires ArtPreviewBoardId'
}
# ArtPreviewBoardId must be a Board ROW id (cuid). The backend stores any
# string but silently builds an empty 20x20 grid when no Board row has that id,
# so a content slug such as 'cobble-city' is refused up front.
if ($ArtPreviewBoardId -and $ArtPreviewBoardId -cnotmatch '^c[a-z0-9]{24}$') {
  throw "ArtPreviewBoardId '$ArtPreviewBoardId' is not a Board row id (cuid); content slugs such as 'cobble-city' are refused. Use a Board row id registered in unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json (e.g. the 5x6 Cobble review board cmuhgs4b2001mwik4f2b2xtf8)."
}
# T3.2: the art board registry is the client's own data file (one source of
# truth): the profile that lists this Board row id gives the expected W x H,
# zone/multizone/obstacle counts and the light profile the traces must show.
$ArtBoard = $null
if ($ArtPreviewBoardId) {
  $ArtBoardsPath = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path 'unreal\Unmatched\Config\ArtBoards\S08ArtBoardProfiles.json'
  if (-not (Test-Path -LiteralPath $ArtBoardsPath)) { throw "art board registry missing: $ArtBoardsPath" }
  $ArtBoardsDoc = [System.IO.File]::ReadAllText($ArtBoardsPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
  $ArtBoard = @($ArtBoardsDoc.boards | Where-Object { @($_.match.boardIds) -ccontains $ArtPreviewBoardId }) | Select-Object -First 1
  if (-not $ArtBoard) {
    $known = (@($ArtBoardsDoc.boards | ForEach-Object { "$($_.id)=$(@($_.match.boardIds) -join '|')" }) -join ', ')
    throw "ArtPreviewBoardId '$ArtPreviewBoardId' is not a registered art board ($known); the backend would build an unrelated grid"
  }
  $ArtLight = $ArtBoardsDoc.lightProfiles.($ArtBoard.light)
  if (-not $ArtLight) { throw "art board '$($ArtBoard.id)' names a missing light profile '$($ArtBoard.light)'" }
  $ArtBoardSize = "$($ArtBoard.match.width)x$($ArtBoard.match.height)"
  $ArtBoardLegacy = [bool]$ArtBoard.legacyCobbleTrace
  Write-Output "art board: profile=$($ArtBoard.id) size=$ArtBoardSize light=$($ArtBoard.light) legacyCobble=$ArtBoardLegacy"
}
if (($ArtPreviewAllMedusa -or $ArtPreviewInputPlan -or $ArtPreviewIconSize -gt 0 -or $ArtPreviewIconProbe) -and -not $ArtPreviewBoardId) {
  throw 'ArtPreviewAllMedusa / ArtPreviewInputPlan / ArtPreviewIconSize / ArtPreviewIconProbe require ArtPreviewBoardId'
}
if ($ArtPreviewInputPlan -and $ArtPreviewInputPlan -notmatch '^[A-Za-z]+(\*[0-9]+)?(\+[A-Za-z]+(\*[0-9]+)?)*$') {
  throw "ArtPreviewInputPlan '$ArtPreviewInputPlan' is not a '+'-separated token list"
}
if ($ArtPreviewBoardId -and $RunSeconds -lt ($ArtPreviewShotAfter + 10)) {
  throw "RunSeconds=$RunSeconds must be at least ArtPreviewShotAfter+10 ($($ArtPreviewShotAfter + 10))"
}
$ExpectedMedusaMesh = @{
  'face-neck-v2' = 'SK_Medusa_FaceNeck_v2Candidate'
  'head-tilt-v3' = 'SK_Medusa_HeadTilt_v3Candidate'
}[$ArtPreviewMedusaVariant]
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Exe) { $Exe = Join-Path $RepoRoot 'unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe' }
if (-not $EvidenceDir) { $EvidenceDir = Join-Path $RepoRoot 'docs\game-design\evidence\S08\run' }

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Script:CleanupFailure = $null

# HTTP 200 + errors[] gate: GraphQL reports failures inside a 200 response.
# Every cleanup-side call must go through this before its data is trusted.
function Assert-GqlOk($Response, [string]$What) {
  if (-not $Response) { throw "$What returned an empty response" }
  # @($null).Count is 1 in PowerShell - only read errors[] when present.
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

# Launches a hidden packaged client with credentials and (for the joiner) the
# room code injected into its per-process environment (not argv).
function Start-S08Client([string[]]$CliArgs, [string]$Email, [string]$Password, [string]$RoomCode = '') {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $Exe
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
  foreach ($arg in $CliArgs) {
    if ($arg -match '\s') { $psi.Arguments += '"' + $arg + '" ' } else { $psi.Arguments += $arg + ' ' }
  }
  # Both offscreen clients render continuously; cap each independently.
  # Keep the quotes around the value so UE receives the full console command.
  # With a CSV capture the engine draws a 'CsvProfiler frame: N' screen message into
  # every frame (evidence PNGs included); DisableAllScreenMessages suppresses it.
  $execCmds = 't.MaxFPS {0}' -f $ClientFps
  if ($ClientCsvFrames -gt 0) { $execCmds += ', DisableAllScreenMessages' }
  $psi.Arguments += ('-ExecCmds="{0}" ' -f $execCmds)
  $psi.EnvironmentVariables['S08_EMAIL'] = $Email
  $psi.EnvironmentVariables['S08_PASSWORD'] = $Password
  if ($RoomCode) { $psi.EnvironmentVariables['S08_ROOM_CODE'] = $RoomCode }
  return [System.Diagnostics.Process]::Start($psi)
}

# Scoped abort of THIS run's game (finally path, failed runs included).
# The id comes from this run's host trace; ownership (hostId == logged-in
# user) and the room code are re-validated against the API before abortGame,
# GraphQL errors[] responses are hard failures, and the abort only counts as
# done once ABORTED was verified for exactly this game id.
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
    Assert-GqlOk $g 'cleanup game lookup'
    $game = $g.data.game
    if (-not $game) { Write-Output "cleanup: game $($Script:ThisRunGameId) no longer resolves - nothing to abort"; return }
    if ($game.hostId -cne $uid) {
      throw "REFUSING abort - host-ownership validation failed for game $($Script:ThisRunGameId) (hostId=$($game.hostId), caller=$uid)"
    }
    if ($Script:ThisRunGameCode -and $game.code -and ($game.code -cne $Script:ThisRunGameCode)) {
      throw "REFUSING abort - room code mismatch for game $($Script:ThisRunGameId)"
    }
    if (@('ABORTED', 'COMPLETED', 'FINISHED') -contains $game.status) {
      Write-Output "cleanup: game $($Script:ThisRunGameId) already terminal ($($game.status))"
      return
    }
    $a = @{ query = 'mutation AB($gameId: String!) { abortGame(gameId: $gameId) { id status } }'; variables = @{ gameId = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
    $r = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers $headers -Body $a
    Assert-GqlOk $r 'cleanup abortGame'
    if (-not $r.data.abortGame) { throw 'abortGame returned no game object' }
    if ($r.data.abortGame.id -cne $Script:ThisRunGameId) {
      throw "abortGame returned a foreign game id: $($r.data.abortGame.id)"
    }
    if ($r.data.abortGame.status -cne 'ABORTED') {
      # Mutation response without terminal status: verify via a fresh lookup
      # that precisely THIS game is ABORTED before counting the cleanup done.
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

# Recursive delete guard: canonical path with a separator boundary against
# the expected root (no prefix-string false positives like C:\TempEvil under
# C:\Temp), reparse points anywhere inside the tree are refused (a junction
# must never let Remove-Item -Recurse reach an unrelated tree), and the
# deletion itself uses -LiteralPath.
function Remove-TreeSafely([string]$Target, [string]$ExpectedRoot) {
  $targetFull = [System.IO.Path]::GetFullPath($Target)
  $rootFull = [System.IO.Path]::GetFullPath($ExpectedRoot).TrimEnd([char]'\', [char]'/')
  $boundary = $rootFull + [System.IO.Path]::DirectorySeparatorChar
  if (-not $targetFull.StartsWith($boundary, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "refusing recursive delete outside $ExpectedRoot : $targetFull"
  }
  if (-not (Test-Path -LiteralPath $targetFull)) { return }
  $stack = New-Object System.Collections.Generic.Stack[string]
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

# ---- Offline cleanup probe (-ProbeCleanupOnly) ------------------------------
# Mocks Invoke-RestMethod at script scope (shadowing the cmdlet for
# Stop-ThisRunGame) with a scripted FIFO of HTTP-200 responses, so the exact
# cleanup state machine can be exercised without the backend or clients:
#   - errors[] on any cleanup call must FAIL the cleanup (not count as success)
#   - the happy path (validated ownership + ABORTED abort) must pass cleanly
#   - a non-terminal abort status must be caught by the re-query and FAIL.
function Invoke-CleanupProbe {
  $Script:ProbeQueue = New-Object System.Collections.Generic.List[object]
  function Script:Invoke-RestMethod {
    param($Uri, $Method, $ContentType, $Headers, $Body)
    if ($Script:ProbeQueue.Count -eq 0) {
      throw "probe mock: unexpected extra HTTP call ($Method $Uri)"
    }
    $item = $Script:ProbeQueue[0]
    $Script:ProbeQueue.RemoveAt(0)
    return $item
  }
  function New-ProbeLogin {
    [pscustomobject]@{ data = [pscustomobject]@{ login = [pscustomobject]@{ accessToken = 'probe-token'; user = [pscustomobject]@{ id = 'u-1' } } } }
  }
  function New-ProbeGame([string]$Status) {
    [pscustomobject]@{ data = [pscustomobject]@{ game = [pscustomobject]@{ id = 'g-probe-1'; code = 'AB12CD'; status = $Status; hostId = 'u-1' } } }
  }
  function New-ProbeErrors([string]$Message) {
    [pscustomobject]@{ errors = @([pscustomobject]@{ message = $Message }) }
  }
  function New-ProbeAbort([string]$Id, [string]$Status) {
    [pscustomobject]@{ data = [pscustomobject]@{ abortGame = [pscustomobject]@{ id = $Id; status = $Status } } }
  }

  $Script:ProbeFailed = 0
  function Invoke-ProbeCase([string]$Name, [object[]]$Queue, [bool]$ExpectFailure, [string]$MustContain) {
    $Script:ProbeQueue = New-Object System.Collections.Generic.List[object]
    foreach ($q in $Queue) { $Script:ProbeQueue.Add($q) }
    $Script:ThisRunGameId = 'g-probe-1'
    $Script:ThisRunGameCode = 'AB12CD'
    $Script:CleanupFailure = $null
    Stop-ThisRunGame
    $ok = $true
    if ($ExpectFailure) {
      if (-not $Script:CleanupFailure) { $ok = $false }
      elseif ($MustContain -and $Script:CleanupFailure -notlike "*$MustContain*") { $ok = $false }
    } else {
      if ($Script:CleanupFailure) { $ok = $false }
    }
    if ($Script:ProbeQueue.Count -ne 0) { $ok = $false }
    if ($ok) {
      Write-Host "PROBE PASS  $Name"
    } else {
      $Script:ProbeFailed++
      Write-Host "PROBE FAIL  $Name (CleanupFailure=$Script:CleanupFailure, unconsumed mock responses: $($Script:ProbeQueue.Count))"
    }
  }

  Invoke-ProbeCase 'success: validated ownership + ABORTED abort passes' `
    @((New-ProbeLogin), (New-ProbeGame 'LOBBY'), (New-ProbeAbort 'g-probe-1' 'ABORTED')) $false $null
  Invoke-ProbeCase 'HTTP-200 errors[] on the game lookup fails the cleanup' `
    @((New-ProbeLogin), (New-ProbeErrors 'game lookup exploded')) $true 'GraphQL errors'
  Invoke-ProbeCase 'HTTP-200 errors[] on abortGame fails the cleanup' `
    @((New-ProbeLogin), (New-ProbeGame 'IN_PROGRESS'), (New-ProbeErrors 'abortGame rejected')) $true 'GraphQL errors'
  Invoke-ProbeCase 'HTTP-200 errors[] on login fails the cleanup' `
    @((New-ProbeErrors 'login exploded')) $true 'GraphQL errors'
  Invoke-ProbeCase 'non-terminal abort status is caught by the re-query' `
    @((New-ProbeLogin), (New-ProbeGame 'IN_PROGRESS'), (New-ProbeAbort 'g-probe-1' 'IN_PROGRESS'), (New-ProbeGame 'IN_PROGRESS')) $true 'NOT terminal ABORTED'
  # A foreign id is a hard stop - no follow-up re-query is issued.
  Invoke-ProbeCase 'abortGame answering for a foreign game id fails the cleanup' `
    @((New-ProbeLogin), (New-ProbeGame 'IN_PROGRESS'), (New-ProbeAbort 'g-OTHER' 'ABORTED')) $true 'foreign game id'

  Remove-Item function:Script:Invoke-RestMethod -ErrorAction SilentlyContinue
  if ($Script:ProbeFailed -gt 0) {
    Write-Host "CLEANUP PROBE FAILED: $($Script:ProbeFailed) case(s)"
    $Script:ProbeExitCode = 1
    return
  }
  Write-Host 'CLEANUP PROBE OK: 6/6 cases'
  $Script:ProbeExitCode = 0
}

if ($ProbeCleanupOnly) {
  Invoke-CleanupProbe > $null
  exit $Script:ProbeExitCode
}

if (-not (Test-Path $Exe)) { throw "packaged exe not found: $Exe" }
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$AccountA = @{
  email    = $env:S08_DEMO_HOST_EMAIL
  password = $env:S08_DEMO_HOST_PASSWORD
}
$AccountB = @{
  email    = $env:S08_DEMO_JOINER_EMAIL
  password = $env:S08_DEMO_JOINER_PASSWORD
}
foreach ($pair in @(@('S08_DEMO_HOST_EMAIL', $AccountA.email), @('S08_DEMO_JOINER_EMAIL', $AccountB.email))) {
  if (-not $pair[1]) { throw "missing $($pair[0]) in process environment (orchestrator provides demo accounts)" }
}
foreach ($pair in @(@('S08_DEMO_HOST_PASSWORD', $AccountA.password), @('S08_DEMO_JOINER_PASSWORD', $AccountB.password))) {
  if (-not $pair[1]) { throw "missing $($pair[0]) in process environment (orchestrator provides demo accounts)" }
}

function Invoke-Phase2Demo {
  $heroA = Get-Hero $AccountA.email $AccountA.password 'Medusa'
  $heroB = Get-Hero $AccountB.email $AccountB.password 'King Arthur'
  Write-Output "heroA=$heroA heroB=$heroB"

  # Unique per-run staging: nothing here is evidence until it passed the checks.
  $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Script:Staging = Join-Path ([System.IO.Path]::GetTempPath()) "s08-phase2-$Stamp-$PID"
  New-Item -ItemType Directory -Force -Path $Script:Staging | Out-Null
  Write-Output "staging: $Script:Staging"

  $hostTrace = Join-Path $Script:Staging 'phase2-client-host.trace.log'
  $joinTrace = Join-Path $Script:Staging 'phase2-client-joiner.trace.log'
  $hostShot = Join-Path $Script:Staging 'phase2-board-host-1920x1080.png'
  $joinShot = Join-Path $Script:Staging 'phase2-board-joiner-1920x1080.png'

  # The game created by THIS run (parsed from the host trace once it appears);
  # the finally block aborts exactly this id - nothing else.
  $Script:ThisRunGameId = $null
  $Script:ThisRunGameCode = $null

  $common = @("-windowed", "-resx=1920", "-resy=1080", "-RenderOffScreen", "log=GrepLog", "-ForceAbandonSequences", "-S08Api=$Api")
  if ($ClientRenderPreset -ne 'None') { $common += "-S08RenderPreset=$ClientRenderPreset" }
  if ($ClientExtraArgs) { $common += @($ClientExtraArgs.Split('+') | Where-Object { $_ }) }
  if ($ArtPreviewBoardId) { $common += @('-ArtPreview', '-ForceRes') }
  if ($ArtPreviewMedusaVariant -ne 'face-neck-v2' -or $MedusaVariantExplicit) { $common += "-ArtPreviewMedusaVariant=$ArtPreviewMedusaVariant" }
  if ($ClientPerf) { $common += '-S08Perf' }
  if ($ArtPreviewAllMedusa) { $common += '-ArtPreviewAllMedusa' }
  if ($ClientCsvFrames -gt 0) { $common += @("-csvCaptureFrames=$ClientCsvFrames", '-csvGpuStats') }
  $hostArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08Create",
    "-S08HeroId=$heroA", "-S08Trace=$hostTrace", "-S08Shot=$hostShot",
    "-S08ExitAfter=$RunSeconds")
  if ($ArtPreviewBoardId) {
    $hostArgs += @("-ArtPreviewBoardId=$ArtPreviewBoardId", "-ArtPreviewShotAfter=$ArtPreviewShotAfter", '-ArtPreviewSelectOwnHero')
    if ($ArtPreviewFocusZoom -gt 0) {
      $hostArgs += ('-ArtPreviewFocusZoom={0}' -f $ArtPreviewFocusZoom.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture))
    }
    if ($ArtPreviewInputPlan) { $hostArgs += "-ArtPreviewInputPlan=$ArtPreviewInputPlan" }
    if ($ArtPreviewIconSize -gt 0) { $hostArgs += "-ArtPreviewIconSize=$ArtPreviewIconSize" }
    if ($ArtPreviewIconProbe) { $hostArgs += '-ArtPreviewIconProbe' }
  } else {
    $hostArgs += @('-S08Maneuver', "-S08ManeuverAfter=$HostManeuverAfter")
  }

  $hostProc = $null
  $joinProc = $null
  $Published = $false
  try {
    $hostStartUtc = [DateTime]::UtcNow
    $hostProc = Start-S08Client $hostArgs $AccountA.email $AccountA.password
    Write-Output "host pid=$($hostProc.Id)"

    # Credentials (and the room code) travel in per-process ENV only; prove
    # they never leak into the process command line (task-list safety).
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

    # Wait for the host to publish the room (id + code) in its trace.
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
    if ($ArtPreviewBoardId) {
      $loginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken } }'; variables = @{ input = @{ email = $AccountA.email; password = $AccountA.password } } } | ConvertTo-Json -Depth 5
      $login = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBody
      Assert-GqlOk $login 'art-preview host login'
      $lookup = @{ query = 'query G($id: String!) { game(id: $id) { id boardId } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
      $game = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers @{ authorization = "Bearer $($login.data.login.accessToken)" } -Body $lookup
      Assert-GqlOk $game 'art-preview board lookup'
      if ($game.data.game.boardId -cne $ArtPreviewBoardId) {
        throw "created room has boardId=$($game.data.game.boardId), expected $ArtPreviewBoardId"
      }
      Write-Output 'art-preview boardId verified against the authoritative game row'
    }

    $joinArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
      "-S08Auto", "-S08HeroId=$heroB", "-S08Trace=$joinTrace", "-S08Shot=$joinShot",
      "-S08DropWsAfter=$JoinerDropWsAfter", "-S08ExitAfter=$RunSeconds")
    if ($ArtPreviewBoardId) { $joinArgs += "-ArtPreviewShotAfter=$ArtPreviewShotAfter" }
    $joinStartUtc = [DateTime]::UtcNow
    $joinProc = Start-S08Client $joinArgs $AccountB.email $AccountB.password $code
    Write-Output "joiner pid=$($joinProc.Id)"
    Assert-NoCredentialOnCmdLine $joinProc.Id @($AccountB.email, $AccountB.password, $code)

    $hostProc.WaitForExit()
    $joinProc.WaitForExit()
    Write-Output "both clients exited"

    # --- Fresh per-client shots (P1): the explicit -S08Shot path is the ONLY
    # accepted source. It must exist, be non-trivial, and be NEWER than that
    # client's process start (i.e. produced by THIS run). No fallback copy from
    # staged HighresScreenshot leftovers - those cannot be attributed to a run.
    function Assert-FreshShot([string]$Path, [DateTime]$ClientStartUtc, [string]$Who) {
      if (-not (Test-Path -LiteralPath $Path)) {
        throw "evidence shot missing for ${Who}: $Path (explicit -S08Shot output absent - failing instead of copying stale staged screenshots)"
      }
      $item = Get-Item -LiteralPath $Path
      if ($item.Length -lt 10KB) { throw "suspiciously small shot (likely black/empty) for ${Who}: $Path" }
      if ($item.LastWriteTimeUtc -le $ClientStartUtc) {
        throw "shot for ${Who} predates its client process (stale file): $Path"
      }
    }
    # A missing trace file means that client exited before
    # AS08FlowGameMode::BeginPlay opened it (e.g. the ART-004 v3 startup crash
    # in UObject class registration); the board id is not the cause then.
    # The backend stores any boardId string but silently falls back to an empty
    # 20x20 grid when no Board row has that id (e.g. the content slug
    # 'cobble-city'). Then the art board and its shot gate never activate;
    # report that cause instead of a generic missing shot.
    if ($ArtPreviewBoardId) {
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        if (-not (Test-Path -LiteralPath $pair[1])) {
          throw "$($pair[0]) trace missing: $($pair[1]). The client likely crashed before AS08FlowGameMode::BeginPlay; copy $(Join-Path (Split-Path -Parent $Exe) 'Unmatched\Saved\Logs')\Unmatched*.log before the next package step wipes it"
        }
        if (-not (Select-String -LiteralPath $pair[1] -SimpleMatch -Pattern "BOARD $ArtBoardSize cells" -Quiet)) {
          $seen = Select-String -LiteralPath $pair[1] -Pattern 'BOARD \d+x\d+ cells' | Select-Object -First 1
          throw "$($pair[0]) trace has no 'BOARD $ArtBoardSize': ArtPreviewBoardId=$ArtPreviewBoardId is registered as $($ArtBoard.id) $ArtBoardSize, the client built '$(if ($seen) { $seen.Line } else { 'no BOARD line' })'"
        }
      }
    }
    Assert-FreshShot $hostShot $hostStartUtc 'host'
    Assert-FreshShot $joinShot $joinStartUtc 'joiner'

    # --- Verdict from the traces (authoritative, redacted) ---
    function Assert-Trace([string]$Path, [string[]]$MustContain, [string]$Who) {
      $text = Get-Content -LiteralPath $Path -Raw
      foreach ($needle in $MustContain) {
        if (-not $text.Contains($needle)) { throw "$Who trace missing '$needle'" }
      }
    }
    $expectedBoard = if ($ArtPreviewBoardId) { "BOARD $ArtBoardSize cells" } else { 'BOARD 20x20' }
    if ($ArtPreviewBoardId) {
      # T3.2 data-driven board art: profile chosen by THIS Board row id, the
      # decoded board equals the registered expectation (expectOk=1), every
      # zone of every multizone cell marked, the light profile applied within
      # budget (1 directional with shadow + <= 6 points without shadow).
      $exp = $ArtBoard.expect
      $pointCount = @($ArtLight.points).Count
      $artLines = @(
        'ARTPREVIEW board profiles loaded=1',
        "ARTPREVIEW board profile=$($ArtBoard.id) match=boardId board=$ArtBoardSize boardId=$ArtPreviewBoardId surface=$($ArtBoard.surface) light=$($ArtBoard.light)",
        "ARTPREVIEW board active profile=$($ArtBoard.id) $ArtBoardSize surface=$($ArtBoard.surface) cells=$($exp.cells) zoneCells=$($exp.zoneCells) multizone=$($exp.multizoneCells) ",
        "obstacles=$($exp.obstacles) zoneKeys=$(@($ArtBoard.match.zoneKeys).Count) ",
        "ARTPREVIEW lights applied profile=$($ArtBoard.light) directional=1 shadow=1 points=$pointCount pointShadows=0 budgetOk=1",
        "ARTPREVIEW board multizone cells=$($exp.multizoneCells) ")
      if ($ArtBoardLegacy) {
        # ART-005 Cobble evidence lines stay byte-compatible; the probe-lights
        # line follows the registered profile (W4-A: the point fill became the
        # SkyLight, so fill=0 unless a point named 'fill' is registered).
        $inv = [Globalization.CultureInfo]::InvariantCulture
        $fillPoint = @($ArtLight.points | Where-Object { $_.name -eq 'fill' }) | Select-Object -First 1
        $warmPoint = @($ArtLight.points | Where-Object { $_.name -eq 'warm' }) | Select-Object -First 1
        $probeKey = ([double]$ArtLight.directional.intensity).ToString('G', $inv)
        $probeFill = if ($fillPoint) { ([double]$fillPoint.intensity).ToString('G', $inv) } else { '0' }
        $probeWarm = if ($warmPoint) { ([double]$warmPoint.intensity).ToString('G', $inv) } else { '0' }
        $artLines += @('ARTPREVIEW Cobble assets ready', 'ARTPREVIEW Cobble active 5x6 zones=30 blue=15 red=15 blueMarks=15 redMarks=45',
          "ARTPREVIEW Cobble probe lights key=$probeKey fill=$probeFill warm=$probeWarm")
      } else {
        $artLines += @('ARTPREVIEW board assets ready cobbleMesh=', ' tiles=1 ')
      }
      Assert-Trace $hostTrace (@('SNAPSHOT applied', $expectedBoard, 'FIGHTERS synced n=6', 'SHOT ctx',
        'ARTPREVIEW fighter=Medusa hero=1 eligible=1 visual=1',
        'ARTPREVIEW selection ownHero=1 selected=1 fighter=Medusa',
        'ARTPREVIEW selection ring shown fighter=Medusa mesh=SM_Marker_SelectionRing') + $artLines) 'host'
      Assert-Trace $joinTrace (@('SNAPSHOT applied', $expectedBoard, 'FIGHTERS synced n=6', 'SHOT ctx',
        'WS DROPPED', 'WS closed', 'WS reconnect attempt', 'WS reconnected',
        'ARTPREVIEW fighter=Medusa hero=1 eligible=1 visual=1') + $artLines) 'joiner'
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        $active = Select-String -LiteralPath $pair[1] -Pattern ('ARTPREVIEW board active profile=' + [regex]::Escape($ArtBoard.id) + ' .* expectOk=(\d)') | Select-Object -Last 1
        if (-not $active -or $active.Matches[0].Groups[1].Value -ne '1') {
          throw "$($pair[0]) board art does not match its registered expectation: $(if ($active) { $active.Line } else { 'no active line' })"
        }
        $mz = Select-String -LiteralPath $pair[1] -Pattern 'ARTPREVIEW board multizone cells=(\d+) zonesListed=(\d+) zonesMarked=(\d+)' | Select-Object -Last 1
        if (-not $mz -or $mz.Matches[0].Groups[2].Value -ne $mz.Matches[0].Groups[3].Value) {
          throw "$($pair[0]) multizone cells lost zones: $(if ($mz) { $mz.Line } else { 'no multizone line' })"
        }
        foreach ($key in @($ArtBoard.match.zoneKeys)) {
          $zoneLine = Select-String -LiteralPath $pair[1] -Pattern ('ARTPREVIEW board zone key=' + [regex]::Escape($key) + ' cells=(\d+) .* fallback=0') | Select-Object -Last 1
          $want = $exp.zoneCellCounts.$key
          if (-not $zoneLine -or [int]$zoneLine.Matches[0].Groups[1].Value -ne [int]$want) {
            throw "$($pair[0]) zone '$key' expected $want cells: $(if ($zoneLine) { $zoneLine.Line } else { 'no zone line' })"
          }
          if ($ArtBoardsDoc.glyphMeshes) {
            # T4.2 content: the zone draws with its MI (MI_ART005_Zone_*) and one glyph-mesh instance per zone cell.
            $content = Select-String -LiteralPath $pair[1] -Pattern ('ARTPREVIEW board zone key=' + [regex]::Escape($key) + ' cells=\d+ .* mi=(MI_ART005_Zone_\S+) glyphMesh=(SM_ART005_ZoneGlyph_\S+) glyphInstances=(\d+) fallback=0') | Select-Object -Last 1
            if (-not $content -or [int]$content.Matches[0].Groups[3].Value -ne [int]$want) {
              throw "$($pair[0]) zone '$key' T4.2 content (MI + $want glyph-mesh instances) missing: $(if ($zoneLine) { $zoneLine.Line } else { 'no zone line' })"
            }
          }
        }
        if ($ArtBoardsDoc.glyphMeshes) {
          $zc = Select-String -LiteralPath $pair[1] -Pattern 'ARTPREVIEW zone content instances=(\d+)/(\d+) glyphMeshes=(\d+)/(\d+)' | Select-Object -Last 1
          if (-not $zc -or $zc.Matches[0].Groups[1].Value -ne $zc.Matches[0].Groups[2].Value -or $zc.Matches[0].Groups[3].Value -ne $zc.Matches[0].Groups[4].Value -or [int]$zc.Matches[0].Groups[2].Value -eq 0) {
            throw "$($pair[0]) T4.2 zone content not fully loaded: $(if ($zc) { $zc.Line } else { 'no zone content line' })"
          }
        }
      }
      if ($ArtBoardLegacy) {
        Assert-Trace $hostTrace @('ARTPREVIEW reachable corners cells=13 placed=1') 'host Cobble reachable'
      } elseif (-not (Select-String -LiteralPath $hostTrace -Pattern 'ARTPREVIEW reachable corners cells=[1-9]\d* placed=1' -Quiet)) {
        throw 'host trace has no placed reachable-corner highlights for the selected hero'
      }
      $requestedLabel = if ($MedusaVariantExplicit) { $ArtPreviewMedusaVariant } else { '(default)' }
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        Assert-Trace $pair[1] @("ARTPREVIEW medusa candidate variant=$ArtPreviewMedusaVariant mesh=$ExpectedMedusaMesh requested=$requestedLabel",
          "visual=1 mesh=$ExpectedMedusaMesh", 'boardValid=1', 'HUD seq=',
          "SHOT head fighter=", "socket=Head mesh=$ExpectedMedusaMesh") "$($pair[0]) Medusa candidate"
        if ($ClientPerf) { Assert-Trace $pair[1] @('PERF config', 'PERF summary scope=started') "$($pair[0]) perf" }
        # W4-A: every SHOT carries a RENDER fingerprint; acceptance runs
        # (-RequireRenderReference) also need it on the reference.
        $render = Select-String -LiteralPath $pair[1] -Pattern 'RENDER tag=SHOT .* reference=(\d)' | Select-Object -Last 1
        if ($RequireRenderReference) {
          if (-not $render) { throw "$($pair[0]) trace has no RENDER fingerprint at its SHOT" }
          if ($render.Matches[0].Groups[1].Value -ne '1') { throw "$($pair[0]) SHOT is off the render reference: $($render.Line)" }
        }
      }
      # ART-004 T2.2: zoom config, flag-marked input and the QA-010 selection/
      # plate lines. The plate must cover no destination cell of the selection
      # (client-side count; tools/art/qa010 plate re-checks the same bbox).
      Assert-Trace $hostTrace @('CAMERA config overview=', 'INPUT select src=flag') 'host T2.2'
      if ($ArtPreviewFocusZoom -gt 0) {
        Assert-Trace $hostTrace @('INPUT zoom src=flag', 'CAMERA focus src=flag', 'SHOT selection fighter=',
          'SHOT reachable fighter=', 'SHOT plate fighter=', 'PLATE fighter=') 'host T2.2 plate'
        $plateLine = Select-String -LiteralPath $hostTrace -Pattern 'SHOT plate fighter=\S+ bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\) overlapReachable=(\d+) .* geom=(\w+)' | Select-Object -Last 1
        if (-not $plateLine) { throw 'host SHOT plate line missing or malformed' }
        if ($plateLine.Matches[0].Groups[6].Value -ne 'painted') { throw "host SHOT plate geometry is not painted: $($plateLine.Line)" }
        if ([int]$plateLine.Matches[0].Groups[5].Value -ne 0) { throw "host plate covers destination cells: $($plateLine.Line)" }
      }
      if ($ArtPreviewAllMedusa) {
        foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
          $copies = @(Select-String -LiteralPath $pair[1] -Pattern ('ARTPREVIEW allMedusa copy fighter=(\S+) hero=\d team=\w+ visual=1 mesh=' + [regex]::Escape($ExpectedMedusaMesh) + ' ') |
            ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique)
          if ($copies.Count -ne 6) { throw "$($pair[0]) trace shows $($copies.Count)/6 Medusa copies with visual=1 mesh=$ExpectedMedusaMesh" }
          Assert-Trace $pair[1] @('ARTPREVIEW allMedusa copies=6 visual=6') "$($pair[0]) all-Medusa"
        }
      }
      if ($ArtPreviewInputPlan) {
        Assert-Trace $hostTrace @('INPUT plan src=flag steps=', 'INPUT plan done src=flag') 'host input plan'
        $clicks = @(Select-String -LiteralPath $hostTrace -Pattern 'INPUT click button=left src=flag step=(\w+) .* match=(\d)')
        foreach ($c in $clicks) {
          if ($c.Matches[0].Groups[2].Value -ne '1') { throw "flag click did not hit its expected target: $($c.Line)" }
        }
        if ($ArtPreviewInputPlan -match 'wheel') { Assert-Trace $hostTrace @('INPUT wheel dir=', 'CAMERA wheel dir=') 'host wheel' }
        if ($ArtPreviewInputPlan -match 'space') { Assert-Trace $hostTrace @('INPUT space src=flag', 'CAMERA space src=flag') 'host Space' }
        if (Select-String -LiteralPath $hostTrace -Pattern 'INPUT (wheel|space|click) .*src=os' -Quiet) {
          throw 'host trace carries src=os input in an offscreen flag run'
        }
      }
      if ($ArtPreviewIconProbe) {
        Assert-Trace $hostTrace @('ARTPREVIEW icon probe src=flag', 'SHOT icon fighter=') 'host icon probe'
      }
      if ($ArtPreviewFocusZoom -gt 0) {
        Assert-Trace $hostTrace @('ARTPREVIEW camera focus requested zoom=', 'CAMERA settled') 'host K2'
        # The evidence shot must be taken after the focus zoom arrived.
        if (-not (Select-String -LiteralPath $hostTrace -Pattern 'SHOT camera .* settled=1 ' -Quiet)) {
          throw 'host K2 shot was taken before the camera settled (SHOT camera settled=0); raise ArtPreviewShotAfter'
        }
      }
    } else {
      Assert-Trace $hostTrace @('SNAPSHOT applied', $expectedBoard, 'FIGHTERS synced n=6', 'MANEUVER begin seq=', 'MANEUVER done', 'CUE move') 'host'
      Assert-Trace $joinTrace @('SNAPSHOT applied', $expectedBoard, 'FIGHTERS synced n=6', 'SUBSCRIBED gameStateUpdated',
        'WS DROPPED', 'WS closed', 'WS reconnect attempt', 'WS reconnected', 'CUE move') 'joiner'
    }
    if ($ArtPreviewBoardId) {
      [System.IO.File]::WriteAllText((Join-Path $Script:Staging 'art-preview-status.json'),
        (([ordered]@{ boardId = $ArtPreviewBoardId; artBoardProfile = $ArtBoard.id; boardSize = $ArtBoardSize; lightProfile = $ArtBoard.light; artFixture = [bool]$ArtBoard.artFixture; multizoneCells = $ArtBoard.expect.multizoneCells; hostAssetsLoaded = $true; joinerAssetsLoaded = $true; hostLiveZones = $ArtBoard.expect.zoneCells; joinerLiveZones = $ArtBoard.expect.zoneCells; hostFocusZoom = $ArtPreviewFocusZoom; medusaVariant = $ArtPreviewMedusaVariant; medusaVariantExplicit = $MedusaVariantExplicit; shotAfterSeconds = $ArtPreviewShotAfter; runSeconds = $RunSeconds; clientFps = $ClientFps; clientPerf = [bool]$ClientPerf; allMedusa = [bool]$ArtPreviewAllMedusa; inputPlan = $ArtPreviewInputPlan; iconSize = $ArtPreviewIconSize; iconProbe = [bool]$ArtPreviewIconProbe }) | ConvertTo-Json), $Utf8NoBom)
    }

    # ProjectWorldLocationToScreen can return true even for offscreen pixels.
    # Count only living fighters whose projected centers lie inside 1920x1080.
    function Assert-SixFightersInFrame([string]$Path, [string]$Who) {
      $lines = @(Select-String -Path $Path -Pattern 'SHOT fighter .* screen=\((-?\d+),(-?\d+)\) projected=1 alive=1')
      $inside = 0
      foreach ($line in $lines) {
        $x = [int]$line.Matches[0].Groups[1].Value
        $y = [int]$line.Matches[0].Groups[2].Value
        if ($x -ge 0 -and $x -lt 1920 -and $y -ge 0 -and $y -lt 1080) { $inside++ }
      }
      if ($inside -ne 6) {
        throw "$Who trace shows $inside/6 living fighter centers inside the frame"
      }
    }
    if ($ArtPreviewFocusZoom -gt 0) {
      $picked = Select-String -Path $hostTrace -Pattern 'ARTPREVIEW selection ownHero=1 selected=1 .* fighterId=(\S+)' | Select-Object -Last 1
      if (-not $picked) { throw 'host K2 trace has no selected hero id' }
      $selectedId = $picked.Matches[0].Groups[1].Value
      $heroShot = Select-String -Path $hostTrace -Pattern ('SHOT fighter ' + [regex]::Escape($selectedId) + ' .* screen=\((-?\d+),(-?\d+)\) projected=1 alive=1') | Select-Object -Last 1
      if (-not $heroShot) { throw "host K2 selected fighter $selectedId is not projected alive" }
      $heroX = [int]$heroShot.Matches[0].Groups[1].Value
      $heroY = [int]$heroShot.Matches[0].Groups[2].Value
      if ($heroX -lt 0 -or $heroX -ge 1920 -or $heroY -lt 0 -or $heroY -ge 1080) {
        throw "host K2 selected fighter $selectedId center is outside the screenshot"
      }
    } else {
      Assert-SixFightersInFrame $hostTrace 'host'
    }
    Assert-SixFightersInFrame $joinTrace 'joiner'

    # Convergence: both clients end on the same highest applied seq.
    function Get-MaxSeq([string]$Path) {
      $seqs = Select-String -Path $Path -Pattern 'SNAPSHOT applied seq=(\d+)' -AllMatches |
        ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value }
      return ($seqs | Measure-Object -Maximum).Maximum
    }
    $hostSeq = Get-MaxSeq $hostTrace
    $joinSeq = Get-MaxSeq $joinTrace
    Write-Output "convergence: host max applied seq=$hostSeq joiner max applied seq=$joinSeq"
    if (-not $hostSeq -or -not $joinSeq) { throw "missing applied seq in traces" }
    if ($hostSeq -ne $joinSeq) { throw "clients diverged: host seq=$hostSeq joiner seq=$joinSeq" }

    # The old S08 checker locates a MID-GREY 20x20 tile box; it cannot judge
    # painted Cobble stone. The art check instead rejects dark/flat/missing-HUD
    # frames; gameplay geometry and all 30 zone instances are trace-gated.
    $checker = Join-Path $PSScriptRoot 'check-board-shot.ps1'
    foreach ($pair in @(@('host', $hostShot), @('joiner', $joinShot))) {
      $who = $pair[0]; $shot = $pair[1]
      if ($ArtPreviewBoardId) {
        $jsonPath = $shot -replace '\.png$', '-artcheck.json'
        # T4.2: obstacle cells of a registered board are intentional dark voids; the lit-fraction gate scales
        # with the registered passable fraction (Cobble: no obstacles -> the original 0.75).
        $minLit = 0.75
        if ($ArtBoard -and $ArtBoard.expect -and [int]$ArtBoard.expect.cells -gt 0 -and [int]$ArtBoard.expect.obstacles -gt 0) {
          $minLit = [math]::Round(0.75 * (1.0 - [double]$ArtBoard.expect.obstacles / [double]$ArtBoard.expect.cells), 4)
        }
        $jsonLines = & python (Join-Path $RepoRoot 'tools/art/check_art_preview_shot.py') $shot --min-board-lit ([string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0}', $minLit))
      } else {
        $jsonPath = $shot -replace '\.png$', '-grid.json'
        $jsonLines = & powershell -NoProfile -ExecutionPolicy Bypass -File $checker -Path $shot
      }
      [System.IO.File]::WriteAllLines($jsonPath, [string[]]$jsonLines, $Utf8NoBom)
      Write-Output $jsonLines
      if ($LASTEXITCODE -ne 0) { throw "board-shot checker FAILED for $who (see $jsonPath)" }
    }

    # --- Rollback-safe publish: a complete versioned run directory, then the
    # pointer flip. Artifacts are copied into run-<stamp>/ with the room code
    # redacted from the traces (unpublished until complete) and a manifest
    # records hashes over the REDACTED bytes. Only then does latest.json flip:
    # a unique temp file in the SAME directory, then [IO.File]::Replace when a
    # previous pointer exists ([IO.File]::Move for the initial publish).
    # Replace performs the swap as a single rename-class operation, so a reader
    # sees the old or the new pointer, never a missing destination; no stronger
    # crash-atomicity is claimed - a crash mid-sequence can leave an orphan
    # .tmp, while the previous run dir and pointer stay intact. A failure
    # anywhere above leaves the previous run untouched and this run's staging
    # behind for inspection.
    $publishNames = @('phase2-client-host.trace.log', 'phase2-client-joiner.trace.log',
      'phase2-board-host-1920x1080.png', 'phase2-board-joiner-1920x1080.png')
    if ($ArtPreviewBoardId) {
      $publishNames += @('phase2-board-host-1920x1080-artcheck.json',
        'phase2-board-joiner-1920x1080-artcheck.json', 'art-preview-status.json')
    } else {
      $publishNames += @('phase2-board-host-1920x1080-grid.json',
        'phase2-board-joiner-1920x1080-grid.json')
    }
    $RunDir = Join-Path $EvidenceDir ("run-" + $Stamp)
    if (Test-Path -LiteralPath $RunDir) { throw "run dir already exists: $RunDir" }
    New-Item -ItemType Directory -Path $RunDir | Out-Null
    foreach ($name in $publishNames) {
      $src = Join-Path $Script:Staging $name
      if (-not (Test-Path -LiteralPath $src)) { throw "staged artifact missing at publish time: $src" }
      if ($name -like '*.trace.log') {
        # Redact the joinable room code from published traces.
        $text = [System.IO.File]::ReadAllText($src)
        if ($code) { $text = $text.Replace($code, '<redacted>') }
        [System.IO.File]::WriteAllText((Join-Path $RunDir $name), $text, $Utf8NoBom)
      } else {
        Move-Item -LiteralPath $src (Join-Path $RunDir $name)
      }
    }
    foreach ($name in $publishNames) {
      if (-not (Test-Path -LiteralPath (Join-Path $RunDir $name))) { throw "run dir incomplete after publish: $name" }
    }
    $manifest = [ordered]@{
      stamp   = $Stamp
      verdict = if ($ArtPreviewBoardId) {
        if ($ArtPreviewFocusZoom -gt 0) {
          "ART PREVIEW K2 PROBE: live $ArtBoardSize board ($($ArtBoard.id)) + selected host hero projected + joiner six fighters + HUD/board pixel gate; visual K2 review still required"
        } else {
          "ART PREVIEW: live $ArtBoardSize board ($($ArtBoard.id)) + $($ArtBoard.expect.zoneCells) zone cells / $($ArtBoard.expect.multizoneCells) multizone + light profile $($ArtBoard.light) + six projected fighters + HUD/board pixel gate; visual K1 review still required"
        }
      } else {
        'TRACES OK + SHOTS PRESENT + GRID VERIFIED + SIX FIGHTERS (trace: n=6, all projected in frame)'
      }
      files   = @()
    }
    function Get-Sha256Hex([string]$Path) {
      # .NET SHA256 instead of Get-FileHash: module autoload is unreliable when
      # this script runs under a spawned powershell with an inherited/broken
      # PSModulePath.
      $sha = [System.Security.Cryptography.SHA256]::Create()
      try {
        $stream = [System.IO.File]::OpenRead($Path)
        try {
          $hash = $sha.ComputeHash($stream)
        } finally { $stream.Dispose() }
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

    $ptrTmp = Join-Path $EvidenceDir ("latest.json.$Stamp-$PID.tmp")
    $ptr = Join-Path $EvidenceDir 'latest.json'
    [System.IO.File]::WriteAllText($ptrTmp, (([ordered]@{ current = (Split-Path $RunDir -Leaf); stamp = $Stamp }) | ConvertTo-Json), $Utf8NoBom)
    if (Test-Path -LiteralPath $ptr) {
      # Explicit backup path (PowerShell marshals a $null backup argument into
      # an empty string and File.Replace rejects it); the backup is removed
      # only AFTER the rollback probe below has confirmed the flip.
      $ptrBak = Join-Path $EvidenceDir 'latest.json.bak'
      [System.IO.File]::Replace($ptrTmp, $ptr, $ptrBak)
      # Rollback probe: re-read the flipped pointer and require it to parse and
      # reference THIS run. A failed probe restores the previous pointer from
      # the backup (Replace needs a non-empty backup arg, so the restore swaps
      # through a unique temp file) instead of leaving readers on a corrupt
      # pointer; the run then fails loudly with staging kept for inspection.
      $probeOk = $false
      try {
        $probe = ([System.IO.File]::ReadAllText($ptr)) | ConvertFrom-Json
        if ($probe.current -eq (Split-Path $RunDir -Leaf)) { $probeOk = $true }
      } catch { }
      if (-not $probeOk) {
        $restoreTmp = Join-Path $EvidenceDir ("latest.json.restore-$Stamp-$PID.tmp")
        [System.IO.File]::Replace($ptrBak, $ptr, $restoreTmp)
        Remove-Item -LiteralPath $restoreTmp -Force
        throw "latest.json flip failed the rollback probe; previous pointer restored"
      }
      Remove-Item -LiteralPath $ptrBak -Force
    } else {
      [System.IO.File]::Move($ptrTmp, $ptr)
      $probe = ([System.IO.File]::ReadAllText($ptr)) | ConvertFrom-Json
      if ($probe.current -ne (Split-Path $RunDir -Leaf)) {
        throw "latest.json initial publish failed the pointer probe"
      }
    }
    $Published = $true

    # One-time archival of pre-versioning flat files; runs only after the pointer
    # no longer references them, so a mid-move failure loses nothing current.
    $legacy = @(Get-ChildItem $EvidenceDir -File -Filter 'phase2-*' -ErrorAction SilentlyContinue)
    if ($legacy.Count -gt 0) {
      $legacyDir = Join-Path $EvidenceDir '_pre-versioning'
      New-Item -ItemType Directory -Force -Path $legacyDir | Out-Null
      foreach ($f in $legacy) { Move-Item -LiteralPath $f.FullName (Join-Path $legacyDir $f.Name) -Force }
    }
    Write-Output "published evidence run dir: $RunDir (pointer: latest.json)"
    if ($ArtPreviewBoardId) {
      if ($ArtPreviewFocusZoom -gt 0) {
        Write-Output 'ART PREVIEW K2 PROBE: host selected hero in frame at the requested zoom; joiner K1 has six fighters in frame. Visual art review remains separate.'
      } else {
        Write-Output "ART PREVIEW: live $ArtBoardSize board ($($ArtBoard.id)), $($ArtBoard.expect.zoneCells) zone cells, light profile $($ArtBoard.light), two 1920x1080 HUD shots, six fighter centers in frame; visual art review remains separate."
      }
      Write-Output 'NOTE: the pixel gate checks a lit textured board and HUD regions; it does not prove K1 readability or color-blind access.'
    } else {
      Write-Output "TRACES OK + SHOTS PRESENT + GRID VERIFIED + SIX FIGHTERS (trace: n=6, all projected in frame)"
      Write-Output "NOTE: silhouette shapes in the PNGs are confirmed by manual screenshot review (the image checker proves grid+team colors only)."
    }
    Write-Output "--- host trace (tail) ---"
    Get-Content -LiteralPath (Join-Path $RunDir 'phase2-client-host.trace.log') | Select-Object -Last 25
    Write-Output "--- joiner trace (tail) ---"
    Get-Content -LiteralPath (Join-Path $RunDir 'phase2-client-joiner.trace.log') | Select-Object -Last 20
  } finally {
    # Failed runs clean up too: kill any client still alive, then abort THIS
    # run's game (scoped + validated; never touches unrelated rooms).
    foreach ($p in @($hostProc, $joinProc)) {
      if ($p -and -not $p.HasExited) {
        Stop-Process -Id $p.Id -Force
        Write-Output "cleanup: killed still-running client pid=$($p.Id)"
      }
    }
    Stop-ThisRunGame
  }

  # Staging deletion happens ONLY on the success path, AFTER the pointer flip:
  # a failed run keeps its staging for inspection. The recursive delete goes
  # through the boundary+reparse guard and -LiteralPath.
  if ($Published) {
    Remove-TreeSafely $Script:Staging ([System.IO.Path]::GetTempPath())
  }
}

Invoke-Phase2Demo

# Cleanup failure propagation: the finally block above swallows the abort
# error into $Script:CleanupFailure (an in-flight demo error must still win);
# on the success path a failed scoped abort therefore lands HERE and makes
# the demo exit nonzero instead of counting a failed cleanup as success.
if ($Script:CleanupFailure) {
  throw "scoped cleanup did not verify ABORTED for this run's game: $Script:CleanupFailure"
}
