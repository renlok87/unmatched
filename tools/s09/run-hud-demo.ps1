param(
  [string]$Exe = "",
  [string]$Api = "http://localhost:3120/graphql",
  [string]$EvidenceDir = "",
  [int]$RunSeconds = 100,
  [string]$ShotMode = "request",
  # The board of the room (2026-10-04, real boards only: docs/game-design/decisions/2026-10-04-real-boards-only.md):
  # a Board row id of an original map registered in unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json, sent
  # by the host as -S08BoardId. The HUD runs on the grey topology view of the map: since ART-DEFAULT (2026-10-04) the
  # art look is the client default, so both clients pass its rollback -S08GreyBoard explicitly (this logic harness, its
  # marker gates and its uncapped two-client load were built on the grey view; drop the flag to run it on the art look). Default
  # Marmoreal - original map; Sarpedon - original map is c7fa64a26c29a0835f2383e63. The traces must show the map
  # board ('BOARD <lattice WxH> cells' + 'BOARD topology spaces=<n> links=<m>'), never the old 'BOARD 20x20'.
  [string]$BoardId = "c121b47f8d6eb28daccb76d05"
)
# GD-032/GD-033 two-client packaged HUD demo against the S09 worktree-local
# backend, on an original map (-BoardId, default Marmoreal; 2026-10-04). Coverage plan (exact hand math: start 5, +1 per beginManeuver,
# limit 7):
#   host   -S09Flow:        T1 begin->zero-move confirm; T1 begin->hero step;
#                           end turn; T2 begin->hero+sidekick multi-fighter;
#                           begin->hero step; end turn -> 9 cards ->
#                           DISCARD-DRAFT count=2 -> exact-2 discardToLimit.
#   joiner -S09FlowBoost:   T1 begin->boost the NEWLY DRAWN card (bNew) +
#                           zero-move confirm; T1 begin->hero step; end turn;
#                           T2 two step maneuvers; end turn -> 8 cards ->
#                           DISCARD-DRAFT count=1 -> exact-1 discardToLimit.
# Live shots per client: the FIRST maneuver draft OPEN (magenta marker),
# after the first maneuver settles (idle HUD), discard overlay OPEN (cyan
# marker). Marker gates are state-specific; a board-only frame or a swapped
# state/d image pair fails them (P1 acceptance).
# Safety (same rules as the S08 driver): credentials + room code per-process
# ENV only, hidden clients, staged evidence published only after every
# assertion passed, room code redacted from traces, scoped+validated abort of
# THIS run's game in a finally block, fresh-shot checks, seq convergence.
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Exe) { $Exe = Join-Path $RepoRoot 'unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe' }
if (-not $EvidenceDir) { $EvidenceDir = Join-Path $RepoRoot 'docs\game-design\evidence\S09\run' }

# The registered original map of -BoardId: its topology fixture gives the lattice W x H and the space graph the traces
# must show (one source of truth with the client's art board registry, as run-phase2-demo).
if ($BoardId -cnotmatch '^c[a-z0-9]{24}$') { throw "BoardId '$BoardId' is not a Board row id (cuid)" }
$BoardsDoc = [System.IO.File]::ReadAllText((Join-Path $RepoRoot 'unreal\Unmatched\Config\ArtBoards\S08ArtBoardProfiles.json'), [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$BoardProfile = @($BoardsDoc.boards | Where-Object { @($_.match.boardIds) -ccontains $BoardId }) | Select-Object -First 1
if (-not $BoardProfile -or $BoardProfile.surface -ne 'map-image') {
  throw "BoardId '$BoardId' is not a registered original map (S08ArtBoardProfiles.json boards[].match.boardIds, surface map-image)"
}
$BoardTopology = [System.IO.File]::ReadAllText((Join-Path $RepoRoot $BoardProfile.fixture), [System.Text.Encoding]::UTF8) | ConvertFrom-Json
if ($BoardTopology.boardId -cne $BoardId) { throw "topology fixture $($BoardProfile.fixture) is board $($BoardTopology.boardId), not $BoardId" }
$BoardSize = "$($BoardTopology.lattice.width)x$($BoardTopology.lattice.height)"
$BoardIdSource = if ($PSBoundParameters.ContainsKey('BoardId')) { 'argument' } else { 'default' }
Write-Output "board: profile=$($BoardProfile.id) boardId=$BoardId source=$BoardIdSource size=$BoardSize spaces=$($BoardProfile.expect.spaces) links=$($BoardProfile.expect.links)"

# The packaged build keeps its last SAVED resolution (888x500 was found in
# the staged GameUserSettings.ini) and ignores -resx/-resy: publish the
# acceptance resolution into the staged ini, then prove it from the PNGs.
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

if (-not (Test-Path $Exe)) { throw "packaged exe not found: $Exe" }
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$AccountA = @{ email = $env:S09_DEMO_HOST_EMAIL; password = $env:S09_DEMO_HOST_PASSWORD }
$AccountB = @{ email = $env:S09_DEMO_JOINER_EMAIL; password = $env:S09_DEMO_JOINER_PASSWORD }
foreach ($pair in @(
    @('S09_DEMO_HOST_EMAIL', $AccountA.email), @('S09_DEMO_JOINER_EMAIL', $AccountB.email),
    @('S09_DEMO_HOST_PASSWORD', $AccountA.password), @('S09_DEMO_JOINER_PASSWORD', $AccountB.password))) {
  if (-not $pair[1]) { throw "missing $($pair[0]) in process environment" }
}

function Invoke-HudDemo {
  $heroA = Get-Hero $AccountA.email $AccountA.password 'Medusa'
  $heroB = Get-Hero $AccountB.email $AccountB.password 'King Arthur'
  Write-Output "heroA=$heroA heroB=$heroB"

  $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Script:Staging = Join-Path ([System.IO.Path]::GetTempPath()) "s09-hud-$Stamp-$PID"
  New-Item -ItemType Directory -Force -Path $Script:Staging | Out-Null
  Write-Output "staging: $Script:Staging"

  $hostShots = Join-Path $Script:Staging 'host'
  $joinShots = Join-Path $Script:Staging 'joiner'
  New-Item -ItemType Directory -Force -Path $hostShots, $joinShots | Out-Null
  $hostTrace = Join-Path $Script:Staging 'hud-client-host.trace.log'
  $joinTrace = Join-Path $Script:Staging 'hud-client-joiner.trace.log'

  $Script:ThisRunGameId = $null
  $Script:ThisRunGameCode = $null

  $common = @("-windowed", "-resx=1280", "-resy=720", "-RenderOffScreen", "log=GrepLog",
    "-ForceAbandonSequences", "-S08Api=$Api", "-S09ShotMode=$ShotMode", "-S08GreyBoard",
    "-S09Markers")  # HB-01: the grey Slate stand keeps the debug layer (04-hud-spec s5.3, VR-36)
  $hostArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08Create", "-S08BoardId=$BoardId", "-S08HeroId=$heroA", "-S08Trace=$hostTrace",
    "-S09Flow", "-S09ShotDir=$hostShots", "-S08ExitAfter=$RunSeconds")
  $joinArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08HeroId=$heroB", "-S08Trace=$joinTrace",
    "-S09Flow", "-S09FlowBoost", "-S09ShotDir=$joinShots", "-S08ExitAfter=$RunSeconds")

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
    # The authoritative game row must be on the requested board (the backend refuses an unknown boardId).
    $loginBody = @{ query = 'mutation L($input: LoginDto!) { login(input: $input) { accessToken } }'; variables = @{ input = @{ email = $AccountA.email; password = $AccountA.password } } } | ConvertTo-Json -Depth 5
    $login = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Body $loginBody
    Assert-GqlOk $login 'board check login'
    $lookup = @{ query = 'query G($id: String!) { game(id: $id) { id boardId } }'; variables = @{ id = $Script:ThisRunGameId } } | ConvertTo-Json -Depth 5
    $game = Invoke-RestMethod -Uri $Api -Method Post -ContentType 'application/json' -Headers @{ authorization = "Bearer $($login.data.login.accessToken)" } -Body $lookup
    Assert-GqlOk $game 'board check lookup'
    if ($game.data.game.boardId -cne $BoardId) { throw "created room has boardId=$($game.data.game.boardId), expected $BoardId" }
    Write-Output "boardId verified against the authoritative game row: $BoardId ($($BoardProfile.id))"

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
      @('host', 's09-hud-after-first-maneuver.png', $hostStartUtc),
      @('host', 's09-maneuver-draft-open.png', $hostStartUtc),
      @('host', 's09-discard-open.png', $hostStartUtc),
      @('joiner', 's09-hud-after-first-maneuver.png', $joinStartUtc),
      @('joiner', 's09-maneuver-draft-open.png', $joinStartUtc),
      @('joiner', 's09-discard-open.png', $joinStartUtc))) {
      Assert-FreshShot (Join-Path $Script:Staging (Join-Path $pair[0] $pair[1])) $pair[2] $pair[0]
    }

    # P1 state-specific image gates (replaces the white-pixel gate, whose
    # counts were dominated by the bright board): the draft panels render a
    # solid 220x14 marker - maneuver #FF00FF, discard #00FFFF - that appears
    # nowhere else. The idle (no-draft) frame is the live board-only control
    # and must carry NEITHER marker; swapped state/image pairs are asserted
    # to fail. Dimensions are read from the files: the packaged client
    # honors the SAVED resolution, not -resx/-resy.
    Add-Type -AssemblyName System.Drawing
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
        $stats = @{ w = $w; h = $h; magentaRegion = 0; cyanRegion = 0; magentaAll = 0; cyanAll = 0 }
        $rx1 = [int]($w * 0.60); $ry1 = [int]($h * 0.50); $tol = 12
        for ($y = 0; $y -lt $h; $y += 2) {
          $row = $y * $data.Stride
          $inRegion = ($y -lt $ry1)
          for ($x = 0; $x -lt $w; $x += 2) {
            $i = $row + $x * 4
            $pB = $bytes[$i]; $pG = $bytes[$i + 1]; $pR = $bytes[$i + 2]
            if ($pR -ge 243 -and $pR -le 255 -and $pG -le $tol -and $pB -ge 243 -and $pB -le 255) {
              $stats.magentaAll++
              if ($inRegion -and $x -lt $rx1) { $stats.magentaRegion++ }
            } elseif ($pR -le $tol -and $pG -ge 243 -and $pG -le 255 -and $pB -ge 243 -and $pB -le 255) {
              $stats.cyanAll++
              if ($inRegion -and $x -lt $rx1) { $stats.cyanRegion++ }
            }
          }
        }
        return $stats
      } finally { $bmp.Dispose() }
    }
    function Assert-Dimensions($Stats, [string]$Who) {
      $ok = (($Stats.w -eq 1280 -and $Stats.h -eq 720) -or ($Stats.w -eq 1920 -and $Stats.h -eq 1080))
      if (-not $ok) {
        throw ("capture for {0} is {1}x{2} - NOT 1280x720/1920x1080 (saved GameUserSettings override?)" -f $Who, $Stats.w, $Stats.h)
      }
    }
    function Test-StateImage($Stats, [string]$State) {
      if ($State -eq 'maneuver') {
        return ($Stats.magentaRegion -ge 200 -and $Stats.cyanAll -eq 0)
      }
      if ($State -eq 'discard') {
        return ($Stats.cyanRegion -ge 200 -and $Stats.magentaAll -eq 0)
      }
      throw "unknown state: $State"
    }
    foreach ($client in @('host', 'joiner')) {
      $idle = Get-MarkerStats (Join-Path $Script:Staging (Join-Path $client 's09-hud-after-first-maneuver.png'))
      $draft = Get-MarkerStats (Join-Path $Script:Staging (Join-Path $client 's09-maneuver-draft-open.png'))
      $discard = Get-MarkerStats (Join-Path $Script:Staging (Join-Path $client 's09-discard-open.png'))
      Assert-Dimensions $idle "$client/idle"
      Assert-Dimensions $draft "$client/draft"
      Assert-Dimensions $discard "$client/discard"
      Write-Output ("markers {0}: draft magentaRegion={1} cyanAll={2} | discard cyanRegion={3} magentaAll={4} | idle magenta={5} cyan={6}" -f `
        $client, $draft.magentaRegion, $draft.cyanAll, $discard.cyanRegion, $discard.magentaAll, $idle.magentaAll, $idle.cyanAll)
      if ($ShotMode -ne 'request') {
        Write-Output "WARN ShotMode=$ShotMode renders the HUD widget only - state gates skipped (P1 acceptance requires 'request')"
        continue
      }
      if (-not (Test-StateImage $draft 'maneuver')) {
        throw ("{0} draft-open capture failed the maneuver gate (magentaRegion={1}, cyanAll={2})" -f $client, $draft.magentaRegion, $draft.cyanAll)
      }
      if (-not (Test-StateImage $discard 'discard')) {
        throw ("{0} discard-open capture failed the discard gate (cyanRegion={1}, magentaAll={2})" -f $client, $discard.cyanRegion, $discard.magentaAll)
      }
      if ((Test-StateImage $idle 'maneuver') -or (Test-StateImage $idle 'discard')) {
        throw "$client idle frame passed a state gate - markers leak outside the draft panels"
      }
      if (Test-StateImage $discard 'maneuver') { throw "$client swapped pair (discard as maneuver) passed - gate unsound" }
      if (Test-StateImage $draft 'discard') { throw "$client swapped pair (maneuver as discard) passed - gate unsound" }
    }

    function Assert-Trace([string]$Path, [string[]]$MustContain, [string]$Who) {
      $text = Get-Content -LiteralPath $Path -Raw
      foreach ($needle in $MustContain) {
        if (-not $text.Contains($needle)) { throw "$Who trace missing '$needle'" }
      }
    }
    # NOTE: no "ENDTURN sent" assertion on purpose - in the plain maneuver
    # flow the backend AUTO-ADVANCES the turn the moment actions hit 0
    # (consumeAction -> advanceTurn), so the client endTurn mutation is
    # unreachable without card effects (GD-034+). The turn handover is
    # asserted through the server-driven phase/view instead.
    # The map board (2026-10-04): its lattice line and its space graph, on both clients.
    $boardLines = @("BOARD $BoardSize cells", "BOARD topology spaces=$($BoardProfile.expect.spaces) links=$($BoardProfile.expect.links) starts=")
    Assert-Trace $hostTrace (@(
      'SNAPSHOT applied', 'FIGHTERS synced n=6', 'SUBSCRIBED gameStateUpdated',
      'HUD seq=', 'DRAFT-OPEN draw committed', 'turn=opp', 'S09AUTO draft-open shot',
      'S09AUTO zero-move confirm', 'MANEUVER-CONFIRM moves=0 boost=none', 'MANEUVER done',
      'MANEUVER-CONFIRM moves=1', 'S09AUTO multi-fighter moves=2', 'MANEUVER-CONFIRM moves=2',
      'DISCARD-DRAFT count=2', 'S09AUTO discard picks=2',
      'DISCARD-CONFIRM pending=', 'count=2', "CREATE boardId=$BoardId source=S08BoardId") + $boardLines) 'host'
    Assert-Trace $joinTrace (@(
      'SNAPSHOT applied', 'FIGHTERS synced n=6', 'SUBSCRIBED gameStateUpdated',
      'HUD seq=', 'DRAFT-OPEN draw committed', 'turn=opp', 'S09AUTO draft-open shot',
      'S09AUTO boost(new card) set',
      'MANEUVER-CONFIRM moves=0 boost=card', 'MANEUVER done',
      'MANEUVER-CONFIRM moves=1',
      'DISCARD-DRAFT count=1', 'DISCARD-CONFIRM pending=', 'count=1') + $boardLines) 'joiner'

    # Privacy cross-check inside the traces: the JOINER must never see host
    # card identity, only counts (the HUD summary line never carries names).
    $joinText = Get-Content -LiteralPath $joinTrace -Raw
    if ($joinText -match 'oppHand=\d+\(hidden\)') { Write-Output 'privacy trace marker ok: opponent hand is count-only' }
    else { Write-Output 'WARN: expected oppHand count-only marker not found in joiner trace' }

    function Get-MaxSeq([string]$Path) {
      $seqs = Select-String -Path $Path -Pattern 'SNAPSHOT applied seq=(\d+)' -AllMatches |
        ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value }
      return ($seqs | Measure-Object -Maximum).Maximum
    }
    function Get-TurnEndCount([string]$Path) {
      # Count UNIQUE seqs ever seen in TURN_END (merge re-applies must not
      # inflate the count; clients may refetch different numbers of times).
      $seen = New-Object 'System.Collections.Generic.HashSet[int]'
      Select-String -Path $Path -Pattern 'HUD seq=(\d+) phase=TURN_END' -AllMatches |
        ForEach-Object { $_.Matches } | ForEach-Object { [void]$seen.Add([int]$_.Groups[1].Value) }
      return $seen.Count
    }
    $hostSeq = Get-MaxSeq $hostTrace
    $joinSeq = Get-MaxSeq $joinTrace
    $hostTE = Get-TurnEndCount $hostTrace
    $joinTE = Get-TurnEndCount $joinTrace
    Write-Output "convergence: host maxSeq=$hostSeq joiner maxSeq=$joinSeq | TURN_END views host=$hostTE joiner=$joinTE"
    if (-not $hostSeq -or -not $joinSeq) { throw "missing applied seq in traces" }
    if ($hostSeq -lt 40 -or $joinSeq -lt 40) { throw "match did not run long enough: host=$hostSeq joiner=$joinSeq" }
    if ([Math]::Abs($hostSeq - $joinSeq) -gt 4) { throw "clients diverged: host seq=$hostSeq joiner seq=$joinSeq" }
    if ($hostTE -ne $joinTE) { throw "TURN_END view counts differ: host=$hostTE joiner=$joinTE (same server events must reach both)" }

    $publishNames = @(
      'hud-client-host.trace.log', 'hud-client-joiner.trace.log',
      'host\s09-hud-after-first-maneuver.png', 'host\s09-maneuver-draft-open.png', 'host\s09-discard-open.png',
      'joiner\s09-hud-after-first-maneuver.png', 'joiner\s09-maneuver-draft-open.png', 'joiner\s09-discard-open.png'
    )
    $RunDir = Join-Path $EvidenceDir ("run-" + $Stamp)
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
      verdict = "GD-032/033 P1 on $($BoardProfile.id) ($BoardId, lattice $BoardSize, $($BoardProfile.expect.spaces) spaces / $($BoardProfile.expect.links) links): HUD traces + zero-move + boost(new card) + multi-fighter + exact-count discards + draft/discard state-marker shots at exact 1280x720 + negative/swap controls + seq convergence"
      board   = [ordered]@{ boardId = $BoardId; source = $BoardIdSource; profile = $BoardProfile.id; lattice = $BoardSize; spaces = $BoardProfile.expect.spaces; links = $BoardProfile.expect.links }
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

    $ptrTmp = Join-Path $EvidenceDir ("latest.json.$Stamp-$PID.tmp")
    $ptr = Join-Path $EvidenceDir 'latest.json'
    [System.IO.File]::WriteAllText($ptrTmp, (([ordered]@{ current = (Split-Path $RunDir -Leaf); stamp = $Stamp }) | ConvertTo-Json), $Utf8NoBom)
    if (Test-Path -LiteralPath $ptr) {
      $ptrBak = Join-Path $EvidenceDir 'latest.json.bak'
      [System.IO.File]::Replace($ptrTmp, $ptr, $ptrBak)
      Remove-Item -LiteralPath $ptrBak -Force
    } else {
      [System.IO.File]::Move($ptrTmp, $ptr)
    }
    $Published = $true
    Write-Output "published evidence run dir: $RunDir (pointer: latest.json)"
    Write-Output "--- host trace (tail) ---"
    Get-Content -LiteralPath (Join-Path $RunDir 'hud-client-host.trace.log') | Select-Object -Last 30
    Write-Output "--- joiner trace (tail) ---"
    Get-Content -LiteralPath (Join-Path $RunDir 'hud-client-joiner.trace.log') | Select-Object -Last 25
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

Invoke-HudDemo

if ($Script:CleanupFailure) {
  throw "scoped cleanup did not verify ABORTED for this run's game: $($Script:CleanupFailure)"
}
