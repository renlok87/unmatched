$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$repo = 'C:/Users/ren/WebstormProjects/unmached/unmached'
$exe = (Get-ChildItem "$env:LOCALAPPDATA/OpenAI/Codex/bin/*/codex.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$E = 'C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-MARTIAN-INVADER-001/evidence/acceptance-concept/20261013-front-r2'
$img = @('-i', "$repo/art/imagegen/concept-martian-invader-codex/design/martian-invader-front.png", '-i', "$repo/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png")
Get-Content "$E/acceptor-prompt.md" -Raw -Encoding UTF8 | & $exe exec --ignore-user-config `
  -m gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' -c 'windows.sandbox="unelevated"' `
  -s read-only -C $repo --skip-git-repo-check `
  --output-schema "$repo/tools/art/acceptance/asset-acceptance-2.output-concept.schema.json" `
  -o "$E/card.json" --json @img -- - 2> "$E/acceptor-stderr.txt" | Out-File -Encoding utf8 "$E/acceptor-events.jsonl"
"exit=$LASTEXITCODE"
exit $LASTEXITCODE
