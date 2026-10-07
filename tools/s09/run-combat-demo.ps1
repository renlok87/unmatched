param(
  [string]$Exe = "",
  [string]$Api = "http://localhost:3120/graphql",
  [string]$EvidenceDir = "",
  [int]$RunSeconds = 240,
  [string]$ShotMode = "request",
  [switch]$ArtPreview,
  [switch]$FullHd,
  [int]$ClientFps = 30,
  # Stage 3 T3.2 port of the run-phase2-demo art-board flags (all opt-in,
  # -ArtPreview only). -ArtPreviewBoardId: a Board row id registered in
  # unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json; the host
  # creates the room on it, the game row is verified and both traces must show
  # 'BOARD WxH' of that registration. Without it the backend default board
  # (first created row) is used as before.
  [string]$ArtPreviewBoardId = "",
  # Both clients load this isolated /Game/ArtPreview Medusa candidate; passed
  # to the clients only when given explicitly (as in run-phase2-demo).
  [ValidateSet('face-neck-v2', 'head-tilt-v3')][string]$ArtPreviewMedusaVariant = 'face-neck-v2',
  # Host-only flag selection of its own hero at ArtPreviewShotAfter-2 (input
  # emulation, traced 'INPUT select src=flag'); -ArtPreviewFocusZoom (> 1)
  # additionally zooms the board camera toward it (traced 'CAMERA focus
  # src=flag'). The S09 combat plan itself is unchanged.
  [switch]$ArtPreviewSelectOwnHero,
  [double]$ArtPreviewFocusZoom = 0,
  [ValidateRange(0, 600)][int]$ArtPreviewShotAfter = 0,
  # Stage 3 T5.2 port of the W4-A render reference flags of run-phase2-demo
  # (user decision 2026-09-28: DX12/SM6 + Lumen, High). Both clients get
  # -S08RenderPreset=<preset> (None = keep the saved GameUserSettings, the
  # pre-T5.2 behaviour of this script); every SHOT of the S08/S09 clients
  # carries a 'RENDER tag=SHOT ... reference=0|1' fingerprint.
  [ValidateSet('None', 'Low', 'Medium', 'High', 'Epic')][string]$ClientRenderPreset = 'High',
  # Fail the run unless EVERY SHOT fingerprint of both clients is on the
  # reference (docs/art-pipeline/render-reference.json; K3 acceptance runs).
  [switch]$RequireRenderReference,
  # W5b-R: require the pixel provenance line of every published frame (SHOT captured, t53-thresholds shotCaptured).
  [switch]$RequireShotCaptured,
  # Opt-in per-client frame timing in the trace (PERF config/window/summary),
  # as run-phase2-demo -ClientPerf. Measurement only.
  [switch]$ClientPerf,
  # Wave 5c-B2 port of the run-phase2-demo 5c-B flags (-ArtPreview + -ArtPreviewBoardId only). Since ART-DEFAULT
  # (2026-10-04) the look-dev C figures and the tray are the client DEFAULT (the art look too, -ArtPreview or not):
  # the client flags -ArtPreviewHeroesV2 / -ArtPreviewDiorama are no-op aliases, and these switches now only add the
  # gates below (rollbacks: -ClientExtraArgs is not offered here; the client flags are -S08HeroesLegacy /
  # -S08DioramaLegacy / -S08GreyBoard). Asserted as in run-phase2-demo: 'ARTPREVIEW heroesV2 summary fighters=6 mapped=6 v2=6', six v2
  # 'ARTPREVIEW heroesV2 fighter=' lines, Idle on 6/6, no 'missing=' fallback; the diorama tray line
  # and no 'diorama tray missing'. The combat clip lines (LungeAttack / HitReact / DeathSettle) are
  # counted into the manifest (heroesV2Anim), not gated: which of them fire depends on the duel.
  [switch]$ArtPreviewHeroesV2,
  [switch]$ArtPreviewDiorama,
  # ENV-MAPS (opt-in): the run must end in a decided duel - both traces carry
  # 'RESULT seq=N outcome=VICTORY|DEFEAT winner=' (exactly one VICTORY and one
  # DEFEAT) and the authoritative game row reads FINISHED with a winnerId that
  # is one of this run's two seats. Without the switch the K3 gates are unchanged.
  [switch]$RequireGameOver,
  # ENV-MAPS P5a (opt-in): the joiner side (King Arthur + Merlin) maneuvers and attacks too, on the
  # same graph rules: joiner plan attack+ranged+defend+resolve (approach + attack; the 'ranged' token
  # puts a zone-only ranged pick - Merlin through a shared zone when no linked enemy exists - first),
  # host plan attack+defend+ownresult (it must answer the joiner's attacks; its result shot waits for a combat it
  # attacked - as a defender Medusa's post-combat pending choice can replace the result panel). Gated: the joiner trace must show
  # its own 'S09AUTO attack (' + 'ATTACK done seq=' and the host trace its 'DEFENSE done seq='.
  # Without the switch both plans and all gates are unchanged.
  [switch]$JoinerAttack,
  # Run E G-LIVE (DE-026, opt-in): the host plan also plays a scheme card after its attack when one is playable
  # (S09 plan token 'scheme'), so the joiner sees an opponent scheme in the source-card slot. Gates unchanged.
  [switch]$HostScheme,
  # Extra client arguments for BOTH clients, '+'-separated, as run-phase2-demo -ClientExtraArgs (run C G-LIVE,
  # since EN-13 the painted Marmoreal backdrop is the default; -NoConceptPaste rolls it back, AGENTS.md "Board scenes and heroes"). Gates unchanged.
  [string]$ClientExtraArgs = '',
  # VS-3 SC-01 (ВР-SC14): -S08ScreenShots on both clients - one evidence frame per new 'SHOT widget id=UI-SCR-* state=<s>'
  # (<UI-ID>-<state>.png in the shot directory of each client)
  [switch]$ScreenShots,
  # AU-S5 (docs/game-design/audio/07-production-log.md §9, opt-in): each client records its whole audio output from the
  # match start to the result + 8 s into <dir>/host.wav and <dir>/joiner.wav (-S08AudioRecord) for the loudness pass
  # (tools/audio/mix_check.py). Gates unchanged.
  [string]$AudioRecordDir = '',
  # AU-S6 (07-production-log §10, opt-in): replace the computed -S09Combat plans ('+'-separated tokens, see
  # S08FlowGameMode.cpp "GD-034 combat plan"), e.g. -JoinPlanOverride 'attack+abilityboost+scheme+storms+defend+resolve'
  # -HostPlanOverride 'attack+defend+feint+slowdefense+ownresult'. Empty keeps the plans below. Gates unchanged.
  [string]$HostPlanOverride = '',
  [string]$JoinPlanOverride = '',
  # VS-1 HB-02 exit frames (opt-in, docs/game-design/visual/05-production-plan.md §3 VS-1): both clients run WITHOUT
  # -S09Markers, the player's default view since HB-02. The state-marker and reveal-marker gates need the debug layer,
  # so they are replaced by the inverse gate: both traces carry 'ARTLOOK ... markers=0' and the defense/resolve/result
  # shots show none of the combat marker hues (<= the scene-noise allowance). Not a GD-034 acceptance run: the gate
  # run keeps -S09Markers. Every other gate (board, heroes v2, render reference, GAME_OVER, traces) is unchanged.
  # VS-4 HB-48: the default run has no -S09Markers either (the gates below read the SHOT widget lines); -PlayerView now
  # only marks the exit-frame runs in the manifest.
  [switch]$PlayerView,
  # VS-4 HB-48 (docs/game-design/visual/04-hud-spec.md s5.3): the rollback of the gate - both clients get -S09Markers
  # (the debug layer) and the GD-034 marker pixel gates run as before. Without it (the default since HB-48) the
  # defense / resolve / result / reveal shots are gated by their 'SHOT widget' lines (tools/s09/HudShotGate.ps1,
  # hud_contract.py check-shots) plus the privacy rules over both traces, and the debug-layer hues must be absent.
  # A block rolled back to Slate (-S08SlateHud=combat in -ClientExtraArgs) fails the default gate with that reason.
  [switch]$S09Markers
)

# W5b-R (t53-thresholds.json shotCaptured): every published frame must carry its pixel provenance line
# "SHOT captured file=<name> frame=<N> px=WxH sha256=<hex> order=BGRA saved=1" (UGameViewportClient::OnScreenshotCaptured;
# the client writes the PNG itself) and the late SHOT block of the same file ("SHOT late begin file=<name> frame=<M>")
# with |N - M| <= 1.
function Assert-ShotCaptured([string]$TracePath, [string]$Name, [string]$Who) {
  $cap = Select-String -LiteralPath $TracePath -Pattern ('SHOT captured file=' + [regex]::Escape($Name) + ' frame=(\d+) px=(\d+)x(\d+) sha256=([0-9a-f]{64}) order=BGRA saved=1') | Select-Object -Last 1
  if (-not $cap) { throw "$Who trace has no 'SHOT captured file=$Name ... saved=1' line (pixel provenance)" }
  $late = Select-String -LiteralPath $TracePath -Pattern ('SHOT late begin file=' + [regex]::Escape($Name) + ' frame=(\d+)') | Select-Object -Last 1
  if (-not $late) { throw "$Who trace has no end-of-frame SHOT block for $Name" }
  $capFrame = [long]$cap.Matches[0].Groups[1].Value
  $lateFrame = [long]$late.Matches[0].Groups[1].Value
  if ([Math]::Abs($capFrame - $lateFrame) -gt 1) { throw "$Who ${Name}: captured frame $capFrame vs late SHOT frame $lateFrame (> 1)" }
  Write-Output ("shot captured {0} {1}: frame={2} lateFrame={3} px={4}x{5} sha256={6}" -f $Who, $Name, $capFrame, $lateFrame, $cap.Matches[0].Groups[2].Value, $cap.Matches[0].Groups[3].Value, $cap.Matches[0].Groups[4].Value.Substring(0, 12))
}
# GD-034 two-client packaged COMBAT demo against the S09 worktree-local
# backend (attack -> defense -> resolve against authoritative snapshots):
#   host   -S09Flow -S09Combat=attack,scheme : greedy approach each own turn,
#           then attack(attacker, card, adjacent target) on the first legal
#           pair; a scheme card afterwards when one is playable.
#   joiner -S09Flow -S09Combat=defend,resolve : waits OUT its own turn window
#           (the defender acts inside the ATTACKER's COMBAT window), plays the
#           first legal defense card for the attacked fighter, then resolves
#           in COMBAT_RESOLVE (resolve is open to any participant).
# Live pixel gates (state-specific markers, drawn only by the matching panel):
#   defense panel #FF4040, resolve panel #40FF40, result panel #40FF80.
#   Each gated shot must show its own marker AND none of the other combat
#   markers; swapped/negative pairs are asserted to fail.
# Safety: per-process ENV credentials only, hidden clients, staged evidence
# published only after every assertion passed, room code redacted from
# published traces, scoped+validated abort of THIS run's game, fresh-shot
# checks, seq convergence between both clients.
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'HudShotGate.ps1')  # VS-4 HB-48
if ($S09Markers -and $PlayerView) { throw '-S09Markers (the marker gate rollback) and -PlayerView (the player view frames) exclude each other' }
# --- T3.2 art-board flag guards (before any process or network call) ---
$MedusaVariantExplicit = $PSBoundParameters.ContainsKey('ArtPreviewMedusaVariant')
if (($ArtPreviewBoardId -or $MedusaVariantExplicit -or $ArtPreviewSelectOwnHero -or $ArtPreviewFocusZoom -gt 0 -or
     $ArtPreviewShotAfter -gt 0) -and -not $ArtPreview) {
  throw 'ArtPreviewBoardId / ArtPreviewMedusaVariant / ArtPreviewSelectOwnHero / ArtPreviewFocusZoom / ArtPreviewShotAfter require -ArtPreview'
}
if (($ArtPreviewHeroesV2 -or $ArtPreviewDiorama) -and -not ($ArtPreview -and $ArtPreviewBoardId)) {
  throw 'ArtPreviewHeroesV2 / ArtPreviewDiorama require -ArtPreview and -ArtPreviewBoardId'
}
if ($ArtPreviewFocusZoom -gt 0 -and ($ArtPreviewFocusZoom -le 1 -or -not $ArtPreviewSelectOwnHero)) {
  throw 'ArtPreviewFocusZoom requires -ArtPreviewSelectOwnHero and a zoom greater than 1'
}
if ($ArtPreviewSelectOwnHero -and $ArtPreviewShotAfter -lt 4) {
  throw 'ArtPreviewSelectOwnHero requires ArtPreviewShotAfter >= 4 (the client selects at ShotAfter-2)'
}
if ($ArtPreviewShotAfter -gt 0 -and $RunSeconds -lt ($ArtPreviewShotAfter + 10)) {
  throw "RunSeconds=$RunSeconds must be at least ArtPreviewShotAfter+10 ($($ArtPreviewShotAfter + 10))"
}
$ArtBoard = $null
$ArtBoardSize = $null
if ($ArtPreviewBoardId) {
  if ($ArtPreviewBoardId -cnotmatch '^c[a-z0-9]{24}$') {
    throw "ArtPreviewBoardId '$ArtPreviewBoardId' is not a Board row id (cuid); content slugs such as 'cobble-city' are refused"
  }
  $ArtBoardsPath = Join-Path $RepoRoot 'unreal\Unmatched\Config\ArtBoards\S08ArtBoardProfiles.json'
  if (-not (Test-Path -LiteralPath $ArtBoardsPath)) { throw "art board registry missing: $ArtBoardsPath" }
  $ArtBoardsDoc = [System.IO.File]::ReadAllText($ArtBoardsPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
  $ArtBoard = @($ArtBoardsDoc.boards | Where-Object { @($_.match.boardIds) -ccontains $ArtPreviewBoardId }) | Select-Object -First 1
  if (-not $ArtBoard) {
    $known = (@($ArtBoardsDoc.boards | ForEach-Object { "$($_.id)=$(@($_.match.boardIds) -join '|')" }) -join ', ')
    throw "ArtPreviewBoardId '$ArtPreviewBoardId' is not a registered art board ($known)"
  }
  $ArtBoardSize = "$($ArtBoard.match.width)x$($ArtBoard.match.height)"
  # ENV-MAPS: an original-map profile (surface map-image) registers no grid W x H; the backend derives
  # W x H from the lattice of the committed topology fixture the profile names (as run-phase2-demo).
  $ArtBoardMap = ($ArtBoard.surface -eq 'map-image')
  if ($ArtBoardMap) {
    $topologyPath = Join-Path $RepoRoot $ArtBoard.fixture
    if (-not $ArtBoard.fixture -or -not (Test-Path -LiteralPath $topologyPath)) { throw "map-image board '$($ArtBoard.id)' names no readable topology fixture: '$($ArtBoard.fixture)'" }
    $ArtTopology = [System.IO.File]::ReadAllText($topologyPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    if ($ArtTopology.boardId -cne $ArtPreviewBoardId) { throw "topology fixture $($ArtBoard.fixture) is board $($ArtTopology.boardId), not $ArtPreviewBoardId" }
    $ArtBoardSize = "$($ArtTopology.lattice.width)x$($ArtTopology.lattice.height)"
  }
  Write-Output "art board: profile=$($ArtBoard.id) size=$ArtBoardSize light=$($ArtBoard.light) map=$ArtBoardMap"
}
if (-not $Exe) { $Exe = Join-Path $RepoRoot 'unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe' }
if (-not $EvidenceDir) { $EvidenceDir = Join-Path $RepoRoot 'docs\game-design\evidence\S09\run' }

function Set-StagedResolution([string]$ExePath, [int]$W, [int]$H) {
  $gsDir = Join-Path (Split-Path -Parent $ExePath) 'Unmatched\Saved\Config\Windows'
  New-Item -ItemType Directory -Force -Path $gsDir | Out-Null
  $gs = Join-Path $gsDir 'GameUserSettings.ini'
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
  Write-Output "staged GameUserSettings -> ${W}x${H} (windowed): $gs"
}
$ShotWidth = if ($FullHd) { 1920 } else { 1280 }
$ShotHeight = if ($FullHd) { 1080 } else { 720 }
# Never write a staged GameUserSettings next to a missing exe (a wrong -Exe
# would otherwise create <exe dir>\Unmatched\Saved\Config anywhere on disk).
if (-not (Test-Path -LiteralPath $Exe)) { throw "packaged exe not found: $Exe" }
Set-StagedResolution $Exe $ShotWidth $ShotHeight

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
    if ($arg -match '\s') { $psi.Arguments += '"' + $arg + '" ' } else { $psi.Arguments += $arg + ' ' }
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
    Assert-GqlOk $g 'cleanup game lookup'
    $game = $g.data.game
    if (-not $game) { Write-Output "cleanup: game $($Script:ThisRunGameId) no longer resolves - nothing to abort"; return }
    if ($game.hostId -cne $uid) {
      throw "REFUSING abort - host-ownership validation failed for game $($Script:ThisRunGameId)"
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
foreach ($pair in @(
    @('S09_DEMO_HOST_EMAIL', $AccountA.email), @('S09_DEMO_JOINER_EMAIL', $AccountB.email),
    @('S09_DEMO_HOST_PASSWORD', $AccountA.password), @('S09_DEMO_JOINER_PASSWORD', $AccountB.password))) {
  if (-not $pair[1]) { throw "missing $($pair[0]) in process environment" }
}

function Invoke-CombatDemo {
  $heroA = Get-Hero $AccountA.email $AccountA.password 'Medusa'
  $heroB = Get-Hero $AccountB.email $AccountB.password 'King Arthur'
  Write-Output "heroA=$heroA heroB=$heroB"

  $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Script:Staging = Join-Path ([System.IO.Path]::GetTempPath()) "s09-combat-$Stamp-$PID"
  New-Item -ItemType Directory -Force -Path $Script:Staging | Out-Null
  Write-Output "staging: $Script:Staging"

  $hostShots = Join-Path $Script:Staging 'host'
  $joinShots = Join-Path $Script:Staging 'joiner'
  New-Item -ItemType Directory -Force -Path $hostShots, $joinShots | Out-Null
  $hostTrace = Join-Path $Script:Staging 'combat-client-host.trace.log'
  $joinTrace = Join-Path $Script:Staging 'combat-client-joiner.trace.log'

  $Script:ThisRunGameId = $null
  $Script:ThisRunGameCode = $null

  $common = @("-windowed", "-resx=$ShotWidth", "-resy=$ShotHeight", "-RenderOffScreen", "log=GrepLog",
    "-ForceAbandonSequences", "-S08Api=$Api", "-S09ShotMode=$ShotMode", "-ExecCmds=t.MaxFPS $ClientFps")
  # HB-01 / VS-4 HB-48: only the marker gate rollback (-S09Markers) draws the debug layer; the default gates read SHOT widget
  if ($S09Markers) { $common += '-S09Markers' }
  if ($ArtPreview) { $common += '-ArtPreview' }
  if ($FullHd) { $common += '-ForceRes' }
  if ($MedusaVariantExplicit) { $common += "-ArtPreviewMedusaVariant=$ArtPreviewMedusaVariant" }
  if ($ClientRenderPreset -ne 'None') { $common += "-S08RenderPreset=$ClientRenderPreset" }
  if ($ClientPerf) { $common += '-S08Perf' }
  if ($ArtPreviewHeroesV2) { $common += '-ArtPreviewHeroesV2' }
  if ($ArtPreviewDiorama) { $common += '-ArtPreviewDiorama' }
  foreach ($extra in @($ClientExtraArgs -split '\+' | Where-Object { $_ })) { $common += $extra }
  if ($ScreenShots) { $common += '-S08ScreenShots' }  # VS-3 SC-01
  $HostPlan = if ($JoinerAttack) { 'attack+defend+ownresult' } else { 'attack' }
  if ($HostScheme) { $HostPlan += '+scheme' }
  $JoinPlan = if ($JoinerAttack) { 'attack+ranged+defend+resolve' } else { 'defend+resolve' }
  if ($HostPlanOverride) { $HostPlan = $HostPlanOverride }
  if ($JoinPlanOverride) { $JoinPlan = $JoinPlanOverride }
  Write-Output "combat plans: host=$HostPlan joiner=$JoinPlan"
  $hostArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08Create", "-S08HeroId=$heroA", "-S08Trace=$hostTrace",
    "-S09Flow", "-S09Combat=$HostPlan", "-S09ShotDir=$hostShots", "-S08ExitAfter=$RunSeconds")
  if ($ArtPreviewBoardId) { $hostArgs += "-ArtPreviewBoardId=$ArtPreviewBoardId" }
  if ($AudioRecordDir) { $hostArgs += ('-S08AudioRecord=' + (Join-Path $AudioRecordDir 'host.wav')) }
  if ($ArtPreviewShotAfter -gt 0) { $hostArgs += "-ArtPreviewShotAfter=$ArtPreviewShotAfter" }
  if ($ArtPreviewSelectOwnHero) { $hostArgs += '-ArtPreviewSelectOwnHero' }
  if ($ArtPreviewFocusZoom -gt 0) {
    $hostArgs += ('-ArtPreviewFocusZoom={0}' -f $ArtPreviewFocusZoom.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture))
  }
  $joinArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08HeroId=$heroB", "-S08Trace=$joinTrace",
    "-S09Flow", "-S09Combat=$JoinPlan", "-S09ShotDir=$joinShots", "-S08ExitAfter=$RunSeconds")
  if ($AudioRecordDir) { $joinArgs += ('-S08AudioRecord=' + (Join-Path $AudioRecordDir 'joiner.wav')) }

  $hostProc = $null
  $joinProc = $null
  $Published = $false
  try {
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
    if ($ArtPreviewBoardId) {
      $loginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken } }'; variables = @{ input = @{ email = $AccountA.email; password = $AccountA.password } } } | ConvertTo-Json -Depth 5
      $login = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBody
      Assert-GqlOk $login 'art-board host login'
      $lookup = @{ query = 'query G($id: String!) { game(id: $id) { id boardId } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
      $game = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers @{ authorization = "Bearer $($login.data.login.accessToken)" } -Body $lookup
      Assert-GqlOk $game 'art-board lookup'
      if ($game.data.game.boardId -cne $ArtPreviewBoardId) {
        throw "created room has boardId=$($game.data.game.boardId), expected $ArtPreviewBoardId"
      }
      Write-Output 'art board id verified against the authoritative game row'
    }

    $joinStartUtc = [DateTime]::UtcNow
    $joinProc = Start-S09Client $joinArgs $AccountB.email $AccountB.password $code
    Write-Output "joiner pid=$($joinProc.Id)"
    Assert-NoCredentialOnCmdLine $joinProc.Id @($AccountB.email, $AccountB.password, $code)

    $hostProc.WaitForExit()
    $joinProc.WaitForExit()
    Write-Output "both clients exited"

    function Assert-FreshShot([string]$Path, [DateTime]$ClientStartUtc, [string]$Who) {
      if (-not (Test-Path -LiteralPath $Path)) {
        throw "evidence shot missing for ${Who}: $Path"
      }
      $item = Get-Item -LiteralPath $Path
      if ($item.Length -lt 10KB) { throw "suspiciously small shot (likely black/empty) for ${Who}: $Path" }
      if ($item.LastWriteTimeUtc -le $ClientStartUtc) {
        throw "shot for ${Who} predates its client process (stale file): $Path"
      }
    }
    foreach ($pair in @(
      @('joiner', 's09-combat-defense-open.png', $joinStartUtc),
      @('joiner', 's09-combat-resolve-window.png', $joinStartUtc),
      @('joiner', 's09-combat-result.png', $joinStartUtc),
      @('host', 's09-combat-result.png', $hostStartUtc))) {
      Assert-FreshShot (Join-Path $Script:Staging (Join-Path $pair[0] $pair[1])) $pair[2] $pair[0]
    }

    # State-specific combat marker gates. Each panel draws one solid marker:
    # defense #FF4040, resolve #40FF40, result #40FF80 (attack draft #FF8000
    # and boost #FFFF40 must stay absent in these three shots). Tight +/-
    # tolerances keep the five hues mutually exclusive in the matcher.
    Add-Type -AssemblyName System.Drawing
    $Markers = @(
      @{ name = 'attack';  r = 255; g = 128; b = 0   },
      @{ name = 'defense'; r = 255; g = 64;  b = 64  },
      @{ name = 'resolve'; r = 64;  g = 255; b = 64  },
      @{ name = 'boost';   r = 255; g = 255; b = 64  },
      @{ name = 'result';  r = 64;  g = 255; b = 128 },
      @{ name = 'reveal';  r = 124; g = 252; b = 0   }
    )
    # VS-3 (ВР-VS3-71): the UMG card blocks draw the real card scans (King Arthur's red, Medusa's green art), whose
    # pixels fall into the marker hue tolerances (run 2026-10-07: 594 #FF4040-like samples in the joiner's hand). The
    # frame-wide ABSENCE counts ('All') skip the rectangles those blocks traced for the shot (SHOT widget id=UI-HUD-HAND |
    # -COMBAT-EDGE | -DECKS | -OPP-HAND | -DECKPANEL, visible=1, + 2 px); the PRESENCE counts ('Region') stay unmasked,
    # and the gate markers are Slate blocks outside them. The masked area is reported with the stats.
    function Get-CardArtRects([string]$TracePath, [string]$Leaf) {
      $lines = [System.IO.File]::ReadAllLines($TracePath)
      $at = -1
      for ($k = 0; $k -lt $lines.Length; $k++) { if ($lines[$k] -match ('SHOT request file=' + [regex]::Escape($Leaf) + ' ')) { $at = $k; break } }
      $rects = @()
      if ($at -lt 0) { return ,$rects }
      for ($k = $at - 1; $k -ge [Math]::Max(0, $at - 800); $k--) {
        $l = $lines[$k]
        if ($l -match 'SHOT (captured|late end) file=') { break }
        # VS-4: the source-card slot, the choice window and the inspector draw card scans too
        $m = [regex]::Match($l, 'SHOT widget id=(UI-HUD-HAND|UI-HUD-COMBAT-EDGE|UI-HUD-DECKS|UI-HUD-OPP-HAND|UI-HUD-DECKPANEL|UI-HUD-SLOT|UI-HUD-PENDING|UI-SCR-INSPECT) impl=umg .*?bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\) geom=painted visible=1')
        # VS-4 (set H, -S08ReducedMotion / speed «Нет»): the hand snaps between rest and lowered in one tick and the
        # captured paint can still show the row the trace already moved - a hand rect also covers 260 px above it
        if ($m.Success) { $up = if ($m.Groups[1].Value -eq 'UI-HUD-HAND') { 260 } else { 2 }; $rects += ,@(([int]$m.Groups[2].Value - 2), ([int]$m.Groups[3].Value - $up), ([int]$m.Groups[4].Value + 2), ([int]$m.Groups[5].Value + 2)) }
        # ВР-VS3-72: a leaving combat card paints outside its edge's rect
        $p = [regex]::Match($l, 'HUD-EDGE-PAINT .*?painted=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)')
        if ($p.Success) { $rects += ,@(([int]$p.Groups[1].Value - 2), ([int]$p.Groups[2].Value - 2), ([int]$p.Groups[3].Value + 2), ([int]$p.Groups[4].Value + 2)) }
      }
      # ВР-VS3-72: the late block of the same file - the hand's row and each card as painted (hover, raise, draw / leave
      # flights) and the combat edges, one rect each. It is written one tick after the captured frame: a card in flight
      # has moved on by up to ~60 px (a 350-500 ms flight, ease-out), so the late rects are widened by 64 px.
      $late = -1
      for ($k = $at + 1; $k -lt [Math]::Min($lines.Length, $at + 4000); $k++) { if ($lines[$k] -match ('SHOT late begin file=' + [regex]::Escape($Leaf) + ' ')) { $late = $k; break } }
      if ($late -ge 0) {
        for ($k = $late + 1; $k -lt [Math]::Min($lines.Length, $late + 2000); $k++) {
          $l = $lines[$k]
          if ($l -match ('SHOT late end file=' + [regex]::Escape($Leaf))) { break }
          if ($l -match 'HUD-PAINT-LATE id=(\S+) .*?rects=(\S+)') {
            $upLate = if ($Matches[1] -eq 'UI-HUD-HAND') { 260 } else { 64 }  # VS-4 set H: the snapped hand (above)
            foreach ($r in [regex]::Matches($Matches[2], '\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)')) {
              $rects += ,@(([int]$r.Groups[1].Value - 64), ([int]$r.Groups[2].Value - $upLate), ([int]$r.Groups[3].Value + 64), ([int]$r.Groups[4].Value + 64))
            }
          }
        }
      }
      return ,$rects
    }
    function Get-MarkerStats([string]$Path, [object[]]$Exclude = @()) {
      $bmp = [System.Drawing.Bitmap]::FromFile($Path)
      try {
        $w = $bmp.Width; $h = $bmp.Height
        $rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
        $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
          [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $bytes = New-Object byte[] ($data.Stride * $data.Height)
        [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
        $bmp.UnlockBits($data)
        $mask = New-Object bool[] ($w * $h)
        $masked = 0
        foreach ($r in $Exclude) {
          for ($my = [Math]::Max(0, $r[1]); $my -lt [Math]::Min($h, $r[3]); $my++) {
            for ($mx = [Math]::Max(0, $r[0]); $mx -lt [Math]::Min($w, $r[2]); $mx++) {
              if (-not $mask[$my * $w + $mx]) { $mask[$my * $w + $mx] = $true; $masked++ }
            }
          }
        }
        $stats = @{ w = $w; h = $h; maskedPx = $masked; maskRects = $Exclude.Count }
        foreach ($m in $Markers) {
          $stats[$m.name + 'Region'] = 0
          $stats[$m.name + 'All'] = 0
        }
        $rx1 = [int]($w * 0.60); $ry1 = [int]($h * 0.50); $tol = 16
        for ($y = 0; $y -lt $h; $y += 2) {
          $row = $y * $data.Stride
          $inRegion = ($y -lt $ry1)
          for ($x = 0; $x -lt $w; $x += 2) {
            $i = $row + $x * 4
            $pB = $bytes[$i]; $pG = $bytes[$i + 1]; $pR = $bytes[$i + 2]
            foreach ($m in $Markers) {
              if ([Math]::Abs($pR - $m.r) -le $tol -and
                  [Math]::Abs($pG - $m.g) -le $tol -and
                  [Math]::Abs($pB - $m.b) -le $tol) {
                if (-not $mask[$y * $w + $x]) { $stats[$m.name + 'All']++ }
                if ($inRegion -and $x -lt $rx1) { $stats[$m.name + 'Region']++ }
                break
              }
            }
          }
        }
        return $stats
      } finally { $bmp.Dispose() }
    }
    function Assert-Dimensions($Stats, [string]$Who) {
      $ok = ($Stats.w -eq $ShotWidth -and $Stats.h -eq $ShotHeight)
      if (-not $ok) {
        throw ("capture for {0} is {1}x{2} - expected {3}x{4} (saved GameUserSettings override?)" -f $Who, $Stats.w, $Stats.h, $ShotWidth, $ShotHeight)
      }
    }
    # DE-031 (run F G-LIVE): an absent marker may still match a few scattered scene pixels - the Sarpedon lit3d fire
    # (#F14D30) sits inside the defense hue tolerance and failed three result gates with 1 sample (runs E and F). A
    # drawn marker panel gives >= 200 samples, so 'absent' allows this much scene noise and the gate still separates
    # every state (the swap controls below keep checking it).
    $MarkerNoise = 4
    function Test-StateImage($Stats, [string]$State) {
      # Exactly ONE combat marker region may light up, and only the expected
      # one; every other combat marker must be absent frame-wide (<= $MarkerNoise scene samples).
      $n = $MarkerNoise
      if ($State -eq 'defense') {
        return ($Stats.defenseRegion -ge 200 -and $Stats.attackAll -le $n -and
                $Stats.resolveAll -le $n -and $Stats.boostAll -le $n -and $Stats.resultAll -le $n)
      }
      if ($State -eq 'resolve') {
        return ($Stats.resolveRegion -ge 200 -and $Stats.attackAll -le $n -and
                $Stats.defenseAll -le $n -and $Stats.boostAll -le $n -and $Stats.resultAll -le $n)
      }
      if ($State -eq 'result') {
        return ($Stats.resultRegion -ge 200 -and $Stats.attackAll -le $n -and
                $Stats.defenseAll -le $n -and $Stats.resolveAll -le $n -and $Stats.boostAll -le $n)
      }
      throw "unknown state: $State"
    }
    $defenseStats = Get-MarkerStats (Join-Path $Script:Staging (Join-Path 'joiner' 's09-combat-defense-open.png')) (Get-CardArtRects $joinTrace 's09-combat-defense-open.png')
    $resolveStats = Get-MarkerStats (Join-Path $Script:Staging (Join-Path 'joiner' 's09-combat-resolve-window.png')) (Get-CardArtRects $joinTrace 's09-combat-resolve-window.png')
    $joinResultStats = Get-MarkerStats (Join-Path $Script:Staging (Join-Path 'joiner' 's09-combat-result.png')) (Get-CardArtRects $joinTrace 's09-combat-result.png')
    $hostResultStats = Get-MarkerStats (Join-Path $Script:Staging (Join-Path 'host' 's09-combat-result.png')) (Get-CardArtRects $hostTrace 's09-combat-result.png')
    Write-Output ("card-art masks (VS-3): joiner defense {0} rects / {1} px, resolve {2} / {3}, result {4} / {5}; host result {6} / {7}" -f `
      $defenseStats.maskRects, $defenseStats.maskedPx, $resolveStats.maskRects, $resolveStats.maskedPx,
      $joinResultStats.maskRects, $joinResultStats.maskedPx, $hostResultStats.maskRects, $hostResultStats.maskedPx)
    foreach ($entry in @(@('joiner/defense', $defenseStats), @('joiner/resolve', $resolveStats),
                         @('joiner/result', $joinResultStats), @('host/result', $hostResultStats))) {
      Assert-Dimensions $entry[1] $entry[0]
    }
    Write-Output ("markers joiner: defense(def={0} atk={1} res={2} rst={3}) resolve(res={4} def={5} rst={6}) result(rst={7} res={8} def={9}) host: result(rst={10} res={11} def={12})" -f `
      $defenseStats.defenseRegion, $defenseStats.attackAll, $defenseStats.resolveAll, $defenseStats.resultAll,
      $resolveStats.resolveRegion, $resolveStats.defenseAll, $resolveStats.resultAll,
      $joinResultStats.resultRegion, $joinResultStats.resolveAll, $joinResultStats.defenseAll,
      $hostResultStats.resultRegion, $hostResultStats.resolveAll, $hostResultStats.defenseAll)
    $ShotGateLines = @()
    if (-not $S09Markers) {
      # HB-02 inverse gate: no debug layer in the player's view - ARTLOOK markers=0 on both clients and none of the
      # combat marker hues in the state shots (the reveal block hue is skipped: the revealed value text keeps it).
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        $look = Select-String -LiteralPath $pair[1] -Pattern 'ARTLOOK .* markers=(\d)' | Select-Object -Last 1
        if (-not $look -or $look.Matches[0].Groups[1].Value -ne '0') {
          throw "player view: $($pair[0]) trace has no 'ARTLOOK ... markers=0': $(if ($look) { $look.Line } else { 'no ARTLOOK line' })"
        }
      }
      foreach ($entry in @(@('joiner/defense', $defenseStats), @('joiner/resolve', $resolveStats),
                           @('joiner/result', $joinResultStats), @('host/result', $hostResultStats))) {
        $s = $entry[1]
        foreach ($hue in @('attack', 'defense', 'resolve', 'boost', 'result')) {
          if ($s[$hue + 'All'] -gt $MarkerNoise) {
            throw ("player view: {0} shot shows the {1} gate marker hue ({2} samples > {3})" -f $entry[0], $hue, $s[$hue + 'All'], $MarkerNoise)
          }
        }
      }
      # GD-033 privacy holds in the player's view too: the revealed value text appears only after the server reveal.
      if ($defenseStats.revealAll -ne 0 -or $resolveStats.revealAll -ne 0) {
        throw ("privacy gate failed: pre-reveal shots show reveal pixels (defense={0} resolve={1})" -f $defenseStats.revealAll, $resolveStats.revealAll)
      }
      Write-Output 'player view: ARTLOOK markers=0 on both clients, no combat marker hue in the defense/resolve/result shots'
      # VS-4 HB-48 SHOT widget gates (04 s5.3): the defender's window, the closed window before the reveal, the result
      # with the combat still on the edges; privacy over both traces (the opponent's card face only in state=reveal, the
      # hidden inspector without values). Defense-open may still show the previous combat's reveal while it stages, so
      # its pre-reveal privacy is the face rule; the resolve window must show no reveal at all.
      $ShotGateLines += Assert-HudShotGate -TracePath $joinTrace -Who joiner -Privacy -Rules @(
        's09-combat-defense-open.png: need UI-HUD-STATUS state=defend; need UI-HUD-COMBAT-EDGE fighter=opp',
        's09-combat-resolve-window.png: need UI-HUD-COMBAT-EDGE fighter=opp; deny UI-HUD-COMBAT-EDGE state=reveal; deny UI-HUD-STATUS state=defend',
        's09-combat-result.png: need UI-HUD-COMBAT-EDGE fighter=own || UI-HUD-COMBAT-EDGE fighter=opp; deny UI-HUD-STATUS state=defend')
      $ShotGateLines += Assert-HudShotGate -TracePath $hostTrace -Who host -Privacy -Rules @(
        's09-combat-result.png: need UI-HUD-COMBAT-EDGE fighter=own || UI-HUD-COMBAT-EDGE fighter=opp; deny UI-HUD-STATUS state=defend')
      # swap controls: a foreign shot never passes the defender's window rule
      $ShotGateLines += Assert-HudShotGateFails $joinTrace 's09-combat-resolve-window.png: need UI-HUD-STATUS state=defend' 'joiner resolve-window as the defense window'
      $ShotGateLines += Assert-HudShotGateFails $joinTrace 's09-combat-result.png: need UI-HUD-STATUS state=defend' 'joiner result as the defense window'
      $ShotGateLines += Assert-HudShotGateFails $hostTrace 's09-combat-result.png: need UI-HUD-STATUS state=defend' 'host result as the defense window'
      # the result reached the UMG combat centre: the COMBAT-RESULT seq of the result shot is staged by HUD-COMBAT
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        $lines = [System.IO.File]::ReadAllLines($pair[1])
        $shotAt = -1
        for ($k = $lines.Length - 1; $k -ge 0; $k--) { if ($lines[$k] -match 'SHOT request file=s09-combat-result\.png ') { $shotAt = $k; break } }
        $resultSeq = $null; $resultAt = -1
        for ($k = $shotAt; $k -ge 0; $k--) { if ($lines[$k] -match 'COMBAT-RESULT seq=(\d+) ') { $resultSeq = $Matches[1]; $resultAt = $k; break } }
        if ($shotAt -lt 0 -or -not $resultSeq) { throw "$($pair[0]): no COMBAT-RESULT before s09-combat-result.png" }
        $staged = $false
        for ($k = $resultAt; $k -lt $lines.Length; $k++) {
          if ($lines[$k] -match ('HUD-COMBAT center=(read|effects|slam|hit) seq=' + $resultSeq + ' ')) { $staged = $true; break }
        }
        if (-not $staged) { throw "$($pair[0]): COMBAT-RESULT seq=$resultSeq never reached the UMG combat centre (no HUD-COMBAT center=read|effects|slam|hit seq=$resultSeq) - -S08SlateHud=combatcenter? the Slate path is gated with -S09Markers" }
        $ShotGateLines += "$($pair[0]) combat centre staged the result seq=$resultSeq"
      }
      foreach ($l in $ShotGateLines) { Write-Output $l }
      Write-Output 'SHOT widget gates (HB-48): defense window, closed window before the reveal, result on the edges and in the centre, privacy - PASS'
    } elseif ($ShotMode -ne 'request') {
      Write-Output "WARN ShotMode=$ShotMode renders the HUD widget only - state gates skipped (P1 acceptance requires 'request')"
    } else {
      if (-not (Test-StateImage $defenseStats 'defense')) {
        throw ("joiner defense-open capture failed the defense gate (def={0} atk={1} res={2} bst={3} rst={4})" -f `
          $defenseStats.defenseRegion, $defenseStats.attackAll, $defenseStats.resolveAll, $defenseStats.boostAll, $defenseStats.resultAll)
      }
      if (-not (Test-StateImage $resolveStats 'resolve')) {
        throw ("joiner resolve-window capture failed the resolve gate (res={0} def={1} rst={2})" -f `
          $resolveStats.resolveRegion, $resolveStats.defenseAll, $resolveStats.resultAll)
      }
      if (-not (Test-StateImage $joinResultStats 'result')) {
        throw ("joiner result capture failed the result gate (rst={0} res={1} def={2})" -f `
          $joinResultStats.resultRegion, $joinResultStats.resolveAll, $joinResultStats.defenseAll)
      }
      if (-not (Test-StateImage $hostResultStats 'result')) {
        throw ("host result capture failed the result gate (rst={0} res={1} def={2})" -f `
          $hostResultStats.resultRegion, $hostResultStats.resolveAll, $hostResultStats.defenseAll)
      }
      # Swapped/negative pairs must NOT pass a foreign gate.
      if (Test-StateImage $defenseStats 'resolve') { throw "swap control failed: defense shot passed the resolve gate" }
      if (Test-StateImage $defenseStats 'result') { throw "swap control failed: defense shot passed the result gate" }
      if (Test-StateImage $resolveStats 'defense') { throw "swap control failed: resolve shot passed the defense gate" }
      if (Test-StateImage $resolveStats 'result') { throw "swap control failed: resolve shot passed the result gate" }
      if (Test-StateImage $joinResultStats 'defense') { throw "swap control failed: result shot passed the defense gate" }
      if (Test-StateImage $joinResultStats 'resolve') { throw "swap control failed: result shot passed the resolve gate" }
      # GD-033 privacy gate: pre-reveal shots must carry ZERO reveal pixels
      # (#7CFC00 block + value text render only after the server reveal).
      if ($defenseStats.revealAll -ne 0) {
        throw ("privacy gate failed: defense-open shot already shows reveal pixels ({0})" -f $defenseStats.revealAll)
      }
      if ($resolveStats.revealAll -ne 0) {
        throw ("privacy gate failed: pre-reveal resolve-window shot already shows reveal pixels ({0})" -f $resolveStats.revealAll)
      }
    }

    function Assert-Trace([string]$Path, [string[]]$MustContain, [string]$Who) {
      $text = Get-Content -LiteralPath $Path -Raw
      foreach ($needle in $MustContain) {
        if (-not $text.Contains($needle)) { throw "$Who trace missing '$needle'" }
      }
    }
    if ($ArtPreviewBoardId) {
      # T3.2 gate: the registered W x H, the board profile chosen by THIS row
      # id with its expectation met, and the light profile applied - on both
      # clients, before any combat assertion.
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        if (-not (Select-String -LiteralPath $pair[1] -SimpleMatch -Pattern "BOARD $ArtBoardSize cells" -Quiet)) {
          $seen = Select-String -LiteralPath $pair[1] -Pattern 'BOARD \d+x\d+ cells' | Select-Object -First 1
          throw "$($pair[0]) trace has no 'BOARD $ArtBoardSize' for $($ArtBoard.id): $(if ($seen) { $seen.Line } else { 'no BOARD line' })"
        }
        $active = Select-String -LiteralPath $pair[1] -Pattern ('ARTPREVIEW board active profile=' + [regex]::Escape($ArtBoard.id) + ' ' + $ArtBoardSize + ' .* expectOk=(\d)') | Select-Object -Last 1
        if (-not $active -or $active.Matches[0].Groups[1].Value -ne '1') {
          throw "$($pair[0]) board art does not match its registration: $(if ($active) { $active.Line } else { 'no active line' })"
        }
        Assert-Trace $pair[1] @("ARTPREVIEW board profile=$($ArtBoard.id) match=boardId board=$ArtBoardSize boardId=$ArtPreviewBoardId",
          "ARTPREVIEW lights applied profile=$($ArtBoard.light) directional=1 shadow=1 ") "$($pair[0]) art board"
        if ($ArtBoardMap) {
          # ENV-MAPS: the client plays the map on its space graph (spaces/links of the registration).
          Assert-Trace $pair[1] @("BOARD topology spaces=$($ArtBoard.expect.spaces) links=$($ArtBoard.expect.links) starts=",
            "ARTPREVIEW board active profile=$($ArtBoard.id) $ArtBoardSize surface=map-image map=$($ArtBoard.mapImage.name) spaces=$($ArtBoard.expect.spaces) links=$($ArtBoard.expect.links) ") "$($pair[0]) map board"
        }
      }
    }
    if ($MedusaVariantExplicit) {
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        Assert-Trace $pair[1] @("ARTPREVIEW medusa candidate variant=$ArtPreviewMedusaVariant ") "$($pair[0]) Medusa variant"
      }
    }
    if ($ArtPreviewSelectOwnHero) {
      Assert-Trace $hostTrace @('ARTPREVIEW selection ownHero=1 selected=1', 'INPUT select src=flag') 'host flag selection'
    }
    $HeroesV2Anim = $null
    if ($ArtPreviewHeroesV2) {
      $HeroesV2Anim = [ordered]@{}
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        Assert-Trace $pair[1] @('ARTPREVIEW heroesV2 summary fighters=6 mapped=6 v2=6', 'ARTPREVIEW anim fighter=') "$($pair[0]) heroes v2"
        $v2 = @(Select-String -LiteralPath $pair[1] -Pattern 'ARTPREVIEW heroesV2 fighter=(\S+) mesh=/Game/PipelineCandidates/\S+ mi=/Game/PipelineCandidates/\S+_P[12] yaw=' |
          ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique)
        if ($v2.Count -ne 6) { throw "$($pair[0]) trace shows $($v2.Count)/6 v2 figures" }
        $idle = @(Select-String -LiteralPath $pair[1] -Pattern 'ARTPREVIEW anim fighter=(\S+) clip=Idle len=' |
          ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique)
        if ($idle.Count -ne 6) { throw "$($pair[0]) trace shows Idle on $($idle.Count)/6 v2 figures" }
        $missing = Select-String -LiteralPath $pair[1] -Pattern 'ARTPREVIEW (heroesV2 fighter=\S+ missing=|anim fighter=\S+ clip=\S+ missing=1)' | Select-Object -First 1
        if ($missing) { throw "$($pair[0]) v2 asset missing in the pak: $($missing.Line)" }
        $clips = [ordered]@{}
        foreach ($clip in @('Idle', 'LungeAttack', 'HitReact', 'DeathSettle')) {
          $clips[$clip] = @(Select-String -LiteralPath $pair[1] -Pattern ('ARTPREVIEW anim fighter=\S+ clip=' + $clip + ' ')).Count
        }
        $HeroesV2Anim[$pair[0]] = $clips
        Write-Output ("heroes v2 {0}: figures={1} idle={2} clips Idle={3} LungeAttack={4} HitReact={5} DeathSettle={6}" -f $pair[0], $v2.Count, $idle.Count, $clips.Idle, $clips.LungeAttack, $clips.HitReact, $clips.DeathSettle)
      }
    }
    if ($ArtPreviewDiorama) {
      foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        Assert-Trace $pair[1] @('ARTPREVIEW diorama requested mesh=/Game/PipelineCandidates/TableBase/', 'ARTPREVIEW diorama tray=/Game/PipelineCandidates/TableBase/') "$($pair[0]) diorama"
        $trayMissing = Select-String -LiteralPath $pair[1] -Pattern 'ARTPREVIEW diorama tray missing' | Select-Object -First 1
        if ($trayMissing) { throw "$($pair[0]) diorama tray not shown: $($trayMissing.Line)" }
        if ($ArtBoardMap) {
          # ENV-MAPS (as run-phase2-demo): the map's 3D perimeter and themed ground spawn with the tray.
          $mapKey = $ArtTopology.map
          $envLine = Select-String -LiteralPath $pair[1] -Pattern ('ARTPREVIEW envlayout map=' + [regex]::Escape($mapKey) + ' props=\d+ .* missingMeshes=0 .*combinedBudgetOk=1 .*boardId=' + [regex]::Escape($ArtPreviewBoardId) + ' .* status=ok') | Select-Object -Last 1
          if (-not $envLine) { throw "$($pair[0]) env layout of $mapKey not spawned ok (no 'ARTPREVIEW envlayout map=$mapKey ... status=ok')" }
          $ground = Select-String -LiteralPath $pair[1] -Pattern ('ARTPREVIEW envlayout ground map=' + [regex]::Escape($mapKey) + ' .* status=ok') | Select-Object -Last 1
          if (-not $ground) { throw "$($pair[0]) env ground of $mapKey not spawned ok" }
        }
      }
    }
    # T5.2: W4-A render reference on every evidence SHOT of both clients that
    # shows the board. The lobby-return shot is taken after leaving the room:
    # no board and no art profile, so its fingerprint reports noArtProfile by
    # design and is listed, not gated.
    foreach ($pair in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
      $shots = New-Object System.Collections.Generic.List[object]
      $lastRef = $null; $lastLine = $null
      foreach ($line in (Get-Content -LiteralPath $pair[1])) {
        if ($line -match 'RENDER tag=SHOT .* reference=(\d)') { $lastRef = $Matches[1]; $lastLine = $line; continue }
        if ($line -match 'SHOT requested: .*[\\/]([^\\/]+\.png)\s*$') {
          $shots.Add([pscustomobject]@{ name = $Matches[1]; ref = $lastRef; line = $lastLine })
          $lastRef = $null; $lastLine = $null
        }
      }
      $gated = @($shots | Where-Object { $_.name -ne 's09-lobby-return.png' })
      $off = @($gated | Where-Object { $_.ref -ne '1' })
      $lobby = @($shots | Where-Object { $_.name -eq 's09-lobby-return.png' })
      Write-Output ("render fingerprint {0}: shots={1} gated={2} offReference={3} lobbyShots={4} preset={5}" -f $pair[0], $shots.Count, $gated.Count, $off.Count, $lobby.Count, $ClientRenderPreset)
      if ($RequireRenderReference) {
        if ($gated.Count -eq 0) { throw "$($pair[0]) trace has no board SHOT" }
        if ($off.Count -gt 0) { throw "$($pair[0]) SHOT $($off[0].name) is off the render reference: $(if ($off[0].line) { $off[0].line } else { 'no RENDER line in its SHOT block' })" }
      }
      # The duel flow exits right after GAME_OVER -> result -> lobby, before -S08ExitAfter,
      # so the exit-time 'PERF summary' lines are not guaranteed here: gate on the
      # config line and the periodic 5 s 'PERF window' samples.
      if ($ClientPerf) { Assert-Trace $pair[1] @('PERF config', 'PERF window t=') "$($pair[0]) perf" }
    }
    if ($ArtPreviewFocusZoom -gt 0) {
      Assert-Trace $hostTrace @('ARTPREVIEW camera focus requested zoom=', 'INPUT zoom src=flag', 'CAMERA focus src=flag') 'host focus zoom'
    }
    Assert-Trace $hostTrace @(
      'SNAPSHOT applied', 'SUBSCRIBED gameStateUpdated', 'HUD seq=',
      'S09AUTO attack (', 'ATTACK sent', 'ATTACK done seq=',
      'COMBAT-RESULT seq=', 'S09AUTO combat-result shot') 'host'
    Assert-Trace $joinTrace @(
      'SNAPSHOT applied', 'SUBSCRIBED gameStateUpdated', 'HUD seq=',
      'S09AUTO defense-window shot', 'S09AUTO defense card picked',
      'DEFENSE sent', 'DEFENSE done seq=',
      'S09AUTO resolve-window shot', 'S09AUTO resolve',
      'RESOLVE sent', 'RESOLVE done seq=',
      'COMBAT-RESULT seq=', 'S09AUTO combat-result shot') 'joiner'
    $JoinerAttackStats = $null
    if ($JoinerAttack) {
      # ENV-MAPS P5a opt-in: the joiner attacked on its own turns and the host answered the defense window.
      Assert-Trace $joinTrace @('S09AUTO attack (', 'ATTACK sent', 'ATTACK done seq=') 'joiner attack plan'
      if (-not (Select-String -LiteralPath $hostTrace -Pattern 'S09AUTO (defense card picked|no legal defense card)' -Quiet)) {
        throw 'host trace never answered a joiner attack (no S09AUTO defense card picked / no legal defense card)'
      }
      $JoinerAttackStats = [ordered]@{
        hostPlan = $HostPlan; joinerPlan = $JoinPlan
        joinerAttacksDone = @(Select-String -LiteralPath $joinTrace -Pattern 'ATTACK done seq=').Count
        joinerRangedPicks = @(Select-String -LiteralPath $joinTrace -Pattern 'S09AUTO ranged target attacker=').Count
        hostAttacksDone = @(Select-String -LiteralPath $hostTrace -Pattern 'ATTACK done seq=').Count
        hostDefenses = @(Select-String -LiteralPath $hostTrace -Pattern 'S09AUTO (defense card picked|no legal defense card)').Count
      }
      Write-Output ("joiner attack plan: joiner attacks done={0} ranged picks={1}; host attacks done={2} defenses={3}" -f `
        $JoinerAttackStats.joinerAttacksDone, $JoinerAttackStats.joinerRangedPicks, $JoinerAttackStats.hostAttacksDone, $JoinerAttackStats.hostDefenses)
    }
    if ($ArtPreview) {
      Assert-Trace $joinTrace @(
        'ARTPREVIEW damage-number fighter=',
        'S09AUTO damage-number shot', ' icon=1 targetMesh=') 'joiner-art'
      foreach ($entry in @(@('host', $hostTrace), @('joiner', $joinTrace))) {
        $seen = @{}
        foreach ($line in (Get-Content -LiteralPath $entry[1])) {
          if ($line -match 'ARTPREVIEW damage-number fighter=(\S+) amount=(\d+) seq=(\d+)') {
            $key = "$($Matches[1]):$($Matches[3])"
            if ($seen.ContainsKey($key)) { throw "$($entry[0]) duplicate damage number: $key" }
            $seen[$key] = $true
          }
        }
      }
    }

    # GD-033 reveal proof: the reveal-marker shot is captured when the server
    # reveal leaves the resolve window open (post-reveal pause). If the combat
    # closed with no pause there is nothing to shoot - report honestly; if the
    # shot was attempted but never appeared, that is an explicit FAILURE.
    $RevealShotRel = Join-Path 'joiner' 's09-combat-resolve-revealed.png'
    $RevealShot = Join-Path $Script:Staging $RevealShotRel
    $RevealProof = 'absent: combat closed without a post-reveal pause (no boost choice) - not faked'
    $joinTextForReveal = Get-Content -LiteralPath $joinTrace -Raw
    if ($joinTextForReveal.Contains('resolve-revealed shot file never appeared')) {
      throw "reveal proof FAILED: the client reported the revealed shot never appeared (see joiner trace)"
    }
    if ($joinTextForReveal.Contains('S09AUTO resolve-revealed shot')) {
      if (-not (Test-Path -LiteralPath $RevealShot)) {
        throw "reveal proof FAILED: trace shows the revealed shot was taken but the file is missing: $RevealShot"
      }
      if (-not $S09Markers) {
        # VS-4 HB-48: the revealed shot shows the reveal on a combat edge (SHOT widget), never a marker
        $ShotGateLines += Assert-HudShotGate -TracePath $joinTrace -Who joiner -Rules @(
          's09-combat-resolve-revealed.png: need UI-HUD-COMBAT-EDGE state=reveal')
        $ShotGateLines += Assert-HudShotGateFails $joinTrace 's09-combat-resolve-revealed.png: deny UI-HUD-COMBAT-EDGE state=reveal' 'joiner revealed shot as a pre-reveal shot'
        Write-Output 'reveal proof (HB-48): UI-HUD-COMBAT-EDGE state=reveal in the revealed shot'
      } elseif ($ShotMode -eq 'request') {
        $revealedStats = Get-MarkerStats $RevealShot (Get-CardArtRects $joinTrace 's09-combat-resolve-revealed.png')  # VS-3 ВР-VS3-71
        Assert-Dimensions $revealedStats 'joiner/revealed'
        Write-Output ("reveal markers joiner: resolve(res={0}) reveal(rvl={1} def={2} rst={3})" -f `
          $revealedStats.resolveRegion, $revealedStats.revealRegion, $revealedStats.defenseAll, $revealedStats.resultAll)
        if ($revealedStats.revealRegion -lt 40 -or $revealedStats.resolveRegion -lt 200) {
          throw ("reveal gate failed: revealed capture needs the resolve marker AND reveal pixels (rvl={0} res={1})" -f `
            $revealedStats.revealRegion, $revealedStats.resolveRegion)
        }
        if ($revealedStats.attackAll -gt $MarkerNoise -or $revealedStats.defenseAll -gt $MarkerNoise -or
            $revealedStats.resultAll -gt $MarkerNoise) {
          throw "reveal gate failed: foreign combat markers present in the revealed shot"
        }
      }
      $RevealProof = if (-not $S09Markers) { 'present (HB-48 SHOT widget): no reveal before it, the face rule over both traces, and the revealed shot shows UI-HUD-COMBAT-EDGE state=reveal' } else { 'present: pre-reveal privacy gates passed (zero reveal pixels) and the revealed shot carries the #7CFC00 reveal block + resolve marker' }
    } else {
      Write-Output "WARN: no reveal pause this run - reveal proof not captured (honest absence, recorded in manifest)"
    }
    # Optional stretch goal: a scheme card played after the combat.
    $hostText = Get-Content -LiteralPath $hostTrace -Raw
    if ($hostText.Contains('SCHEME sent') -and $hostText.Contains('SCHEME done seq=')) {
      Write-Output 'scheme stretch goal reached: SCHEME sent + done present'
    } else {
      Write-Output 'WARN: scheme not played this run (no legal card/action left) - not a gate'
    }
    # Role-gate trace cross-checks: both clients observed the combat phases;
    # the defender's DEFENSE/RESOLVE lines must exist even though the COMBAT
    # window opens inside the ATTACKER's turn.
    $joinText = Get-Content -LiteralPath $joinTrace -Raw
    if (-not $joinText.Contains('phase=COMBAT')) { throw "joiner trace never observed phase=COMBAT" }
    if (-not $joinText.Contains('phase=COMBAT_RESOLVE')) { throw "joiner trace never observed phase=COMBAT_RESOLVE" }
    if (-not ($hostText -match 'phase=COMBAT')) { throw "host trace never observed phase=COMBAT" }

    # Privacy: published traces must not carry card ids for combat actions.
    # ENV-MAPS P5a: 'PEND-RESOLVE sent type=<T> stage=N id=<effect id>' (pending-choice answer, GD-035) is not a
    # combat command; the case-insensitive 'card' used to hit its type DISCARD_CARDS / id 'discard-choice-...' (an
    # after-combat effect of an already revealed card - the same id class as the accepted BOOST_CHOICE / MOVE ids).
    # Only that exact pending-answer line shape is exempt; any other PEND-RESOLVE line (e.g. one logging a card
    # field) is still checked like every combat command.
    $pendAnswer = '^\S+ PEND-RESOLVE sent type=[A-Z_]+ stage=\d+ id=\S+$'
    foreach ($t in @(@('host', $hostText), @('joiner', $joinText))) {
      foreach ($line in ($t[1] -split "`r?`n")) {
        if ($line -match $pendAnswer) { continue }
        # AU-S6: 'ATTACK sent ability=card|none' (DE-020) only says whether an ability boost went with the attack -
        # no identity; the token is cut before the check (the first live Arthur ability-boost run tripped on it).
        $checked = $line -replace ' ability=(card|none)', ''
        if ($checked -match '(ATTACK|DEFENSE|RESOLVE|SCHEME) sent .*card') {
          throw "$($t[0]) trace appears to log card identities with a combat command"
        }
      }
    }

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

    $GameOver = $null
    if ($RequireGameOver) {
      $mH = [regex]::Match($hostText, 'RESULT seq=(\d+) outcome=([A-Z]+) winner=')
      $mJ = [regex]::Match($joinText, 'RESULT seq=(\d+) outcome=([A-Z]+) winner=')
      if (-not $mH.Success -or -not $mJ.Success) { throw "GAME_OVER gate: 'RESULT seq=' missing (host=$($mH.Success) joiner=$($mJ.Success)) - the duel did not reach GAME_OVER within RunSeconds=$RunSeconds" }
      $hostOutcome = $mH.Groups[2].Value; $joinOutcome = $mJ.Groups[2].Value
      if (-not (($hostOutcome -eq 'VICTORY' -and $joinOutcome -eq 'DEFEAT') -or ($hostOutcome -eq 'DEFEAT' -and $joinOutcome -eq 'VICTORY'))) {
        throw "GAME_OVER gate: outcomes are not one VICTORY + one DEFEAT (host=$hostOutcome joiner=$joinOutcome)"
      }
      $goLoginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }'; variables = @{ input = @{ email = $AccountA.email; password = $AccountA.password } } } | ConvertTo-Json -Depth 5
      $goLoginA = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $goLoginBody
      Assert-GqlOk $goLoginA 'GAME_OVER gate host login'
      $goLoginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }'; variables = @{ input = @{ email = $AccountB.email; password = $AccountB.password } } } | ConvertTo-Json -Depth 5
      $goLoginB = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $goLoginBody
      Assert-GqlOk $goLoginB 'GAME_OVER gate joiner login'
      $goQuery = @{ query = 'query G($id: String!) { game(id: $id) { id status winnerId boardId } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
      $goRow = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers @{ authorization = "Bearer $($goLoginA.data.login.accessToken)" } -Body $goQuery
      Assert-GqlOk $goRow 'GAME_OVER gate game lookup'
      $row = $goRow.data.game
      if (-not $row -or $row.id -cne $Script:ThisRunGameId) { throw "GAME_OVER gate: game $($Script:ThisRunGameId) does not resolve" }
      if ($row.status -cne 'FINISHED') { throw "GAME_OVER gate: game row status=$($row.status), expected FINISHED" }
      $seatA = $goLoginA.data.login.user.id; $seatB = $goLoginB.data.login.user.id
      if (-not $row.winnerId -or @($seatA, $seatB) -notcontains $row.winnerId) { throw 'GAME_OVER gate: FINISHED row has no winnerId of this run''s two seats' }
      $rowWinnerSeat = if ($row.winnerId -eq $seatA) { 'host' } else { 'joiner' }
      $traceWinnerSeat = if ($hostOutcome -eq 'VICTORY') { 'host' } else { 'joiner' }
      if ($rowWinnerSeat -ne $traceWinnerSeat) { throw "GAME_OVER gate: server winner ($rowWinnerSeat) contradicts the presented VICTORY ($traceWinnerSeat)" }
      if ($ArtPreviewBoardId -and $row.boardId -cne $ArtPreviewBoardId) { throw "GAME_OVER gate: row boardId=$($row.boardId), expected $ArtPreviewBoardId" }
      $GameOver = [ordered]@{ status = $row.status; winnerSeat = $rowWinnerSeat; hostOutcome = $hostOutcome; joinerOutcome = $joinOutcome; hostResultSeq = [int]$mH.Groups[1].Value; joinerResultSeq = [int]$mJ.Groups[1].Value; boardId = $row.boardId }
      Write-Output ("GAME_OVER gate ok: row FINISHED, winner seat={0} (host {1}, joiner {2}), result seq host={3} joiner={4}" -f $rowWinnerSeat, $hostOutcome, $joinOutcome, $GameOver.hostResultSeq, $GameOver.joinerResultSeq)
    }

    $publishNames = @(
      'combat-client-host.trace.log', 'combat-client-joiner.trace.log',
      'host\s09-combat-result.png',
      'joiner\s09-combat-defense-open.png', 'joiner\s09-combat-resolve-window.png', 'joiner\s09-combat-result.png'
    )
    if ($RevealProof.StartsWith('present')) { $publishNames += $RevealShotRel }
    if ($ArtPreview) { $publishNames += (Join-Path 'joiner' 's09-damage-number.png') }
    # W5b-R: the damage number of the first COMBAT (host evidence; the first damage of a game can be an ability's).
    if ($ArtPreview) {
      foreach ($side in @('host', 'joiner')) {
        $combatDamage = Join-Path $side 's09-damage-combat.png'
        if (Test-Path -LiteralPath (Join-Path $Script:Staging $combatDamage)) { $publishNames += $combatDamage }
        else { Write-Output "damage-combat frame: $side has none (no damage CUE on the combat target while its number was painted)" }
      }
    }
    # Run C G-LIVE (DE-019): with -RequireGameOver the result-screen frame of each seat is evidence too (the screen comes
    # after the dead hero is gone + 1000 ms); published when the seat wrote it.
    if ($RequireGameOver) {
      foreach ($side in @('host', 'joiner')) {
        $resultScreen = Join-Path $side 's09-result-screen.png'
        if (Test-Path -LiteralPath (Join-Path $Script:Staging $resultScreen)) { $publishNames += $resultScreen }
        else { Write-Output "result-screen frame: $side has none" }
        # Run F G-LIVE (DE-029): the final board ("VIEW BOARD") after the result screen; published when written.
        $resultBoard = Join-Path $side 's09-result-board.png'
        if (Test-Path -LiteralPath (Join-Path $Script:Staging $resultBoard)) { $publishNames += $resultBoard }
        else { Write-Output "result-board frame: $side has none" }
      }
    }
    # Run D G-LIVE (move-selection 06 MS-AT-30): the opponent-client frames of the first opponent move - in flight
    # (MS-T-16 / DE-021) and with its last-move highlight + feed line (MS-T-17 / DE-022). Published when written; not gated.
    if ($ArtPreview) {
      foreach ($side in @('host', 'joiner')) {
        foreach ($leaf in @('s09-opponent-move.png', 's09-opponent-last-move.png')) {
          $oppFrame = Join-Path $side $leaf
          if (Test-Path -LiteralPath (Join-Path $Script:Staging $oppFrame)) { $publishNames += $oppFrame }
          else { Write-Output "opponent frame: $side has no $leaf" }
        }
      }
      # Run E G-LIVE (S11e): the own-turn banner (DE-023), the hand-limit toast and the discard (DE-024), the
      # source-card slot per owner (DE-026). Each appears only when the match reaches that moment: published when
      # written; not gated.
      foreach ($side in @('host', 'joiner')) {
        foreach ($leaf in @('s09-turn-banner.png', 's09-hand-limit-hint.png', 's09-discard-open.png',
            's09-card-slot-opp.png', 's09-card-slot-own.png', 's09-no-defense-stamp.png')) {
          $runEFrame = Join-Path $side $leaf
          if (Test-Path -LiteralPath (Join-Path $Script:Staging $runEFrame)) { $publishNames += $runEFrame }
          else { Write-Output "run E frame: $side has no $leaf" }
        }
        # Run F G-LIVE (DE-030): the deck side panel - my deck, then the opponent's (opened by the auto client in the
        # opponent's turn); published when written; not gated.
        foreach ($leaf in @('s09-deck-own.png', 's09-deck-opp.png')) {
          $runFFrame = Join-Path $side $leaf
          if (Test-Path -LiteralPath (Join-Path $Script:Staging $runFFrame)) { $publishNames += $runFFrame }
          else { Write-Output "run F frame: $side has no $leaf" }
        }
        # VS-2 exit frames (opt-in client flag -S08ExitShots through -ClientExtraArgs, 05-production-plan s3 VS-2): the
        # own / opponent turn start + 0.5 s and + 3 s; published when written; not gated.
        foreach ($exitFrame in @(Get-ChildItem -LiteralPath (Join-Path $Script:Staging $side) -Filter 's09-exit-*.png' -ErrorAction SilentlyContinue | Sort-Object Name)) {
          $publishNames += (Join-Path $side $exitFrame.Name)
        }
        # VS-3 SC-01 (ВР-SC14, -ScreenShots): the UI-SCR-<id>-<state>.png frames of the client; published when written
        if ($ScreenShots) {
          foreach ($scrFrame in @(Get-ChildItem -LiteralPath (Join-Path $Script:Staging $side) -Filter 'UI-SCR-*.png' -ErrorAction SilentlyContinue | Sort-Object Name)) {
            $publishNames += (Join-Path $side $scrFrame.Name)
          }
        }
      }
    }
    if ($RequireShotCaptured) {
      foreach ($name in $publishNames) {
        if ($name -notlike '*.png') { continue }
        $who = ($name -split '[\\/]')[0]
        $tracePath = if ($who -eq 'host') { $hostTrace } else { $joinTrace }
        Assert-ShotCaptured $tracePath (Split-Path -Leaf $name) $who
      }
    }
    $RunDir = Join-Path $EvidenceDir ("combat-" + $Stamp)
    if (Test-Path -LiteralPath $RunDir) { throw "run dir already exists: $RunDir" }
    New-Item -ItemType Directory -Path $RunDir | Out-Null
    foreach ($name in $publishNames) {
      $src = Join-Path $Script:Staging $name
      if (-not (Test-Path -LiteralPath $src)) { throw "staged artifact missing at publish time: $src" }
      $dst = Join-Path $RunDir $name
      $dstDir = Split-Path -Parent $dst
      if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
      if ($name -like '*.trace.log') {
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
    $manifest = [ordered]@{
      stamp   = $Stamp
      verdict = if (-not $S09Markers) { "VS-4 HB-48 SHOT widget gates$(if ($PlayerView) { ' (player view frames)' }): live attack->defense->resolve two-client demo WITHOUT -S09Markers at exact ${ShotWidth}x${ShotHeight} - defense window / pre-reveal resolve window / result on the combat edges and centre / reveal by their SHOT widget lines with swap controls, privacy rules over both traces, ARTLOOK markers=0 and no marker hue, role-gated traces, seq convergence; artPreview=$([bool]$ArtPreview); clientFpsCap=$ClientFps" } elseif ($PlayerView) { "VS-1 HB-02 player view: live attack->defense->resolve two-client demo WITHOUT -S09Markers at exact ${ShotWidth}x${ShotHeight} - ARTLOOK markers=0, no combat marker hue in the state shots, privacy-clean, role-gated traces, seq convergence (the GD-034 marker gates need -S09Markers); artPreview=$([bool]$ArtPreview); clientFpsCap=$ClientFps" } else { "GD-034 P1: live attack->defense->resolve two-client demo, defense/resolve/result state-marker shots at exact ${ShotWidth}x${ShotHeight} with swap/negative controls, role-gated traces, privacy-clean logs, seq convergence; artPreview=$([bool]$ArtPreview); clientFpsCap=$ClientFps" }
      playerView = [bool]$PlayerView
      gateMode = if ($S09Markers) { 'markers' } else { 'shot-widget' }
      shotGate = @($ShotGateLines)
      artBoard = if ($ArtBoard) { [ordered]@{ boardId = $ArtPreviewBoardId; profile = $ArtBoard.id; size = $ArtBoardSize; light = $ArtBoard.light; artFixture = [bool]$ArtBoard.artFixture } } else { $null }
      artPreviewFlags = [ordered]@{ medusaVariant = $(if ($MedusaVariantExplicit) { $ArtPreviewMedusaVariant } else { '(default)' }); selectOwnHero = [bool]$ArtPreviewSelectOwnHero; focusZoom = $ArtPreviewFocusZoom; shotAfter = $ArtPreviewShotAfter; heroesV2 = [bool]$ArtPreviewHeroesV2; diorama = [bool]$ArtPreviewDiorama }
      heroesV2Anim = $HeroesV2Anim
      render = [ordered]@{ clientRenderPreset = $ClientRenderPreset; requireRenderReference = [bool]$RequireRenderReference; clientPerf = [bool]$ClientPerf }
      revealProof = $RevealProof
      gameOver = $GameOver
      joinerAttack = $JoinerAttackStats
      files   = @()
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

    $ptrTmp = Join-Path $EvidenceDir ("latest-combat.json.$Stamp-$PID.tmp")
    $ptr = Join-Path $EvidenceDir 'latest-combat.json'
    [System.IO.File]::WriteAllText($ptrTmp, (([ordered]@{ current = (Split-Path $RunDir -Leaf); stamp = $Stamp }) | ConvertTo-Json), $Utf8NoBom)
    if (Test-Path -LiteralPath $ptr) {
      $ptrBak = Join-Path $EvidenceDir 'latest-combat.json.bak'
      [System.IO.File]::Replace($ptrTmp, $ptr, $ptrBak)
      Remove-Item -LiteralPath $ptrBak -Force
    } else {
      [System.IO.File]::Move($ptrTmp, $ptr)
    }
    $Published = $true
    Write-Output "published evidence run dir: $RunDir (pointer: latest-combat.json)"
    Write-Output "--- host trace (combat tail) ---"
    Get-Content -LiteralPath (Join-Path $RunDir 'combat-client-host.trace.log') |
      Select-String -Pattern 'S09AUTO|ATTACK|COMBAT|SCHEME|RESOLVE' | Select-Object -Last 20
    Write-Output "--- joiner trace (combat tail) ---"
    Get-Content -LiteralPath (Join-Path $RunDir 'combat-client-joiner.trace.log') |
      Select-String -Pattern 'S09AUTO|DEFENSE|COMBAT|RESOLVE' | Select-Object -Last 20
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

Invoke-CombatDemo

if ($Script:CleanupFailure) {
  throw "scoped cleanup did not verify ABORTED for this run's game: $($Script:CleanupFailure)"
}
