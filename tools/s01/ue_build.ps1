param(
 [string]$Engine = 'C:/Program Files/Epic Games/UE_5.8',
 [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$project = "$root/unreal/Unmatched/Unmatched.uproject"
$work = "$root/unreal/Unmatched"
function Invoke-Checked([string]$Exe, [string[]]$Arguments, [string]$Log) {
 & $Exe @Arguments *> $Log
 if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Exe. See $Log" }
}
Invoke-Checked $Blender @('--background','--factory-startup','--python',"$PSScriptRoot/ue_blender_probe.py") "$work/blender-output.txt"
Invoke-Checked "$Engine/Engine/Build/BatchFiles/Build.bat" @('UnmatchedEditor','Win64','Development',$project,'-WaitMutex','-NoHotReloadFromIDE','-NoLiveCoding') "$work/editor-build.txt"
Invoke-Checked "$Engine/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" @($project,'-run=pythonscript',"-script=$PSScriptRoot/ue_import_scene.py",'-unattended','-nosplash','-nullrhi','-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False') "$work/import-output.txt"
# Game target WITHOUT -NoLiveCoding (R14, ART-004 v3-live-hookup diagnosis): in a monolithic game it
# sets WITH_RELOAD=0 against the precompiled UnrealGame engine (WITH_RELOAD=1); the packaged client can
# then crash in UClass registration. -NoLiveCoding stays only on the UnmatchedEditor line above.
Invoke-Checked "$Engine/Engine/Build/BatchFiles/Build.bat" @('Unmatched','Win64','Development',$project,'-WaitMutex','-NoHotReloadFromIDE') "$work/game-build.txt"
Invoke-Checked "$Engine/Engine/Build/BatchFiles/RunUAT.bat" @('BuildCookRun',"-project=$project",'-noP4','-platform=Win64','-clientconfig=Development','-nocompileeditor','-skipbuildeditor','-cook','-stage','-pak','-archive',"-archivedirectory=$work/Artifacts/S01",'-unattended','-utf8output') "$work/package-output.txt"
Write-Output "Packaged executable: $work/Artifacts/S01/Windows/Unmatched/Binaries/Win64/Unmatched.exe"
