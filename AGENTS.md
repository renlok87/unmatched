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
- **One package per change.** Package once in the worktree; `package-client.ps1` stamps the staged build with the commit.
  After `safe-integrate.sh --apply`, do two things in the main checkout:
  - rebuild UnmatchedEditor;
  - copy the staged build with `tools/s08/sync-staged-build.ps1 -From <worktree>`. It refuses when the stamp commit differs from the main HEAD; do not repackage.
- **Packaging trap.** A new or renamed `Config/**.json` reaches the pak only after the game makefile is regenerated: touch `unreal/Unmatched/Source/Unmatched/Unmatched.Build.cs`, then build the game target with `-MaxParallelActions=4`.
