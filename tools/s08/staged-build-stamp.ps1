# Shared by package-client.ps1 (writes the stamp) and sync-staged-build.ps1 (checks it).
# The source hash covers what decides the packaged client besides Content/ (which is synced separately):
# unreal/Unmatched/Source, unreal/Unmatched/Config and the .uproject, every non-ignored file, line endings
# normalised (worktree and main checkout may differ in CRLF/LF for the same commit).

function Get-UnmatchedSourceHash([string]$RepoRoot) {
  $paths = @(git -C $RepoRoot ls-files --cached --others --exclude-standard -- `
      unreal/Unmatched/Source unreal/Unmatched/Config unreal/Unmatched/Unmatched.uproject | Sort-Object -Unique)
  if ($paths.Count -eq 0) { throw "no source files under $RepoRoot/unreal/Unmatched" }
  $latin1 = [Text.Encoding]::GetEncoding(28591)
  $sha = [Security.Cryptography.SHA256]::Create()
  $sb = New-Object Text.StringBuilder
  foreach ($rel in $paths) {
    $full = Join-Path $RepoRoot $rel
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }  # deleted but still in the index
    $text = $latin1.GetString([IO.File]::ReadAllBytes($full)).Replace("`r`n", "`n")
    $h = [BitConverter]::ToString($sha.ComputeHash($latin1.GetBytes($text))).Replace('-', '').ToLowerInvariant()
    [void]$sb.Append($rel).Append(' ').Append($h).Append("`n")
  }
  $all = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($sb.ToString()))).Replace('-', '').ToLowerInvariant()
  return [pscustomobject]@{ hash = $all; files = $paths.Count }
}
