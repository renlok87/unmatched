# Stage-6 clip acceptor (Sol 6.1 xhigh) of ASSET-ACHILLES-001 - TEMPLATE prepared 2026-10-14, NOT run.
# Stage 7a, after h2anim_ue.py import/measure/frames: copy acceptance-anim-prompts/<Clip>/acceptor-prompt.md to
# $E/<Clip>/acceptor-prompt.md with the placeholders filled (20261014-h2anim/README.md), put the frames of
# animation-vfx-sfx.md §10.3 plus preview/closeups-blender/Achilles-<Clip>-*.jpg into $E/<Clip>/frames/, then:
#   powershell -NoProfile -ExecutionPolicy Bypass -File run-acceptor.ps1 <E relative to repo> <Clip> [tag]
# (command: references/acceptance-and-blender.md §8.4 with the anim output schema)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$repo = "C:/Users/ren/WebstormProjects/unmached/unmached"
# exe that passed the exec probe (references/concept-sheet.md §5.2)
$exe = Get-ChildItem "$env:LOCALAPPDATA\OpenAI\Codex\bin\*\codex.exe" | Select-Object -First 1 -ExpandProperty FullName
$E = "$repo/" + $args[0]
$clip = $args[1]
$tag = if ($args.Count -gt 2) { $args[2] } else { "" }
$C = "$E/$clip"
# library-pattern contact sheets of each clip (the figure has no own video reference)
$refs = @{
  "Idle" = @("art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-Idle/contact-sheet-2fps.png",
             "art/animation-refs/ASSET-MERLIN-001/MER-Idle/contact-sheet-2fps.png");
  "LungeAttack" = @("art/animation-refs/ASSET-MERLIN-001/MER-LungeAttack/contact-sheet-2fps.png",
                    "art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-LungeAttack/contact-sheet-2fps.png");
  "HitReact" = @("art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-HitReact/contact-sheet-2fps.png",
                 "art/animation-refs/ASSET-MERLIN-001/MER-HitReact/contact-sheet-2fps.png");
  "DeathSettle" = @("art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-DeathSettle/contact-sheet-2fps.png",
                    "art/animation-refs/ASSET-MERLIN-001/MER-DeathSettle/contact-sheet-2fps.png")
}
$img = @()
Get-ChildItem "$C/frames/*" -Include *.jpg,*.png | ForEach-Object { $img += "-i"; $img += $_.FullName }
foreach ($r in $refs[$clip]) { $img += "-i"; $img += "$repo/$r" }
$img += "-i"; $img += "$repo/art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r2/frames/sheet.png"
$img += "-i"; $img += "$repo/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
"images=$($img.Count / 2) prompt=$C/acceptor-prompt$tag.md"
Get-Content "$C/acceptor-prompt$tag.md" -Raw -Encoding UTF8 | & $exe exec --ignore-user-config `
  -m gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' -c 'windows.sandbox="unelevated"' `
  -s read-only -C $repo --skip-git-repo-check `
  --output-schema "$repo/tools/art/acceptance/asset-acceptance-2.output-anim.schema.json" `
  -o "$C/card$tag.json" --json @img -- - 2> "$C/acceptor-stderr$tag.txt" | Out-File -Encoding utf8 "$C/acceptor-events$tag.jsonl"
"exit=$LASTEXITCODE"
