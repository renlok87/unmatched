param([string]$ReportPath)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not $ReportPath) {
    $ReportPath = Join-Path $repoRoot 'docs/game-design/evidence/S02/harness-results.json'
}
$ReportPath = [System.IO.Path]::GetFullPath($ReportPath)
$reportDirectory = Split-Path -Parent $ReportPath
New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
$previousReport = $env:S02_REPORT
try {
    $env:S02_REPORT = $ReportPath
    Push-Location (Join-Path $repoRoot 'backend')
    try {
        & npm.cmd test -- --runInBand s02-combat.spec.ts
        if ($LASTEXITCODE -ne 0) { throw "S02 gameplay harness failed (exit $LASTEXITCODE)." }
    } finally { Pop-Location }
    $report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
    if ($report.observations.Count -ne 22) { throw 'Incomplete S02 report.' }
    Write-Output "S02: 18 gameplay scenarios passed (22 observations). HP/outcomes: $ReportPath"
} finally { $env:S02_REPORT = $previousReport }
