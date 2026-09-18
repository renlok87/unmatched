param([int]$TimeoutSeconds = 60)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$work = "$root/unreal/Unmatched"
$exe = "$work/Artifacts/S01/Windows/Unmatched/Binaries/Win64/Unmatched.exe"
$log = "$work/runtime-output.txt"
$screenshot = "$work/Artifacts/S01/Windows/Unmatched/Saved/Screenshots/Windows/S01Smoke.png"
# Remove only these two exact run outputs; never accept leftovers from a prior run.
foreach ($output in @($log, $screenshot)) {
 if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Force }
}
$runStartedUtc = [DateTime]::UtcNow
$process = Start-Process -FilePath $exe -ArgumentList @('-S01Smoke','-unattended','-nosplash','-windowed','-RenderOffscreen','-ResX=1280','-ResY=720',('-abslog="'+$log+'"')) -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) { throw "Smoke process $($process.Id) did not exit within $TimeoutSeconds seconds. Inspect $log" }
if ($process.ExitCode -ne 0) { throw "Smoke failed: exit $($process.ExitCode)" }
foreach ($output in @($log, $screenshot)) {
 if (-not (Test-Path -LiteralPath $output -PathType Leaf)) { throw "Fresh run output missing: $output" }
 $file = Get-Item -LiteralPath $output
 # Two seconds accommodates filesystem timestamp granularity; prior files were removed.
 if ($file.Length -eq 0 -or $file.LastWriteTimeUtc -lt $runStartedUtc.AddSeconds(-2)) { throw "Run output empty or stale: $output" }
}
$text = Get-Content $log -Raw
if ($text -notmatch 'S01_SMOKE_READY map=Smoke api=http://localhost:3000/graphql' -or $text -notmatch 'S01_SMOKE_COMPLETE') { throw 'Smoke markers or configured API URL missing' }
Copy-Item $screenshot "$root/docs/game-design/evidence/S01/ue/packaged-smoke.png" -Force
"EXIT_CODE=$($process.ExitCode)" | Set-Content "$work/runtime-exit.txt"
Write-Output "S01 packaged smoke PASS: exit 0; fresh log and screenshot; map, URL and completion markers. Started UTC: $($runStartedUtc.ToString('o'))"
