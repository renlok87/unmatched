# VS-4 HB-48 (docs/game-design/visual/04-hud-spec.md s5.3, s7.1): the s09 gates check their evidence shots by the
# 'SHOT widget' lines the client wrote for each shot (tools/s08/hud_contract/hud_contract.py check-shots), not by the
# debug marker colours. -S09Markers on a gate script keeps the old marker pixel gates as the rollback (and is what the
# Slate path of a block rolled back with -S08SlateHud needs). Dot-sourced by run-combat-demo, run-duel-demo,
# run-pending-demo and run-hud-probe. ASCII only (Windows PowerShell 5.1 reads a BOM-less script as ANSI).
#
# A rule is '<shot file>: need <UI-ID> k=v|v2 ...; deny <UI-ID> k=v; need <A> || <B>' (see hud_contract.py).

function Invoke-HudShotGate {
  param(
    [Parameter(Mandatory)][string]$TracePath,
    [string[]]$Rules = @(),
    [switch]$Privacy,
    [string]$Who = ''
  )
  $py = Join-Path $PSScriptRoot '..\s08\hud_contract\hud_contract.py'
  if (-not (Test-Path -LiteralPath $py)) { throw "hud_contract.py missing: $py" }
  $python = (Get-Command python -ErrorAction SilentlyContinue)
  if (-not $python) { throw 'python is not on PATH (needed by the SHOT widget gates; -S09Markers runs the old pixel gates)' }
  $report = Join-Path ([System.IO.Path]::GetTempPath()) ("hud-shot-gate-{0}-{1}.txt" -f $PID, [Guid]::NewGuid().ToString('N'))
  $argv = @($py, 'check-shots', $TracePath, '--report', $report)
  foreach ($r in $Rules) { $argv += '--rule'; $argv += $r }
  if ($Privacy) { $argv += '--privacy' }
  $oldEnc = $env:PYTHONIOENCODING
  $env:PYTHONIOENCODING = 'utf-8'
  $ErrorActionPreference = 'Continue'  # a stderr line of the native call must not terminate the caller's 'Stop' scope
  try {
    $null = & $python.Source @argv 2>&1
    $code = $LASTEXITCODE
  } finally {
    $env:PYTHONIOENCODING = $oldEnc
  }
  $lines = @()
  if (Test-Path -LiteralPath $report) {
    $lines = @([System.IO.File]::ReadAllLines($report, [System.Text.Encoding]::UTF8) | Where-Object { $_ })
    Remove-Item -LiteralPath $report -Force
  }
  if ($code -eq 2 -or $lines.Count -eq 0) { throw "SHOT widget gate could not run ($Who, exit $code): $($lines -join ' | ')" }
  return [pscustomobject]@{ Ok = ($code -eq 0); Code = $code; Lines = @($lines | ForEach-Object { if ($Who) { "$Who $_" } else { $_ } }) }
}

# The gate itself: every rule must pass (and the privacy rules when asked); throws with the failing lines.
function Assert-HudShotGate {
  param(
    [Parameter(Mandatory)][string]$TracePath,
    [string[]]$Rules = @(),
    [switch]$Privacy,
    [string]$Who = ''
  )
  $r = Invoke-HudShotGate -TracePath $TracePath -Rules $Rules -Privacy:$Privacy -Who $Who
  if (-not $r.Ok) {
    $bad = @($r.Lines | Where-Object { $_ -match ' FAIL' })
    throw ("SHOT widget gate failed ({0}): {1}" -f $Who, ($bad -join ' || '))
  }
  return $r.Lines
}

# Swap / negative control: the rule must FAIL on this trace (a foreign shot passing it means the gate is unsound).
function Assert-HudShotGateFails {
  param(
    [Parameter(Mandatory)][string]$TracePath,
    [Parameter(Mandatory)][string]$Rule,
    [string]$What = ''
  )
  $r = Invoke-HudShotGate -TracePath $TracePath -Rules @($Rule)
  if ($r.Ok) { throw "swap control failed: $What passed a foreign SHOT widget rule - the gate is unsound ($Rule)" }
  return "swap control ok: $What fails '$Rule'"
}
