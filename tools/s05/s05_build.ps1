param(
 [string]$Engine = 'C:/Program Files/Epic Games/UE_5.8',
 [switch]$SkipEditorBuild,
 [switch]$SkipPackage
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$project = "$root/unreal/Unmatched/Unmatched.uproject"
$work = "$root/unreal/Unmatched"
function Invoke-Checked([string]$Exe, [string[]]$Arguments, [string]$Log) {
 & $Exe @Arguments *> $Log
 if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Exe. See $Log" }
 # Build.bat can exit 0 even on a compile failure (2026-09-25 session: a C3553 error in
 # SmokeGameMode.cpp produced exit 0 and the stale exe was packaged); trust the UBT result line.
 if ((Get-Content $Log -Raw) -match 'Result: Failed') { throw "Command reported 'Result: Failed': $Exe. See $Log" }
}
if (-not $SkipEditorBuild) {
 Invoke-Checked "$Engine/Engine/Build/BatchFiles/Build.bat" @('UnmatchedEditor','Win64','Development',$project,'-WaitMutex','-NoHotReloadFromIDE','-NoLiveCoding') "$work/s05-editor-build.txt"
}
$importEvidence = "$root/docs/game-design/evidence/S05/art-references/s05-import-result.json"
if (Test-Path -LiteralPath $importEvidence) { Remove-Item -LiteralPath $importEvidence -Force }
Invoke-Checked "$Engine/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" @($project,'-run=pythonscript',"-script=$PSScriptRoot/s05_import_scene.py",'-unattended','-nosplash','-nullrhi','-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False') "$work/s05-import-output.txt"
# the commandlet process exits 0 even when the python script raises (2026-09-25: a failed import
# left the stale evidence JSON in place and the chain packaged old content); gate on the log
if ((Get-Content "$work/s05-import-output.txt" -Raw) -match 'Python script executed with errors|LogPython: Error: Traceback') {
    throw "Import script raised (see $work/s05-import-output.txt)"
}
if (-not (Test-Path -LiteralPath $importEvidence)) { throw "Import evidence JSON missing (script died before writing it): $work/s05-import-output.txt" }
Invoke-Checked "$Engine/Engine/Build/BatchFiles/Build.bat" @('Unmatched','Win64','Development',$project,'-WaitMutex','-NoHotReloadFromIDE','-NoLiveCoding') "$work/s05-game-build.txt"
if (-not $SkipPackage) {
 # -NoXGE: the material gained a SkeletalMesh usage flag, so the cooker must compile a new shadermap;
 # the XGE Controller path hangs on this machine (license not activated) and the cook stalls forever.

 Invoke-Checked "$Engine/Engine/Build/BatchFiles/RunUAT.bat" @('BuildCookRun',"-project=$project",'-noP4','-platform=Win64','-clientconfig=Development','-nocompileeditor','-skipbuildeditor','-cook','-stage','-pak','-archive',"-archivedirectory=$work/Artifacts/S05",'-unattended','-utf8output','-NoXGE') "$work/s05-package-output.txt"
}
Write-Output "Packaged executable: $work/Artifacts/S05/Windows/Unmatched/Binaries/Win64/Unmatched.exe"
