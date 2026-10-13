$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$repo = "C:/Users/ren/WebstormProjects/unmached/unmached"
# exe from %LOCALAPPDATA% (glob, not pinned); passed the exec probe 2026-10-14 (codex-cli 0.162.0-alpha.17.2,
# command_execution exit_code 0; references/concept-sheet.md §5.2)
$exe = Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin\*\codex.exe" | Select-Object -First 1 -ExpandProperty FullName
$E = "$repo/art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r1"
$tag = if ($args.Count -gt 0) { $args[0] } else { "" }
$prompt = "$E/acceptor-prompt$tag.md"
$img = @()
Get-ChildItem "$E/frames/*" -Include *.jpg,*.png | ForEach-Object { $img += "-i"; $img += $_.FullName }
$img += "-i"; $img += "$repo/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
Get-ChildItem "$repo/docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg" |
  ForEach-Object { $img += "-i"; $img += $_.FullName }
"exe=$exe images=$($img.Count / 2) prompt=$prompt"
Get-Content $prompt -Raw -Encoding UTF8 | & $exe exec --ignore-user-config `
  -m gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' -c 'windows.sandbox="unelevated"' `
  -s read-only -C $repo --skip-git-repo-check `
  --output-schema "$repo/tools/art/acceptance/asset-acceptance-2.output-model.schema.json" `
  -o "$E/card$tag.json" --json @img -- - 2> "$E/acceptor-stderr$tag.txt" | Out-File -Encoding utf8 "$E/acceptor-events$tag.jsonl"
"exit=$LASTEXITCODE"
