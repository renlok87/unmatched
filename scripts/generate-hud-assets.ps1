param(
  [string]$OutRoot = "public/assets"
)

Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = "Stop"

function New-AssetBitmap([int]$Width, [int]$Height) {
  $bitmap = New-Object System.Drawing.Bitmap $Width, $Height, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
  $graphics.Clear([System.Drawing.Color]::Transparent)
  return @($bitmap, $graphics)
}

function New-RoundRectPath([float]$X, [float]$Y, [float]$Width, [float]$Height, [float]$Radius) {
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  $d = $Radius * 2
  $path.AddArc($X, $Y, $d, $d, 180, 90)
  $path.AddArc($X + $Width - $d, $Y, $d, $d, 270, 90)
  $path.AddArc($X + $Width - $d, $Y + $Height - $d, $d, $d, 0, 90)
  $path.AddArc($X, $Y + $Height - $d, $d, $d, 90, 90)
  $path.CloseFigure()
  return $path
}

function Color-A([int]$A, [int]$R, [int]$G, [int]$B) {
  return [System.Drawing.Color]::FromArgb($A, $R, $G, $B)
}

function Save-Png($Bitmap, $Graphics, [string]$Path) {
  $dir = Split-Path $Path
  if (!(Test-Path $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  $Bitmap.Save((Resolve-Path $dir).Path + "\" + (Split-Path $Path -Leaf), [System.Drawing.Imaging.ImageFormat]::Png)
  $Graphics.Dispose()
  $Bitmap.Dispose()
}

function Draw-Panel([string]$Path, [int]$Width, [int]$Height, [bool]$Local) {
  $pair = New-AssetBitmap $Width $Height
  $bitmap = $pair[0]
  $g = $pair[1]

  $panel = New-RoundRectPath 4 6 ($Width - 8) ($Height - 12) 18
  $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    (New-Object System.Drawing.Rectangle 0, 0, $Width, $Height),
    (Color-A 238 18 22 33),
    (Color-A 222 41 47 62),
    [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
  )
  $g.FillPath($brush, $panel)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 225 209 177 87), 2.0), $panel)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 120 70 215 220), 1.0), (New-RoundRectPath 8 10 ($Width - 16) ($Height - 20) 14))

  $portraitX = if ($Local) { 58 } else { $Width - 58 }
  $g.FillEllipse((New-Object System.Drawing.SolidBrush (Color-A 210 7 9 15)), $portraitX - 33, 18, 66, 66)
  $g.DrawEllipse((New-Object System.Drawing.Pen (Color-A 230 218 188 96), 3.0), $portraitX - 33, 18, 66, 66)
  $g.DrawEllipse((New-Object System.Drawing.Pen (Color-A 160 87 205 219), 1.5), $portraitX - 26, 25, 52, 52)

  $miniX = $portraitX
  $miniY = if ($Local) { $Height - 26 } else { $Height - 22 }
  $g.FillEllipse((New-Object System.Drawing.SolidBrush (Color-A 230 13 16 25)), $miniX - 18, $miniY - 18, 36, 36)
  $g.DrawEllipse((New-Object System.Drawing.Pen (Color-A 210 210 216 226), 1.5), $miniX - 18, $miniY - 18, 36, 36)

  $statX = if ($Local) { 104 } else { 26 }
  $statW = $Width - 148
  for ($i = 0; $i -lt 3; $i++) {
    $slot = New-RoundRectPath ($statX + ($i * 62)) ($Height - 38) 48 22 8
    $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 150 5 8 15)), $slot)
    $g.DrawPath((New-Object System.Drawing.Pen (Color-A 110 215 184 75), 1.0), $slot)
  }

  $lane = New-RoundRectPath $statX 20 $statW 24 9
  $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 130 5 8 15)), $lane)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 100 110 126 156), 1.0), $lane)

  Save-Png $bitmap $g $Path
}

function Draw-Pill([string]$Path) {
  $pair = New-AssetBitmap 220 54
  $bitmap = $pair[0]
  $g = $pair[1]
  $body = New-RoundRectPath 4 7 212 40 18
  $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 234 9 13 22)), $body)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 225 209 177 87), 2.0), $body)
  $g.FillEllipse((New-Object System.Drawing.SolidBrush (Color-A 210 65 213 220)), 20, 22, 10, 10)
  $g.FillEllipse((New-Object System.Drawing.SolidBrush (Color-A 210 220 159 68)), 190, 22, 10, 10)
  Save-Png $bitmap $g $Path
}

function Draw-Tray([string]$Path, [int]$Width, [int]$Height) {
  $pair = New-AssetBitmap $Width $Height
  $bitmap = $pair[0]
  $g = $pair[1]
  $body = New-RoundRectPath 6 16 ($Width - 12) ($Height - 22) 24
  $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 220 11 15 24)), $body)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 215 209 177 87), 2.0), $body)
  $g.DrawLine((New-Object System.Drawing.Pen (Color-A 140 84 218 226), 2.0), 28, 22, $Width - 28, 22)
  for ($x = 58; $x -lt ($Width - 40); $x += 78) {
    $slot = New-RoundRectPath ($x - 30) 34 60 ($Height - 48) 8
    $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 75 255 255 255)), $slot)
    $g.DrawPath((New-Object System.Drawing.Pen (Color-A 75 255 255 255), 1.0), $slot)
  }
  Save-Png $bitmap $g $Path
}

function Draw-Slot([string]$Path, [bool]$Discard) {
  $pair = New-AssetBitmap 96 132
  $bitmap = $pair[0]
  $g = $pair[1]
  $accent = if ($Discard) { Color-A 225 220 159 68 } else { Color-A 225 76 210 220 }
  for ($i = 0; $i -lt 3; $i++) {
    $rect = New-RoundRectPath (12 + $i * 3) (8 + $i * 3) 68 104 8
    $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 170 13 17 27)), $rect)
    $g.DrawPath((New-Object System.Drawing.Pen (Color-A 90 255 255 255), 1.0), $rect)
  }
  $front = New-RoundRectPath 18 18 64 96 8
  $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 210 22 27 39)), $front)
  $g.DrawPath((New-Object System.Drawing.Pen $accent, 2.0), $front)
  Save-Png $bitmap $g $Path
}

function Draw-CardBack([string]$Path) {
  $pair = New-AssetBitmap 120 180
  $bitmap = $pair[0]
  $g = $pair[1]
  $body = New-RoundRectPath 8 8 104 164 12
  $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 255 15 20 34)), $body)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 240 207 173 84), 3.0), $body)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 135 64 210 218), 2.0), (New-RoundRectPath 18 18 84 144 8))
  $pen = New-Object System.Drawing.Pen (Color-A 180 207 173 84), 3.0
  $g.DrawBezier($pen, 28, 118, 52, 62, 74, 132, 94, 58)
  $g.DrawBezier($pen, 28, 62, 52, 132, 74, 48, 94, 118)
  Save-Png $bitmap $g $Path
}

function Draw-BoardVignette([string]$Path) {
  $pair = New-AssetBitmap 1024 768
  $bitmap = $pair[0]
  $g = $pair[1]
  for ($i = 0; $i -lt 80; $i += 4) {
    $alpha = [Math]::Max(0, 74 - $i)
    $pen = New-Object System.Drawing.Pen (Color-A $alpha 4 7 13), 4.0
    $g.DrawRectangle($pen, $i, $i, 1024 - $i * 2, 768 - $i * 2)
  }
  Save-Png $bitmap $g $Path
}

function Draw-BoardFrame([string]$Path) {
  $pair = New-AssetBitmap 640 430
  $bitmap = $pair[0]
  $g = $pair[1]
  $outer = New-RoundRectPath 4 4 632 422 20
  $inner = New-RoundRectPath 22 22 596 386 12
  $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 205 19 23 31)), $outer)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 230 207 173 84), 4.0), $outer)
  $g.FillPath((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::Transparent)), $inner)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 135 70 215 220), 2.0), $inner)
  $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
  $g.FillPath((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::Transparent)), $inner)
  $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
  Save-Png $bitmap $g $Path
}

function Draw-Chip([string]$Path) {
  $pair = New-AssetBitmap 132 34
  $bitmap = $pair[0]
  $g = $pair[1]
  $body = New-RoundRectPath 3 4 126 26 12
  $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 220 14 18 28)), $body)
  $g.DrawPath((New-Object System.Drawing.Pen (Color-A 170 207 173 84), 1.5), $body)
  Save-Png $bitmap $g $Path
}

function Draw-Badges([string]$Path) {
  $pair = New-AssetBitmap 384 64
  $bitmap = $pair[0]
  $g = $pair[1]
  $colors = @(
    (Color-A 230 226 67 83),
    (Color-A 230 76 210 220),
    (Color-A 230 222 151 55),
    (Color-A 230 92 142 226),
    (Color-A 230 151 96 222),
    (Color-A 230 220 220 220)
  )
  for ($i = 0; $i -lt 6; $i++) {
    $cx = $i * 64 + 32
    $g.FillEllipse((New-Object System.Drawing.SolidBrush (Color-A 225 13 17 27)), $cx - 25, 7, 50, 50)
    $g.DrawEllipse((New-Object System.Drawing.Pen (Color-A 220 207 173 84), 2.0), $cx - 25, 7, 50, 50)
    $pen = New-Object System.Drawing.Pen $colors[$i], 4.0
    switch ($i) {
      0 { $g.FillEllipse((New-Object System.Drawing.SolidBrush $colors[$i]), $cx - 10, 22, 20, 18) }
      1 { $g.DrawLine($pen, $cx - 14, 40, $cx, 20); $g.DrawLine($pen, $cx, 20, $cx + 14, 40) }
      2 { $g.DrawLine($pen, $cx - 14, 39, $cx + 14, 21); $g.DrawLine($pen, $cx + 4, 21, $cx + 14, 21) }
      3 { $g.DrawArc($pen, $cx - 15, 19, 30, 26, 30, 120); $g.DrawLine($pen, $cx - 13, 30, $cx, 45) }
      4 { $g.DrawPolygon($pen, @((New-Object System.Drawing.Point ($cx), 17), (New-Object System.Drawing.Point ($cx + 14), 34), (New-Object System.Drawing.Point ($cx), 48), (New-Object System.Drawing.Point ($cx - 14), 34))) }
      5 { $g.DrawRectangle($pen, $cx - 12, 20, 24, 30); $g.DrawLine($pen, $cx - 8, 15, $cx + 8, 15) }
    }
  }
  Save-Png $bitmap $g $Path
}

function Draw-Actions([string]$Path) {
  $pair = New-AssetBitmap 360 72
  $bitmap = $pair[0]
  $g = $pair[1]
  for ($i = 0; $i -lt 5; $i++) {
    $cx = $i * 72 + 36
    $body = New-RoundRectPath ($cx - 28) 8 56 56 14
    $g.FillPath((New-Object System.Drawing.SolidBrush (Color-A 230 13 17 27)), $body)
    $g.DrawPath((New-Object System.Drawing.Pen (Color-A 220 207 173 84), 2.0), $body)
    $pen = New-Object System.Drawing.Pen (Color-A 225 82 214 222), 4.0
    switch ($i) {
      0 { $g.DrawLine($pen, $cx - 15, 42, $cx + 12, 25); $g.DrawLine($pen, $cx + 12, 25, $cx + 5, 22); $g.DrawLine($pen, $cx + 12, 25, $cx + 11, 33) }
      1 { $g.DrawLine($pen, $cx - 16, 48, $cx + 14, 20); $g.DrawLine($pen, $cx + 2, 20, $cx + 14, 20) }
      2 { $g.DrawArc($pen, $cx - 16, 20, 32, 28, 25, 130); $g.DrawLine($pen, $cx - 13, 33, $cx, 51) }
      3 { $g.DrawPolygon($pen, @((New-Object System.Drawing.Point ($cx), 17), (New-Object System.Drawing.Point ($cx + 15), 36), (New-Object System.Drawing.Point ($cx), 55), (New-Object System.Drawing.Point ($cx - 15), 36))) }
      4 { $g.DrawLine($pen, $cx - 13, 24, $cx + 13, 36); $g.DrawLine($pen, $cx + 13, 36, $cx - 13, 48) }
    }
  }
  Save-Png $bitmap $g $Path
}

function Draw-Ring([string]$Path) {
  $pair = New-AssetBitmap 128 128
  $bitmap = $pair[0]
  $g = $pair[1]
  $g.DrawEllipse((New-Object System.Drawing.Pen (Color-A 230 238 255 255), 5.0), 19, 19, 90, 90)
  $g.DrawEllipse((New-Object System.Drawing.Pen (Color-A 170 61 214 226), 10.0), 22, 22, 84, 84)
  Save-Png $bitmap $g $Path
}

function Draw-Highlight([string]$Path, [System.Drawing.Color]$Color) {
  $pair = New-AssetBitmap 128 128
  $bitmap = $pair[0]
  $g = $pair[1]
  $g.FillEllipse((New-Object System.Drawing.SolidBrush (Color-A 42 $Color.R $Color.G $Color.B)), 16, 16, 96, 96)
  $g.DrawEllipse((New-Object System.Drawing.Pen (Color-A 220 $Color.R $Color.G $Color.B), 4.0), 18, 18, 92, 92)
  $g.DrawEllipse((New-Object System.Drawing.Pen (Color-A 120 255 255 255), 1.5), 30, 30, 68, 68)
  Save-Png $bitmap $g $Path
}

function Draw-Shield([string]$Path) {
  $pair = New-AssetBitmap 96 96
  $bitmap = $pair[0]
  $g = $pair[1]
  $pen = New-Object System.Drawing.Pen (Color-A 220 137 226 255), 6.0
  $g.DrawArc($pen, 18, 12, 60, 72, 205, 130)
  $g.DrawArc((New-Object System.Drawing.Pen (Color-A 100 255 255 255), 2.0), 25, 20, 46, 54, 205, 130)
  Save-Png $bitmap $g $Path
}

function Draw-Strip([string]$Path, [int]$FrameW, [int]$FrameH, [int]$Frames, [bool]$Spark) {
  $pair = New-AssetBitmap ($FrameW * $Frames) $FrameH
  $bitmap = $pair[0]
  $g = $pair[1]
  for ($i = 0; $i -lt $Frames; $i++) {
    $cx = $i * $FrameW + $FrameW / 2
    $cy = $FrameH / 2
    $r = 8 + $i * 3
    $alpha = [Math]::Max(30, 230 - $i * 22)
    $color = if ($Spark) { Color-A $alpha 255 172 54 } else { Color-A $alpha 76 210 220 }
    $g.FillEllipse((New-Object System.Drawing.SolidBrush $color), $cx - $r, $cy - $r, $r * 2, $r * 2)
    $pen = New-Object System.Drawing.Pen (Color-A $alpha 255 255 255), 2.0
    for ($ray = 0; $ray -lt 8; $ray++) {
      $angle = ($ray / 8) * [Math]::PI * 2
      $x1 = $cx + [Math]::Cos($angle) * ($r + 2)
      $y1 = $cy + [Math]::Sin($angle) * ($r + 2)
      $x2 = $cx + [Math]::Cos($angle) * ($r + 12 + $i)
      $y2 = $cy + [Math]::Sin($angle) * ($r + 12 + $i)
      $g.DrawLine($pen, [float]$x1, [float]$y1, [float]$x2, [float]$y2)
    }
  }
  Save-Png $bitmap $g $Path
}

$hud = Join-Path $OutRoot "ui/hud"
$fx = Join-Path $OutRoot "ui/effects"

Draw-Panel (Join-Path $hud "player-panel-local.png") 380 112 $true
Draw-Panel (Join-Path $hud "player-panel-opponent.png") 380 96 $false
Draw-Pill (Join-Path $hud "turn-phase-pill.png")
Draw-Panel (Join-Path $hud "selected-card-panel.png") 260 360 $true
Draw-Panel (Join-Path $hud "mobile-bottom-sheet.png") 390 320 $true
Draw-Tray (Join-Path $hud "hand-tray.png") 760 130
Draw-Tray (Join-Path $hud "hand-tray-mobile.png") 390 122
Draw-Slot (Join-Path $hud "deck-slot.png") $false
Draw-Slot (Join-Path $hud "discard-slot.png") $true
Draw-CardBack (Join-Path $hud "hidden-card-back.png")
Draw-BoardVignette (Join-Path $hud "board-vignette.png")
Draw-BoardFrame (Join-Path $hud "board-frame-6x4.png")
Draw-Chip (Join-Path $hud "zone-legend-chip.png")
Draw-Badges (Join-Path $hud "status-badges.png")
Draw-Actions (Join-Path $hud "action-buttons.png")

Draw-Ring (Join-Path $fx "selection-ring.png")
Draw-Highlight (Join-Path $fx "move-highlight.png") ([System.Drawing.Color]::FromArgb(76, 210, 220))
Draw-Highlight (Join-Path $fx "attack-highlight.png") ([System.Drawing.Color]::FromArgb(230, 92, 70))
Draw-Shield (Join-Path $fx "defense-shield.png")
Draw-Strip (Join-Path $fx "hit-spark-strip.png") 64 64 8 $true
Draw-Strip (Join-Path $fx "card-play-flash-strip.png") 96 96 8 $false

Write-Host "Generated HUD assets under $OutRoot"
