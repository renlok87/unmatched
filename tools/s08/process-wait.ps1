# Start a hidden process and wait for THAT process only (dot-sourced by package-client.ps1).
#
# Windows PowerShell 5.1 `Start-Process -Wait` waits for the process AND every descendant. After the night packages of
# 2026-10-20/21 RunUAT itself had exited ("AutomationTool exiting ... Success" at 23:17:13 and 01:54:38) and
# package-client.ps1 returned only ~14 min later (BuildStamp.json builtAt 02:08:25): some child of the UBT build
# outlived UAT and -Wait waited for it. Here we wait on the process handle instead and list the descendants that are
# still alive (diagnostic only, never killed: AGENTS.md "Agent and process lifecycle").
#
#   . (Join-Path $PSScriptRoot 'process-wait.ps1')
#   $r = Invoke-HiddenProcessWait -FilePath $exe -ArgumentList $args -StdOut $log -StdErr "$log.err"
#   $r.ExitCode; $r.Seconds; $r.Survivors   # Survivors: @(@{ ProcessId; Name; CommandLine }, ...)

function Get-ProcessDescendants {
  param([int]$RootId, [datetime]$NotBefore)
  # PPIDs stay recorded after the parent exits, so the tree of an exited root can still be walked. A process created
  # before the root started is not its descendant (PID reuse).
  $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
  $byParent = @{}
  foreach ($proc in $all) {
    $ppid = [int]$proc.ParentProcessId
    if (-not $byParent.ContainsKey($ppid)) { $byParent[$ppid] = New-Object System.Collections.ArrayList }
    [void]$byParent[$ppid].Add($proc)
  }
  $out = New-Object System.Collections.ArrayList
  $queue = New-Object System.Collections.Queue
  $queue.Enqueue($RootId)
  $seen = @{ $RootId = $true }
  while ($queue.Count -gt 0) {
    $id = [int]$queue.Dequeue()
    if (-not $byParent.ContainsKey($id)) { continue }
    foreach ($child in $byParent[$id]) {
      $cid = [int]$child.ProcessId
      if ($seen.ContainsKey($cid)) { continue }
      $seen[$cid] = $true
      if ($child.CreationDate -and $child.CreationDate -lt $NotBefore) { continue }
      [void]$out.Add([pscustomobject]@{ ProcessId = $cid; Name = $child.Name; CommandLine = "$($child.CommandLine)" })
      $queue.Enqueue($cid)
    }
  }
  return $out.ToArray()
}

function Invoke-HiddenProcessWait {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$ArgumentList = @(),
    [Parameter(Mandatory = $true)][string]$StdOut,
    [Parameter(Mandatory = $true)][string]$StdErr
  )
  $started = (Get-Date).AddSeconds(-2)
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $startArgs = @{ FilePath = $FilePath; WindowStyle = 'Hidden'; PassThru = $true
                  RedirectStandardOutput = $StdOut; RedirectStandardError = $StdErr }
  if ($ArgumentList.Count -gt 0) { $startArgs.ArgumentList = $ArgumentList }
  $p = Start-Process @startArgs
  # PowerShell 5.1: without a cached handle the ExitCode of a process started without -Wait reads back empty.
  $null = $p.Handle
  $p.WaitForExit()
  $sw.Stop()
  $code = $p.ExitCode
  if ($null -eq $code) { $code = -1 }
  $survivors = @(Get-ProcessDescendants -RootId $p.Id -NotBefore $started)
  return [pscustomobject]@{ ExitCode = [int]$code; Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
                            ProcessId = $p.Id; Survivors = $survivors }
}
