param(
  # The checkout whose staged build is copied (default: the ENV-MAPS worktree).
  [string]$From = 'C:\tmp\wt-envmaps',
  # Only report what would happen.
  [switch]$DryRun
)
# Copy a packaged client from a worktree into this checkout instead of repackaging (AGENTS.md "Iteration speed").
# Refuses unless the staged build's BuildStamp.json (written by package-client.ps1) carries the same source hash as
# this checkout (unreal/Unmatched/Source + Config + .uproject), and no client of this checkout is running.
# Content/ is not covered by the hash: sync the gitignored Content folders first (as after every integration).
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'staged-build-stamp.ps1')
$To = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$From = (Resolve-Path $From).Path
if ($From -eq $To) { throw "From and To are the same checkout: $To" }
$src = Join-Path $From 'unreal\Unmatched\Saved\StagedBuilds\Windows'
$dst = Join-Path $To 'unreal\Unmatched\Saved\StagedBuilds\Windows'
$stampPath = Join-Path $src 'BuildStamp.json'
if (-not (Test-Path -LiteralPath $stampPath)) { throw "no BuildStamp.json in $src (package with tools/s08/package-client.ps1 first)" }
$stamp = Get-Content -LiteralPath $stampPath -Raw | ConvertFrom-Json
$mine = Get-UnmatchedSourceHash $To
Write-Output "STAMP commit=$($stamp.commit) sourceHash=$($stamp.sourceHash) files=$($stamp.sourceFiles) builtAt=$($stamp.builtAt)"
Write-Output "HERE  commit=$((git -C $To rev-parse HEAD).Trim()) sourceHash=$($mine.hash) files=$($mine.files)"
if ($stamp.sourceHash -ne $mine.hash) {
  throw 'source hash differs: the staged build was not made from this checkout''s sources - integrate first or repackage'
}
$running = @(Get-CimInstance Win32_Process -Filter "Name='Unmatched.exe' OR Name='Unmatched-Win64-Shipping.exe'" |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($dst, [StringComparison]::OrdinalIgnoreCase) })
if ($running.Count -gt 0) { throw "a client of this checkout is running (pid $($running[0].ProcessId)); close it first" }
if ($DryRun) { Write-Output "DRYRUN would mirror $src -> $dst"; exit 0 }
robocopy $src $dst /MIR /R:1 /W:1 /NFL /NDL /NP /NJH | Select-Object -Last 6
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with $LASTEXITCODE" }
Write-Output "SYNC-STAGED-BUILD OK $src -> $dst"
exit 0
