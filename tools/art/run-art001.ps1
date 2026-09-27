param(
    [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe',
    [string]$Engine = 'C:/Program Files/Epic Games/UE_5.8'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$check = "$root/blender/_shared/check_set"
$project = "$root/unreal/Unmatched/Unmatched.uproject"
$logDir = "$root/unreal/Unmatched/Artifacts/ART001"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$contentRoot = [IO.Path]::GetFullPath("$root/unreal/Unmatched/Content")
$art001Content = [IO.Path]::GetFullPath((Join-Path $contentRoot 'ArtTests/ART001'))
$contentPrefix = $contentRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $art001Content.StartsWith($contentPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe ART-001 content path: $art001Content"
}

function Invoke-CheckedProcess {
    param([string]$Exe, [string[]]$Arguments, [string]$Log, [string]$RequiredMarker)
    if (Test-Path -LiteralPath $Log) { Remove-Item -LiteralPath $Log -Force }
    $process = Start-Process -FilePath $Exe -ArgumentList $Arguments -WindowStyle Hidden -PassThru -Wait `
        -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"
    if ($process.ExitCode -ne 0) { throw "Command failed ($($process.ExitCode)): $Exe. See $Log" }
    $text = (Get-Content -LiteralPath $Log -Raw) + (Get-Content -LiteralPath "$Log.err" -Raw)
    if ($text -match 'Traceback|Python script executed with errors|Result: Failed') {
        throw "Command reported an error: $Exe. See $Log"
    }
    if ($RequiredMarker -and $text -notmatch [regex]::Escape($RequiredMarker)) {
        throw "Required marker '$RequiredMarker' missing. See $Log"
    }
}

Invoke-CheckedProcess $Blender @('--background','--factory-startup','--python',"$root/blender/_tools/build_check_set.py") `
    "$logDir/blender-build.txt" 'ART001_BUILD'
Invoke-CheckedProcess $Blender @('--background','--factory-startup',"$root/blender/_shared/check_set.blend",'--python',"$root/blender/_tools/mesh_report.py") `
    "$logDir/blender-report.txt" '"result": "PASS"'
Invoke-CheckedProcess $Blender @('--background','--factory-startup','--python',"$root/blender/_tools/batch_export.py",'--','--all') `
    "$logDir/blender-export.txt" 'ART001_EXPORT_COMPLETE'

$manifest = "$check/export/export-manifest.json"
if (-not (Test-Path -LiteralPath $manifest)) { throw "Missing export manifest: $manifest" }
$files = (Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json).files
if ($files.Count -ne 6) { throw "Expected 6 FBX files, got $($files.Count)" }
if (($files | Where-Object { $_.unit_scale_factor_after_patch -ne 1.0 }).Count -ne 0) {
    throw 'Not every FBX has UnitScaleFactor=1.0'
}

$ueLog = "$logDir/ue-import.txt"
Invoke-CheckedProcess "$Engine/Engine/Build/BatchFiles/Build.bat" `
    @('UnmatchedEditor','Win64','Development',$project,'-WaitMutex','-NoHotReloadFromIDE','-NoLiveCoding','-MaxParallelActions=4') `
    "$logDir/ue-editor-build.txt" ''
if (Test-Path -LiteralPath $art001Content) {
    Remove-Item -LiteralPath $art001Content -Recurse -Force
}
Invoke-CheckedProcess "$Engine/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" `
    @($project,'-run=pythonscript',"-script=$root/tools/art/art001_import_verify.py",'-unattended','-nosplash','-nullrhi','-DisablePlugins=Tripo3DUEBridge','-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False') `
    $ueLog 'Python script executed successfully'

$ueReport = "$check/ue-import-report.json"
if (-not (Test-Path -LiteralPath $ueReport)) { throw "Missing UE report: $ueReport" }
$failed = (Get-Content -LiteralPath $ueReport -Raw | ConvertFrom-Json).checks.PSObject.Properties | `
    Where-Object { -not $_.Value.ok }
if ($failed.Count -ne 0) { throw "ART-001 checks failed: $($failed.Name -join ', ')" }

Invoke-CheckedProcess "$Engine/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" `
    @($project,"-ExecutePythonScript=$root/tools/art/art001_capture.py",'-unattended','-nosplash','-RenderOffScreen','-stdout','-FullStdOutLogOutput','-DisablePlugins=Tripo3DUEBridge','-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False') `
    "$logDir/ue-capture.txt" 'ART001_CAPTURE_COMPLETE'

$overview = "$check/preview/ue-art001-overview.png"
$normalProbe = "$check/preview/ue-art001-normal-probe.png"
foreach ($evidence in @($overview, $normalProbe)) {
    if (-not (Test-Path -LiteralPath $evidence) -or (Get-Item -LiteralPath $evidence).Length -eq 0) {
        throw "Missing ART-001 visual evidence: $evidence"
    }
}

Write-Output "ART-001 PASS: $check/REPORT.md"
