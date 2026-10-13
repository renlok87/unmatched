$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$repo = "C:/Users/ren/WebstormProjects/unmached/unmached"
# exe, passed the exec probe 2026-10-13 (codex-cli 0.162.0-alpha.17.2; references/concept-sheet.md §5.2)
$exe = "C:\Users\ren\AppData\Local\OpenAI\Codex\bin\2e5e00daee91c61d\codex.exe"
$E = "$repo/art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance/20261013-r1"
$tag = if ($args.Count -gt 0) { $args[0] } else { "" }
$prompt = "$E/acceptor-prompt$tag.md"
$img = @()
Get-ChildItem "$E/frames/*" -Include *.jpg,*.png | ForEach-Object { $img += "-i"; $img += $_.FullName }
$img += "-i"; $img += "$repo/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
Get-ChildItem "$repo/docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames/close-*.jpg" |
  ForEach-Object { $img += "-i"; $img += $_.FullName }
"images=$($img.Count / 2) prompt=$prompt"
Get-Content $prompt -Raw -Encoding UTF8 | & $exe exec --ignore-user-config `
  -m gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' -c 'windows.sandbox="unelevated"' `
  -s read-only -C $repo --skip-git-repo-check `
  --output-schema "$repo/tools/art/acceptance/asset-acceptance-2.output-model.schema.json" `
  -o "$E/card$tag.json" --json @img -- - 2> "$E/acceptor-stderr$tag.txt" | Out-File -Encoding utf8 "$E/acceptor-events$tag.jsonl"
"exit=$LASTEXITCODE"
