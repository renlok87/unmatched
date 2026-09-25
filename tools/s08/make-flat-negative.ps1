param(
  [string]$Out = ""
)
# Negative control fixture for check-board-shot.ps1: a SYNTHETIC flat board
# (uniform mid-grey slab, NO grooves) with team base color patches and a
# bright background. Every other acceptance criterion (grey board region,
# team pixels, non-black) passes; the groove detector alone must fail it.
# Regenerates tools/s08/fixtures/flat-board-negative-1920x1080.png byte-stably.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
if (-not $Out) { $Out = Join-Path $PSScriptRoot 'fixtures\flat-board-negative-1920x1080.png' }
$dir = Split-Path $Out
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

$w = 1920; $h = 1080
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
# Dark-but-not-black background (outside the checker's grey band, so the
# detected board box is the slab itself, not the whole frame).
$g.Clear([System.Drawing.Color]::FromArgb(90, 90, 90))
# Flat uniform board slab (mid-grey, no grooves at all).
$slab = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(190, 190, 190))
$g.FillRectangle($slab, 360, 60, 1200, 960)
# Team base patches outside the slab: blue passes (b>180, b-r>40, g>r), red
# passes (r>150, r-g>40, r-b>40) - same rules as the checker.
$blue = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(100, 150, 240))
$g.FillRectangle($blue, 40, 40, 200, 200)
$red = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(240, 100, 80))
$g.FillRectangle($red, 1640, 800, 200, 200)
$g.Dispose()
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "negative fixture written: $Out"
