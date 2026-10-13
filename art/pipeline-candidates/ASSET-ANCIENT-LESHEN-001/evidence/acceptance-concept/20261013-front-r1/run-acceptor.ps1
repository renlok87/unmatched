$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
$exe = 'C:\Users\ren\AppData\Local\OpenAI\Codex\bin\2e5e00daee91c61d\codex.exe'
$argsForAcceptor = @('exec', '--ignore-user-config', '-m', 'gpt-6.1-sol', '-c', 'model_reasoning_effort="xhigh"', '-c', 'windows.sandbox="unelevated"', '-s', 'read-only', '-C', 'C:\Users\ren\WebstormProjects\unmached\unmached', '--skip-git-repo-check', '--output-schema', 'C:\Users\ren\WebstormProjects\unmached\unmached\tools\art\acceptance\asset-acceptance-2.output-concept.schema.json', '-o', 'C:\Users\ren\WebstormProjects\unmached\unmached\art\pipeline-candidates\ASSET-ANCIENT-LESHEN-001\evidence\acceptance-concept\20261013-front-r1\card.json', '--json', '-i', 'C:\Users\ren\WebstormProjects\unmached\unmached\art\imagegen\concept-ancient-leshen-codex\design\ancient-leshen-front.png', '-i', 'C:\Users\ren\WebstormProjects\unmached\unmached\art\imagegen\hero-quality-v1\reference\medusa-quality-reference.png', '--', '-')
Get-Content 'C:\Users\ren\WebstormProjects\unmached\unmached\art\pipeline-candidates\ASSET-ANCIENT-LESHEN-001\evidence\acceptance-concept\20261013-front-r1\acceptor-prompt.md' -Raw -Encoding UTF8 | & $exe @argsForAcceptor 2> 'C:\Users\ren\WebstormProjects\unmached\unmached\art\pipeline-candidates\ASSET-ANCIENT-LESHEN-001\evidence\acceptance-concept\20261013-front-r1\acceptor-stderr.txt' | Out-File -Encoding utf8 'C:\Users\ren\WebstormProjects\unmached\unmached\art\pipeline-candidates\ASSET-ANCIENT-LESHEN-001\evidence\acceptance-concept\20261013-front-r1\acceptor-events.jsonl'
$resultCode = $LASTEXITCODE
Write-Output "acceptor_exit=$resultCode"
exit $resultCode
