# Deliberately interactive manual demo. For a hidden timed gate use ue_smoke.ps1.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$exe = "$root/unreal/Unmatched/Artifacts/S01/Windows/Unmatched.exe"
if (-not (Test-Path $exe)) { throw 'Build first with tools/s01/ue_build.ps1' }
Start-Process -FilePath $exe -ArgumentList @('-windowed','-ResX=1280','-ResY=720')
