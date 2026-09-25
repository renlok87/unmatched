param(
  [Parameter(Mandatory = $true)][string]$Path,
  [int]$MinVerticalGrooves = 12,
  [int]$MinHorizontalGrooves = 10,
  [int]$MinTeamPixels = 150,
  [double]$MinNonBlackPct = 35.0
)
# GD-030 board-shot verdict. A non-black frame with saturated team colors is
# NOT enough: the old build rendered 20x20 tiles at full XY scale and merged
# them into one unbroken slab. This checker therefore locates the grey board
# bounding box and REQUIRES resolvable dark groove lines on BOTH axes inside
# it (vertical grooves between columns, horizontal between rows), plus team
# base colors INSIDE that box. The slab produces ~0 grooves and is rejected;
# team colors painted outside the board box do not count. The checker proves
# grid + team presence only - it does NOT count fighter silhouettes (that is
# asserted from client traces and a manual screenshot review).
# Exit code 1 + JSON reasons on failure.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$bmp = [System.Drawing.Bitmap]::FromFile($Path)
$w = $bmp.Width; $h = $bmp.Height
$rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
$data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
  [System.Drawing.Imaging.PixelFormat]::Format32bppRgb)
$stride = $data.Stride
$bytes = New-Object byte[] ($stride * $h)
[System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
$bmp.UnlockBits($data)
$bmp.Dispose()

function Get-Lum([int]$x, [int]$y) {
  $o = $y * $script:stride + $x * 4
  return 0.2126 * $script:bytes[$o + 2] + 0.7152 * $script:bytes[$o + 1] + 0.0722 * $script:bytes[$o]
}

# --- board bounding box: contiguous band of columns/rows dominated by the
# mid-grey tile tone (dark grooves/underlay and bright labels average out).
$stepY = [Math]::Max(1, [int]($h / 270))
$colFrac = New-Object 'double[]' $w
for ($x = 0; $x -lt $w; $x++) {
  $n = 0; $grey = 0
  for ($y = 0; $y -lt $h; $y += $stepY) {
    $l = Get-Lum $x $y
    $n++
    if ($l -ge 120 -and $l -le 245) { $grey++ }
  }
  $colFrac[$x] = $grey / [double]$n
}
$boardCols = @()
for ($x = 0; $x -lt $w; $x++) { if ($colFrac[$x] -gt 0.25) { $boardCols += $x } }
if ($boardCols.Count -lt 200) {
  Write-Output (@{ pass = $false; reasons = @('no grey board region found') } | ConvertTo-Json)
  exit 1
}
$x0 = ($boardCols | Measure-Object -Minimum).Minimum
$x1 = ($boardCols | Measure-Object -Maximum).Maximum

$stepX = [Math]::Max(1, [int](($x1 - $x0) / 480))
$rowFrac = New-Object 'double[]' $h
for ($y = 0; $y -lt $h; $y++) {
  $n = 0; $grey = 0
  for ($x = $x0; $x -le $x1; $x += $stepX) {
    $l = Get-Lum $x $y
    $n++
    if ($l -ge 120 -and $l -le 245) { $grey++ }
  }
  $rowFrac[$y] = $grey / [double]$n
}
$boardRows = @()
for ($y = 0; $y -lt $h; $y++) { if ($rowFrac[$y] -gt 0.25) { $boardRows += $y } }
if ($boardRows.Count -lt 120) {
  Write-Output (@{ pass = $false; reasons = @('no grey board rows found') } | ConvertTo-Json)
  exit 1
}
$y0 = ($boardRows | Measure-Object -Minimum).Minimum
$y1 = ($boardRows | Measure-Object -Maximum).Maximum
$inset = 14

# --- mean-luminance profiles inside the board box.
$vx0 = $x0 + $inset; $vx1 = $x1 - $inset; $vy0 = $y0 + $inset; $vy1 = $y1 - $inset
$vProf = New-Object 'double[]' ($vx1 - $vx0 + 1)
for ($x = $vx0; $x -le $vx1; $x++) {
  $sum = 0.0; $n = 0
  for ($y = $vy0; $y -le $vy1; $y++) { $sum += Get-Lum $x $y; $n++ }
  $vProf[$x - $vx0] = $sum / $n
}
$hProf = New-Object 'double[]' ($vy1 - $vy0 + 1)
for ($y = $vy0; $y -le $vy1; $y++) {
  $sum = 0.0; $n = 0
  for ($x = $vx0; $x -le $vx1; $x++) { $sum += Get-Lum $x $y; $n++ }
  $hProf[$y - $vy0] = $sum / $n
}

function Smooth([double[]]$p) {
  $out = New-Object 'double[]' $p.Count
  for ($i = 0; $i -lt $p.Count; $i++) {
    $a = $p[[Math]::Max(0, $i - 1)]; $b = $p[$i]; $c = $p[[Math]::Min($p.Count - 1, $i + 1)]
    $out[$i] = ($a + $b + $c) / 3.0
  }
  return $out
}
function Median([double[]]$p) {
  $s = $p | Sort-Object
  return [double]$s[[int]($s.Count / 2)]
}
function Count-GrooveRuns([double[]]$prof) {
  # Locally-adaptive groove detector. A global (min + 45%*range) threshold
  # cannot see THIN vertical grooves: a 15 uu groove is <10% of a tile column,
  # so its mean-luminance dip is small even though it is plainly visible to
  # the eye. Compare each sample against a LOCAL envelope (window max) and
  # require a dip >= $MinDip. A rendered slab stays flat -> 0 runs, so the
  # slab rejection semantics are unchanged.
  $Half = 36; $MinDip = 10.0
  $n = $prof.Count
  $env = New-Object 'double[]' $n
  for ($i = 0; $i -lt $n; $i++) {
    $lo = [Math]::Max(0, $i - $Half); $hi = [Math]::Min($n - 1, $i + $Half)
    $m = $prof[$lo]
    for ($j = $lo + 1; $j -le $hi; $j++) { if ($prof[$j] -gt $m) { $m = $prof[$j] } }
    $env[$i] = $m
  }
  $runs = 0; $runLen = 0; $inRun = $false
  for ($i = 0; $i -lt $n; $i++) {
    if ($prof[$i] -lt $env[$i] - $MinDip) { $runLen++; $inRun = $true }
    else {
      if ($inRun -and $runLen -le 30) { $runs++ }
      $inRun = $false; $runLen = 0
    }
  }
  if ($inRun -and $runLen -le 30) { $runs++ }
  $med = Median $prof
  $min = ($prof | Measure-Object -Minimum).Minimum
  return @{ runs = $runs; threshold = [Math]::Round($MinDip, 1); median = [Math]::Round($med, 1); profileMin = [Math]::Round($min, 1) }
}

$vGrid = Count-GrooveRuns (Smooth $vProf)
$hGrid = Count-GrooveRuns (Smooth $hProf)

# --- team bases inside the BOARD BOX only + non-black over the full frame.
# Team-pixel counting is bounded to the detected board box: a synthetic
# negative must not pass the team-pixel gate with color patches painted
# OUTSIDE the board (the real fighters' base rings sit on board tiles).
$bluePx = 0; $redPx = 0
$bx0 = $x0; $bx1 = [Math]::Min($x1, $w - 1); $by0 = $y0; $by1 = [Math]::Min($y1, $h - 1)
for ($y = $by0; $y -le $by1; $y += 2) {
  for ($x = $bx0; $x -le $bx1; $x += 2) {
    $o = $y * $stride + $x * 4
    $r = $bytes[$o + 2]; $g = $bytes[$o + 1]; $b = $bytes[$o]
    # Tonemapped team bases: the HDR blue base lands near (179,223,242)
    # (pale cyan), the red base near (244,180,180). Neutral greys (tiles,
    # bodies, white labels) have near-equal channels and never match.
    if ($b -gt 180 -and ($b - $r) -gt 40 -and $g -gt $r) { $bluePx++ }
    if ($r -gt 150 -and ($r - $g) -gt 40 -and ($r - $b) -gt 40) { $redPx++ }
  }
}
$nonBlack = 0; $total = 0
for ($y = 0; $y -lt $h; $y += 2) {
  for ($x = 0; $x -lt $w; $x += 2) {
    $o = $y * $stride + $x * 4
    $lum = 0.2126 * $bytes[$o + 2] + 0.7152 * $bytes[$o + 1] + 0.0722 * $bytes[$o]
    $total++
    if ($lum -gt 10) { $nonBlack++ }
  }
}
$nonBlackPct = [Math]::Round(100.0 * $nonBlack / [double]$total, 1)

$reasons = @()
if ($vGrid.runs -lt $MinVerticalGrooves) { $reasons += "vertical grooves $($vGrid.runs) < $MinVerticalGrooves (solid slab?)" }
if ($hGrid.runs -lt $MinHorizontalGrooves) { $reasons += "horizontal grooves $($hGrid.runs) < $MinHorizontalGrooves (solid slab?)" }
if ($bluePx -lt $MinTeamPixels) { $reasons += "own blue base pixels $bluePx < $MinTeamPixels" }
if ($redPx -lt $MinTeamPixels) { $reasons += "enemy red base pixels $redPx < $MinTeamPixels" }
if ($nonBlackPct -lt $MinNonBlackPct) { $reasons += "nonBlackPct $nonBlackPct < $MinNonBlackPct" }

$out = [ordered]@{
  path              = $Path
  size              = "${w}x${h}"
  boardBox          = "x:${x0}-${x1} y:${y0}-${y1}"
  verticalGrooves   = $vGrid.runs
  horizontalGrooves = $hGrid.runs
  vThreshold        = $vGrid.threshold
  hThreshold        = $hGrid.threshold
  bluePx            = $bluePx
  redPx             = $redPx
  nonBlackPct       = $nonBlackPct
  pass              = ($reasons.Count -eq 0)
  reasons           = $reasons
}
$out | ConvertTo-Json -Depth 3
if ($reasons.Count -gt 0) { exit 1 }
exit 0
