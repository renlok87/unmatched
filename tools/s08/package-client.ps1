param(
  [string]$Log = (Join-Path ([System.IO.Path]::GetTempPath()) 's08-uat.log')
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

$argList = @(
  'BuildCookRun',
  "-project=$Uproject",
  '-noP4', '-platform=Win64', '-clientconfig=Development',
  '-cook', '-stage', '-pak', '-package', '-compressed', '-build',
  '-unattended', '-nosplash',
  '-AdditionalCookerArgs=-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:bAutoStartServer=False'
)
$p = Start-Process -FilePath $Uat -ArgumentList $argList -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"
Write-Output "UAT_EXIT=$($p.ExitCode)"
if ($p.ExitCode -ne 0) { throw "RunUAT failed with exit code $($p.ExitCode); see $Log" }
