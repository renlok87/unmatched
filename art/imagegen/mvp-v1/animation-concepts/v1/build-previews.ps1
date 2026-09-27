$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sets = [ordered]@{
    'medusa' = [ordered]@{
        'Idle' = 'med-idle-keyposes-v1.png'
        'LungeAttack' = 'med-lunge-attack-keyposes-v1.png'
        'HitReact' = 'med-hit-react-keyposes-v1.png'
        'DeathSettle' = 'med-death-settle-keyposes-v1.png'
    }
    'harpy' = [ordered]@{
        'Idle' = 'har-idle-keyposes-v1.png'
        'LungeAttack' = 'har-lunge-attack-keyposes-v1.png'
        'HitReact (conditional)' = 'har-hit-react-keyposes-v1.png'
        'DeathSettle' = 'har-death-settle-keyposes-v1.png'
    }
    'king-arthur' = [ordered]@{
        'Idle' = 'arth-idle-keyposes-v1.png'
        'LungeAttack' = 'arth-lunge-attack-keyposes-v1.png'
        'HitReact' = 'arth-hit-react-keyposes-v1.png'
        'DeathSettle' = 'arth-death-settle-keyposes-v1.png'
    }
    'merlin' = [ordered]@{
        'Idle' = 'mer-idle-keyposes-v1.png'
        'LungeAttack' = 'mer-lunge-attack-keyposes-v1.png'
        'HitReact' = 'mer-hit-react-keyposes-v1.png'
        'DeathSettle' = 'mer-death-settle-keyposes-v1.png'
    }
}

function Draw-FittedImage {
    param(
        [System.Drawing.Graphics]$Graphics,
        [System.Drawing.Image]$Image,
        [System.Drawing.RectangleF]$Bounds
    )
    $scale = [Math]::Min($Bounds.Width / $Image.Width, $Bounds.Height / $Image.Height)
    $width = [single]($Image.Width * $scale)
    $height = [single]($Image.Height * $scale)
    $x = [single]($Bounds.X + (($Bounds.Width - $width) / 2))
    $y = [single]($Bounds.Y + (($Bounds.Height - $height) / 2))
    $Graphics.DrawImage($Image, $x, $y, $width, $height)
}

function Build-Sheet {
    param(
        [string]$Title,
        [System.Collections.IDictionary]$Items,
        [string]$OutputPath
    )
    $canvas = New-Object System.Drawing.Bitmap 1600, 1000
    $graphics = [System.Drawing.Graphics]::FromImage($canvas)
    $graphics.Clear([System.Drawing.Color]::FromArgb(24, 26, 30))
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $titleFont = New-Object System.Drawing.Font 'Segoe UI', 24, ([System.Drawing.FontStyle]::Bold)
    $labelFont = New-Object System.Drawing.Font 'Segoe UI', 16, ([System.Drawing.FontStyle]::Bold)
    $brush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $graphics.DrawString($Title, $titleFont, $brush, 24, 12)

    $index = 0
    foreach ($entry in $Items.GetEnumerator()) {
        $column = $index % 2
        $row = [Math]::Floor($index / 2)
        $left = 20 + ($column * 790)
        $top = 65 + ($row * 460)
        $graphics.DrawString($entry.Key, $labelFont, $brush, $left, $top)
        $path = Join-Path (Split-Path -Parent $OutputPath) $entry.Value
        $image = [System.Drawing.Image]::FromFile($path)
        try {
            Draw-FittedImage -Graphics $graphics -Image $image -Bounds (New-Object System.Drawing.RectangleF ($left), ($top + 36), 760, 400)
        }
        finally {
            $image.Dispose()
        }
        $index++
    }

    $canvas.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $brush.Dispose()
    $labelFont.Dispose()
    $titleFont.Dispose()
    $graphics.Dispose()
    $canvas.Dispose()
}

foreach ($set in $sets.GetEnumerator()) {
    $directory = Join-Path $root $set.Key
    Build-Sheet -Title $set.Key.ToUpperInvariant() -Items $set.Value -OutputPath (Join-Path $directory 'overview-v1.png')
}

$master = [ordered]@{}
foreach ($set in $sets.GetEnumerator()) {
    $master[$set.Key.ToUpperInvariant()] = "$($set.Key)/overview-v1.png"
}
Build-Sheet -Title 'ANIMATION CONCEPTS V1' -Items $master -OutputPath (Join-Path $root 'animation-concepts-v1-preview.png')

Write-Output "Built 5 previews under $root"
