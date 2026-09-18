param([string]$ReportPath)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not $ReportPath) {
    $ReportPath = Join-Path $repoRoot 'docs/game-design/evidence/S03/transport-results.json'
}
$ReportPath = [System.IO.Path]::GetFullPath($ReportPath)
New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null
$previousReport = $env:S03_TRANSPORT_REPORT
try {
    $env:S03_TRANSPORT_REPORT = $ReportPath
    Push-Location (Join-Path $repoRoot 'backend')
    try {
        & npm.cmd test -- --runInBand s03-transport.spec.ts --silent
        if ($LASTEXITCODE -ne 0) { throw "S03 transport harness failed (exit $LASTEXITCODE)." }
    } finally { Pop-Location }
    $report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
    if ($report.checks.Count -ne 3 -or $report.http.Count -lt 20 -or $report.ws.Count -ne 14) {
        throw 'Incomplete S03 HTTP/WS evidence.'
    }
    Write-Output "S03 HTTP/WS: 3 scenarios, $($report.http.Count) HTTP responses, $($report.ws.Count) WS updates. $ReportPath"
} finally { $env:S03_TRANSPORT_REPORT = $previousReport }
