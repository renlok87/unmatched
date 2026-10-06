param(
  [string]$Exe = "",
  [string]$Api = "http://localhost:3120/graphql",
  [string]$EvidenceDir = "",
  [int]$RunSeconds = 300,
  [string]$ShotMode = "request",
  [string]$EnvFile = ""
)
# GD-035 two-client packaged PENDING-CHOICE demo against the S09 worktree-local
# backend. Both clients also play scheme cards, so viewer-owned queue heads
# open over the real server and the S09AUTO driver answers them through the
# authoritative resolvePendingEffect/declinePendingEffect mutations:
#   host   -S09Flow -S09Combat=attack+scheme : approach, attack, then schemes.
#   joiner -S09Flow -S09Combat=defend+resolve+scheme : defense, resolve, schemes.
# The FIRST queue head gets a live UI shot (s09-pending-<TYPE>.png, blue
# #4080FF marker) held until the file exists, then the auto-answer fires.
# GATES:
#   - at least one pending head opened and was answered OR a mandatory head
#     with no legal pick was observed (the live CHOOSE_SPACE zone-data gap -
#     reported as gapObserved, never hidden and never client-side faked);
#   - pending shot: exactly the pending marker region, no other state marker;
#   - traces: PEND-RESOLVE sent / PEND resolve done seq= (or the gap wait),
#     privacy-clean (no card ids with combat commands), seq convergence.
# Safety: per-process ENV credentials only, hidden clients, staged evidence
# published only after every assertion passed, room code redacted, scoped
# host-ownership-validated abort of THIS run's game, fresh-shot checks.
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

function Invoke-PendingDemo {
  $heroA = Get-Hero $AccountA.email $AccountA.password 'Medusa'
  $heroB = Get-Hero $AccountB.email $AccountB.password 'King Arthur'
  Write-Output "heroA=$heroA heroB=$heroB"

  $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Script:Staging = Join-Path ([System.IO.Path]::GetTempPath()) "s09-pending-$Stamp-$PID"
  New-Item -ItemType Directory -Force -Path $Script:Staging | Out-Null
  Write-Output "staging: $Script:Staging"

  $hostShots = Join-Path $Script:Staging 'host'
  $joinShots = Join-Path $Script:Staging 'joiner'
  New-Item -ItemType Directory -Force -Path $hostShots, $joinShots | Out-Null
  $hostTrace = Join-Path $Script:Staging 'pending-client-host.trace.log'
  $joinTrace = Join-Path $Script:Staging 'pending-client-joiner.trace.log'

  $Script:ThisRunGameId = $null
  $Script:ThisRunGameCode = $null

  $common = @("-windowed", "-resx=1280", "-resy=720", "-RenderOffScreen", "log=GrepLog",
    "-ForceAbandonSequences", "-S08Api=$Api", "-S09ShotMode=$ShotMode",
    "-S09Markers")  # HB-01: the marker pixel gates below need the debug layer (04-hud-spec s5.3)
  $hostArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08Create", "-S08HeroId=$heroA", "-S08Trace=$hostTrace",
    "-S09Flow", "-S09Combat=attack+scheme", "-S09ShotDir=$hostShots", "-S08ExitAfter=$RunSeconds")
  $joinArgs = @("/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode") + $common + @(
    "-S08Auto", "-S08HeroId=$heroB", "-S08Trace=$joinTrace",
    "-S09Flow", "-S09Combat=defend+resolve+scheme", "-S09ShotDir=$joinShots", "-S08ExitAfter=$RunSeconds")

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

    # ---- coverage report from both traces (authoritative evidence) ----
    $hostText = Get-Content -LiteralPath $hostTrace -Raw
    $joinText = Get-Content -LiteralPath $joinTrace -Raw
    $both = $hostText + "`n" + $joinText
    # Trace lines carry `(type=X id=...)` / `(type=X stage=N)`: match the type
    # group and ignore the rest of the parenthesized payload.
    $pickedTypes = @([regex]::Matches($both, 'S09AUTO pending picked \(type=([A-Z_]+)[^)]*\)') |
      ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
    $declinedTypes = @([regex]::Matches($both, 'S09AUTO pending declined \(type=([A-Z_]+)[^)]*\)') |
      ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
    $openTypes = @()
    foreach ($pat in @(
        'S09AUTO mandatory pending without a legal pick \(type=([A-Z_]+)[^)]*\)',
        'S09AUTO pending head \S+ stayed open after \d+ auto-answers \(type=([A-Z_]+)[^)]*\)')) {
      $openTypes += @([regex]::Matches($both, $pat) | ForEach-Object { $_.Groups[1].Value })
    }
    $openTypes = @($openTypes | Sort-Object -Unique)
    Write-Output ("pending coverage: picked=[{0}] declined=[{1}] open/stuck=[{2}]" -f `
      ($pickedTypes -join ','), ($declinedTypes -join ','), ($openTypes -join ','))
    if ($pickedTypes.Count -eq 0 -and $declinedTypes.Count -eq 0 -and $openTypes.Count -eq 0) {
      throw "no pending head ever opened this run - run is not representative of GD-035"
    }

    # ---- pending UI shot gate (first queue head, whichever client owns it) ----
    $pendingShots = @(Get-ChildItem -LiteralPath $hostShots, $joinShots -Filter 's09-pending-*.png' -ErrorAction SilentlyContinue)
    if ($pendingShots.Count -eq 0) {
      throw "no s09-pending-*.png shot found in either client shot dir"
    }
    $pendingShot = $pendingShots[0]
    $pendingWho = if ($pendingShot.FullName.StartsWith($hostShots)) { 'host' } else { 'joiner' }
    $clientStartUtc = if ($pendingWho -eq 'host') { $hostStartUtc } else { $joinStartUtc }
    if ($pendingShot.Length -lt 10KB) {
      throw "suspiciously small pending shot (likely black/empty): $($pendingShot.FullName)"
    }
    if ($pendingShot.LastWriteTimeUtc -le $clientStartUtc) {
      throw "pending shot predates its client process (stale file): $($pendingShot.FullName)"
    }
    Write-Output "pending shot: $($pendingShot.Name) ($pendingWho, $($pendingShot.Length) bytes)"

    Add-Type -AssemblyName System.Drawing
    $Markers = @(
      @{ name = 'pending'; r = 64;  g = 128; b = 255 },
      @{ name = 'attack';  r = 255; g = 128; b = 0   },
      @{ name = 'defense'; r = 255; g = 64;  b = 64  },
      @{ name = 'resolve'; r = 64;  g = 255; b = 64  },
      @{ name = 'boost';   r = 255; g = 255; b = 64  },
      @{ name = 'result';  r = 64;  g = 255; b = 128 },
      @{ name = 'maneuver';r = 255; g = 0;   b = 255 },
      @{ name = 'discard'; r = 0;   g = 255; b = 255 },
      @{ name = 'revealline'; r = 128; g = 64; b = 255 },
      @{ name = 'blocked'; r = 255; g = 64; b = 176 },
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
    $pendingStats = Get-MarkerStats $pendingShot.FullName
    if (-not (($pendingStats.w -eq 1280 -and $pendingStats.h -eq 720) -or
              ($pendingStats.w -eq 1920 -and $pendingStats.h -eq 1080))) {
      throw ("pending shot is {0}x{1} - NOT 1280x720/1920x1080" -f $pendingStats.w, $pendingStats.h)
    }
    if ($ShotMode -eq 'request') {
      if ($pendingStats.pendingRegion -lt 200) {
        throw ("pending shot failed the pending-marker gate (pending={0})" -f $pendingStats.pendingRegion)
      }
      foreach ($other in @('attack', 'defense', 'resolve', 'boost', 'result', 'maneuver', 'discard')) {
        if ($pendingStats[$other + 'All'] -ne 0) {
          throw ("pending shot shows a foreign state marker: {0}={1}" -f $other, $pendingStats[$other + 'All'])
        }
      }
      Write-Output ("pending shot markers: pending={0} (foreign all-zero)" -f $pendingStats.pendingRegion)
      # ---- P3 reveal-pause + pre-reveal privacy pixel gates ----
      # BOOST_CHOICE opens post-reveal: its owner shot MUST show the already-
      # public committed combat (#8040FF). Every OTHER pending shot is a
      # pre-reveal head and must show NONE of the reveal artifacts (#7CFC00
      # text, #8040FF line, #FF40B0 blocked) - the flag-driven privacy gate.
      $boostShots = @($pendingShots | Where-Object { $_.Name -eq 's09-pending-BOOST_CHOICE.png' })
      if ($boostShots.Count -eq 0) {
        throw "no s09-pending-BOOST_CHOICE.png this run - cannot verify the owner reveal-pause panel"
      }
      $bs = Get-MarkerStats $boostShots[0].FullName
      if ($bs.reveallineAll -lt 10) {
        throw ("BOOST_CHOICE owner shot missing the revealed-combat line #8040FF (revealline={0})" -f $bs.reveallineAll)
      }
      Write-Output ("BOOST_CHOICE owner shot: revealed-combat line present (revealline={0})" -f $bs.reveallineAll)
      foreach ($shot in $pendingShots) {
        if ($shot.Name -eq 's09-pending-BOOST_CHOICE.png') { continue }
        $s = Get-MarkerStats $shot.FullName
        if ($s.revealtextAll -ne 0 -or $s.reveallineAll -ne 0 -or $s.blockedAll -ne 0) {
          throw ("pre-reveal privacy violation in {0}: revealtext={1} revealline={2} blocked={3}" -f $shot.Name, $s.revealtextAll, $s.reveallineAll, $s.blockedAll)
        }
      }
      Write-Output "pre-reveal privacy: non-BOOST_CHOICE pending shots show zero reveal/blocked markers"
      $blockedShots = @(Get-ChildItem -LiteralPath $hostShots, $joinShots -Filter 's09-resolve-blocked-*.png' -ErrorAction SilentlyContinue)
      foreach ($shot in $blockedShots) {
        $s = Get-MarkerStats $shot.FullName
        if ($s.blockedAll -lt 10) {
          throw ("blocked resolve shot missing #FF40B0 (blocked={0}): {1}" -f $s.blockedAll, $shot.Name)
        }
        if ($shot.Name -like '*BOOST_CHOICE*') {
          if ($s.revealtextAll -lt 10) {
            throw ("post-reveal blocked shot missing the revealed combat text #7CFC00 (revealtext={0}): {1}" -f $s.revealtextAll, $shot.Name)
          }
        } elseif ($s.revealtextAll -ne 0) {
          throw ("pre-reveal privacy violation in blocked shot {0}: revealtext={1}" -f $shot.Name, $s.revealtextAll)
        }
        Write-Output ("blocked resolve shot verified: {0} (blocked={1} revealtext={2})" -f $shot.Name, $s.blockedAll, $s.revealtextAll)
      }
    } else {
      Write-Output "WARN ShotMode=$ShotMode - pixel state gates skipped"
    }

    # ---- trace gates ----
    foreach ($t in @(@('host', $hostText), @('joiner', $joinText))) {
      foreach ($needle in @('SNAPSHOT applied', 'SUBSCRIBED gameStateUpdated', 'HUD seq=')) {
        if (-not $t[1].Contains($needle)) { throw "$($t[0]) trace missing '$needle'" }
      }
      if ($t[1] -match '(ATTACK|DEFENSE|RESOLVE|SCHEME|PEND) sent .*card') {
        throw "$($t[0]) trace appears to log card identities with a combat command"
      }
    }
    if (-not $both.Contains('S09AUTO pending-open shot (type=')) {
      throw "no client took a pending-open shot"
    }
    if ($pickedTypes.Count -gt 0) {
      if (-not $both.Contains('PEND-RESOLVE sent type=')) { throw "pending picked but no PEND-RESOLVE sent line" }
      if (-not $both.Contains('PEND resolve done seq=')) { throw "pending sent but no authoritative PEND resolve done line" }
    }
    if ($declinedTypes.Count -gt 0 -and -not $both.Contains('PEND-DECLINE sent type=')) {
      throw "pending declined but no PEND-DECLINE sent line"
    }

    # ---- resolved-head ledger: which (type, stage) actually CLOSED, at which seq ----
    # A published run may only claim "answered" for heads whose sent line is
    # followed by an authoritative `PEND resolve done seq=N`. An open head
    # (stuck / bounded-hold) must show up in the verdict instead.
    $resolvedHeads = @()
    foreach ($line in ($both -split "`n")) {
      if ($line -match 'PEND-RESOLVE sent type=([A-Z_]+) stage=(\d+) id=(\S+)') {
        $resolvedHeads += [pscustomobject]@{ type = $Matches[1]; stage = [int]$Matches[2]; id = $Matches[3]; seq = $null }
      } elseif ($line -match 'PEND resolve done seq=(\d+)') {
        for ($i = $resolvedHeads.Count - 1; $i -ge 0; $i--) {
          if ($null -eq $resolvedHeads[$i].seq) { $resolvedHeads[$i].seq = [int]$Matches[1]; break }
        }
      }
    }
    $resolvedHeads = @($resolvedHeads | Where-Object { $null -ne $_.seq })
    $unresolvedHeads = [int](@([regex]::Matches($both, 'PEND-RESOLVE sent type=')).Count) - $resolvedHeads.Count
    if ($unresolvedHeads -lt 0) { $unresolvedHeads = 0 }
    $csResolved = @($resolvedHeads | Where-Object { $_.type -eq 'CHOOSE_SPACE' })
    $csStage1 = @($csResolved | Where-Object { $_.stage -eq 1 })
    $csStage2 = @($csResolved | Where-Object { $_.stage -eq 2 })
    $csPairs = @()
    foreach ($s1 in $csStage1) {
      foreach ($s2 in $csStage2) {
        if ($s2.seq -eq ($s1.seq + 1)) { $csPairs += ("{0}->{1}" -f $s1.seq, $s2.seq); break }
      }
    }
    $otherResolvedTypes = @($resolvedHeads | Where-Object { $_.type -ne 'CHOOSE_SPACE' } |
      ForEach-Object { $_.type } | Sort-Object -Unique)
    Write-Output ("resolved heads: {0} (CHOOSE_SPACE stage1={1} stage2={2} pairs=[{3}]) unresolved-sent={4} other=[{5}]" -f `
      $resolvedHeads.Count, $csStage1.Count, $csStage2.Count, ($csPairs -join ','), $unresolvedHeads, ($otherResolvedTypes -join ','))
    # The published compact trace must contain a REAL two-stage CHOOSE_SPACE
    # resolve (stage1 seqN -> stage2 seqN+1) plus at least one other live
    # resolved pending type - otherwise the run is not the requested proof.
    if ($csPairs.Count -eq 0) {
      throw "no back-to-back CHOOSE_SPACE stage1->stage2 resolve this run (stage1=$($csStage1.Count) stage2=$($csStage2.Count)) - not the requested demo"
    }
    if ($otherResolvedTypes.Count -eq 0) {
      throw "no non-CHOOSE_SPACE pending type resolved this run - not the requested demo"
    }
    if ($unresolvedHeads -gt 0 -or $openTypes.Count -gt 0) {
      Write-Output "OPEN HEADS PRESENT: sent-without-done=$unresolvedHeads open/stuck types=[$($openTypes -join ',')]"
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

    # ---- compact traces (hash-verified evidence of the requested proof) ----
    $compactPattern = 'S09AUTO pending|PEND |PENDING panel revealed|RESOLVE panel|SNAPSHOT applied seq=|MODE seq='
    foreach ($pair in @(@('pending-client-host.trace.log', 'pending-client-host.compact.log'),
                        @('pending-client-joiner.trace.log', 'pending-client-joiner.compact.log'))) {
      $srcLines = Get-Content -LiteralPath (Join-Path $Script:Staging $pair[0])
      $kept = @($srcLines | Where-Object { $_ -match $compactPattern })
      if ($code) { $kept = @($kept | ForEach-Object { $_.Replace($code, '<redacted>') }) }
      [System.IO.File]::WriteAllLines((Join-Path $Script:Staging $pair[1]), $kept, $Utf8NoBom)
    }

    # ---- publish ----
    $publishNames = @(
      'pending-client-host.trace.log', 'pending-client-joiner.trace.log',
      'pending-client-host.compact.log', 'pending-client-joiner.compact.log'
    )
    $allPendingShots = @(Get-ChildItem -LiteralPath $hostShots, $joinShots -Filter 's09-pending-*.png' -ErrorAction SilentlyContinue |
      Sort-Object Name)
    foreach ($shot in $allPendingShots) {
      $who = if ($shot.FullName.StartsWith($hostShots)) { 'host' } else { 'joiner' }
      $publishNames += ($who + '\' + $shot.Name)
    }
    $allBlockedShots = @(Get-ChildItem -LiteralPath $hostShots, $joinShots -Filter 's09-resolve-blocked-*.png' -ErrorAction SilentlyContinue |
      Sort-Object Name)
    foreach ($shot in $allBlockedShots) {
      $who = if ($shot.FullName.StartsWith($hostShots)) { 'host' } else { 'joiner' }
      $publishNames += ($who + '\' + $shot.Name)
    }
    $RunDir = Join-Path $EvidenceDir ("pending-" + $Stamp)
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
    # Verdict is CONDITIONAL on what actually resolved: with any open head
    # (stuck mandatory / bounded-hold / sent-without-done) the run must NOT
    # claim that every observed head was answered.
    $verdict = if ($openTypes.Count -eq 0 -and $unresolvedHeads -eq 0) {
      'GD-035 P1: live two-client pending-choice demo - viewer-owned queue heads opened over the authoritative server and were answered via resolvePendingEffect/declinePendingEffect; first-head UI shot gated on the pending marker #4080FF with all other state markers absent; privacy-clean traces; seq convergence'
    } else {
      $openKinds = @()
      if ($openTypes.Count -gt 0) { $openKinds += ("open/stuck types: " + ($openTypes -join ',')) }
      if ($unresolvedHeads -gt 0) { $openKinds += ("$unresolvedHeads sent head(s) without an authoritative done") }
      'GD-035 P1 (PARTIAL - OPEN HEADS REPORTED): live two-client pending demo; some queue heads resolved via resolvePendingEffect/declinePendingEffect, but NOT every observed head was answered - ' + ($openKinds -join '; ') + '; see gapObserved/compact traces; privacy-clean; seq convergence'
    }
    $manifest = [ordered]@{
      stamp         = $Stamp
      verdict       = $verdict
      pendingPicked = $pickedTypes
      pendingDeclined = $declinedTypes
      gapObserved   = $openTypes
      gapNote       = 'gapObserved = open/stuck head types (mandatory with no legal pick, or bounded-hold after repeated rejected answers); sent-without-done counts sit in the verdict. Reported as-is, never client-side faked.'
      chooseSpaceStages = $csPairs
      resolvedOtherTypes = $otherResolvedTypes
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

    $ptrTmp = Join-Path $EvidenceDir ("latest-pending.json.$Stamp-$PID.tmp")
    $ptr = Join-Path $EvidenceDir 'latest-pending.json'
    [System.IO.File]::WriteAllText($ptrTmp, (([ordered]@{ current = (Split-Path $RunDir -Leaf); stamp = $Stamp }) | ConvertTo-Json), $Utf8NoBom)
    if (Test-Path -LiteralPath $ptr) {
      $ptrBak = Join-Path $EvidenceDir 'latest-pending.json.bak'
      [System.IO.File]::Replace($ptrTmp, $ptr, $ptrBak)
      Remove-Item -LiteralPath $ptrBak -Force
    } else {
      [System.IO.File]::Move($ptrTmp, $ptr)
    }
    $Published = $true
    Write-Output "published evidence run dir: $RunDir (pointer: latest-pending.json)"
    Write-Output "--- host trace (pending tail) ---"
    Get-Content -LiteralPath $hostTrace |
      Select-String -Pattern 'S09AUTO pending|PEND|SCHEME|QUEUE' | Select-Object -Last 20
    Write-Output "--- joiner trace (pending tail) ---"
    Get-Content -LiteralPath $joinTrace |
      Select-String -Pattern 'S09AUTO pending|PEND|SCHEME|QUEUE' | Select-Object -Last 20
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

Invoke-PendingDemo

if ($Script:CleanupFailure) {
  throw "scoped cleanup did not verify ABORTED for this run's game: $($Script:CleanupFailure)"
}
