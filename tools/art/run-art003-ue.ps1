param(
    [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe',
    [string]$Engine = 'C:/Program Files/Epic Games/UE_5.8'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$project = "$root/unreal/Unmatched/Unmatched.uproject"
$source = "$root/blender/A01"
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$logs = "$root/unreal/Unmatched/Artifacts/ART003/$runId"
New-Item -ItemType Directory -Path $logs -Force | Out-Null

function Invoke-CheckedProcess {
    param([string]$Exe, [string[]]$Arguments, [string]$Name, [string]$RequiredMarker)
    $out = Join-Path $logs "$Name.txt"
    $err = Join-Path $logs "$Name.err.txt"
    $process = Start-Process -FilePath $Exe -ArgumentList $Arguments -WindowStyle Hidden -PassThru -Wait `
        -RedirectStandardOutput $out -RedirectStandardError $err
    $combined = (Get-Content -LiteralPath $out -Raw) + (Get-Content -LiteralPath $err -Raw)
    if ($process.ExitCode -ne 0 -or $combined -match 'Traceback|Python script executed with errors|ART003_CAPTURE_FAILED|Result: Failed') {
        throw "$Name failed (exit $($process.ExitCode)); inspect $out"
    }
    if ($combined -notmatch [regex]::Escape($RequiredMarker)) {
        throw "$Name missing marker $RequiredMarker; inspect $out"
    }
}

if (-not (Test-Path -LiteralPath "$root/unreal/Unmatched/Binaries/Win64/UnrealEditor-Unmatched.dll")) {
    Invoke-CheckedProcess "$Engine/Engine/Build/BatchFiles/Build.bat" `
        @('UnmatchedEditor','Win64','Development',$project,'-WaitMutex','-NoHotReloadFromIDE','-NoLiveCoding','-MaxParallelActions=4') `
        'ue-editor-build' ''
}
Invoke-CheckedProcess $Blender @('--background','--factory-startup','--python',"$root/blender/_tools/export_art003_blockouts.py") `
    'blender-export' 'ART003_EXPORT_COMPLETE 4'
$manifest = Get-Content -LiteralPath "$source/export/export-manifest.json" -Raw | ConvertFrom-Json
if ($manifest.files.Count -ne 4 -or ($manifest.files | Where-Object { $_.unit_scale_factor_after_patch -ne 1.0 }).Count -ne 0) {
    throw 'ART-003 FBX manifest failed count or unit-scale check'
}
$editor = "$Engine/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
Invoke-CheckedProcess $editor `
    @($project,'-run=pythonscript',"-script=$root/tools/art/art003_import_verify.py",'-unattended','-nosplash','-nullrhi','-DisablePlugins=Tripo3DUEBridge','-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False') `
    'ue-import' 'Python script executed successfully'
$report = Get-Content -LiteralPath "$source/ue-import-report.json" -Raw | ConvertFrom-Json
if ($report.status -ne 'editor_import_pass' -or $report.board.cells -ne 30 -or $report.fighter_instances.Count -ne 6) {
    throw 'ART-003 UE import report failed'
}
Invoke-CheckedProcess $editor `
    @($project,"-ExecutePythonScript=$root/tools/art/art003_capture.py",'-unattended','-nosplash','-RenderOffScreen','-stdout','-FullStdOutLogOutput','-DisablePlugins=Tripo3DUEBridge','-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False') `
    'ue-capture' 'ART003_CAPTURE_COMPLETE'
$capture = "$source/preview/ue-art003-k1-gray.png"
if (-not (Test-Path -LiteralPath $capture) -or (Get-Item -LiteralPath $capture).Length -eq 0) {
    throw "ART-003 UE K1 capture missing: $capture"
}
Write-Output "ART003_UE_PASS $source/ue-import-report.json $capture"
