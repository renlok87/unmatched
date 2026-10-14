# Clip acceptor (Sol 6.1 xhigh) of ASSET-BEOWULF-001, stage 7a.2 cycle r1 (references/acceptance-and-blender.md §8.4 with
# the anim output schema; animation-vfx-sfx.md §10). Written by the stage-7a executor 2026-10-14: prep_acceptance.py found
# no run-acceptor.ps1 among the stage-6 prompt templates. Inputs = <E>/<Clip>/frames/* (prep_acceptance.py, <= 1200 px)
# plus the references the prompt names: King Arthur contact sheet of the clip, the concept sheet of the model acceptance,
# the concept front view and the quality reference.
#   powershell -NoProfile -ExecutionPolicy Bypass -File run-acceptor.ps1 <E relative to repo> <Clip> [tag]
$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$repo = "C:/Users/ren/WebstormProjects/unmached/unmached"
$exe = Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin\*\codex.exe" | Select-Object -First 1 -ExpandProperty FullName
$E = "$repo/" + $args[0]
$clip = $args[1]
$tag = if ($args.Count -gt 2) { $args[2] } else { "" }
$C = "$E/$clip"
$img = @()
Get-ChildItem "$C/frames/*" -Include *.jpg,*.png | ForEach-Object { $img += "-i"; $img += $_.FullName }
$img += "-i"; $img += "$repo/art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-$clip/contact-sheet-2fps.png"
$img += "-i"; $img += "$repo/art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance/20261014-r1/frames/sheet.png"
$img += "-i"; $img += "$repo/art/imagegen/concept-beowulf-codex/beowulf-front.png"
$img += "-i"; $img += "$repo/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
"exe=$exe images=$($img.Count / 2) prompt=$C/acceptor-prompt$tag.md"
Get-Content "$C/acceptor-prompt$tag.md" -Raw -Encoding UTF8 | & $exe exec --ignore-user-config `
  -m gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' -c 'windows.sandbox="unelevated"' `
  -s read-only -C $repo --skip-git-repo-check `
  --output-schema "$repo/tools/art/acceptance/asset-acceptance-2.output-anim.schema.json" `
  -o "$C/card$tag.json" --json @img -- - 2> "$C/acceptor-stderr$tag.txt" | Out-File -Encoding utf8 "$C/acceptor-events$tag.jsonl"
"exit=$LASTEXITCODE"
