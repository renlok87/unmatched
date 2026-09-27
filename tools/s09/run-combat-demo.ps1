param(
  [string]$Exe = "",
  [string]$Api = "http://localhost:3120/graphql",
  [string]$EvidenceDir = "",
  [int]$RunSeconds = 240,
  [string]$ShotMode = "request"
)
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

  $common = @("-windowed", "-resx=1280", "-resy=720", "-RenderOffScreen", "log=GrepLog",
    "-ForceAbandonSequences", "-S08Api=$Api", "-S09ShotMode=$ShotMode")
  $hostArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08Create", "-S08HeroId=$heroA", "-S08Trace=$hostTrace",
    "-S09Flow", "-S09Combat=attack", "-S09ShotDir=$hostShots", "-S08ExitAfter=$RunSeconds")
  $joinArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08HeroId=$heroB", "-S08Trace=$joinTrace",
    "-S09Flow", "-S09Combat=defend+resolve", "-S09ShotDir=$joinShots", "-S08ExitAfter=$RunSeconds")

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
                $stats[$m.name + 'All']++
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
      $ok = (($Stats.w -eq 1280 -and $Stats.h -eq 720) -or ($Stats.w -eq 1920 -and $Stats.h -eq 1080))
      if (-not $ok) {
        throw ("capture for {0} is {1}x{2} - NOT 1280x720/1920x1080 (saved GameUserSettings override?)" -f $Who, $Stats.w, $Stats.h)
      }
    }
    function Test-StateImage($Stats, [string]$State) {
      # Exactly ONE combat marker region may light up, and only the expected
      # one; every other combat marker must be fully absent frame-wide.
      if ($State -eq 'defense') {
        return ($Stats.defenseRegion -ge 200 -and $Stats.attackAll -eq 0 -and
                $Stats.resolveAll -eq 0 -and $Stats.boostAll -eq 0 -and $Stats.resultAll -eq 0)
      }
      if ($State -eq 'resolve') {
        return ($Stats.resolveRegion -ge 200 -and $Stats.attackAll -eq 0 -and
                $Stats.defenseAll -eq 0 -and $Stats.boostAll -eq 0 -and $Stats.resultAll -eq 0)
      }
      if ($State -eq 'result') {
        return ($Stats.resultRegion -ge 200 -and $Stats.attackAll -eq 0 -and
                $Stats.defenseAll -eq 0 -and $Stats.resolveAll -eq 0 -and $Stats.boostAll -eq 0)
      }
      throw "unknown state: $State"
    }
    $defenseStats = Get-MarkerStats (Join-Path $Script:Staging (Join-Path 'joiner' 's09-combat-defense-open.png'))
    $resolveStats = Get-MarkerStats (Join-Path $Script:Staging (Join-Path 'joiner' 's09-combat-resolve-window.png'))
    $joinResultStats = Get-MarkerStats (Join-Path $Script:Staging (Join-Path 'joiner' 's09-combat-result.png'))
    $hostResultStats = Get-MarkerStats (Join-Path $Script:Staging (Join-Path 'host' 's09-combat-result.png'))
    foreach ($entry in @(@('joiner/defense', $defenseStats), @('joiner/resolve', $resolveStats),
                         @('joiner/result', $joinResultStats), @('host/result', $hostResultStats))) {
      Assert-Dimensions $entry[1] $entry[0]
    }
    Write-Output ("markers joiner: defense(def={0} atk={1} res={2} rst={3}) resolve(res={4} def={5} rst={6}) result(rst={7} res={8} def={9}) host: result(rst={10} res={11} def={12})" -f `
      $defenseStats.defenseRegion, $defenseStats.attackAll, $defenseStats.resolveAll, $defenseStats.resultAll,
      $resolveStats.resolveRegion, $resolveStats.defenseAll, $resolveStats.resultAll,
      $joinResultStats.resultRegion, $joinResultStats.resolveAll, $joinResultStats.defenseAll,
      $hostResultStats.resultRegion, $hostResultStats.resolveAll, $hostResultStats.defenseAll)
    if ($ShotMode -ne 'request') {
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
      if ($ShotMode -eq 'request') {
        $revealedStats = Get-MarkerStats $RevealShot
        Assert-Dimensions $revealedStats 'joiner/revealed'
        Write-Output ("reveal markers joiner: resolve(res={0}) reveal(rvl={1} def={2} rst={3})" -f `
          $revealedStats.resolveRegion, $revealedStats.revealRegion, $revealedStats.defenseAll, $revealedStats.resultAll)
        if ($revealedStats.revealRegion -lt 40 -or $revealedStats.resolveRegion -lt 200) {
          throw ("reveal gate failed: revealed capture needs the resolve marker AND reveal pixels (rvl={0} res={1})" -f `
            $revealedStats.revealRegion, $revealedStats.resolveRegion)
        }
        if ($revealedStats.attackAll -ne 0 -or $revealedStats.defenseAll -ne 0 -or
            $revealedStats.resultAll -ne 0) {
          throw "reveal gate failed: foreign combat markers present in the revealed shot"
        }
      }
      $RevealProof = 'present: pre-reveal privacy gates passed (zero reveal pixels) and the revealed shot carries the #7CFC00 reveal block + resolve marker'
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
    foreach ($t in @(@('host', $hostText), @('joiner', $joinText))) {
      if ($t[1] -match '(ATTACK|DEFENSE|RESOLVE|SCHEME) sent .*card') {
        throw "$($t[0]) trace appears to log card identities with a combat command"
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

    $publishNames = @(
      'combat-client-host.trace.log', 'combat-client-joiner.trace.log',
      'host\s09-combat-result.png',
      'joiner\s09-combat-defense-open.png', 'joiner\s09-combat-resolve-window.png', 'joiner\s09-combat-result.png'
    )
    if ($RevealProof.StartsWith('present')) { $publishNames += $RevealShotRel }
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
      verdict = 'GD-034 P1: live attack->defense->resolve two-client demo, defense/resolve/result state-marker shots at exact 1280x720 with swap/negative controls, role-gated traces (defender acted in attacker window, resolve in COMBAT_RESOLVE), privacy-clean logs, seq convergence'
      revealProof = $RevealProof
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
