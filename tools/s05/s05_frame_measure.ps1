# Reproducible frame measurements for the S05 evidence report (luma table).
# Usage: powershell -File s05_frame_measure.ps1  -> measures docs/game-design/evidence/S05/art-references/frames/frame-K*.png
# Writes frame-measurements.json next to the frames with explicit UTC and local timestamps.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$framesDir = "$root/docs/game-design/evidence/S05/art-references/frames"
Add-Type -AssemblyName System.Drawing

function Measure-Frame([string]$Path) {
    $img = [System.Drawing.Image]::FromFile($Path)
    try {
        $bmp = New-Object System.Drawing.Bitmap($img)
        try {
            $rect = New-Object System.Drawing.Rectangle(0, 0, $bmp.Width, $bmp.Height)
            $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
            try {
                $stride = $data.Stride
                $bytes = New-Object byte[] ($stride * $bmp.Height)
                [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
            } finally { $bmp.UnlockBits($data) }
            $lum = New-Object System.Collections.Generic.List[double]
            $step = 4  # sample every 4th pixel row and column (stride-safe, deterministic)
            for ($y = 0; $y -lt $bmp.Height; $y += $step) {
                $row = $y * $stride
                for ($x = 0; $x -lt $bmp.Width; $x += $step) {
                    $i = $row + $x * 3
                    $lum.Add(0.2126 * $bytes[$i + 2] + 0.7152 * $bytes[$i + 1] + 0.0722 * $bytes[$i])
                }
            }
            $arr = $lum.ToArray()
            $spatial = $arr.Clone()
            [Array]::Sort($arr)
            $n = $arr.Length
            $mean = ($arr | Measure-Object -Average).Average
            $dark = @($arr | Where-Object { $_ -lt 30 }).Count / $n
            $bright = @($arr | Where-Object { $_ -gt 150 }).Count / $n
            $edge = 0
            # edge density on the sampled grid: mean abs horizontal luminance gradient
            $cols = [math]::Floor($bmp.Width / $step)
            for ($r = 1; $r -lt [math]::Floor($n / $cols); $r++) {
                for ($c = 1; $c -lt $cols; $c++) {
                    $edge += [math]::Abs($spatial[$r * $cols + $c] - $spatial[$r * $cols + $c - 1])
                }
            }
            [ordered]@{
                file = [IO.Path]::GetFileName($Path)
                width = $img.Width; height = $img.Height
                mean = [math]::Round($mean, 1)
                p50 = [math]::Round($arr[[int][math]::Floor($n * 0.50)], 1)
                p90 = [math]::Round($arr[[int][math]::Floor($n * 0.90)], 1)
                darkUnder30 = [math]::Round($dark * 100, 2)
                brightOver150 = [math]::Round($bright * 100, 2)
                edgeDensity = [math]::Round($edge / ($n - $cols), 2)
            }
        } finally { $bmp.Dispose() }
    } finally { $img.Dispose() }
}

$now = [DateTime]::Now
$out = [ordered]@{
    measuredAtLocal = $now.ToString('yyyy-MM-ddTHH:mm:sszzz')
    measuredAtUtc = ([DateTime]::UtcNow).ToString('yyyy-MM-ddTHH:mm:ssZ')
    sampler = 'System.Drawing LockBits 24bpp, Rec.709 luma, stride 4x4 grid'
    frames = @()
}
foreach ($p in (Get-ChildItem -LiteralPath $framesDir -Filter 'frame-K*.png' | Sort-Object Name)) {
    $out.frames += (Measure-Frame $p.FullName)
}
if ($out.frames.Count -eq 0) { throw "No frame-K*.png found in $framesDir" }
$out | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $framesDir 'frame-measurements.json') -Encoding UTF8
Write-Output ($out | ConvertTo-Json -Depth 4)
