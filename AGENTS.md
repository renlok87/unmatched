# AGENTS

<skills_system priority="1">

## Available Skills

<!-- SKILLS_TABLE_START -->
<usage>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke: `npx openskills read <skill-name>` (run in your shell)
  - For multiple: `npx openskills read skill-one,skill-two`
- The skill content will load with detailed instructions on how to complete the task
- Base directory provided in output for resolving bundled resources (references/, scripts/, assets/)

Usage notes:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already loaded in your context
- Each skill invocation is stateless
</usage>

<available_skills>

<skill>
<name>3d-model-pipeline</name>
<description>Сквозной пайплайн новой 3D-фигуры Unmatched (герой, помощник, крылатое существо-бипед, проп). Этапы — концепт-лист в Gemini, генерация в Tripo3D Studio, сборка H2 в Blender, приёмка с коэффициентом и доработкой, анимация с VFX/SFX и упаковка с подключением в Unreal. Триггеры — «сгенерируй 3D-модель», «новый герой / помощник / существо / проп», «новая фигура», «3D model pipeline», «модель через Tripo», «концепт-лист героя». Статический проп (бочка, фонарь, ящик) — да, до импорта в UE; его размещение в раскладке доски — нет. НЕ для окружения, задников и сцен досок и размещения пропов в EnvLayouts (Marmoreal/Sarpedon — трек ENV-MAPS) и НЕ для разовых правок существующих ассетов.</description>
<location>project</location>
</skill>

<skill>
<name>algorithmic-art</name>
<description>Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists' work to avoid copyright violations.</description>
<location>project</location>
</skill>

<skill>
<name>brand-guidelines</name>
<description>Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having Anthropic's look-and-feel. Use it when brand colors or style guidelines, visual formatting, or company design standards apply.</description>
<location>project</location>
</skill>

<skill>
<name>canvas-design</name>
<description>Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when the user asks to create a poster, piece of art, design, or other static piece. Create original visual designs, never copying existing artists' work to avoid copyright violations.</description>
<location>project</location>
</skill>

<skill>
<name>doc-coauthoring</name>
<description>Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. This workflow helps users efficiently transfer context, refine content through iteration, and verify the doc works for readers. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks.</description>
<location>project</location>
</skill>

<skill>
<name>docx</name>
<description>"Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. When Claude needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"</description>
<location>project</location>
</skill>

<skill>
<name>frontend-design</name>
<description>Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics.</description>
<location>project</location>
</skill>

<skill>
<name>internal-comms</name>
<description>A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use. Claude should use this skill whenever asked to write some sort of internal communications (status reports, leadership updates, 3P updates, company newsletters, FAQs, incident reports, project updates, etc.).</description>
<location>project</location>
</skill>

<skill>
<name>mcp-builder</name>
<description>Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK).</description>
<location>project</location>
</skill>

<skill>
<name>pdf</name>
<description>Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms. When Claude needs to fill in a PDF form or programmatically process, generate, or analyze PDF documents at scale.</description>
<location>project</location>
</skill>

<skill>
<name>pptx</name>
<description>"Presentation creation, editing, and analysis. When Claude needs to work with presentations (.pptx files) for: (1) Creating new presentations, (2) Modifying or editing content, (3) Working with layouts, (4) Adding comments or speaker notes, or any other presentation tasks"</description>
<location>project</location>
</skill>

<skill>
<name>skill-creator</name>
<description>Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.</description>
<location>project</location>
</skill>

<skill>
<name>slack-gif-creator</name>
<description>Knowledge and utilities for creating animated GIFs optimized for Slack. Provides constraints, validation tools, and animation concepts. Use when users request animated GIFs for Slack like "make me a GIF of X doing Y for Slack."</description>
<location>project</location>
</skill>

<skill>
<name>template</name>
<description>Replace with description of the skill and when Claude should use it.</description>
<location>project</location>
</skill>

<skill>
<name>theme-factory</name>
<description>Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. There are 10 pre-set themes with colors/fonts that you can apply to any artifact that has been creating, or can generate a new theme on-the-fly.</description>
<location>project</location>
</skill>

<skill>
<name>web-artifacts-builder</name>
<description>Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies (React, Tailwind CSS, shadcn/ui). Use for complex artifacts requiring state management, routing, or shadcn/ui components - not for simple single-file HTML/JSX artifacts.</description>
<location>project</location>
</skill>

<skill>
<name>webapp-testing</name>
<description>Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs.</description>
<location>project</location>
</skill>

<skill>
<name>xlsx</name>
<description>"Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization. When Claude needs to work with spreadsheets (.xlsx, .xlsm, .csv, .tsv, etc) for: (1) Creating new spreadsheets with formulas and formatting, (2) Reading or analyzing data, (3) Modify existing spreadsheets while preserving formulas, (4) Data analysis and visualization in spreadsheets, or (5) Recalculating formulas"</description>
<location>project</location>
</skill>

</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>

## Integration workflow

User instruction (2026-09-18): after completing and verifying each worktree/task,
commit its changes and integrate them into the single target branch `fix/admin-panel`
in the original project checkout. Start follow-up sessions from that updated branch.
Do not leave completed work only on separate `codex/*` branches.

Preserve unrelated working-tree changes. If untracked files overlap incoming files,
compare them and keep verified local backups before integrating; never reset, clean,
blindly stash the entire project, or overwrite unrelated user work.
Local integration is authorized; remote pushes are not implied by this instruction.

Parallel sessions (user request 2026-10-01: «мне нужно чтобы два окна не сломались при мержде в
ветку fix/admin-panel»): one session works in the main checkout on `fix/admin-panel`, others in
worktrees on feature branches. A worktree session integrates ONLY through
`tools/git/safe-integrate.sh <branch> --apply` (run the dry run first): it requires that the
branch already contains the latest `fix/admin-panel` (merge it in, rebuild and test first), that
the main checkout has no git operation in progress and nothing staged, that no incoming file has
uncommitted or untracked work in the main checkout, and that no UnrealEditor/UBT/packaged client
of the main checkout is running when `unreal/` changes; then it fast-forwards. The main-checkout
session commits its own work promptly (never leaves changes staged) and, after an integration
that touched `unreal/`, rebuilds UnmatchedEditor before opening the editor. Neither session
merges the other's branch by hand, stashes, resets or edits the other's uncommitted files.

Commits without hooks (user decision 2026-10-03: «разреши глобально в проекте no verify»):
commit in this repository with `git commit --no-verify`, in every checkout and worktree. The
husky/lint-staged pre-commit hook is broken (no `eslint`/`prettier` in the root `node_modules`),
and when it fails, lint-staged's revert also fails: it resets tracked working-tree files, wiping
other sessions' uncommitted changes (it already erased `.claude/settings.local.json` twice).
Run formatters/linters explicitly when a change needs them instead.

## Agent and process lifecycle

Keep only the sessions needed for the current task. Do not launch a large pool of
parallel subagents, terminals, Unreal clients, or build processes. Prefer one GLM
development session at a time; use another session only when independent parallel
work has a clear benefit, and close it as soon as its task ends. Run background
commands without opening visible console windows when possible.

At the end of each task or test run, check for processes it started and stop any
that are no longer needed. Before stopping a process, verify its command line,
parent, executable path, and relation to this run; never kill processes by name
alone. Do not close the user's Unreal Editor or Codex-owned MCP services. Keep a
shared development service running only while current work needs it.

## AI tools and side models (user decision 2026-10-20, binding)

The user's words on 2026-10-20: «Я отменил подписку на ChatGPT, так что если нужно генерировать ассеты, либо
использовать какой-то побочную модель, переключись на приложение Z-Code, оно использует модель GLM5.3. С F-Max. А для
ассетов можно использовать создание изображений в приложении Gemini. Музыку можно создавать как и в моих существующих
подписках Syntax и вот второй сервис тоже на букву S английскую, забыл название, Steve или как-то так. Вот. Либо
пользоваться сервисами Гугла, которые встроены в Gemini. Запиши это в основные правила проекта.» Then: «Этот код можешь
использовать через Computer Use» (Z-Code is driven through Computer Use).

This section wins over every mention of Codex, the ChatGPT app, `codex exec`, `codex_lane.py`, Sol (`gpt-6.1-sol`) and
GPT Astra (`gpt-6-astra`) in skills, docs, tools and memory, until those are rewritten.

| Need | Use now | No longer available |
|---|---|---|
| Side model: second opinion, text or scope review, prompt drafting, a parallel agent | **Z-Code** desktop app (`C:\Program Files\ZCode\ZCode.exe`, Start menu "ZCode"), model **GLM-5.3**, reasoning **max** (the user's «F-Max»; max is GLM-5.3's default variant), driven through Computer Use | Codex app (`ChatGPT.exe`), `codex exec`, Sol, GPT Astra |
| A side model has to look at images (acceptance frames, blind X/Y pairs) | Z-Code with **GLM-5.3-Flash**. In the user's Z.AI coding plan GLM-5.3 takes text only; GLM-5.3-Flash takes text, image and video (`~/.zcode/v2/config.json`, checked 2026-10-20) | Sol / Astra with `-i` frames |
| Images: concept sheets 1a/1c, references, glyph masks, texture sources | Image generation in the **Gemini** app (`com.google.gemini.windows`, `%LOCALAPPDATA%\Google\Gemini\app-*\Gemini.exe`), or the Google services built into Gemini | Codex `image_gen` |
| Music, SFX, voice | **SYNTX** (existing subscription, MCP `syntx-ai`) and **stiva.ai** (the second «S» service, «Steve или как-то так»; it carries ElevenLabs SFX), or the Google services built into Gemini | — |
| 3D generation | Tripo3D Studio, unchanged | — |

- Never call Codex or ChatGPT: no `codex exec`, no ChatGPT app, no Sol or Astra acceptor. The tool lanes were ported
  on 2026-10-20: `sheet_acceptance.py` and `ue7a/run_clip_acceptors.py` default to the Opus path (prepare → Workflow
  `second-acceptor` → finish), their Sol path and `codex_lane.py` without an explicit generator command stop with
  "Codex/Sol отключён"; `tools/art/acceptance/side_models.py` holds the profiles and the Z-Code stub (skill §0).
- **Z-Code through Computer Use** (main path). Claude writes the prompt to a file in the repo. Then: open Z-Code, pick
  the project `unmached` (it is in Z-Code's recent projects), start a new task, select GLM-5.3 (or GLM-5.3-Flash for
  images) and paste the prompt; attach images through the composer. Z-Code writes only into the folder that the
  prompt names and never commits; Claude reviews its diff and commits. Do not close Z-Code tasks the user started.
- **Z-Code headless** (spare path, like `codex exec`). The bundled CLI `resources\glm\zcode.cjs` has
  `-p <prompt> --attach <file> --mode plan --json`. It only starts from a copy that has its provider file next to it:
  `<dir>\zcode.cjs` plus `<dir>\provider\zcode-builtin.json`, copied from `resources\config\provider\`. On 2026-10-20 it
  still stopped with «Select a model before sending a message»: the standalone CLI has no Z.AI account until the user
  runs `zcode login zai` once. That is a browser sign-in and the user's step; an agent never signs in. Until a probe
  passes, use the GUI path.
- **Second acceptor and blind reviews "of another profile":** Z-Code GLM-5.3-Flash. While no scripted Z-Code lane
  exists, use the Opus `second-acceptor` workflow in a fresh context. Write the profile actually used into the card.
- **Gemini:** the user's Gemini app through Computer Use, or gemini.google.com in their Chrome through Claude in
  Chrome. Prompts come from files in the repo. Outputs are saved into the folder that the skill or task names. On a
  sign-in screen, stop and ask the user. Look for a visible watermark before an image is used.
- Music and SFX keep the audio pipeline rules (`docs/game-design/audio`, ledger lines, licence notes). stiva.ai and the
  Gemini services are new to the pipeline. `tools/art/visual/ledger.py` knows them as subscriptions: a `terms` row
  before the first use of a model, then `add --service Gemini|stiva.ai --generations N` (templates T-GEMINI-IMG,
  T-GEMINI-AUDIO, T-STIVA-AUDIO); `add --service Codex` is refused.

## Unreal GPU load

The live Unreal project is `unreal/Unmatched`. Keep its normal packaged-client
default at 60 FPS (`Config/DefaultGameUserSettings.ini`, `FrameRateLimit=60`)
so ACC-022's 1080p/60 FPS performance target remains testable. Existing saved
GameUserSettings can override this default; inspect the effective FPS.
For the S08 two-client offscreen demo, cap **each** process at 30 FPS using
`tools/s08/run-phase2-demo.ps1` (`-ClientFps 30` by default). `-RenderOffScreen`
only hides the windows; it does not avoid GPU rendering. Check effective FPS
and GPU frame time in a packaged Development build and record GPU utilization
for both clients together before claiming an improvement.

Rendering (user decision 2026-09-28, W4-A): the project runs DX12/SM6 with
Lumen GI and reflections (`DefaultGraphicsRHI_DX12`, PCD3D_SM6 + PCD3D_SM5
cooked); High (`sg.*=2`) is the acceptance reference for K1-K3 and ACC-022,
screen percentage is pinned to 100. Machines without SM6 start on the SM5
fallback without Lumen. Every evidence SHOT carries a `RENDER` fingerprint;
frames off `docs/art-pipeline/render-reference.json` do not count.
Do not use `r.DynamicRes.TargetedGPUHeadRoomPercentage` as a GPU-usage limit.
Dynamic resolution is technically available on DX12, but it is a per-process
frame-time target that changes the screen percentage (and so every acceptance
frame), not a hard cap on the combined GPU percentage of the two clients;
the 60/30 FPS caps above remain the only GPU-load limits. Compare render cost
with `tools/art/render/render_bench.py` (packaged `-Bench`, no FPS cap,
ProfileGPU / CSV per pass), never with capped `gpuMs`.

## Iteration speed (user decision 2026-10-02)

User request: «Конечно, делай и закрепи это в основном пайплайне.» The user asked for this after asking why tasks take so long. Most of the time goes to three things: relaunching the engine for every bench frame (1.5–2 min each), double packaging, and full gates on small edits.
- **Live tune.** Iterate on parameter-only changes in ONE running client, using
  `python tools/art/render/live_tune.py start|reload|shot|cycle|stop`. See
  `tools/art/render/LIVE-TUNE.md`.
  - Parameter-only means the light/board profiles in `S08ArtBoardProfiles.json` and the `EnvLayouts/*.layout.json` files.
  - Relaunch only after C++, mesh, texture or material-instance changes.
  - Measured on 2026-10-02 (`docs/game-design/evidence/ENV-MAPS/live-tune-2026-10-02/`): an edit plus three views takes about 20 s, against about 115 s when relaunching.
  - Live-tune frames are valid for tuning, for before/after pairs taken in one session and for mask or region metrics.
  - Final acceptance frames still come from a fresh `-Bench` run (`live_tune.py bench`). Reason: Cobble K2 live frames differ from it by 0.51–0.72 mean, as uniform noise.
- **Light mode** applies to small visual fixes and parameter tuning that add no new system:
  - at most 3 tuning iterations;
  - before/after frames of the affected views plus only the affected gates;
  - no separate review agent;
  - no `render_bench.py` cost run, unless the change adds lights, meshes, materials or FX;
  - UE tests only when C++ changed, otherwise pytest and the `--check` validators.
- **Full mode** is everything above (review pass, all gates, cost bench). Use it for new systems or architecture changes, or when the user asks for an acceptance round.
- **No cost optimizations within budget.** The user's words on 2026-10-08: «Больше не делай таких оптимизаций, мы
  просрали целых три часа работы». The reason: a VS-6 fix of +0.33 ms GPU took about 1.5 h, three repackages and a self-made
  crash, although the limit was 1 ms.
  - Measure cost only where a card requires it, in one run. Within the threshold → write the number down and move on.
  - Fix only a threshold breach (the card's limit or ACC-022 60 FPS), a crash, visibly broken output or a failed gate.
  - Anything else found "wasteful" goes to the open items of the evidence README, not into the current task.
  - No repackaging and no repeat benches for cost's sake.
- **One package per change.** Package once in the worktree; `package-client.ps1` stamps the staged build with the commit.
  After `safe-integrate.sh --apply`, do two things in the main checkout:
  - rebuild UnmatchedEditor;
  - copy the staged build with `tools/s08/sync-staged-build.ps1 -From <worktree>`. It refuses when the stamp commit differs from the main HEAD; do not repackage.
- **Packaging trap.** A new or renamed `Config/**.json` reaches the pak only after the game makefile is regenerated: touch `unreal/Unmatched/Source/Unmatched/Unmatched.Build.cs`, then build the game target with `-MaxParallelActions=4`.

## Live Coding dev loop for edits and bug fixes (user decision 2026-10-15, binding)

The user's words: «Я не хочу полностью пересобирать игру каждый раз во время фикса. Запусти ее так чтобы ты мог
интерактивно ее фиксить», then «Закрепи дополнительно правила лайфкодинга при правках, изменений, фиксе багов, чтобы можно
было делать вещи быстрее». Tool and details: `tools/dev/devexec.py`, `tools/dev/DEV-LOOP.md` (`S08/S08DevExec.cpp`).

- **Default for every gameplay, HUD or visual bug fix and code change of the client:** one uncooked client
  `python tools/dev/devexec.py start` (`UnrealEditor.exe Unmatched.uproject -game -LiveCoding -DevExec=C:\tmp\devexec`),
  started once and kept for the whole task. No packaging and no packaged client while iterating.
- **Pick the cheapest path for each edit:**

  | Edit | Path | Typical time |
  |---|---|---|
  | function body in a `.cpp` (logic, layout numbers, texts, colours in code) | `devexec.py lc` | 8–20 s |
  | `Config/**/*.json`, layouts, art profiles | re-read in the client (live tune) or `stop`/`start` | ≤ 10 s |
  | code that only runs at startup (BuildUi, widget trees), a new `.cpp`, headers, struct / UCLASS / UPROPERTY fields (also structs declared in a `.cpp`) | `devexec.py stop` → `node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=<uproject> -WaitMutex` → `start` | ~20 s build + 10 s start |
  | backend | `docker exec unmatched-backend npm run build && docker compose restart backend` | ~40 s |

  A Live Coding patch lives only in memory: before any restart after patches, run the incremental build, or the client
  comes back with the old code. Never patch a struct layout through Live Coding.
- **Verify in the running client, not by reasoning:** reproduce first, then fix, then `devexec.py run "…"` input
  (synthetic Slate clicks, keys, text — the user's mouse is never touched) and `devexec.py shot <name>`; read the PNG.
  The game trace `unreal/Unmatched/Saved/S08/trace-*.log` (INPUT / TOAST / PENDING / MODE / HUD lines) is the first
  diagnostic. Use test accounts from `backend/prisma/seed.ts`, never the account the user plays with (test1).
- **Resolutions:** check HUD changes with `run "res 1920x1080w" … "res 2560x1080w" "res 3840x1080w" "res 1440x1080w"
  "res 1280x720w"` and shots in the same session.
- **Parallel work:** playtests and research go to cheap subagents (Sonnet / Haiku) driving the same client through
  `devexec.py`, while the main session edits code. One client = one input channel: one driving agent at a time, or
  extra clients with their own `DEVEXEC_DIR` and account. Compilation is serial for the whole machine.
- **Locks:** while a `-LiveCoding` client lives, Build.bat of UnmatchedEditor fails in every checkout (Live Coding
  mutex), and `safe-integrate.sh` of other sessions waits on the running UnrealEditor of the main checkout. Stop the
  client before a full build, before packaging and at the end of the task (`devexec.py stop` kills only its own PID).
- **Gates stay light:** after the fix, only the UE tests of the touched area
  (`node tools/s08/run-ue-tests.cjs "<filter>" <log>`, client stopped) and the backend specs of the touched files.
  Package once at the end of the task, only when the user's normal launch must get the fix (Iteration speed rules
  above). Frames from this client are for iteration; acceptance frames still come from a fresh packaged `-Bench`.

## Board scenes and heroes (user decisions, binding)

The user's words on 2026-10-04: «закрепи это в главных правилах проекта, как собираются сцены с героями». They gave
this order after two mistakes on 2026-10-04: grey blockouts shown instead of the finished hero models, and a
3D-modelled backdrop shown on a map that must be painted. This section wins over older notes, evidence and
memory. A change that contradicts it needs the user's explicit word first.

- **Boards: only the real game maps** (decision record `docs/game-design/decisions/2026-10-04-real-boards-only.md`):
  - Marmoreal · original map — Board `c121b47f8d6eb28daccb76d05`, profile `marmoreal-original`. This is the
    default board for new games, demos and tools.
  - Sarpedon · original map — Board `c7fa64a26c29a0835f2383e63`, profile `sarpedon-original`.

  Synthetic boards do not count as evidence and are never used for new runs or acceptance: Cobble City 5×6,
  the ART FIXTURE grids and the 20×20 fallback. Every live run passes a real map (`-ArtPreviewBoardId` or the
  backend default).
- **Backdrop around the map field.** The board itself is always the painted map field. Around it:
  - **Marmoreal**: a painted backdrop taken from the concept (concept paste). It has a static painted plate plus
    semi-static animated elements: flicker, water, wind and the like. Small details from the concept-paste design
    may be 3D models with animation. The user's answer on 2026-10-04: «Нарисованный задник». The 3D-modelled
    surroundings of P5c (palace, 3D trees, layout props) are a rollback flag only, never the default. The user's
    acceptance of the 3D P5c look on 2026-10-01 is superseded.
  - **Sarpedon**: `lit3d`, path 1 — a 3D island under the de-lit concept paint, with animated waterfall, fire,
    banner and cannons. The user's answer on 2026-10-04: «lit3d — путь 1». Do not switch it to `paste` or to the
    plain 3D scene without the user.
  - Never turn on extra 3D-modelled surroundings by default on top of a painted backdrop. Never take a "look" from
    a bench variant or an older acceptance act without checking it against this section.
- **Heroes: the finished look-dev v2 figures are the default.** That means King Arthur, Merlin, Medusa and the
  three Harpies: `SK_<Hero>_H2LD` / `SK_Harpy_H3LD`, `S08HeroesV2`, team MIs and Idle/Lunge/Hit/Death clips.
  Grey blockouts and the Medusa candidate appear only through the rollback flag `-S08HeroesLegacy`.
- **Accepted art is the default; flags only roll it back.** This holds even for art accepted by delegation.
  - Never hide finished art behind an opt-in review flag.
  - `-ArtPreview` gates review tooling only: shots, probes, focus zoom, input plans.
  - Rollback flags: `-S08GreyBoard`, `-S08HeroesLegacy`, `-S08DioramaLegacy`, `-S08IconLegacy` and
    `-S08LegacyRender`; `-NoConceptPaste` (Marmoreal: the 3D P5c surroundings and the T2b tray).
  - The client writes the look it used in the trace line `ARTLOOK …`.
- **Look before you report.** Before reporting any live run, demo, package or acceptance, open the shot yourself
  (Read the PNG). Check against this section: the board is a real map, the backdrop is right for that map, and
  all six figures are the v2 models. Trace lines alone are not enough.
- **Decided by delegation on 2026-10-06.** The user's words: «Не знаю. Делай сам, меня это не касается. Все решения
  принимай». The record is `docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`:
  - figure facing (ART-012) is ВР-06: idle three-quarter to the camera, turn to the target for the attack, never back
    to the camera. The old draft `wip/art012-facing-2026-10-04` is not used;
  - HUD name plates over the figures are ВР-07: no permanent name plates, the name only on hover or selection,
    harpies carry the digit 1–3.
- **ENV-U16 fixed (`8ea9c6c9`, EN-13).** Marmoreal shows the painted backdrop by default; the 3D P5c surroundings with
  the T2b tray come back only with the rollback flag `-NoConceptPaste` (ВР-56).

## Hero showcase high-poly (user decision 2026-10-16, binding)

The user's words: «добавь в проект основное правило, что теперь у нас есть витрина, где должна быть проработанная
хайполи модель без косяков для каждого нового героя». Context: `docs/game-design/select-screens/` (05-HIPOLY-COMPARE,
06-HIPOLY-LOOKDEV, blind rounds `blind-s1`…`blind-s3`).

- The select screens (room and VS splash) show each hero as a **high-poly showcase figure** in a 3D niche
  (`AUmHeroShowcase`, S08/UI/UmHeroShowcase.*), not the in-game H2LD. The in-game figure stays on the board.
- **Every new hero needs a finished showcase high-poly as a deliverable of `3d-model-pipeline`**, next to the game
  figure. "Finished" means all of the following:
  - **No generation defects.** No phantom parts, no second face profile, no extra weapon or limb, no holes, no
    reversed feet. A source with such defects is regenerated in Tripo with the correct view slots
    (`references/tripo3d-stages.md` §5.5). Do not patch a broken head or limb in Blender: King Arthur c24eeff0 could not
    be fixed that way and was regenerated (4f059621).
  - **Seated on the game pedestal.** The Tripo base is cut off (`tools/art/showcase/clean_hipoly.py`) and the figure
    stands on the game pedestal with the team ring.
  - **Game colours.** Use the game look-dev maps when the game low-poly shares the source's frame
    (`hp_lookdev_bake.py` → `import_hipoly_lookdev.py`, `/Game/PipelineCandidates/<Key>/HPLD`). Otherwise use the
    source's own clean Tripo 8K materials (`import_hipoly.py`, `/HP2`).
  - **Faced so the face is visible.** The hero's own niche yaw keeps the face clear: the weapon must never cross the
    face (example: King Arthur 85° / 95°).
  - **Accepted blind.** A blind before/after review (unlabeled X/Y with swapped sides) is done before it becomes the
    default. Reviewers: Opus plus Z-Code GLM-5.3-Flash; GPT Astra until 2026-10-20 ("AI tools and side models").
  - **Registered and cooked.** The path is registered in `UmShowcase::HiPolyPath` and its folder is in
    `DirectoriesToAlwaysCook`.
- A hero without a finished showcase high-poly falls back to its H2LD figure in the niche. Treat that as an open item,
  not as done.
- Rollback: `-S08ShowcaseV2` shows the animated H2LD figures in every niche.

## Rollback flags (phase-3 closing, 2026-10-09)

Accepted art is the default; each flag below only rolls one piece back (client command line; the trace line `ARTLOOK …`
names the look in use). Sources: `docs/game-design/visual/03-asset-registry.csv` (column `rollback_flag`) and
`docs/game-design/evidence/VISUAL/CLOSEOUT-2026-10-09.md`.
- **Whole look / render:** `-S08GreyBoard` (all art off), `-S08LegacyRender` (pre-W4-A render), `-S08DioramaLegacy`
  (no tray and no environment, v2 figures stay), `-S08DpiLegacy` (engine DPI curve), `-S08MixLegacy` (audio mix without limiter).
- **Boards:** Marmoreal `-NoConceptPaste` (3D P5c surroundings + T2b tray instead of the painted backdrop); Sarpedon
  `-EnvLayoutVariant=p5c` or `-ConceptPaste=paste` (instead of lit3d path 1); `-NoHeroLight` (no hero light rig).
- **Figures and animation:** `-S08HeroesLegacy` (grey blockouts + Medusa candidate), `-S08HeroMatFixLegacy` (ignore the
  profile `heroMaterials` block), `-S08FacingLegacy` (no three-quarter idle / turn to target), `-S08FaceCapLegacy`
  (Medusa's rest offset back to 45° instead of 10°, VC C1), `-S08MoveEaseLegacy` (old step ease),
  `-S08BaseDigitLegacy` (old harpy digit placement), `-S08DissolveFade` (fade instead of ash death).
- **Combat and field FX:** `-S08FxLegacy` (combat VFX off), `-S08FigureCueLegacy` (old rim cue), `-S08HitTintLegacy`
  (red hit fill), `-S08ChoiceLegacy`, `-S08MovePlatesLegacy`, `-S08LastMoveLegacy`, `-S08TargetArcLegacy` (field FX of
  FX-07…FX-15 back to the MS-T look).
- **HUD "Стол" (2026-10-16, docs/game-design/hud-redesign):** `-S08HudTableLegacy` brings back the HUD v2 look of
  9360ae41 (HP tags over every fighter, marble panels with laurel medallions, the prompt cartouche at the top, the
  turn strip in the TOP row, square action bezels, the empty journal, «Рука N/7», the connection chip).
- **Select screens "SEL" (2026-10-16, docs/game-design/select-screens):** `-S08SelectLegacy` brings back the room
  SC-14…SC-18 panels and the SC-19 loading panel instead of the fighting-game look (3D v2 figures in niches, roster strip,
  board step with `selectBoard`, VS splash). `-S08ShowcaseV2` puts the animated H2LD figures back into the niches instead
  of the cleaned static Tripo high-poly sources (default since the blind rounds of 2026-10-16,
  docs/game-design/select-screens/05-HIPOLY-COMPARE.md).
- **HUD, icons, cards, screens:** `-S08SlateHud` (whole UMG HUD and screens back to Slate) or `-S08SlateHud=<block,…>`
  (top, panels, hand, combat, slot, actions, log, toast, pending, cursor, boot, login, lobby, room, loading, pause,
  reconnect, gameover, aborted, menubg, turnstrip (HB-50 полоса стадий хода, 2026-10-16), …); `-S08FontLegacy` (шрифт
  заголовков Philosopher → Roboto); `-S08IconLegacy` (v3 icons → old set), `-S08TrackerLegacy`,
  `-S08TurnRingLegacy`, `-S08HeartGlowLegacy`, `-S08CrossLegacy` (turn-portrait details), `-S08CardArtLegacy` (card
  frames and art), `-S08PortraitLegacy` (monogram portraits), `-S09Markers` (debug markers and the old pixel gates).
