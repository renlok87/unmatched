$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$repo = "C:/Users/ren/WebstormProjects/unmached/unmached"
$exe = "C:/Users/ren/AppData/Local/OpenAI/Codex/bin/2e5e00daee91c61d/codex.exe"
$E = "C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-EREDIN-001/evidence/acceptance-concept/20261013-front-r2"
$img = @("-i", "$repo/art/imagegen/concept-eredin-codex/design/eredin-front.png", "-i", "$repo/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png")
Get-Content "$E/acceptor-prompt.md" -Raw -Encoding UTF8 | & $exe exec --ignore-user-config `
  -m gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' -c 'windows.sandbox="unelevated"' `
  -s read-only -C $repo --skip-git-repo-check `
  --output-schema "$repo/tools/art/acceptance/asset-acceptance-2.output-concept.schema.json" `
  -o "$E/card.json" --json @img -- - 2> "$E/acceptor-stderr.txt" | Out-File -Encoding utf8 "$E/acceptor-events.jsonl"
Write-Output "acceptor_exit=$LASTEXITCODE"
exit $LASTEXITCODE
