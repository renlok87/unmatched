param(
  [string]$Exe = "",
  [int]$TimeoutSeconds = 120,
  [bool]$OffScreen = $true,
  # VS-4 HB-48 (docs/game-design/visual/04-hud-spec.md s5.3): the rollback of the gate - the client gets -S09Markers and
  # the #FF00FF / #00FFFF marker pixel gates run as before. Without it (the default since HB-48) the three shots are
  # gated by their SHOT widget lines (tools/s09/HudShotGate.ps1): board-only - no UI-HUD block visible; maneuver draft
  # - the ACTIONS model in mode=maneuver (the backend-less probe keeps the ACTIONS row collapsed - no live match - so
  # its model is read, visible=0|1) with the hand at rest, no discard; discard - UI-HUD-HAND / UI-HUD-STATUS
  # state=discard and the LIMIT window, no maneuver draft; the board-only control and both swapped pairs must fail.
  [switch]$S09Markers
)
# Backend-less packaged HUD probe (GD-032/033 P1): hidden client renders
# 1) a board-only negative control (HUD hidden),
# 2) the fixture-04 maneuver-draft HUD state, 3) the discard overlay state,
# then proves the REAL Slate key path (route-split verdict; the direct
# PlayerController::InputKey fallback is reported but NOT accepted).
#
# Acceptance gates (state-specific, replaces the old white-pixel gate):
#   - every capture is EXACTLY 1280x720 or 1920x1080 read from the file -
#     the packaged client loads the SAVED GameUserSettings resolution and
#     ignores -resx/-resy, so this script rewrites the staged ini first;
#   - maneuver shot: >= 200 sampled #FF00FF marker pixels in the command
#     panel region AND zero #00FFFF anywhere;
#   - discard shot: >= 200 sampled #00FFFF in the region AND zero #FF00FF;
#   - board-only control and each swapped (state, image) pair MUST fail -
#     asserted explicitly.
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'HudShotGate.ps1')  # VS-4 HB-48
if (-not $Exe) { $Exe = Join-Path $RepoRoot 'unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched.exe' }
$Fixtures = Join-Path $RepoRoot 'docs\game-design\evidence\S08\fixtures'
if (-not (Test-Path -LiteralPath $Exe)) { throw "packaged exe not found: $Exe" }

# --- staged resolution enforcement -----------------------------------------
# The packaged build keeps its last saved resolution (888x500 was found here)
# and ignores -resx/-resy, so publish the target into the staged ini and let
# the PNG dimension gate prove it took effect.
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

$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Dir = Join-Path ([System.IO.Path]::GetTempPath()) "s09-hud-probe-$Stamp-$PID"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$Trace = Join-Path $Dir 'hud-probe.trace.log'
Write-Output "probe staging: $Dir"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $Exe
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$renderArgs = if ($OffScreen) { "-RenderOffScreen" } else { "" }
# HB-01 / VS-4 HB-48: -S09Markers only for the marker gate rollback (04-hud-spec s5.3)
$markersArg = if ($S09Markers) { "-S09Markers " } else { "" }
$psi.Arguments = "/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode -windowed -resx=1280 -resy=720 $renderArgs log=GrepLog -ForceAbandonSequences " +
  $markersArg +
  "-S08Fixtures=`"$Fixtures`" -S09HudProbe=`"$Dir`" -S08Trace=`"$Trace`""
$proc = [System.Diagnostics.Process]::Start($psi)
Write-Output "probe pid=$($proc.Id)"
if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
  Stop-Process -Id $proc.Id -Force
  throw "probe client did not exit within ${TimeoutSeconds}s"
}
Write-Output "probe exit=$($proc.ExitCode) elapsed=$([int]$proc.TotalProcessorTime.TotalSeconds)s cpu"

if (-not (Test-Path -LiteralPath $Trace)) { throw "probe trace missing: $Trace" }
$text = Get-Content -LiteralPath $Trace -Raw
foreach ($needle in @(
    'S09PROBE start', 'S09PROBE board-only view live',
    'S09PROBE maneuver-draft view live',
    'S09PROBE discard overlay live', 'S09PROBE slate key')) {
  if (-not $text.Contains($needle)) { throw "probe trace missing '$needle'" }
}
# Split keyboard verdict: accept ONLY the real Slate route. The direct
# PlayerController::InputKey fallback is a documented non-acceptance.
if ($text -notmatch 'S09PROBE verdict slate-key-route seen=1 direct-key-route seen=0 picks=1 -> SLATE-PASS') {
  $tail = ($text -split "`n" | Select-String 'S09PROBE' | Select-Object -Last 4) -join ' | '
  throw "probe Slate key route did not PASS: $tail"
}
if ($text -match 'mouse-click path: MANUAL-OPEN') {
  Write-Output 'trace gate ok: keyboard SLATE-PASS; mouse path marked MANUAL-OPEN'
}

# --- VS-4 HB-48 SHOT widget gates (default) -------------------------------------
if (-not $S09Markers) {
  $look = Select-String -LiteralPath $Trace -Pattern 'ARTLOOK .* markers=(\d)' | Select-Object -Last 1
  if (-not $look -or $look.Matches[0].Groups[1].Value -ne '0') { throw "probe trace has no 'ARTLOOK ... markers=0' (debug layer on without -S09Markers?)" }
  $board = 's09-probe-board-only.png: deny UI-HUD-*'
  $maneuver = 's09-probe-maneuver-draft.png: need UI-HUD-ACTIONS state=mode=maneuver visible=0|1; need UI-HUD-HAND state=rest|hover|selected; deny UI-HUD-HAND state=discard; deny UI-HUD-STATUS state=discard'
  $discard = 's09-probe-discard-open.png: need UI-HUD-HAND state=discard; need UI-HUD-STATUS state=discard; need UI-HUD-PENDING kind=LIMIT; deny UI-HUD-ACTIONS state=mode=maneuver visible=0|1'
  foreach ($l in (Assert-HudShotGate -TracePath $Trace -Who probe -Privacy -Rules @($board, $maneuver, $discard))) { Write-Output $l }
  # negative controls: the board-only frame and both swapped pairs MUST fail
  $swap = @(
    @('s09-probe-board-only.png', $maneuver), @('s09-probe-board-only.png', $discard),
    @('s09-probe-discard-open.png', $maneuver), @('s09-probe-maneuver-draft.png', $discard))
  foreach ($s in $swap) {
    $rule = $s[0] + ':' + $s[1].Split(':', 2)[1]
    Write-Output (Assert-HudShotGateFails $Trace $rule ("{0} as '{1}'" -f $s[0], $s[1].Split(':', 2)[0]))
  }
  Write-Output 'negative controls ok: board-only and both swapped pairs fail the SHOT widget rules'
  foreach ($name in @('s09-probe-board-only.png', 's09-probe-maneuver-draft.png', 's09-probe-discard-open.png')) {
    $p = Join-Path $Dir $name
    if (-not (Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -lt 10KB) { throw "probe shot missing or too small: $p" }
  }
  Write-Output "PROBE PASS (SHOT widget, HB-48; staging kept for inspection): $Dir"
  return
}

# --- image gates (-S09Markers rollback) ------------------------------------------
Add-Type -AssemblyName System.Drawing

function Get-MarkerStats([string]$Path) {
  # One sampled pass: counts of the two state-marker colors both inside the
  # command-panel region (top-left 60%x50%) and across the whole image.
  if (-not (Test-Path -LiteralPath $Path)) { throw "probe shot missing: $Path" }
  $item = Get-Item -LiteralPath $Path
  if ($item.Length -lt 10KB) { throw "suspiciously small probe shot: $Path" }
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
  # $true only for the matching marker in the panel region AND the opposite
  # marker absent everywhere - a board-only frame or a swapped state fails.
  if ($State -eq 'maneuver') {
    return ($Stats.magentaRegion -ge 200 -and $Stats.cyanAll -eq 0)
  }
  if ($State -eq 'discard') {
    return ($Stats.cyanRegion -ge 200 -and $Stats.magentaAll -eq 0)
  }
  throw "unknown state: $State"
}

$board = Get-MarkerStats (Join-Path $Dir 's09-probe-board-only.png')
$maneuver = Get-MarkerStats (Join-Path $Dir 's09-probe-maneuver-draft.png')
$discard = Get-MarkerStats (Join-Path $Dir 's09-probe-discard-open.png')
foreach ($pair in @(@($board, 'board-only'), @($maneuver, 'maneuver'), @($discard, 'discard'))) {
  Assert-Dimensions $pair[0] $pair[1]
}
Write-Output ("markers board-only: magenta={0} cyan={1}" -f $board.magentaAll, $board.cyanAll)
Write-Output ("markers maneuver:   magentaRegion={0} cyanAll={1}" -f $maneuver.magentaRegion, $maneuver.cyanAll)
Write-Output ("markers discard:    cyanRegion={0} magentaAll={1}" -f $discard.cyanRegion, $discard.magentaAll)

if (-not (Test-StateImage $maneuver 'maneuver')) {
  throw ("maneuver-draft capture failed its state gate (magentaRegion={0}, cyanAll={1})" -f $maneuver.magentaRegion, $maneuver.cyanAll)
}
if (-not (Test-StateImage $discard 'discard')) {
  throw ("discard capture failed its state gate (cyanRegion={0}, magentaAll={1})" -f $discard.cyanRegion, $discard.magentaAll)
}
# Negative controls: MUST fail.
if (Test-StateImage $board 'maneuver') { throw "board-only control PASSED the maneuver gate - gate is unsound" }
if (Test-StateImage $board 'discard') { throw "board-only control PASSED the discard gate - gate is unsound" }
if (Test-StateImage $discard 'maneuver') { throw "swapped image (discard as maneuver) passed - gate is unsound" }
if (Test-StateImage $maneuver 'discard') { throw "swapped image (maneuver as discard) passed - gate is unsound" }
Write-Output 'negative controls ok: board-only and both swapped pairs fail the state gates'

Write-Output "PROBE PASS (staging kept for inspection): $Dir"

# VC C4 (VR-VC-22): an explicit exit code. Without it a caller's $LASTEXITCODE after '& <this script>' is the last
# native command inside (e.g. a negative-control gate that must return 1) - the wrappers printed DEMO_EXIT=1 on a
# passing run. A failure above throws (non-zero); reaching this line means the run passed.
exit 0
