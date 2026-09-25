param(
 [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$script = "$root/blender/S05/build_medusa.py"
$out = "$root/blender/S05/blender-output.txt"
$err = "$root/blender/S05/blender-error.txt"
foreach ($f in @($out, $err)) { if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force } }
$report = "$root/blender/S05/build-report.json"
if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report -Force }
$process = Start-Process -FilePath $Blender -ArgumentList @('--background','--factory-startup','--python',$script) -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err -Wait
if ($process.ExitCode -ne 0) { throw "Blender build failed ($($process.ExitCode)). See $err" }
# blender --background exits 0 even on python exceptions: gate on fresh artifacts, not exit code
if (-not (Test-Path -LiteralPath $report)) { throw "Blender build failed (no fresh build-report.json). See $err" }
$usf = (Select-String -LiteralPath $out -Pattern 'S05_USF_PATCH' -SimpleMatch).Count
$fbxCount = (Get-ChildItem -LiteralPath "$root/blender/S05/export" -Filter '*.fbx').Count
if ($usf -ne $fbxCount) { throw "UnitScaleFactor patch count mismatch: $usf patched / $fbxCount exported. See $out" }
Write-Output "Blender build PASS: report at blender/S05/build-report.json, USF patches: $usf/$fbxCount"
