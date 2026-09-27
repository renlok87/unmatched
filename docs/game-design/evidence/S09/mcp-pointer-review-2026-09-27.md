# GD-032 Slate pointer check through Unreal MCP (2026-09-27)

UE 5.8 `UnmatchedEditor`, one editor process, `EditorToolset.EditorAppToolset.StartPIE` with `PlayMode_InViewPort`, and `SlateInspectorToolset.SlateInspectorToolset.Observe`/`Snapshot`/`Click`. `-S09McpHold` kept the existing offline HUD probe in PIE after its keyboard checks. The temporary input was derived from S08 `04-game-state-query-host.json`: one card was placed in the owner's public discard; the opponent pile was tested once with a `hidden-0` placeholder and once with a public face carrying distinct test text. `node tools/s09/make-mcp-discard-fixtures.cjs` reproduces both variants in a temporary directory; pass a generated variant directory as `-S08Fixtures` and a writable capture directory as `-S09HudProbe` when starting the editor. No server state was changed for this UI check.

| Slate MCP action | Observed Slate tree after click |
| --- | --- |
| Click `BROWSE DISCARD PILES (D)` | Both `your discard (1)` and `opponent discard (1)` opened. |
| Click owner's public `The Hounds of Mighty Zeus` | `inspector: your discard`; type, banner, instance, attack/defense/boost and full `text: MCP inspection: own public discard card text.` appeared. |
| Click opponent's `hidden-0` placeholder | `inspector: opponent discard` showed only `hidden card - no face is available to this viewer`; no identity or card text appeared. |
| Click opponent's public `Opponent Public Card` after restarting PIE with the public fixture | `inspector: opponent discard`, `instance: mcp-opponent-public::0`, and full `text: MCP inspection: opponent public discard card text.` appeared. [Screenshot](run/mcp-discard-opponent-public-20260927.png). |

`SlateInspectorToolset.Click` sends Slate pointer events to the observed widget, rather than calling `HandleDiscardCardClick` directly. This proves the PIE widget hit-test/click path. The captured editor viewport was approximately 1014×550 inside the editor window; the 1280×720 packaged layout is checked separately. A physical mouse pass by the project owner remains a distinct optional visual check.
