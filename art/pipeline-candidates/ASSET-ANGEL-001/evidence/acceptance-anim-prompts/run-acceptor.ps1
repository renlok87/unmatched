# Stage-6 clip acceptor (Sol 6.1 xhigh) of ASSET-ANGEL-001 - TEMPLATE prepared 2026-10-14, NOT run.
# Stage 7, after h2anim_ue.py import/measure/frames: copy acceptance-anim-prompts/<Clip>/acceptor-prompt.md to
# $E/<Clip>/acceptor-prompt.md with the placeholders filled (README.md next to this file), put the frames of
# animation-vfx-sfx.md §10.3 into $E/<Clip>/frames/, then:
#   powershell -NoProfile -ExecutionPolicy Bypass -File run-acceptor.ps1 <E relative to repo> <Clip> [tag]
# (command: references/acceptance-and-blender.md §8.4 with the anim output schema)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$repo = "C:/Users/ren/WebstormProjects/unmached/unmached"
# exe that passed the exec probe (references/concept-sheet.md §5.2); stage 4 of Angel used bin\2e5e00daee91c61d
$exe = Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin\*\codex.exe" | Select-Object -First 1 -ExpandProperty FullName
$E = "$repo/" + $args[0]
$clip = $args[1]
$tag = if ($args.Count -gt 2) { $args[2] } else { "" }
$C = "$E/$clip"
$img = @()
Get-ChildItem "$C/frames/*" -Include *.jpg,*.png | ForEach-Object { $img += "-i"; $img += $_.FullName }
$img += "-i"; $img += "$repo/art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-$clip/contact-sheet-2fps.png"
$img += "-i"; $img += "$repo/art/imagegen/concept-angel-codex/sheet-angel.png"
$img += "-i"; $img += "$repo/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
"images=$($img.Count / 2) prompt=$C/acceptor-prompt$tag.md"
Get-Content "$C/acceptor-prompt$tag.md" -Raw -Encoding UTF8 | & $exe exec --ignore-user-config `
  -m gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' -c 'windows.sandbox="unelevated"' `
  -s read-only -C $repo --skip-git-repo-check `
  --output-schema "$repo/tools/art/acceptance/asset-acceptance-2.output-anim.schema.json" `
  -o "$C/card$tag.json" --json @img -- - 2> "$C/acceptor-stderr$tag.txt" | Out-File -Encoding utf8 "$C/acceptor-events$tag.jsonl"
"exit=$LASTEXITCODE"
