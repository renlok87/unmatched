param(
  [string]$Log = (Join-Path ([System.IO.Path]::GetTempPath()) 's08-uat.log'),
  # Cook+stage the already built game binary. Use when an editor with Live
  # Coding blocks the UnmatchedEditor build step of BuildCookRun -build.
  [switch]$SkipBuild
)
# Hidden RunUAT package (Development, cook+stage+pak).
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Uproject = Join-Path $RepoRoot 'unreal\Unmatched\Unmatched.uproject'
$ueRoot = if ($env:UE_ROOT) { $env:UE_ROOT } else { 'C:\Program Files\Epic Games\UE_5.8' }
$Uat = Join-Path $ueRoot 'Engine\Build\BatchFiles\RunUAT.bat'
if (-not (Test-Path $Uat)) { throw "RunUAT.bat not found: $Uat" }
$logDir = Split-Path -Parent $Log
if ($logDir -and -not (Test-Path -LiteralPath $logDir)) {
  New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Committed-intent asset gate: S08 packaging requires its map/materials.
# Earlier sprint maps may also be cooked after branch integration. Content/ is gitignored by
# unreal/Unmatched/.gitignore, so a clean checkout needs these three binaries
# force-added or packaging fails here with an explicit reason.
$ProjectDir = Join-Path $RepoRoot 'unreal\Unmatched'
$requiredAssets = @(
  'Content\S08\S08Arena.umap',
  'Content\S08\M_S08_Tile.uasset',
  'Content\S08\M_S08_Solid.uasset'
)
foreach ($rel in $requiredAssets) {
  $p = Join-Path $ProjectDir $rel
  if (-not (Test-Path $p)) {
    throw "required S08 asset missing (clean checkout without force-added binaries?): $p"
  }
}
git -C $RepoRoot check-ignore unreal/Unmatched/Content/S08/S08Arena.umap *> $null
if ($LASTEXITCODE -eq 0) {
  Write-Output 'WARN: unreal/Unmatched/Content/S08 is gitignored; these binaries must be force-added at commit time or clean-checkout packaging will fail the gate above'
}

# -skipbuild stages Binaries\Win64\Unmatched.exe as it is. A game target built
# with UBT -NoLiveCoding compiles WITH_LIVE_CODING=0 (so WITH_RELOAD=0 in a
# monolithic game) against the installed engine's precompiled UnrealGame
# objects built with WITH_RELOAD=1. The packaged client can then crash in UObject
# class registration before the map loads, as the ART-004 v3 live run did (2026-09-28).
if ($SkipBuild) {
  $gameDefs = Join-Path $ProjectDir 'Intermediate\Build\Win64\x64\Unmatched\Development'
  $defs = @(Get-ChildItem -LiteralPath $gameDefs -Recurse -Filter 'SharedDefinitions.*.h' -ErrorAction SilentlyContinue)
  if ($defs.Count -eq 0) { throw "no game-target SharedDefinitions under $gameDefs; build the Unmatched game target before -SkipBuild" }
  $noLive = @($defs | Select-String -SimpleMatch '#define WITH_LIVE_CODING 0' -List)
  if ($noLive.Count -gt 0) {
    throw "game target was built with -NoLiveCoding ($($noLive[0].Path)); rebuild Unmatched Win64 Development without -NoLiveCoding"
  }
}

$argList = @(
  'BuildCookRun',
  "-project=$Uproject",
  '-noP4', '-platform=Win64', '-clientconfig=Development',
  '-cook', '-stage', '-pak', '-package', '-compressed',
  $(if ($SkipBuild) { '-skipbuild' } else { '-build' }),
  '-unattended', '-nosplash',
  '-AdditionalCookerArgs=-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:bAutoStartServer=False'
)
$p = Start-Process -FilePath $Uat -ArgumentList $argList -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"
Write-Output "UAT_EXIT=$($p.ExitCode)"
if ($p.ExitCode -ne 0) { throw "RunUAT failed with exit code $($p.ExitCode); see $Log" }

# Stamp the staged build with the source hash it was packaged from: tools/s08/sync-staged-build.ps1 copies it into
# another checkout only when that checkout's sources hash the same (AGENTS.md "Iteration speed": one package per change).
$staged = Join-Path $ProjectDir 'Saved\StagedBuilds\Windows'
if (Test-Path -LiteralPath $staged) {
  . (Join-Path $PSScriptRoot 'staged-build-stamp.ps1')
  $src = Get-UnmatchedSourceHash $RepoRoot
  $stamp = [ordered]@{
    schema = 'unmatched.staged-build-stamp/1'
    commit = (git -C $RepoRoot rev-parse HEAD).Trim()
    sourceHash = $src.hash
    sourceFiles = $src.files
    builtAt = (Get-Date).ToString('o')
    skipBuild = [bool]$SkipBuild
  }
  $stamp | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $staged 'BuildStamp.json') -Encoding UTF8
  Write-Output "STAMP sourceHash=$($src.hash) files=$($src.files)"
}
