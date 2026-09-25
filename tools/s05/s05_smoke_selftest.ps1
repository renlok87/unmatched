# Negative self-test for the S05 smoke gate: proves the validator actually fails on
# bad root-motion numbers (0 / 10000), missing markers, non-1920x1080 frames, and the
# pixel-gate regressions (vertical labels, pale seat labels without dark backing, bottom-team
# labels straddling the zone divider, K2 clipping incl. the real top-clipped frame, missing
# K2 hero title incl. the real -S05NoK2Title capture, missing scene panel incl. the real
# no-HUD K3 frame, no zone split).
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
. "$PSScriptRoot/s05_validate.ps1"
Add-Type -AssemblyName System.Drawing
$fixtureDir = Join-Path $env:TEMP ("s05-selftest-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force -Path $fixtureDir | Out-Null
# Real captured frames kept as permanent negative fixtures (2026-09-25 run): K3 without any
# visible HUD (the HighResShot/Slate gap), K2 with the top-clipped H1 MEDUSA label, K2 with the
# hero title suppressed via the -S05NoK2Title diagnostic flag, and K1 with the blank f-1
# nameplates (quad face exactly on the text plane - no glyphs inside either plate).
$realK3NoHud = Join-Path $PSScriptRoot 'fixtures/frame-K3-nohud-real.png'
$realK2Clipped = Join-Path $PSScriptRoot 'fixtures/frame-K2-clippedlabel-real.png'
$realK1BlankPlate = Join-Path $PSScriptRoot 'fixtures/frame-K1-blankplate-real.png'
foreach ($p in @($realK3NoHud, $realK2Clipped, $realK1BlankPlate)) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Real negative fixture missing: $p" }
}

function New-FixturePng([string]$Path, [int]$W, [int]$H) {
    $bmp = New-Object System.Drawing.Bitmap($W, $H)
    try { $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png) } finally { $bmp.Dispose() }
}

function New-K1Fixture([string]$Path, [System.Drawing.Color]$Blue, [System.Drawing.Color]$Red, [switch]$NoLabels, [switch]$VerticalText, [switch]$PaleLabels, [switch]$StraddleLabels, [switch]$BlankPlate, [switch]$SolidGlyphs) {
    $bmp = New-Object System.Drawing.Bitmap(1920, 1080)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    # dark background (luma<90): the K3 panel gate light-differential requires the K1 reference
    # to be dark inside the panel rect, matching the real capture (~60 luma there).
    $g.Clear([System.Drawing.Color]::FromArgb(70, 70, 74))
    $brush = New-Object System.Drawing.SolidBrush($Blue)
    $g.FillRectangle($brush, 600, 270, 720, 80)
    $brush.Color = $Red
    $g.FillRectangle($brush, 600, 700, 720, 160)
    # bright board band across the bottom-team label search zone (y 600..690): mirrors the real
    # capture where only the plate is dark there, so the measured plate-localization has something
    # to actually find (a dark background would make it vacuous).
    $brush.Color = [System.Drawing.Color]::FromArgb(244, 176, 143)
    $g.FillRectangle($brush, 600, 560, 720, 140)
    # seat labels at the Assert-S05SeatLabels rects: f-0 above-head anchors y~406 (S2 274) are
    # presence-gated only; the f-1 foot-plates y~651 carry the dark plate + pale-cyan GLYPH
    # CLUSTERS (the gate requires glyph-shaped column variation inside the measured plate bounds).
    # -PaleLabels: pale cyan text, no backing. -StraddleLabels: plates on the divider band (y~530).
    # -BlankPlate: dark plate without glyphs (the 2026-09-25 quad-on-text-plane regression).
    # -SolidGlyphs: one solid bright rectangle instead of glyphs (uniform fill must be rejected).
    $labelRects = @(@(788, 406), @(960, 406), @(1131, 406), @(960, 274), @(960, 651), @(1134, 651))
    if (-not $NoLabels) {
        foreach ($lr in $labelRects) {
            $ly = $lr[1]
            $isBottom = $ly -ge 600
            if ($StraddleLabels -and $isBottom) { $ly = 530 }
            if ($PaleLabels) {
                $brush.Color = [System.Drawing.Color]::FromArgb(168, 196, 224)
                $g.FillRectangle($brush, $lr[0] - 48, $ly - 20, 97, 20)
            } elseif ($isBottom) {
                $brush.Color = [System.Drawing.Color]::FromArgb(28, 28, 34)
                $g.FillRectangle($brush, $lr[0] - 70, $ly - 21, 140, 42)
                if (-not $BlankPlate) {
                    $brush.Color = [System.Drawing.Color]::FromArgb(205, 220, 255)
                    if ($SolidGlyphs) {
                        $g.FillRectangle($brush, $lr[0] - 60, $ly - 10, 120, 20)
                    } else {
                        for ($i = 0; $i -lt 8; $i++) { $g.FillRectangle($brush, $lr[0] - 52 + $i * 13, $ly - 10, 8, 20) }
                    }
                }
            } else {
                $brush.Color = [System.Drawing.Color]::White
                $g.FillRectangle($brush, $lr[0] - 48, $ly - 20, 97, 20)
            }
        }
    }
    if ($VerticalText) { $brush.Color = [System.Drawing.Color]::White; $g.FillRectangle($brush, 800, 120, 24, 260) }
    $g.Dispose(); $brush.Dispose()
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}

function New-K2Fixture([string]$Path, [switch]$Clipped, [switch]$NoTitle, [switch]$TopClipped) {
    # H1 MEDUSA title as DARK glyphs on the REAL band (measured on the 2026-09-25 packaged K2:
    # dark rows y31..123, columns x392..1524, ~12.5k dark px at stride 2). Assert-S05K2TitleGlyphs
    # scans dark pixels in y10..139 x340..1579 ONLY: above it the bright sky strip (luma>140),
    # below it the dark backdrop band starting at y150 - both reproduced here so the fixture
    # exercises the scan-window boundaries. -NoTitle drops the glyphs for the missing-title
    # negative; -TopClipped puts the band at row 0 (top-clipped title); -Clipped adds a tall dark
    # column at the right frame edge for the framing gate.
    $bmp = New-Object System.Drawing.Bitmap(1920, 1080)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::FromArgb(148, 146, 140))
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(40, 40, 44))
    $g.FillRectangle($brush, 300, 150, 1320, 300)
    $brush.Color = [System.Drawing.Color]::FromArgb(20, 20, 24)
    $g.FillRectangle($brush, 820, 300, 300, 500)
    if (-not $NoTitle) {
        $brush.Color = [System.Drawing.Color]::Black
        $ty = 36
        if ($TopClipped) { $ty = 0 }
        for ($i = 0; $i -lt 9; $i++) { $g.FillRectangle($brush, 640 + $i * 57, $ty, 34, 84) }
    }
    if ($Clipped) { $brush.Color = [System.Drawing.Color]::Black; $g.FillRectangle($brush, 1830, 120, 90, 700) }
    $g.Dispose(); $brush.Dispose()
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}

function New-K3Fixture([string]$Path, [switch]$NoText, [switch]$NoBodies) {
    # Scene panel fixture at the MEASURED panel rect (1140,24)-(1900,408): the panel backing lifts
    # a dark background (luma>90 vs <90 around) and 7 white text lines sit at the computed line
    # centers (54,96,150,222,268,306,344), keeping >20px clear of every frame edge. The background
    # is LIGHT so the silhouette gate (dark fighter windows at x925..995, y408..480 / y550..620)
    # has to find the two dark combatant rectangles; -NoBodies removes them.
    $bmp = New-Object System.Drawing.Bitmap(1920, 1080)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::FromArgb(40, 40, 44))
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(230, 228, 225))
    $g.FillRectangle($brush, 300, 30, 1400, 870)
    $brush.Color = [System.Drawing.Color]::FromArgb(100, 98, 140)
    $g.FillRectangle($brush, 1140, 24, 760, 384)
    if (-not $NoText) {
        $brush.Color = [System.Drawing.Color]::White
        foreach ($ly in @(54, 96, 150, 222, 268, 306, 344)) { $g.FillRectangle($brush, 1180, $ly - 14, 680, 28) }
    }
    if (-not $NoBodies) {
        $brush.Color = [System.Drawing.Color]::FromArgb(60, 60, 64)
        $g.FillRectangle($brush, 936, 412, 56, 64)
        $g.FillRectangle($brush, 936, 554, 56, 62)
    }
    $g.Dispose(); $brush.Dispose()
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}

$goodLog = @'
S05_REF_READY map=Reference active=1
S05_REF_SCENE figures=6 selection=1 target=1 k3_actors=3
S05_K3_HUD panel=scene hud_actors=8
S05_MEDUSA_RM AM_Medusa_Idle=(0.00,0.00,0.00) AM_Medusa_LungeAttack=(0.00,-0.00,0.00) AM_Medusa_HitReact=(0.00,0.00,0.00) AM_Medusa_DeathSettle=(0.00,0.00,0.00)
S05_FRAME_STATS frames=2100 avg_ms=2.2 min_ms=0.6 max_ms=210.0 note=dev-machine-not-target-D07
S05_ROOTMOTION_RESULT delta=(x=0.00 y=100.00 z=0.00) rm_frames=926
S05_REF_COMPLETE elapsed=16.10
'@

$k1Good = Join-Path $fixtureDir 'frame-K1-overview.png'
$k2Good = Join-Path $fixtureDir 'frame-K2-closeup.png'
$k3Good = Join-Path $fixtureDir 'frame-K3-combat.png'
New-K1Fixture $k1Good ([System.Drawing.Color]::FromArgb(120, 160, 220)) ([System.Drawing.Color]::FromArgb(200, 80, 60))
New-K2Fixture $k2Good
New-K3Fixture $k3Good
$frames1920 = @($k1Good, $k2Good, $k3Good)

$cases = @(
    @{ name = 'valid log + 1920x1080 frames + pixel gates -> PASS'
       log = $goodLog; frames = $frames1920; expectFail = $false },
    @{ name = 'root motion y=0 -> FAIL'
       log = $goodLog -replace 'y=100\.00', 'y=0.00'; frames = $frames1920; expectFail = $true },
    @{ name = 'root motion y=10000 -> FAIL'
       log = $goodLog -replace 'y=100\.00', 'y=10000.00'; frames = $frames1920; expectFail = $true },
    @{ name = 'root motion x drift 50 -> FAIL'
       log = $goodLog -replace 'x=0\.00', 'x=50.00'; frames = $frames1920; expectFail = $true },
    @{ name = 'root motion non-numeric text -> FAIL'
       log = $goodLog -replace 'delta=\(x=0\.00 y=100\.00 z=0\.00\)', 'delta=completed'; frames = $frames1920; expectFail = $true },
    @{ name = 'figures=5 -> FAIL'
       log = $goodLog -replace 'figures=6', 'figures=5'; frames = $frames1920; expectFail = $true },
    @{ name = 'missing S05_REF_COMPLETE -> FAIL'
       log = $goodLog -replace 'S05_REF_COMPLETE elapsed=16\.10', ''; frames = $frames1920; expectFail = $true },
    @{ name = 'missing S05_MEDUSA_RM -> FAIL'
       log = $goodLog -replace 'S05_MEDUSA_RM[^\r\n]*', ''; frames = $frames1920; expectFail = $true },
    @{ name = 'Medusa clip with root motion -> FAIL'
       log = $goodLog -replace 'AM_Medusa_Idle=\(0\.00,0\.00,0\.00\)', 'AM_Medusa_Idle=(12.00,0.00,0.00)'; frames = $frames1920; expectFail = $true },
    @{ name = 'missing S05_K3_HUD marker -> FAIL'
       log = $goodLog -replace 'S05_K3_HUD[^\r\n]*', ''; frames = $frames1920; expectFail = $true }
)
$smallFrame = Join-Path $fixtureDir 'small.png'
New-FixturePng $smallFrame 888 500
$cases += @{ name = '888x500 frame -> FAIL'
             log = $goodLog; frames = @($smallFrame); expectFail = $true }
$missingFrame = Join-Path $fixtureDir 'missing.png'
$cases += @{ name = 'missing frame file -> FAIL'
             log = $goodLog; frames = @($missingFrame); expectFail = $true }

# pixel-gate negatives (review P1-1..P1-4)
$k1NoZone = Join-Path $fixtureDir 'frame-K1-nozone.png'
New-K1Fixture $k1NoZone ([System.Drawing.Color]::FromArgb(120, 120, 122)) ([System.Drawing.Color]::FromArgb(122, 120, 120))
$cases += @{ name = 'K1 zones same color -> FAIL'; log = $goodLog; frames = @($k1NoZone, $k2Good, $k3Good); expectFail = $true }

$k1NoLabels = Join-Path $fixtureDir 'frame-K1-nolabels.png'
New-K1Fixture $k1NoLabels ([System.Drawing.Color]::FromArgb(120, 160, 220)) ([System.Drawing.Color]::FromArgb(200, 80, 60)) -NoLabels
$cases += @{ name = 'K1 labels absent -> FAIL'; log = $goodLog; frames = @($k1NoLabels, $k2Good, $k3Good); expectFail = $true }

$k1Vertical = Join-Path $fixtureDir 'frame-K1-vertical.png'
New-K1Fixture $k1Vertical ([System.Drawing.Color]::FromArgb(120, 160, 220)) ([System.Drawing.Color]::FromArgb(200, 80, 60)) -VerticalText
$cases += @{ name = 'K1 vertical text regression -> FAIL'; log = $goodLog; frames = @($k1Vertical, $k2Good, $k3Good); expectFail = $true }

# review P1 negatives (2026-09-25): pale seat labels without backing / bottom labels on divider
$k1Pale = Join-Path $fixtureDir 'frame-K1-palelabels.png'
New-K1Fixture $k1Pale ([System.Drawing.Color]::FromArgb(120, 160, 220)) ([System.Drawing.Color]::FromArgb(200, 80, 60)) -PaleLabels
$cases += @{ name = 'K1 pale seat labels without dark backing -> FAIL'; log = $goodLog; frames = @($k1Pale, $k2Good, $k3Good); expectFail = $true }

$k1Straddle = Join-Path $fixtureDir 'frame-K1-straddle.png'
New-K1Fixture $k1Straddle ([System.Drawing.Color]::FromArgb(120, 160, 220)) ([System.Drawing.Color]::FromArgb(200, 80, 60)) -StraddleLabels
$cases += @{ name = 'K1 bottom-team labels straddling the zone divider -> FAIL'; log = $goodLog; frames = @($k1Straddle, $k2Good, $k3Good); expectFail = $true }

# blank-plate negatives (2026-09-25 correction): the plate gates must fail on glyph-less plates
$k1Blank = Join-Path $fixtureDir 'frame-K1-blankplate.png'
New-K1Fixture $k1Blank ([System.Drawing.Color]::FromArgb(120, 160, 220)) ([System.Drawing.Color]::FromArgb(200, 80, 60)) -BlankPlate
$cases += @{ name = 'K1 blank dark plates without glyphs -> FAIL'; log = $goodLog; frames = @($k1Blank, $k2Good, $k3Good); expectFail = $true }

$k1Solid = Join-Path $fixtureDir 'frame-K1-solidglyphs.png'
New-K1Fixture $k1Solid ([System.Drawing.Color]::FromArgb(120, 160, 220)) ([System.Drawing.Color]::FromArgb(200, 80, 60)) -SolidGlyphs
$cases += @{ name = 'K1 solid uniform bright rectangles on plates (no glyph gaps) -> FAIL'; log = $goodLog; frames = @($k1Solid, $k2Good, $k3Good); expectFail = $true }

$cases += @{ name = 'real K1 frame with blank f-1 plates (2026-09-25 capture, 0 glyph px) -> FAIL'
             log = $goodLog; frames = @($realK1BlankPlate, $k2Good, $k3Good); expectFail = $true }

$k2Clipped = Join-Path $fixtureDir 'frame-K2-clipped.png'
New-K2Fixture $k2Clipped -Clipped
$cases += @{ name = 'K2 clipped silhouette at edge -> FAIL'; log = $goodLog; frames = @($k1Good, $k2Clipped, $k3Good); expectFail = $true }

# P1 final correction negatives: the title gate scans DARK glyphs in the true top band (y10..139).
# Synthetic: no title / title pushed against row 0 (top-clipped). Real: the -S05NoK2Title capture.
$k2NoTitle = Join-Path $fixtureDir 'frame-K2-notitle.png'
New-K2Fixture $k2NoTitle -NoTitle
$cases += @{ name = 'K2 hero title glyphs missing -> FAIL'; log = $goodLog; frames = @($k1Good, $k2NoTitle, $k3Good); expectFail = $true }

$k2TopClipped = Join-Path $fixtureDir 'frame-K2-topclipped.png'
New-K2Fixture $k2TopClipped -TopClipped
$cases += @{ name = 'K2 hero title touching the top frame edge (band at row 0) -> FAIL'; log = $goodLog; frames = @($k1Good, $k2TopClipped, $k3Good); expectFail = $true }

$realK2NoTitle = Join-Path $PSScriptRoot 'fixtures/frame-K2-notitle-real.png'
if (-not (Test-Path -LiteralPath $realK2NoTitle -PathType Leaf)) { throw "Real negative fixture missing: $realK2NoTitle" }
$cases += @{ name = 'real K2 frame with the hero title suppressed (2026-09-25 -S05NoK2Title capture, 0 dark rows in window) -> FAIL'
             log = $goodLog; frames = @($k1Good, $realK2NoTitle, $k3Good); expectFail = $true }

$k3NoHud = Join-Path $fixtureDir 'frame-K3-nohud.png'
$img = New-Object System.Drawing.Bitmap(1920, 1080)
$g = [System.Drawing.Graphics]::FromImage($img)
$g.Clear([System.Drawing.Color]::FromArgb(60, 60, 64))
$g.Dispose(); $img.Save($k3NoHud, [System.Drawing.Imaging.ImageFormat]::Png); $img.Dispose()
$cases += @{ name = 'K3 scene panel missing -> FAIL'; log = $goodLog; frames = @($k1Good, $k2Good, $k3NoHud); expectFail = $true }

$k3NoText = Join-Path $fixtureDir 'frame-K3-notext.png'
New-K3Fixture $k3NoText -NoText
$cases += @{ name = 'K3 scene panel without readable text lines -> FAIL'; log = $goodLog; frames = @($k1Good, $k2Good, $k3NoText); expectFail = $true }

$cases += @{ name = 'real K3 frame without visible HUD (2026-09-25 capture) -> FAIL'
             log = $goodLog; frames = @($k1Good, $k2Good, $realK3NoHud); expectFail = $true }

# P0 negatives: staged combatants missing (the preserved real missing-bodies capture +
# the synthetic no-bodies panel fixture); the silhouette gate must fail both
$realK3NoBodies = Join-Path $PSScriptRoot 'fixtures/frame-K3-nobodies-real.png'
if (-not (Test-Path -LiteralPath $realK3NoBodies -PathType Leaf)) { throw "Real negative fixture missing: $realK3NoBodies" }
$cases += @{ name = 'real K3 frame without fighter bodies (2026-09-25 capture, attacker 215/4 target 110/1) -> FAIL'
             log = $goodLog; frames = @($k1Good, $k2Good, $realK3NoBodies); expectFail = $true }

$k3NoBodies = Join-Path $fixtureDir 'frame-K3-nobodies.png'
New-K3Fixture $k3NoBodies -NoBodies
$cases += @{ name = 'K3 scene panel present but combatant silhouettes missing -> FAIL'; log = $goodLog; frames = @($k1Good, $k2Good, $k3NoBodies); expectFail = $true }

$cases += @{ name = 'real K2 frame with top-clipped label (2026-09-25 capture) -> FAIL'
             log = $goodLog; frames = @($k1Good, $realK2Clipped, $k3Good); expectFail = $true }

$failed = 0
foreach ($case in $cases) {
    $threw = $false
    $reason = ''
    try {
        Assert-S05Run -LogText $case.log -FramePaths $case.frames | Out-Null
    } catch {
        $threw = $true
        $reason = $_.Exception.Message
    }
    if ($case.expectFail -and -not $threw) {
        Write-Output "SELFTEST FAIL (expected throw, got PASS): $($case.name)"
        $failed++
    } elseif (-not $case.expectFail -and $threw) {
        Write-Output "SELFTEST FAIL (expected PASS, threw): $($case.name) -- $reason"
        $failed++
    } else {
        $detail = 'passed'
        if ($threw) { $detail = "threw: $reason" }
        Write-Output "SELFTEST OK: $($case.name) ($detail)"
    }
}
# cleanup hardening: only ever delete the exact TEMP/s05-selftest-<8hex> directory this run
# created. Resolve the absolute path first, require it to sit inside the TEMP root, and require
# the expected basename - then remove via -LiteralPath. Anything else is refused loudly.
$fixtureFull = [System.IO.Path]::GetFullPath($fixtureDir)
$tempRootFull = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\', '/')
$fixtureBase = [System.IO.Path]::GetFileName($fixtureFull.TrimEnd('\', '/'))
if (-not $fixtureFull.StartsWith($tempRootFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Selftest cleanup refused: '$fixtureFull' is not inside the TEMP root '$tempRootFull'"
}
if ($fixtureBase -notmatch '^s05-selftest-[0-9a-f]{8}$') {
    throw "Selftest cleanup refused: unexpected fixture basename '$fixtureBase'"
}
if (Test-Path -LiteralPath $fixtureFull -PathType Container) {
    Remove-Item -LiteralPath $fixtureFull -Recurse -Force
}
if ($failed -gt 0) { throw "S05 smoke selftest: $failed case(s) misbehaved" }
Write-Output "S05 smoke selftest PASS: $($cases.Count) cases"
