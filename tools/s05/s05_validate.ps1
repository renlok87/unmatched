# S05 packaged-run validation: shared by s05_smoke.ps1 (real run) and s05_smoke_selftest.ps1
# (negative fixtures). All assertions throw on failure; returning normally means PASS.
# Requires: $LogText (string), $FramePaths (array of png paths containing K1/K2/K3 in names).
$ErrorActionPreference = 'Stop'

function Assert-S05Marker([string]$LogText, [string]$Marker) {
    if ($LogText -notmatch [regex]::Escape($Marker)) { throw "Required marker missing: $Marker" }
}

function Assert-S05RootMotion([string]$LogText) {
    # Numeric gate: exactly ~100uu along +Y, X/Z bounded. Any text (0, 10000, ...) fails.
    $m = [regex]::Match($LogText, 'S05_ROOTMOTION_RESULT delta=\(x=(-?[\d.]+) y=(-?[\d.]+) z=(-?[\d.]+)\)')
    if (-not $m.Success) { throw 'S05_ROOTMOTION_RESULT not found or not numeric' }
    $x = [double]$m.Groups[1].Value; $y = [double]$m.Groups[2].Value; $z = [double]$m.Groups[3].Value
    if ([math]::Abs($y - 100.0) -gt 2.0) { throw "Root motion Y out of range: y=$y (expected 100 +/- 2)" }
    if ([math]::Abs($x) -gt 2.0 -or [math]::Abs($z) -gt 2.0) { throw "Root motion X/Z out of range: x=$x z=$z (|.| <= 2)" }
    return "rootmotion ok: x=$x y=$y z=$z"
}

function Assert-S05MedusaRm([string]$LogText) {
    # ART-004: all four Medusa clips must show zero root-motion delta.
    $m = [regex]::Match($LogText, 'S05_MEDUSA_RM (.*)')
    if (-not $m.Success) { throw 'S05_MEDUSA_RM marker missing' }
    $line = $m.Groups[1].Value
    foreach ($clip in @('AM_Medusa_Idle', 'AM_Medusa_LungeAttack', 'AM_Medusa_HitReact', 'AM_Medusa_DeathSettle')) {
        $cm = [regex]::Match($line, [regex]::Escape("$clip=") + '\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)')
        if (-not $cm.Success) { throw "S05_MEDUSA_RM: $clip delta missing/unparseable" }
        $dx = [math]::Abs([double]$cm.Groups[1].Value)
        $dy = [math]::Abs([double]$cm.Groups[2].Value)
        $dz = [math]::Abs([double]$cm.Groups[3].Value)
        if ($dx -gt 0.5 -or $dy -gt 0.5 -or $dz -gt 0.5) { throw "S05_MEDUSA_RM: $clip has root motion ($($cm.Groups[1].Value),$($cm.Groups[2].Value),$($cm.Groups[3].Value))" }
    }
    return 'medusa clip root motion: all zero'
}

function Assert-S05Png1920x1080([string[]]$FramePaths) {
    Add-Type -AssemblyName System.Drawing
    foreach ($p in $FramePaths) {
        if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Frame missing: $p" }
        $item = Get-Item -LiteralPath $p
        if ($item.Length -eq 0) { throw "Frame empty: $p" }
        $img = [System.Drawing.Image]::FromFile($p)
        try {
            if ($img.Width -ne 1920 -or $img.Height -ne 1080) { throw "Frame not 1920x1080: $p is $($img.Width)x$($img.Height)" }
        } finally { $img.Dispose() }
    }
    return "frames ok: $($FramePaths.Count) at 1920x1080"
}

# ---------------------------------------------------------------- pixel gates (review P1-1..P1-4)
# Geometry: K1/K3 camera (0,1032.4,1474.5) pitch -55 yaw -90 FOV 35 -> board (500uu wide)
# spans screen x 537..1383; blue rows (world y -250..-50) map to screen y 222..475, red rows
# (y +50..+250) to y 614..921. Sampling strips sit inside those bands away from figures/labels.

function Get-S05StripRgb([System.Drawing.Bitmap]$Bmp, [int]$X0, [int]$X1, [int]$Y0, [int]$Y1) {
    $sr = 0.0; $sg = 0.0; $sb = 0.0; $n = 0
    for ($y = $Y0; $y -lt $Y1; $y += 3) {
        for ($x = $X0; $x -lt $X1; $x += 3) {
            $c = $Bmp.GetPixel($x, $y); $sr += $c.R; $sg += $c.G; $sb += $c.B; $n++
        }
    }
    return @(($sr / $n), ($sg / $n), ($sb / $n))
}

function Assert-S05ZoneSplit([string]$Path) {
    # P1-4: upper (blue) vs lower (red) board tiles must differ in B/R by a visible margin.
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $blue = Get-S05StripRgb $bmp 640 1280 270 350
        $red = Get-S05StripRgb $bmp 640 1280 700 860
        $blueRatio = $blue[2] / [math]::Max($blue[0], 1.0)
        $redRatio = $red[2] / [math]::Max($red[0], 1.0)
        $split = $blueRatio - $redRatio
        if ($split -lt 0.25) {
            throw ("K1 zone split too weak: blue B/R={0:N2} red B/R={1:N2} split={2:N2} (need >= 0.25): {3}" -f $blueRatio, $redRatio, $split, $Path)
        }
        return ("zone split ok: blue B/R={0:N2} red B/R={1:N2}" -f $blueRatio, $redRatio)
    } finally { $bmp.Dispose() }
}

function Assert-S05LabelsHorizontal([string]$Path) {
    # P1-1: labels present (bright pixels over the figure band) and horizontal. The vertical-text
    # detector looks for a NARWOW tall bright column: run > 110px at x while x +/- 20px stays low.
    # Broad bright areas (sky above the board, the warm-lit red zone) fail the narrowness test and
    # must not trip the gate (2026-09-25 false positive: sky rows y<320, red zone rows y>686).
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $bright = 0
        for ($y = 180; $y -lt 760; $y += 2) {
            for ($x = 400; $x -lt 1520; $x += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -gt 190) { $bright++ }
            }
        }
        if ($bright -lt 1500) { throw "K1 label pixels too few: $bright < 1500 (labels missing?): $Path" }
        $runs = @{}
        for ($x = 400; $x -lt 1520; $x += 4) {
            $run = 0; $best = 0
            for ($y = 100; $y -lt 900; $y += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -gt 190) { $run += 2; if ($run -gt $best) { $best = $run } }
                else { $run = 0 }
            }
            $runs[$x] = $best
        }
        foreach ($x in $runs.Keys) {
            if ($runs[$x] -gt 150) {
                $left = $runs[[math]::Max(400, $x - 20)]
                $right = $runs[[math]::Min(1516, $x + 20)]
                if ($left -lt 60 -and $right -lt 60) {
                    throw ("K1 narrow tall bright column at x={0}: run={1}px (neighbors {2}/{3}) - vertical text regression?: {4}" -f $x, $runs[$x], $left, $right, $Path)
                }
            }
        }
        return ("labels ok: brightPx=$bright (narrow-column filter applied)")
    } finally { $bmp.Dispose() }
}

function Assert-S05K2TitleGlyphs([string]$Path) {
    # P1 final correction (2026-09-25 orchestrator inspection of the packaged K2 PNG): the actual
    # H1 MEDUSA title renders as DARK glyphs in the TOP band of the frame (measured: dark rows
    # y31..123, dark columns x392..1524, ~12.3k dark samples at stride 2). The previous gate scanned
    # BRIGHT pixels in y200..500 - that band holds background/model content, not the title, and the
    # synthetic selftest fixture drew its fake bright title in the same wrong band, so the 28/28
    # selftest pass proved nothing about a missing real title. This gate scans DARK (luma<90) pixels
    # in the true title window y10..139 x340..1579 ONLY: above it rows 0..28 are the bright
    # edge-to-edge sky strip (luma>140), below it the dark backdrop band starts only at ~y150, so
    # neither can produce a qualifying dark band. It localizes the contiguous dark row band
    # (>=100 dark px per sampled row of 620), then proves glyph structure inside it: band starts
    # >=20px below the top edge (the real top-clipped negative starts at row 0), height >=60px
    # (real good band ~94px; backdrop slivers inside the window are <40), >=5000 dark px at stride
    # 2 (real good ~25k), fill <=0.60 (solid block rejected), >=5 dark column clusters with >=4
    # gaps, column span >=300px (a 9-glyph title). Missing title -> no qualifying band. The real
    # no-title negative (fixtures/frame-K2-notitle-real.png, captured with -S05NoK2Title) measures
    # ~0 dark rows in the window.
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $gx0 = 340; $gx1 = 1580
        $rowDark = @{}
        for ($y = 10; $y -lt 140; $y += 2) {
            $cnt = 0
            for ($x = $gx0; $x -lt $gx1; $x += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -lt 90) { $cnt++ }
            }
            if ($cnt -ge 100) { $rowDark[$y] = $true }
        }
        $runs = @(); $cur = @()
        $ys = $rowDark.Keys | Sort-Object
        foreach ($y in $ys) {
            if ($cur.Count -gt 0 -and $y - $cur[-1] -gt 6) { $runs += ,@($cur); $cur = @() }
            $cur += $y
        }
        if ($cur.Count -gt 0) { $runs += ,@($cur) }
        # a substantial dark band starting in rows 10..19 = the top-clipped title (the real
        # clipped negative's band spans y0..47; scanned window starts at y10). Small slivers
        # (<30px) are noise and ignored.
        foreach ($r in $runs) {
            if ($r[0] -lt 20 -and (($r[-1] + 1) - $r[0]) -ge 30) {
                throw ("K2 hero title touches the top frame edge: dark band y{0}..{1} (need start >=20; the real top-clipped negative starts at row 0): {2}" -f $r[0], ($r[-1] + 1), $Path)
            }
        }
        $best = $null
        foreach ($r in $runs) { if (-not $best -or $r.Count -gt $best.Count) { $best = $r } }
        if (-not $best) {
            throw ("K2 hero title missing: no dark glyph band in y10..139 x340..1579 (qualifying rows={0}): {1}" -f $rowDark.Count, $Path)
        }
        $y0 = $best[0]; $y1 = $best[-1] + 1; $h = $y1 - $y0
        if ($y0 -lt 20) {
            throw ("K2 hero title touches the top frame edge: dark band starts at y={0} (need >=20; the real top-clipped negative starts at row 0): {1}" -f $y0, $Path)
        }
        if ($h -lt 60) { throw "K2 hero title band too short: ${h}px at y$($y0)..$($y1) (need >=60): $Path" }
        $dark = 0
        for ($y = $y0; $y -le $y1; $y += 2) {
            for ($x = $gx0; $x -lt $gx1; $x += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -lt 90) { $dark++ }
            }
        }
        if ($dark -lt 5000) { throw "K2 hero title glyphs too few: $dark dark px in band y$($y0)..$($y1) (need >=5000): $Path" }
        $fill = $dark / ((($y1 - $y0) / 2 + 1) * 620.0)
        if ($fill -gt 0.60) { throw ("K2 hero title uniform fill {0:N2} > 0.60 (solid block, not glyphs): {1}" -f $fill, $Path) }
        $rowCnt = [math]::Floor(($y1 - $y0) / 2) + 1
        $colHit = @{}
        for ($x = $gx0; $x -lt $gx1; $x += 2) {
            $cnt = 0
            for ($y = $y0; $y -le $y1; $y += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -lt 90) { $cnt++ }
            }
            if ($cnt -ge [math]::Max(2, [math]::Ceiling($rowCnt * 0.25))) { $colHit[$x] = $true }
        }
        $xs = $colHit.Keys | Sort-Object
        $clusters = 1; $gaps = 0; $prev = $xs[0]
        foreach ($x in $xs) {
            if ($x - $prev -gt 2) { $clusters++; $gaps++ }
            $prev = $x
        }
        $spanX = $xs[-1] - $xs[0]
        if ($clusters -lt 5 -or $gaps -lt 4) {
            throw ("K2 hero title not glyph-shaped: {0} column clusters / {1} gaps in band y{2}..{3} (need >=5/>=4): {4}" -f $clusters, $gaps, $y0, $y1, $Path)
        }
        if ($spanX -lt 300) { throw "K2 hero title too narrow: column span $spanX < 300px: $Path" }
        return ("K2 title glyphs ok: dark band y$y0..$y1 dark=$dark fill={0:N2} clusters=$clusters spanX=$spanX" -f $fill)
    } finally { $bmp.Dispose() }
}

function Assert-S05K2Framing([string]$Path) {
    # P1-2: the frame must isolate ONE full hero. Clipped neighbor bodies would show as tall dark
    # VERTICAL columns attached to the left/right/top edges (a cut torso is 300+ px at this zoom);
    # dark stone tiles at the edges and the dark backdrop band above the far board edge are
    # legitimate scene content and stay under the threshold. Also requires the hero silhouette in
    # the frame center and the hero label near the top.
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        # A clipped neighbor body would be a tall dark column crossing the UPPER half (a cut
        # torso reaches from the edge deep into y<540). The dark wedge tiles in the lower
        # corners (foreshortened stone in shadow, starts y>650, symmetric L/R) are scene content.
        $maxCol = 0
        foreach ($x in 0..79) {
            $run = 0; $best = 0
            for ($y = 0; $y -lt 540; $y += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -lt 50) { $run += 2; if ($run -gt $best) { $best = $run } } else { $run = 0 }
            }
            if ($best -gt $maxCol) { $maxCol = $best }
        }
        foreach ($x in 1840..1919) {
            $run = 0; $best = 0
            for ($y = 0; $y -lt 540; $y += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -lt 50) { $run += 2; if ($run -gt $best) { $best = $run } } else { $run = 0 }
            }
            if ($best -gt $maxCol) { $maxCol = $best }
        }
        $maxTop = 0
        for ($x = 0; $x -lt 1920; $x += 8) {
            $run = 0
            for ($y = 0; $y -lt 1080; $y += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -lt 50) { $run += 2 } else { break }
            }
            if ($run -gt $maxTop) { $maxTop = $run }
        }
        if ($maxCol -gt 240 -or $maxTop -gt 260) {
            throw ("K2 clipped content: edge dark column ${maxCol}px (upper half) / top run ${maxTop}px (clipped figure?): {0}" -f $Path)
        }
        $heroCols = 0
        # window follows the 2026-09-25 target-z lift (+6uu shifts the hero ~70px down): the
        # figure now spans roughly y 270..950, so the silhouette window is 260..1000
        for ($x = 700; $x -lt 1200; $x += 4) {
            $darkRows = 0
            for ($y = 260; $y -lt 1000; $y += 6) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -lt 55) { $darkRows++ }
            }
            if ($darkRows -ge 20) { $heroCols++ }
        }
        if ($heroCols -lt 60) { throw "K2 hero silhouette too narrow: $heroCols columns < 60 in frame center: $Path" }
        $title = Assert-S05K2TitleGlyphs $Path
        return ("K2 framing ok: edgeColumns=${maxCol}px topRun=${maxTop}px heroCols=$heroCols; $title")
    } finally { $bmp.Dispose() }
}

function Assert-S05TopEdgeClear([string]$Path) {
    # 2026-09-25: the K2 hero label was top-clipped (glyphs touched row 0). Plain luma cannot be
    # gated directly: the K2 top band holds a bright sky/tile strip that runs edge to edge, and
    # scene geometry near the left/right frame borders shows small bright fragments in every
    # capture. The working discriminator (calibrated on the real 2026-09-25 negative fixture): in
    # the CENTRAL band (x 300..1600) of rows 0..27 the solid background renders as long
    # uninterrupted bright runs, while clipped glyphs show as many short fragmented runs
    # (real clipped frame: 273 short runs; corrected frame and K1: 0).
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $short = 0
        for ($y = 0; $y -lt 28; $y += 2) {
            $run = 0
            for ($x = 300; $x -lt 1600; $x++) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -gt 140) { $run++ }
                else {
                    if ($run -ge 1 -and $run -le 14) { $short++ }
                    $run = 0
                }
            }
            if ($run -ge 1 -and $run -le 14) { $short++ }
        }
        if ($short -ge 10) { throw "K2 label text touches the top frame edge: $short short glyph runs in rows 0..27 (central band): $Path" }
        return 'K2 top edge clear of label text'
    } finally { $bmp.Dispose() }
}

function Assert-S05K3ScenePanel([string]$Path, [string]$K1Path) {
    # 2026-09-25 correction: HighResShot re-renders the scene WITHOUT the Slate/UMG layer, so the
    # previous screen-space WBP HUD never appeared in any capture and the old gate was a false
    # positive (its region (28,640)-(808,1056) held red-zone board tiles: K1 bright=17489/amber=177
    # vs K3 bright=17413/amber=171 - K3 had FEWER HUD-like pixels than K1). The inspector is real
    # scene geometry now (quad + TextRender 620uu in front of the camera, revealed in K3).
    # Measured facts on the 2026-09-25 rebuilt scene: the quad lands on screen rect
    # (1140,24)-(1900,408) (right-top; the camera right vector resolves to +X world), the panel
    # backing (dark base + emissive) LIFTS the dark background there (K1 luma~60 -> K3 luma~95),
    # and all 7 TextRender lines show as bright rows at their computed centers (y 54,96,150,222,
    # 268,306,344 +-26). Color-based gates are unusable: the tone mapper desaturates the header
    # (255,184,77) into ~(213,190,175), so this gate proves VISIBILITY geometrically instead:
    # (1) light-differential K3-vs-K1 in the rect, (2) bright text in >=5 of the 7 line windows,
    # (3) no text brighter than 150 in the 20px bands at the right/top frame edges. Real no-HUD
    # negative: light delta ~0, 0 line windows. Real good frame: +28632 light, 7/7 windows.
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    $bmp1 = [System.Drawing.Bitmap]::FromFile($K1Path)
    try {
        $light = 0; $light1 = 0
        for ($y = 24; $y -lt 408; $y += 2) {
            for ($x = 1140; $x -lt 1900; $x += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -gt 90) { $light++ }
                $c1 = $bmp1.GetPixel($x, $y)
                if ((0.2126 * $c1.R + 0.7152 * $c1.G + 0.0722 * $c1.B) -gt 90) { $light1++ }
            }
        }
        if (($light - $light1) -lt 15000) { throw "K3-vs-K1 light differential too small in panel rect (1140,24)-(1900,408): K3=$light K1=$light1 (panel not rendered?): $Path" }
        $windows = @(54, 96, 150, 222, 268, 306, 344)
        $linesHit = 0
        foreach ($wy in $windows) {
            $cnt = 0
            for ($y = $wy - 26; $y -lt $wy + 26; $y += 2) {
                for ($x = 1140; $x -lt 1900; $x += 2) {
                    $c = $bmp.GetPixel($x, $y)
                    if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -gt 150) { $cnt++ }
                }
            }
            if ($cnt -ge 40) { $linesHit++ }
        }
        if ($linesHit -lt 5) { throw "K3 scene panel readable text lines too few: $linesHit of 7 windows have >=40 bright px: $Path" }
        $edgeText = 0
        for ($y = 20; $y -lt 408; $y += 2) {
            for ($x = 1900; $x -lt 1920; $x += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -gt 150) { $edgeText++ }
            }
        }
        for ($y = 12; $y -lt 20; $y += 2) {
            for ($x = 1140; $x -lt 1920; $x += 2) {
                $c = $bmp.GetPixel($x, $y)
                if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -gt 150) { $edgeText++ }
            }
        }
        if ($edgeText -gt 0) { throw "K3 panel text touches the frame edge: $edgeText bright px in the right/top 20px bands: $Path" }
        return ("K3 scene panel ok: lightDelta=$($light - $light1) textLines=$linesHit/7 edgeClear")
    } finally { $bmp.Dispose(); $bmp1.Dispose() }
}

function Assert-S05SeatLabels([string]$Path) {
    # Review P1 (2026-09-25) + blank-plate correction: the BOTTOM-team (f-1) labels must be READABLE
    # GLYPHS on their dark plate. The previous gate counted bright pixels in a fixed rect around the
    # expected position and passed the 2026-09-25 blank-plate capture: its rect y 633..677 included
    # the bright orange board BELOW the plate, and the two solid RGB(83,92,156) bars contained zero
    # glyphs. This gate measures the plate bounds first and only then counts bright/cyan pixels
    # INSIDE the plate interior (3px edge margin), requiring glyph-shaped column variation so that
    # uniform or unrelated colored rectangles fail. The top-team (f-0) labels keep their reviewed
    # above-head placement (gold on blue) and stay presence-gated only. Rects are the projected
    # anchors of the six label actors (camera (0,1032.4,1474.5) pitch -55 yaw -90 FOV 35; see
    # project_k1 in s05_import_scene.py): f-0 anchors at screen y ~406 (S2 ~274), f-1 plates at
    # ~630..671 (center ~651). Calibration: real 2026-09-25 blank-plate negative fixture +
    # recapture, and the synthetic negatives in s05_smoke_selftest.ps1.
    $rects = @(
        @{ n = 'S3'; x = 788; y = 406; bottom = $false },
        @{ n = 'H1'; x = 960; y = 406; bottom = $false },
        @{ n = 'S1'; x = 1131; y = 406; bottom = $false },
        @{ n = 'S2'; x = 960; y = 274; bottom = $false },
        @{ n = 'H2'; x = 960; y = 651; bottom = $true },
        @{ n = 'S4'; x = 1134; y = 651; bottom = $true }
    )
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $readable = 0
        $plateMetrics = @()
        foreach ($r in $rects) {
            if ($r.bottom) {
                # (1) localize the plate: contiguous run of rows that are >=75% PLATE pixels
                # (dark luma<120 OR pale-cyan glyph: luma>150 with B-R>15 - glyph rows measure
                # only ~50% dark because the strokes cover half the row). Warm board bleed and sky
                # are R-dominant and match neither, so they cannot hold a run together. The
                # blank-plate regression only ever produced an 18px bar (quad face on the text
                # plane, no glyphs), so a camera-facing plate must be >=25px tall. Median row must
                # sit in its own tile band (divider bar ends ~545, row-3 tile ends ~676).
                $bx0 = $r.x - 80; $bx1 = $r.x + 80
                $darkRow = @{}
                for ($y = 600; $y -lt 690; $y++) {
                    $cnt = 0
                    for ($x = $bx0; $x -lt $bx1; $x += 2) {
                        $c = $bmp.GetPixel($x, $y)
                        $l = 0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B
                        if ($l -lt 120 -or ($l -gt 150 -and ($c.B - $c.R) -gt 15)) { $cnt++ }
                    }
                    if ($cnt -ge 60) { $darkRow[$y] = $true }
                }
                $y0 = -1; $y1 = -1; $bestLen = 0
                $y = 600
                while ($y -lt 690) {
                    if ($darkRow.ContainsKey($y)) {
                        $s = $y
                        while ($y -lt 690 -and $darkRow.ContainsKey($y)) { $y++ }
                        if (($y - $s) -gt $bestLen) { $bestLen = $y - $s; $y0 = $s; $y1 = $y - 1 }
                    } else { $y++ }
                }
                if ($y0 -lt 0) { throw "K1 bottom-team label $($r.n): no dark plate rows in search band y600..689: $Path" }
                if ($bestLen -lt 25) {
                    throw ("K1 bottom-team label {0} plate too small: {1}px tall at y{2} (need >=25px; the 2026-09-25 blank-plate bar was 18px): {3}" -f $r.n, $bestLen, $y0, $Path)
                }
                $midY = [int](($y0 + $y1) / 2)
                if ($midY -lt 585 -or $midY -gt 672) {
                    throw ("K1 bottom-team label {0} misplaced: plate center y={1} (rows {2}..{3}) outside its own tile band 585..672 (divider ~526..545): {4}" -f $r.n, $midY, $y0, $y1, $Path)
                }
                # (2) plate columns from the localized rows (>=60% dark-or-cyan down the column).
                $colDark = @{}
                for ($x = $bx0; $x -lt $bx1; $x++) {
                    $cnt = 0; $tot = 0
                    for ($y = $y0; $y -le $y1; $y += 2) {
                        $c = $bmp.GetPixel($x, $y); $tot++
                        $l = 0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B
                        if ($l -lt 120 -or ($l -gt 150 -and ($c.B - $c.R) -gt 15)) { $cnt++ }
                    }
                    if ($tot -gt 0 -and ($cnt / $tot) -ge 0.6) { $colDark[$x] = $true }
                }
                if ($colDark.Count -lt 60) { throw "K1 bottom-team label $($r.n) plate too narrow: $($colDark.Count) dark columns < 60: $Path" }
                $px0 = ($colDark.Keys | Measure-Object -Minimum).Minimum
                $px1 = ($colDark.Keys | Measure-Object -Maximum).Maximum
                # (3) glyph metrics STRICTLY INSIDE the plate (3px edge margin excludes the rim and
                # any board bleed). Uniform fills and unrelated bright rectangles are rejected by
                # the fill-fraction cap and the column-cluster requirement.
                $ix0 = $px0 + 3; $ix1 = $px1 - 3; $iy0 = $y0 + 3; $iy1 = $y1 - 3
                $bright = 0; $tot = 0; $brR = 0.0; $brB = 0.0
                $colBright = @{}
                $rowBrightMin = 99999; $rowBrightMax = -1
                for ($y = $iy0; $y -le $iy1; $y++) {
                    for ($x = $ix0; $x -le $ix1; $x++) {
                        $c = $bmp.GetPixel($x, $y); $tot++
                        $l = 0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B
                        if ($l -gt 150) {
                            $bright++; $brR += $c.R; $brB += $c.B
                            if (-not $colBright.ContainsKey($x)) { $colBright[$x] = 0 }
                            $colBright[$x]++
                            if ($y -lt $rowBrightMin) { $rowBrightMin = $y }
                            if ($y -gt $rowBrightMax) { $rowBrightMax = $y }
                        }
                    }
                }
                if ($bright -lt 60) {
                    throw ("K1 bottom-team label {0} blank plate: {1} bright glyph px inside plate interior x{2}..{3} y{4}..{5} (need >=60): {6}" -f $r.n, $bright, $ix0, $ix1, $iy0, $iy1, $Path)
                }
                $fill = $bright / $tot
                if ($fill -gt 0.60) {
                    throw ("K1 bottom-team label {0} uniform fill: bright fraction {1:N2} > 0.60 inside the plate (uniform rectangle, not glyphs): {2}" -f $r.n, $fill, $Path)
                }
                $sortedCols = $colBright.Keys | Sort-Object
                # glyph clusters: bright column groups separated by >=1 dark column. At the real
                # 13uu glyph size adjacent letters merge into 15-35px runs with 1-2px gaps
                # (measured 2026-09-25 recapture: H2 -> 6 clusters/5 gaps, S4 -> 4 clusters/3
                # gaps), so a >=2px-gap requirement is over-strict. A uniform or two-block
                # rectangle still fails (1-2 clusters, 0-1 gaps).
                $clusters = 0; $gapCols = 0; $gap = 0; $inCluster = $false
                $prev = -100
                foreach ($x in $sortedCols) {
                    if ($x -eq ($prev + 1)) { $gap = 0 }
                    else { $gap += ($x - $prev - 1) }
                    if ($gap -ge 1) { if ($inCluster) { $gapCols++ }; $clusters++; $inCluster = $true; $gap = 0 }
                    elseif (-not $inCluster) { $clusters++; $inCluster = $true; $gap = 0 }
                    $prev = $x
                }
                if ($clusters -lt 4 -or $gapCols -lt 3) {
                    throw ("K1 bottom-team label {0} no glyph-shaped variation: {1} bright column clusters with {2} gaps inside the plate (need >=4 clusters, >=3 gaps): {3}" -f $r.n, $clusters, $gapCols, $Path)
                }
                $span = $rowBrightMax - $rowBrightMin + 1
                if ($span -lt 8) {
                    throw ("K1 bottom-team label {0} glyph height too small: bright rows span {1}px (need >=8): {2}" -f $r.n, $span, $Path)
                }
                $cyan = ($brB / $bright) - ($brR / $bright)
                if ($cyan -lt 15) {
                    throw ("K1 bottom-team label {0} wrong glyph color: mean B-R={1:N1} < 15 (pale cyan expected; warm board bleed is R-dominant): {2}" -f $r.n, $cyan, $Path)
                }
                $plateMetrics += ("{0}:plate y{1}..{2} x{3}..{4} bright={5} fill={6:N2} clusters={7} span={8} cyan={9:N0}" -f $r.n, $y0, $y1, $px0, $px1, $bright, $fill, $clusters, $span, $cyan)
            }
            $x0 = $r.x - 75; $x1 = $r.x + 75; $y0 = $r.y - 25; $y1 = $r.y + 19
            $bright = 0; $dark = 0
            for ($y = $y0; $y -lt $y1; $y += 2) {
                for ($x = $x0; $x -lt $x1; $x += 2) {
                    $c = $bmp.GetPixel($x, $y)
                    $l = 0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B
                    if ($l -gt 140) { $bright++ }
                    if ($l -lt 125) { $dark++ }
                }
            }
            if ($bright -lt 40) { throw "K1 seat label $($r.n) unreadable: bright glyph pixels $bright < 40: $Path" }
            if ($r.bottom -and $dark -lt 60) { throw "K1 seat label $($r.n) low contrast: dark backing pixels $dark < 60: $Path" }
            $readable++
        }
        return ("seat labels ok: $readable/6 present; f-1 measured plates [$($plateMetrics -join ' | ')]")
    } finally { $bmp.Dispose() }
}

function Assert-S05K3Silhouettes([string]$Path) {
    # P0 (2026-09-25 review): both staged combatants vanished in packaged K3 the moment
    # EnterK3 froze attacker LungeAttack t=0.29 / target HitReact t=0.16 (a bone-0 unit
    # factor mismatch collapsed every played clip to 1/100 while the un-ticked K1 ref
    # pose still looked right). Camera (0,1032.4,1474.5) pitch -55 yaw -90 FOV 35 puts
    # the attacker figure (world (0,-50), ~38uu tall) at screen y 416..472 and the target
    # (world (0,+50)) at y 557..610, x ~936..993. This gate counts dark(<150) pixels and
    # columns with >=15 dark px inside those two windows. Calibration on the real frames:
    # fresh K3 attacker 2587 dark / 50 cols, target 772 / 23; the preserved real negative
    # frame-K3-nobodies-real.png has 215 / 4 and 110 / 1 (markers only). Supplementary to
    # the S05_K3_POSE log bounds - the log proves the pose, this proves it on screen.
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $wins = @(@{ n = 'attacker'; x0 = 925; x1 = 995; y0 = 408; y1 = 480 },
                  @{ n = 'target'; x0 = 925; x1 = 995; y0 = 550; y1 = 620 })
        foreach ($w in $wins) {
            $dark = 0
            $colDark = @{}
            for ($y = $w.y0; $y -lt $w.y1; $y++) {
                for ($x = $w.x0; $x -lt $w.x1; $x++) {
                    $c = $bmp.GetPixel($x, $y)
                    if ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -lt 150) {
                        $dark++
                        if ($colDark.ContainsKey($x)) { $colDark[$x]++ } else { $colDark[$x] = 1 }
                    }
                }
            }
            $cols = 0
            foreach ($x in $colDark.Keys) { if ($colDark[$x] -ge 15) { $cols++ } }
            if ($dark -lt 400 -or $cols -lt 10) {
                throw ("K3 {0} silhouette missing: {1} dark px / {2} dark columns in window x{3}..{4} y{5}..{6} (need >=400/>=10; the real no-bodies negative measures 215/4 and 110/1): {7}" -f $w.n, $dark, $cols, $w.x0, $w.x1, $w.y0, $w.y1, $Path)
            }
        }
        return 'K3 combatant silhouettes ok: attacker+target visible'
    } finally { $bmp.Dispose() }
}

function Assert-S05Run([string]$LogText, [string[]]$FramePaths) {
    Assert-S05Marker $LogText 'S05_REF_READY'
    $fm = [regex]::Match($LogText, 'S05_REF_SCENE figures=(\d+) selection=(\d+) target=(\d+)')
    if (-not $fm.Success) { throw 'S05_REF_SCENE marker missing or unparseable' }
    if ([int]$fm.Groups[1].Value -ne 6) { throw "Expected 6 figures, got $($fm.Groups[1].Value)" }
    if ([int]$fm.Groups[2].Value -ne 1 -or [int]$fm.Groups[3].Value -ne 1) { throw 'Selection/target markers not 1/1' }
    Assert-S05Marker $LogText 'S05_FRAME_STATS'
    Assert-S05MedusaRm $LogText
    Assert-S05RootMotion $LogText
    Assert-S05Marker $LogText 'S05_K3_HUD panel=scene'
    Assert-S05Marker $LogText 'S05_REF_COMPLETE'
    Assert-S05Png1920x1080 $FramePaths
    $k1 = $FramePaths | Where-Object { $_ -match 'K1' } | Select-Object -First 1
    $k2 = $FramePaths | Where-Object { $_ -match 'K2' } | Select-Object -First 1
    $k3 = $FramePaths | Where-Object { $_ -match 'K3' } | Select-Object -First 1
    $details = @()
    if ($k1) { $details += Assert-S05ZoneSplit $k1; $details += Assert-S05LabelsHorizontal $k1; $details += Assert-S05SeatLabels $k1 }
    if ($k2) { $details += Assert-S05K2Framing $k2; $details += Assert-S05TopEdgeClear $k2 }
    if ($k3) { $details += Assert-S05K3Silhouettes $k3 }
    if ($k3 -and $k1) { $details += Assert-S05K3ScenePanel $k3 $k1 }
    return 'validation PASS: ' + ($details -join '; ')
}
